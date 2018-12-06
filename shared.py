"""
The purpose of this file is to allow Machine_Widget 
(used for machine inspection, scan_check and m5copy) to be used stand alone 
as well as within the modules on ccsbeta. 
The shared code is extracted to here, with minimal imports from other modules.
"""

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QCursor, QDialog, QVBoxLayout, QTextEdit, \
    QFontMetrics, QDialogButtonBox

import threading
import collections
import subprocess
import shlex
import re
import contextlib
import os.path

disk_pattern = {
    "flexbuff" : "/mnt/disk*",
    "mark6" : "/mnt/disks/*/*/data"
}

file_regexp = {
    "flexbuff" : re.compile(
        "^/mnt/disk[0-9]{1,3}/"
        "(?P<experiment>[^_/]+)_(?P<station>[^_/]+)_(?P<scan>[^/]+)/"
        "(?P=experiment)_(?P=station)_(?P=scan)\.[0-9]{8}"),
    "mark6" : re.compile(
        "^/mnt/disks/[1-4]/[0-7]/data/"
        "(?P<experiment>[^_/]+)_(?P<station>[^_/]+)_(?P<scan>[^/]+)/"
        "(?P=experiment)_(?P=station)_(?P=scan)\.[0-9]{8}")
}

dir_regexp = {
    "flexbuff" : re.compile(
        "^/mnt/disk[0-9]{1,3}/"
        "(?P<experiment>[^_/]+)_(?P<station>[^_/]+)_(?P<scan>[^/]+)/"),
    "mark6" : re.compile(
        "^/mnt/disks/[1-4]/[0-7]/data/"
        "(?P<experiment>[^_/]+)_(?P<station>[^_/]+)_(?P<scan>[^/]+)/")
}

du_error_regexp = {
    "flexbuff" : re.compile(
        "^du: cannot access.*(?P<disk>/mnt/disk[0-9]{1,3}/)"
        "(?P<recording>[^/\s]+)"),
    "mark6" : re.compile(
        "^du: cannot access.*(?P<disk>/mnt/disks/[1-4]/[0-7]/data/)"
        "(?P<recording>[^/\s]+)")
}


@contextlib.contextmanager
def wait_cursor(application):
    application.setOverrideCursor(QCursor(Qt.WaitCursor))
    try:
        yield
    finally:
        application.restoreOverrideCursor()

def format_bytes(x, size):
    """
    returns a human readable representation of number of bytes 'x' 
    with string length 'size'
    """
    if x == None:
        return " " * size
    if x < 0:
        return "-" + format_bytes(-x, size-1)
    if x < 1024:
        return ("{0:>%dd}" % size).format(x)
    for print_unit in ["K", "M", "G", "T", "P"]:
        x = x / 1024.0
        if x < 1024:
            after_point_size = size - len(print_unit) - 1 - len("%.0f" % x)
            number_string = "%.*f%s" % (after_point_size, x, print_unit)
            return ("{0:>%ds}" % size).format(number_string)
    raise RuntimeError("number of bytes too large to print")

class Text_Edit_Dialog(QDialog):
    def __init__(self, text, parent=None):
        super(Text_Edit_Dialog, self).__init__(parent)
        self.setSizeGripEnabled(True)
        layout = QVBoxLayout(self)
        text_edit = QTextEdit(self)
        text_edit.setText(text)
        metrics = QFontMetrics(text_edit.document().defaultFont())
        size = metrics.size(0, text)
        text_edit.setMinimumSize(size.width() + 30, 
                                 min(1000, size.height() + 30))
        layout.addWidget(text_edit)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

def get_flexbuff_meta_data(check):
    """
    Check: a list of flexbuff machines to check
    Returns a 3-tuple (usage, available, errors)
    usage = 
      { flexbuff : { experiment : { station : { scan : number of bytes } } } }
    available = 
      { flexbuff : [sum of disk sizes in bytes, sum of bytes used over 
                    all disks, sum of bytes available over all disks] }
    errors = { flexbuff : { mount point : [recordings] } }
    """ 
    threads = []
    # [ FLEXBUF ][ EXP ][ STATION ][ SCAN ] = <number>
    usage = collections.defaultdict(
        lambda: collections.defaultdict(
            lambda: collections.defaultdict(
                lambda: collections.defaultdict(int))))
    available = collections.defaultdict(list)
    errors = collections.defaultdict(lambda: collections.defaultdict(list))
    for flexbuff in check:
        thread = threading.Thread(
            target=check_flexbuff, 
            args=(flexbuff, 
                  usage[flexbuff.machine], 
                  available[flexbuff.machine], 
                  errors[flexbuff.machine]))
        thread.start()
        threads.append(thread)

    for t in threads:
        t.join()

    return (usage, available, errors)

def check_flexbuff(flexbuff, usage, available, errors, recording_name=None):
    """
    if recording_name:
     usage has to be a dict, it will be filled in with {chunk path: size}
     available is ignored
    else:
     usage has to be a defaultdict, it will be filled in with:
     {experiment: {station: {(scan, recording): size}}}
    """
    try:
        # disk usage
        process = subprocess.Popen(
            args=shlex.split(
                "ssh -o PasswordAuthentication=no {flexbuff} "
                "\"bash -c 'echo {p}/{r} | "
                "xargs du -b -s --exclude lost+found/'\"".\
                format(
                    p=disk_pattern[flexbuff.machine_type],
                    r=(os.path.join(recording_name, recording_name) + ".*")\
                      if recording_name else "*/",
                    flexbuff=flexbuff.machine if flexbuff.user is None \
                    else "@".join([flexbuff.user, flexbuff.machine]))),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        (output, error) = process.communicate()
        returncode = process.wait()
        if returncode != 0:
            if returncode not in [1, 123]:
                # return code of du when encoutering disk problems (123)
                # or permission problems (1)
                raise RuntimeError("du failed with return code {r}".format(
                    r=returncode))
            for line in error.split('\n'):
                if line == "":
                    continue
                match = du_error_regexp[flexbuff.machine_type].match(line)
                if match:
                    errors[match.group("disk")].append(match.group("recording"))
        
        recording_regex = re.compile("^(?P<bytes>\d+)\s+(?P<recording>\S+)\s*$")
        for line in output.split('\n'):
            if line == "":
                continue
            match = recording_regex.match(line)
            if match:
                size = int(match.group("bytes"))
                if recording_name:
                    path = match.group("recording")
                    usage[path] = size
                else:
                    # recording is last directory
                    recording = os.path.split(
                        os.path.split(match.group("recording"))[0])[1]
                    split = recording.split("_")
                    (experiment, station, scan) = \
                        (split[0].upper(), 
                         split[1].capitalize(), 
                         "_".join(split[2:])) \
                         if len(split)>=3 \
                         else (None, None, None)
                    usage[experiment][station][(scan, recording)] += size
            else:
                raise RuntimeError(
                    "Unexpected line on du output: '{line}'".format(line=line))
                    
        if not recording_name:
            # disk space available
            output = subprocess.check_output(
                shlex.split("ssh -o PasswordAuthentication=no {flexbuff} "
                            "\"bash -c 'df -B 1 --total /mnt/disk*'\"".format(
                                flexbuff=flexbuff.machine \
                                if flexbuff.user is None else \
                                "@".join([flexbuff.user, flexbuff.machine]))))
            regex = re.compile("^total\s+(?P<total>\d+)\s+(?P<used>\d+)\s+(?P<available>\d+)\s+\d+%")
            for line in output.split('\n'):
                match = regex.match(line)
                if match:
                    available[:] = [int(match.group("total")),
                                    int(match.group("used")),
                                    int(match.group("available"))]

    except Exception as e:
        print "{f}: {e}".format(f = flexbuff.machine, e = e)
