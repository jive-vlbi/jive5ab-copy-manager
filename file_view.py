from import_proxy import execute_query, send_query
from shared import format_bytes
from abstract_machine_view import (Invalid_Selection_Exception, 
                                   Abstract_Machine_View, Tree_Widget_Item)


import PyQt4.QtGui as QtGui
import PyQt4.QtCore as QtCore

import os.path
import subprocess
import shlex
import re
import contextlib
import socket

class File_View(Abstract_Machine_View):
    header_labels = ["File", "Size"]
    check_text = "File check"

    def _get_selection(self):
        indices = self.view.selectedIndexes()
        if any([self.view.itemFromIndex(index).childIndicatorPolicy() == \
                Tree_Widget_Item.ShowIndicator for index in indices]):
            raise Invalid_Selection_Exception("Can only operate on files, "
                                              "not directories.")
        return [self._get_path(index) for index in indices \
                if index.column() == 0]

    def _check_selection(self, selection):
        text = ""
        with contextlib.closing(self._create_socket()) as s:
            for filepath in selection:
                text += send_query(s, "file_check?::{f}".format(f=filepath))
        return text

    def _emit_copy(self, selection):
        self.copy_from.emit(self.args.control_ip, 
            [("file://{host}:{port}/".format(
                host=self.args.control_ip, 
                port=self.args.port), \
              filename)
             for filename in selection])

    def _get_m5copy_to(self):
        indices = self.view.selectedIndexes()
        items = list(set(self.view.itemFromIndex(index) for index in indices))
        if (len(items) != 1) or \
           (items[0].childIndicatorPolicy() != \
           Tree_Widget_Item.ShowIndicator):
            raise Invalid_Selection_Exception("Only one directory has to be "
                "selected as the target directory to copy to.")

        return (self.args.control_ip, 
                "file://{host}:{port}:{data_ip}/{dirname}/".format(
                    host=self.args.control_ip,
                    port=self.args.port,
                    data_ip=self.args.data_ip,
                    dirname=self._get_path(indices[0])))

    def _selection_size(self, selection):
        return sum([self.file_sizes[filepath] for filepath in selection])
        

    def _create_view_widget(self):
        self.view = QtGui.QTreeWidget(self)
        self.root_item = Tree_Widget_Item(self.view)
        self.root_item.setText(self.header_labels.index("File"), 
                               self.args.root_path)
        self.root_item.setChildIndicatorPolicy(
            Tree_Widget_Item.ShowIndicator)

        return self.view

    def _create_socket(self, timeout=10):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((self.args.control_ip, self.args.port))
        return s

    def _get_path(self, index):
        paths = [str(self.view.itemFromIndex(index).text(
            self.header_labels.index("File")))]
        parent = index.parent()
        while parent.isValid():
            paths.insert(0, str(self.view.itemFromIndex(parent).text(
                self.header_labels.index("File"))))
            parent = parent.parent()
        return os.path.join(*paths)

    #-rw-rw-r-- 1 jops jive    700 Sep  9 14:07 time_conversion.py
    # for now only handle directories and regular files
    ls_re = re.compile(
        "\s*(?P<type>[d-])"
        "(?P<permissions>([r-][w-][xTtsS-]){3})\s+"
        "(?P<links>\d+)\s+"
        "(?P<owner>\S+)\s+"
        "(?P<group>\S+)\s+"
        "(?P<size>\d+)\s+"
        "(?P<date_time>\S+\s+\S+\s+\S+)\s+"
        "(?P<name>.+)")
    def _expand_dir(self, index):
        expanding = self.view.itemFromIndex(index)
        if expanding in self.expanded:
            return
        dir_ = self._get_path(index)
        output = subprocess.check_output(shlex.split(
            "ssh -o PasswordAuthentication=no {user}{machine} ls -l {dir_}".\
            format(user=(self.args.user + "@" if self.args.user else ""),
                   machine=self.args.control_ip,
                   dir_=dir_)))
        for line in output.split("\n")[1:]: # first line is total line
            match = self.ls_re.match(line)
            if match:
                item = Tree_Widget_Item(expanding)
                groups = match.groupdict()
                name = groups["name"]
                item.setText(self.header_labels.index("File"), name)
                if groups["type"] == "d":
                    item.setChildIndicatorPolicy(
                        Tree_Widget_Item.ShowIndicator)
                else:
                    size = int(groups["size"])
                    item.setText(self.header_labels.index("Size"), 
                                 format_bytes(size, self.bytes_print_size))
                    self.file_sizes[os.path.join(dir_, name)] = size
                    
            else:
                print "warning, failed to match:", line
        self.expanded.add(expanding)
        # Qt wouldn't show the scroll bar when the above actions would expand
        # the expand the size of the view beyond the viewport, 
        # resizing seems to force this to happen
        self.resize(self.size())

    def __init__(self, args, parent=None):
        """
        @args: Bunch(user, machine, port, root_path)
        """
        self.args = args
        if self.args.root_path[-1] != '/':
            self.args.root_path = self.args.root_path + '/'

        super(File_View, self).__init__(parent)
        
        # get directory contents on expand, but only once
        self.view.expanded.connect(self._expand_dir)
        self.expanded = set()

        self.file_sizes = {} # {absolute path: number of bytes}
