from abstract_machine_view import (Invalid_Selection_Exception, 
                                   Abstract_Machine_View, Tree_Widget_Item)

from import_proxy import execute_query, send_query
from shared import format_bytes

import PyQt4.QtGui as QtGui
import PyQt4.QtCore as QtCore

import socket
import contextlib
import time
import collections

class Mark5_View(Abstract_Machine_View):
    header_labels = ["Bank", "VSN", "#scan", "Recording", "Size"]
    
    def _get_selection(self):
        indices = self.view.selectedIndexes()
        # we get one index for each row and column, reduce it to one per row
        # and order the bank, rows
        row_bank_scan = {}
        for index in indices:
            if not index.parent().isValid():
                raise Invalid_Selection_Exception("Can only operate on "
                    "recordings, not banks.")
            bank = str(self.view.itemFromIndex(index.parent()).text(
                self.header_labels.index("Bank")))
            assert bank in ["A", "B"]
            scan = str(self.view.itemFromIndex(index).text(
                self.header_labels.index("Recording")))
            number = int(str(self.view.itemFromIndex(index).text(
                self.header_labels.index("#scan"))))
            row_bank_scan[(bank,index.row())] = (number, scan)
        return [(bank, row_bank_scan[(bank, row)]) \
                for (bank, row) in sorted(row_bank_scan.keys())]

    def _check_selection(self, selection):
        text = ""
        with contextlib.closing(self._create_socket()) as s:
            for (bank, (number, scan)) in selection:
                self._select_bank(s, bank)
                execute_query(s, "scan_set={scan}".format(scan=number), ["0"])
                reply = send_query(s, "scan_check?")
                text += reply
        return text

    def _emit_copy(self, selection):
        self.copy_from.emit(
            self.mark5.control_ip, 
            [("mk5://{host}:{port}/{bank}/".format(
                host=self.mark5.control_ip, port=self.mark5.port, bank=bank), 
              scan) for (bank, (number, scan)) in selection])


    def _get_m5copy_to(self):
        indices = self.view.selectedIndexes()
        items = list(set(self.view.itemFromIndex(index) for index in indices))
        if (len(items) != 1) or \
           (items[0].childIndicatorPolicy() != \
           Tree_Widget_Item.ShowIndicator):
            raise Invalid_Selection_Exception("Only one bank has to be "
                "selected as the target bank to copy to.")

        return (self.mark5.control_ip, "mk5://{host}:{port}:{data_ip}/{bank}/".\
                format(
                    host=self.mark5.control_ip, 
                    port=self.mark5.port,
                    data_ip=self.mark5.data_ip,
                    bank=str(items[0].text(self.header_labels.index("Bank")))))

    def _selection_size(self, selection):
        return sum([self.recording_sizes[bank][number] \
                    for (bank, (number, scan)) in selection])

    def _create_view_widget(self):
        self.view = QtGui.QTreeWidget(self)
        self.banks = {bank : Tree_Widget_Item(self.view) \
                      for bank in ["A", "B"]}
        self.recording_sizes = {bank : {} for bank in self.banks.keys()}
        for bank, item in self.banks.items():
            item.setText(self.header_labels.index("Bank"), bank)

        with contextlib.closing(self._create_socket()) as s:
            reply = execute_query(s, "bank_set?", ["0"])
            for index in [3,5]:
                if len(reply) > index:
                    bank = reply[index-1]
                    if bank in self.banks.keys():
                        vsn = reply[index]
                        bank_item = self.banks[bank]
                        bank_item.setText(self.header_labels.index("VSN"), vsn)
                        bank_item.setChildIndicatorPolicy(
                            Tree_Widget_Item.ShowIndicator)
                        if index == 3: # active bank
                            dir_info = execute_query(s, "dir_info?", ["0"])
                            bank_item.setText(self.header_labels.index("#scan"),
                                              dir_info[2])
                            bank_item.setText(self.header_labels.index("Size"),
                                              format_bytes(
                                                  int(dir_info[3]),
                                                  self.bytes_print_size))
                        else:
                            # don't want to activate the bank just yet
                            bank_item.setText(self.header_labels.index("#scan"),
                                              "?")
                            bank_item.setText(self.header_labels.index("Size"),
                                              "?")
        return self.view

    def _create_socket(self, timeout=10):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((self.mark5.control_ip, self.mark5.port))
        return s

    def _select_bank(self, socket, bank):
        reply = execute_query(socket, "bank_set?", ["0", "1"])
        while reply[1] == "1":
            time.sleep(0.1)
            reply = execute_query(socket, "bank_set?", ["0", "1"])
        if reply[2] != bank:
            reply = execute_query(socket, "bank_set={b}".format(b=bank), 
                                  ["0", "1"])
            while reply[1] in ["1", "6"]:
                time.sleep(0.1)
                reply = execute_query(socket, "bank_set?", ["0", "6"])
        assert reply[2] == bank

    def _display_bank_info(self, root):
        data = self.background_data[root]
        root.setText(self.header_labels.index("#scan"), str(len(data.scans)))
        root.setText(self.header_labels.index("Size"), 
                     format_bytes(data.size, self.bytes_print_size))
        for index, (recording, size) in enumerate(data.scans):
            item = Tree_Widget_Item(root)
            item.setText(self.header_labels.index("#scan"), str(index+1))
            item.setText(self.header_labels.index("Recording"), recording)
            item.setText(self.header_labels.index("Size"), 
                         format_bytes(size, self.bytes_print_size))

    def _get_bank_info(self, bank, root):
        data = self.background_data[root]
        with contextlib.closing(self._create_socket()) as s:
            self._select_bank(s, bank)

            dir_info = execute_query(s, "dir_info?", ["0"])
            # refresh display data
            scans = int(dir_info[2])
            data.size = int(dir_info[3])

            data.scans = []
            for scan_index in xrange(scans):
                execute_query(s, "scan_set={i}".format(i=scan_index+1), 
                              ["0"])
                reply = execute_query(s, "scan_set?", ["0"])
                number = int(reply[2])
                recording = reply[3]
                bytes_ = int(reply[5]) - int(reply[4])
                self.recording_sizes[bank][number] = bytes_
                data.scans.append((recording, bytes_))

    def _expand_disk(self, index):
        bank = str(self.view.itemFromIndex(index).text(
            self.header_labels.index("Bank")))
        bank_item = self.banks.get(bank)
        if bank_item and (bank_item.childCount() == 0):
            self.recording_sizes[bank] = {}
            self.load_in_background(bank_item,
                lambda: self._get_bank_info(bank, bank_item),
                lambda: self._display_bank_info(bank_item))

    def __init__(self, mark5, parent=None):
        self.mark5 = mark5

        super(Mark5_View, self).__init__(parent)
        
        self.view.expanded.connect(self._expand_disk)


