from shared import get_flexbuff_meta_data, check_flexbuff, format_bytes
from import_proxy import execute_query, send_query, Hashable_Bunch
from abstract_machine_view import (Invalid_Selection_Exception, 
                                   Abstract_Machine_View, Tree_Widget_Item)
import rename_widget


import PyQt4.QtGui as QtGui
import PyQt4.QtCore as QtCore

import collections
import contextlib
import socket

def disk_selection(flexbuff):
    if flexbuff.machine_type == "mark6":
        return "mk6"
    else:
        return flexbuff.machine_type

class Flexbuff_View(Abstract_Machine_View):
    header_labels = ["Experiment", "Station", "Scan", "Chunk", "Size", 
                     "FlexBuff"]
    
    def _get_selection(self):
        """
        selection items is of type Bunch(recording, size)
        if the item represents a file chunk, recording contains the file path
        """
        indices = self.view.selectedIndexes()
        if not indices:
            return []

        # the meaning of operating on a selection including different levels
        # at same time is not immediately clear, so show an error in such a case
        levels = set()
        # we get one index for each row and column, so remove doubles
        row_index = {}
        for index in indices:
            rows = [index.row()]
            level = 0
            parent = index.parent()
            while parent.isValid():
                level += 1
                rows.insert(0, parent.row())
                parent = parent.parent()
            levels.add(level)
            if len(levels) > 1:
                raise Invalid_Selection_Exception("Can only operate on "
                    "selections that contain one group "
                    "(experiments, stations, recordings or file chunks).")
            row_index[tuple(rows)] = index

        flexbuff_recordings = [] # [(flexbuff, Bunch(recording,size))]
        def handle_scan_item(experiment, station, scan_item):
            scan = str(scan_item.text(self.header_labels.index("Scan")))
            if len(self.flexbuffs) > 1:
                for machine in str(scan_item.text(
                        self.header_labels.index("FlexBuff"))).split(", "):
                    flexbuff_recordings.append(
                        (self.flexbuffs[machine],
                         self.data[experiment][station][scan]))
            else:
                flexbuff_recordings.append(
                    (self.flexbuffs.values()[0],
                     self.data[experiment][station][scan]))

        def handle_station_item(experiment, station_item):
            station = str(station_item.text(
                self.header_labels.index("Station")))
            for scan_item in [station_item.child(i) for i in \
                              xrange(station_item.childCount())]:
                handle_scan_item(experiment, station, scan_item)

        def handle_experiment_item(experiment_item):
            experiment = str(experiment_item.text(self.header_labels.index(
                "Experiment")))
            for station_item in [experiment_item.child(i) for i in \
                                 xrange(experiment_item.childCount())]:
                handle_station_item(experiment, station_item)

        for _, index in sorted(row_index.items()):
            if level == 0:
                # experiment level
                handle_experiment_item(self.view.itemFromIndex(index))
            elif level == 1:
                # station level
                experiment = str(self.view.itemFromIndex(index.parent()).text(
                    self.header_labels.index("Experiment")))
                station_item = self.view.itemFromIndex(index)
                handle_station_item(experiment, station_item)
            elif level == 2:
                # scan level
                station_index = index.parent()
                experiment = str(self.view.itemFromIndex(
                    station_index.parent()).text(
                        self.header_labels.index("Experiment")))
                station = str(self.view.itemFromIndex(station_index).text(
                    self.header_labels.index("Station")))
                scan_item = self.view.itemFromIndex(index)
                handle_scan_item(experiment, station, scan_item)
            elif level == 3:
                # chunk level
                scan_index = index.parent()
                scan = str(self.view.itemFromIndex(scan_index).text(
                        self.header_labels.index("Scan")))
                station_index = scan_index.parent()
                experiment = str(self.view.itemFromIndex(
                    station_index.parent()).text(
                        self.header_labels.index("Experiment")))
                station = str(self.view.itemFromIndex(station_index).text(
                    self.header_labels.index("Station")))
                scan_item = self.view.itemFromIndex(index)
                chunk_index = str(self.view.itemFromIndex(index).text(
                    self.header_labels.index("Chunk"))).split()[0]
                if len(self.flexbuffs) > 1:
                    for machine in str(scan_item.text(
                            self.header_labels.index("FlexBuff"))).split(", "):
                        flexbuff_recordings.append(
                            (self.flexbuffs[machine],
                             self.chunks[experiment][station][scan]\
                             [chunk_index]))
                else:
                    flexbuff_recordings.append(
                        (self.flexbuffs.values()[0],
                         self.chunks[experiment][station][scan][chunk_index]))
            else:
                raise RuntimeError("Invalid level {l}.".format(l=level))
                    
        return flexbuff_recordings

    def _check_selection(self, selection):
        text = ""
        flexbuffs = set(flexbuff for (flexbuff, _) in selection)
        for fb in flexbuffs:
            with contextlib.closing(self._create_socket(fb, timeout=60)) as s:
                flexbuff_recordings = [data.recording for (flexbuff, data) \
                                       in selection if flexbuff == fb]
                for recording in flexbuff_recordings:
                    if recording.startswith("/"):
                        # chunk
                        text += send_query(s, "file_check?::{f}".format(
                            f=recording))
                    else:
                        # recording
                        execute_query(s, "scan_set={r}".format(r=recording), 
                                      ["0"])
                        reply = send_query(s, "scan_check?")
                        text += reply
        return text

    def _emit_copy(self, selection):
        if any([data.recording.startswith("/") for (_, data) in selection]):
            QtGui.QMessageBox.critical(
                self, "Cannot copy", 
                "Cannot copy file chunks from FlexBuff view.")
            return
            
        if len(selection) > len(set(data for (_, data) in selection)):
            QtGui.QMessageBox.critical(
                self, "Cannot copy", "Some recordings are present on multiple "
                "FlexBuffs, reduce FlexBuff source selection first.")
            return

        flexbuffs = set(fb.machine for (fb, _) in selection)
        data_format = "mk6" if self.mark6_format.isChecked() else "vbs"
        self.copy_from.emit(", ".join(flexbuffs),
                            [("{data}://{host}:{port}/{type_}/".format(
                                data=data_format,
                                host=flexbuff.machine,
                                port=flexbuff.port,
                                type_=disk_selection(flexbuff)),
                              data.recording) \
                             for (flexbuff, data) in selection])


    def _get_m5copy_to(self):
        if len(self.flexbuffs) > 1:
            raise RuntimeError("Cannot copy to multiple FlexBuffs, "
                "choose one FlexBuff as the destination.")
        if self.view.selectedIndexes():
            raise Invalid_Selection_Exception("Selection on the target "
                "FlexBuff has to be empty as copying to a specific "
                "destination is not supported.")
        flexbuff = self.flexbuffs.values()[0]
        data_format = "mk6" if self.mark6_format.isChecked() else "vbs"
        return (flexbuff.machine, "{data}://{host}:{port}:{data_ip}/{type_}/".

                format(data=data_format,
                       host=flexbuff.control_ip, 
                       port=flexbuff.port, 
                       data_ip=flexbuff.data_ip,
                       type_=disk_selection(flexbuff)))

    def _selection_size(self, selection):
        return sum([data.size for (_, data) in selection])

    def _display_data(self):
        data = self.background_data[self.view]

        # clear the disk usage layout
        while True:
            item = self.disk_usage_layout.takeAt(0)
            if not item:
                break
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for index, text in enumerate(["Total", "Used", "Free"]):
            if index > 0:
                self.disk_usage_layout.addStretch(1)
            try:
                size = format_bytes(sum([l[index] \
                                         for l in data.available.values()]),
                                    self.bytes_print_size)
            except IndexError:
                size = "?"
            self.disk_usage_layout.addWidget(QtGui.QLabel(
                "{text}: {n}".format(text=text, n=size)))

        policy = Tree_Widget_Item.ShowIndicator \
                 if self.show_file_chunks.isChecked() \
                 else Tree_Widget_Item.DontShowIndicator
        multi_flexbuff = (len(self.flexbuffs) > 1)
        experiments = sorted(data.presence.keys())
        for experiment in experiments:
            experiment_item = Tree_Widget_Item(self.view)
            experiment_item.setText(self.header_labels.index("Experiment"), 
                                    experiment)
            experiment_size = sum(
                [scan_size for experiment_data in data.usage.values() \
                 for station_data in experiment_data[experiment].values() \
                 for scan_size in station_data.values()])
            experiment_item.setText(self.header_labels.index("Size"), 
                format_bytes(experiment_size, self.bytes_print_size))
            if multi_flexbuff:
                station_flexbuffs = [set.union(*scan_data.values()) \
                    for scan_data in data.presence[experiment].values()]
                experiment_flexbuffs = set.union(*station_flexbuffs)
                experiment_item.setText(
                    self.header_labels.index("FlexBuff"), 
                    ", ".join(experiment_flexbuffs))
            stations = sorted(data.presence[experiment].keys())
            for station in stations:
                station_item = Tree_Widget_Item(experiment_item)
                station_item.setText(self.header_labels.index("Station"), 
                                     station)
                station_size = sum(
                    [scan_size for experiment_data in data.usage.values() \
                     for scan_size in \
                     experiment_data[experiment][station].values()])
                station_item.setText(self.header_labels.index("Size"), 
                    format_bytes(station_size, self.bytes_print_size))
                if multi_flexbuff:
                    station_flexbuffs = set.union(
                        *data.presence[experiment][station].values())
                    station_item.setText(
                        self.header_labels.index("FlexBuff"), 
                        ", ".join(station_flexbuffs))
                scans = sorted(data.presence[experiment][station].keys())
                for (scan, recording) in scans:
                    scan_item = Tree_Widget_Item(station_item)
                    scan_item.setText(self.header_labels.index("Scan"), 
                                      scan)
                    scan_size = sum(
                        [experiment_data[experiment][station] \
                         [(scan, recording)] \
                         for experiment_data in data.usage.values()])
                    scan_item.setText(self.header_labels.index("Size"), 
                        format_bytes(scan_size, self.bytes_print_size))
                    scan_item.setChildIndicatorPolicy(policy)
                    if multi_flexbuff:
                        scan_item.setText(
                            self.header_labels.index("FlexBuff"), 
                            ", ".join(data.presence[experiment]\
                                      [station][(scan, recording)]))

        self.view.collapseAll()
        self.mark6_format.setEnabled(True)


    def _get_data(self):
        data = self.background_data[self.view]

        is_mark6_data_format = self.mark6_format.isChecked()
        (data.usage, data.available, data.errors) = \
            get_flexbuff_meta_data(self.flexbuffs.values(), is_mark6_data_format)

        # {experiment : {station : {(scan, recording) : set(flexbuffs)}}}
        data.presence = collections.defaultdict(
            lambda: collections.defaultdict(
                lambda: collections.defaultdict(set)))
        # {experiment : {station : {scan : Bunch(recording, size)}}}
        self.data = collections.defaultdict(
            lambda: collections.defaultdict(dict))
        for flexbuff, experiment_data in data.usage.items():
            for experiment, station_data in experiment_data.items():
                if experiment is None:
                    # used to indicate not-vbs-type data
                    continue
                for station, scan_data in station_data.items():
                    for ((scan, recording), size) in scan_data.items():
                        data.presence[experiment][station]\
                            [(scan, recording)].add(flexbuff)
                        self.data[experiment][station][scan] = \
                            Hashable_Bunch(recording=recording, size=size) 

    def _create_view_widget(self):
        widget = QtGui.QWidget(self)
        layout = QtGui.QVBoxLayout(widget)
        disk_usage_widget = QtGui.QGroupBox("Disk usage", widget)
        self.disk_usage_layout = QtGui.QHBoxLayout(disk_usage_widget)
        self.disk_usage_layout.addWidget(QtGui.QLabel("Loading", self))
        layout.addWidget(disk_usage_widget)

        self.view = QtGui.QTreeWidget(widget)
        layout.addWidget(self.view)

        return widget

    def _create_socket(self, flexbuff, timeout=10):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((flexbuff.machine, flexbuff.port))
        return s

    def _set_data_format(self):
        self.mark6_format.setEnabled(False)
        self.view.clear()
        self.load_in_background(self.view, self._get_data, self._display_data)

    def _set_chunk_visibility(self):
        visible = self.show_file_chunks.isChecked()
        if visible:
            self.view.showColumn(self.header_labels.index("Chunk"))
            policy = Tree_Widget_Item.ShowIndicator
        else:
            self.view.hideColumn(self.header_labels.index("Chunk"))
            policy = Tree_Widget_Item.DontShowIndicator

        for experiment_item in [self.view.topLevelItem(i) for i in \
                                xrange(self.view.topLevelItemCount())]:
            for station_item in [experiment_item.child(i) for i in \
                                 xrange(experiment_item.childCount())]:
                for scan_item in [station_item.child(i) for i in \
                              xrange(station_item.childCount())]:
                    if not visible:
                        scan_item.setExpanded(False)
                    scan_item.setChildIndicatorPolicy(policy)

    def _expand_scan(self, index):
        level = 0
        parent = index.parent()
        while parent.isValid():
            level += 1
            parent = parent.parent()
        if level != 2:
            # no need to do work on experiment or station level indices
            return
        
        scan_item = self.view.itemFromIndex(index)
        if scan_item in self.expanded:
            # already scanned for the chunks
            return

        scan = str(scan_item.text(self.header_labels.index("Scan")))
        station_item = scan_item.parent()
        station = str(station_item.text(self.header_labels.index("Station")))
        experiment = str(station_item.parent().text(
            self.header_labels.index("Experiment")))
        if len(self.flexbuffs) > 1:
            machines = str(scan_item.text(
                self.header_labels.index("FlexBuff"))).split(", ")
        else:
            machines = self.flexbuffs.keys()
        for flexbuff in [self.flexbuffs[machine] for machine in machines]:
            chunks = {}
            errors = {}
            is_mark6_data_format = self.mark6_format.isChecked()
            check_flexbuff(flexbuff, chunks, None, errors,
                           self.data[experiment][station][scan].recording,
                           is_mark6_data_format)
            
            display = set()
            if is_mark6_data_format:
                for chunk, size in chunks.items():
                    disk = "/".join(chunk.split("/")[3:5])
                    display.add((disk, size))
                for (disk, size) in sorted(display):
                    self.chunks[experiment][station][scan][disk] = \
                        Hashable_Bunch(recording=chunk, size=size)
                    item = Tree_Widget_Item(scan_item)
                    item.setText(self.header_labels.index("Chunk"),
                                 disk)
                    item.setText(self.header_labels.index("Size"),
                                 format_bytes(size, self.bytes_print_size))
                    if len(self.flexbuffs) > 1:
                        item.setText(self.header_labels.index("FlexBuff"),
                        flexbuff.machine)
            else:
                for chunk, size in chunks.items():
                    disk = chunk.split("/")[2]
                    index = chunk.split(".")[-1]
                    display.add((index, disk, size))
                    self.chunks[experiment][station][scan][index] = \
                        Hashable_Bunch(recording=chunk, size=size)
                for (index, disk, size) in sorted(display):
                    item = Tree_Widget_Item(scan_item)
                    item.setText(self.header_labels.index("Chunk"),
                                 index + " on " + disk)
                    item.setText(self.header_labels.index("Size"),
                                 format_bytes(size, self.bytes_print_size))
                    if len(self.flexbuffs) > 1:
                        item.setText(self.header_labels.index("FlexBuff"),
                        flexbuff.machine)

        self.expanded.add(scan_item)
        
    def _get_m5copy_options(self):
        return super(Flexbuff_View, self)._get_m5copy_options() + \
            (" -p 4000" if self.local else "")

    def _rename(self):
        selection = self._get_selection()

        # make the base widget the parent, such that the dialog lives on and
        # is centered properly
        grandparent = self
        while grandparent.parentWidget():
            grandparent = grandparent.parentWidget()

        dialog = rename_widget.Rename_Dialog(selection, grandparent)
        dialog.show()
        dialog.raise_()

    def __init__(self, (flexbuffs, local), parent=None):
        if not flexbuffs:
            raise RuntimeError("Empty set of FlexBuffs.")
        self.flexbuffs = {flexbuff.machine : flexbuff for flexbuff in flexbuffs}
        self.local = local

        super(Flexbuff_View, self).__init__(parent)

        self.mark6_format = QtGui.QCheckBox("Mark6 format", self)
        self.selection_layout.addWidget(self.mark6_format)
        self.mark6_format.clicked.connect(self._set_data_format)
        self.mark6_format.setEnabled(False)

        self.show_file_chunks = QtGui.QCheckBox("Show file chunks", self)
        self.selection_layout.addWidget(self.show_file_chunks)
        self.show_file_chunks.clicked.connect(self._set_chunk_visibility)

        self.view.expanded.connect(self._expand_scan)
        self.expanded = set()
        self.view.hideColumn(self.header_labels.index("Chunk"))
        # {experiment : {station : {scan : {index: Bunch(recording, size)}}}}
        self.chunks = collections.defaultdict(lambda: collections.defaultdict(
            lambda: collections.defaultdict(dict)))
        
        if len(self.flexbuffs) == 1:
            self.view.hideColumn(self.header_labels.index("FlexBuff"))

        self.rename_action = QtGui.QAction("Rename", self)
        self.rename_action.triggered.connect(self._rename)
        self.view.addAction(self.rename_action)

        self.load_in_background(self.view, self._get_data, self._display_data)
        


