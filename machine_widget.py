import mark5_view
import flexbuff_view
import file_view
import import_proxy
from import_proxy import Bunch, Hashable_Bunch

import PyQt4.QtGui as QtGui
import PyQt4.QtCore as QtCore

import collections
import traceback
import logging
import copy

class Machine_Widget(QtGui.QWidget):
    copy_from = QtCore.pyqtSignal(str, list)
    def copy_to(self, from_, recordings):
        if hasattr(self.view, "copy_to"):
            self.view.copy_to(from_, recordings)
        else:
            QtGui.QMessageBox.critical(self, "Cannot copy", "No suitable "
                                       "destination to copy to selected")

    def _initialize_machine_types(self):
        self.machine_types = {} # {type : {display names: type dependent data}}
        """
        type_dependent_data:
        Mark5: Bunch (control_ip, port, data_ip)
        FlexBuff: [flexbuff Bunch(name, control_ip, port, user[, data_ip])] 
                  multiple flexbuffs can be combined
        File: Bunch(user, control_ip, data_ip, port)
        """
        self.machine_types["Mark5"] = collections.OrderedDict([
            ("{name} ({ip})".format(name=du.machine, ip=du.control_ip), du) 
            for du in import_proxy.get_mark5s()])
        local_flexbuffs = import_proxy.get_local_flexbuffs()
        remote_flexbuffs = import_proxy.get_remote_flexbuffs()
        # a flexbuff can host multiple stations, group 
        grouped_remote_flexbuffs = collections.defaultdict(list)
        # also group all flexbuffs for a station
        station_remote_flexbuffs = collections.defaultdict(list)
        for fb in remote_flexbuffs:
            # use control ip as machine name
            stationless_fb = Hashable_Bunch(user=fb.user, 
                                            machine=fb.control_ip, 
                                            port=fb.port, 
                                            control_ip=fb.control_ip,
                                            data_ip=fb.data_ip, 
                                            machine_type=fb.machine_type)
            grouped_remote_flexbuffs[stationless_fb].append(fb.station)
            station_remote_flexbuffs[fb.station].append(stationless_fb)
        self.machine_types["FlexBuff"] = collections.OrderedDict(
            [("All local FlexBuffs", (local_flexbuffs, True))] +
            # single local flexbuffs
            [("{name} ({ip})".format(name=fb.machine, ip=fb.control_ip), 
              ([fb], True)) for fb in local_flexbuffs] +
            # remote stations, group stations being hosted
            [("{name} ({stations})".format(name=fb.machine, stations=", ".join(
                sorted(stations))),
              ([fb], False)) 
             for fb, stations in grouped_remote_flexbuffs.items()] +
            # remote stations, group flexbuffs by station if multiple flexbuff
            [("{station} ({machines})".format(
                station=station, 
                machines=", ".join([fb.machine for fb in flexbuffs])),
              (flexbuffs, False))
             for station, flexbuffs in station_remote_flexbuffs.items()
             if len(flexbuffs) > 1]
            )
        self.machine_types["File"] = collections.OrderedDict(
            ("{name} ({ip})".format(name=fm.machine, ip=fm.control_ip), fm)
            for fm in import_proxy.get_file_machines())

    def _parse_host(self, host, machine_type):
        machine = host.strip()
        # machine: [user@]<control_ip/host>[:port[:data_ip]]

        at_index = machine.find("@")
        if at_index != -1:
            user = machine[:at_index]
            machine = machine[at_index+1:]
        else:
            user = None
        
        colon_index = machine.rfind(":")
        if colon_index != -1:
            last = machine[colon_index+1:]
            machine = machine[:colon_index]
            colon_index = machine.rfind(":")
            if colon_index == -1:
                port = int(last)
                data_ip = machine
            else:
                data_ip = last
                port = int(machine[colon_index+1:])
                machine = machine[:colon_index]
        else:
            port = 2620
            data_ip = machine


        if machine_type == "Mark5":
            self.machine_types[machine_type][host] = Hashable_Bunch(
                control_ip=machine, 
                port=port, 
                data_ip=data_ip)
        elif machine_type == "FlexBuff":
            self.machine_types[machine_type][host] = (
                [Hashable_Bunch(
                    user=user, 
                    machine=machine, 
                    port=port, 
                    control_ip=machine,
                    data_ip=data_ip, 
                    machine_type="flexbuff")],
                False) # assume non-local flexbuff
        elif machine_type == "File":
            self.machine_types[machine_type][host] = Hashable_Bunch(
                user=user, 
                control_ip=machine,
                data_ip=data_ip,
                port=port)

    def _machine_type_selected(self, machine):
        machine = str(machine)
        self.host.clear()
        self.host.addItems([""] + self.machine_types[machine].keys())
        if machine == "File":
            self.file_widget.show()
        else:
            self.file_widget.hide()

    def _reload_clicked(self):
        host = self.host.currentText()
        self._host_selected(host)

    def _cleanup_references(self):
         # make a copy of the list as items might be removed
        for widget in self.widget_references[:]:
            if not widget.background_data:
                widget.deleteLater()
                self.widget_references.remove(widget)

    def await_threads(self):
        for widget in self.widget_references:
            widget.await_threads()
        
    def _host_selected(self, host):
        self.master_layout.removeWidget(self.view)
        self.view.hide()
        self._cleanup_references()
        w = self._create_machine_type_widget(host)
        if not w:
            # failed to create widget, create an empty one
            w = QtGui.QWidget(self)
        else:
            w.copy_from.connect(self.copy_from)
            self.widget_references.append(w)
        self.view = w
        self.master_layout.addWidget(self.view)
            
    def _create_machine_type_widget(self, host):
        host = str(host)
        machine_type = str(self.machine_type.currentText())
        args = self.machine_types[machine_type].get(host)
        if not args:
            try:
                self._parse_host(host, machine_type)
            except Exception as e:
                QtGui.QMessageBox.critical(self, "Cannot parse host", 
                "Cannot parse host '{host}', exception: {e}".format(
                    host=host, e=e))
                self.host.removeItem(self.host.findText(host))
                return None
            args = self.machine_types[machine_type][host]
            
        try:
            machine = str(self.machine_type.currentText())
            if machine == "Mark5":
                return mark5_view.Mark5_View(args, self)
            elif machine == "FlexBuff":
                return flexbuff_view.Flexbuff_View(args, self)
            elif machine == "File":
                path = str(self.file_selection.text())
                if len(path) == 0:
                    QtGui.QMessageBox.critical(self, "No path selected", 
                        "No root path selected for file view on host {host}".\
                        format(host=host))
                instance_args = Bunch(args)
                instance_args.root_path = path
                return file_view.File_View(instance_args, self)

        except Exception as e:
            logging.debug("{e}\n{t}".format(e=e,t=traceback.format_exc()))
            return None

    def _create_selection_widget(self):
        self._initialize_machine_types()
        widget = QtGui.QGroupBox("Selection", self)
        layout = QtGui.QHBoxLayout(widget)
        layout.addWidget(QtGui.QLabel("Type", self))
        self.machine_type = QtGui.QComboBox(self)
        items = self.machine_types.keys()
        self.machine_type.addItems(items)
        self.machine_type.setCurrentIndex(items.index("FlexBuff"))
        layout.addWidget(self.machine_type)
        layout.addStretch(1)
        reload_button = QtGui.QPushButton("Reload", self)
        layout.addWidget(reload_button)

        self.file_widget = QtGui.QWidget(self)
        file_layout = QtGui.QHBoxLayout(self.file_widget)
        file_layout.addWidget(QtGui.QLabel("Root path", self.file_widget))
        self.file_selection = QtGui.QLineEdit("/", self.file_widget)
        file_layout.addWidget(self.file_selection)
        # use a much higher stretch than the stretch before reload
        layout.addWidget(self.file_widget, 1000) 

        host_widget = QtGui.QWidget(self)
        host_layout = QtGui.QHBoxLayout(host_widget)
        host_layout.addWidget(QtGui.QLabel("Host", host_widget))
        self.host = QtGui.QComboBox(host_widget)
        self.host.setEditable(True)
        self.host.setInsertPolicy(QtGui.QComboBox.InsertAtBottom)

        host_layout.addWidget(self.host)
        layout.addWidget(host_widget)
        
        self.machine_type.activated[QtCore.QString].\
            connect(self._machine_type_selected)
        reload_button.clicked.connect(self._reload_clicked)
        self.host.activated[QtCore.QString].connect(self._host_selected)
        self._machine_type_selected(self.machine_type.currentText())
        return widget

    def __init__(self, parent = None):
        super(Machine_Widget, self).__init__(parent)

        self._initialize_machine_types()

        self.master_layout = QtGui.QVBoxLayout(self)
        selection_widget = self._create_selection_widget()
        self.master_layout.addWidget(selection_widget)

        self.view = QtGui.QWidget(self)
        self.master_layout.addWidget(self.view)

        # the machine widget can have thread to collect information
        # while these threads are running, keep a reference to allow 
        # proper cleanup
        self.widget_references = []
       
