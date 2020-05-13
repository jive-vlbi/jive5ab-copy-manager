from command_widget import Command_Progress_Widget, Command_Dialog

import PyQt4.QtGui as QtGui

import re

class M5copy_Progress_Widget(Command_Progress_Widget):
    progress_re = re.compile("(?P<percentage>\d+(\.\d+)?)%"
                             "(\s+(?P<rate>\d+(\.\d+) .byte/s))?")
    
    def __init__(self, total_commands, parent=None):
        super(M5copy_Progress_Widget, self).__init__(total_commands, parent)
        self.label_layout.addStretch(1)
        self.data_rate_label = QtGui.QLabel(self)
        self.label_layout.addWidget(self.data_rate_label)
        
        self.progress_bar = QtGui.QProgressBar(self)
        self.layout.addWidget(self.progress_bar)
        self.progress_bar.setRange(0, 100*100)

    def set_command_index(self, index):
        super(M5copy_Progress_Widget, self).set_command_index(index)
        self.progress_bar.setValue(0)

    def process_output(self, text):
        super(M5copy_Progress_Widget, self).process_output(text)
        match = self.progress_re.search(text)
        if match:
            groupdict = match.groupdict()
            percentage = float(groupdict["percentage"])
            self.progress_bar.setValue(int(percentage*100))
            rate = groupdict.get("rate")
            if rate:
                self.data_rate_label.setText(rate)

class M5copy_Dialog(Command_Dialog):
    command = "m5copy"
    progress_display_class = M5copy_Progress_Widget
    
    def _protocol_changed(self):
        self.udt_widget.setEnabled(
            self.protocol_buttons.checkedButton().text() == "UDT")

    def generate_commands(self):
        commands = []
        for recording in self.recordings:
            if self.protocol_buttons.checkedButton().text() == "UDT":
                udt = "-udt "
                mtu = str(self.mtu_widget.text())
                if mtu != "":
                    udt += "-m {m} ".format(m=mtu)
                rate = str(self.rate_widget.text())
                if rate != "":
                    udt += "-r {r} ".format(r=int(float(rate)*1e6))
            else:
                udt = ""

            dest = self.destination
            if self.do_replace.isChecked():
                match = re.match(str(self.format_regex.text()), recording[1])
                if match:
                    try:
                        dest = self.destination + \
                        str(self.replace_format.text()).\
                            format(**match.groupdict()).lower()
                    except Exception as e:
                        print "warning, failed to rename recording:", e
                else:
                    print "warning, recording '{r}' failed to match regular "\
                        "expression".format(r=recording[1])
            
            commands.append("m5copy {udt}{extra} {src} {dest}".format(
                udt=udt,
                extra=str(self.extra_widget.text()),
                src="".join(recording),
                dest=dest))
        return commands

    def add_config_widgets(self, master_layout):
        network_layout = QtGui.QHBoxLayout()
        protocol_widget = QtGui.QGroupBox("Protocol", self)
        protocol_layout = QtGui.QVBoxLayout(protocol_widget)
        self.protocol_buttons = QtGui.QButtonGroup(protocol_widget)
        tcp_button = QtGui.QRadioButton("TCP", protocol_widget)
        protocol_layout.addWidget(tcp_button)
        self.protocol_buttons.addButton(tcp_button)
        udt_button = QtGui.QRadioButton("UDT", protocol_widget)
        protocol_layout.addWidget(udt_button)
        self.protocol_buttons.addButton(udt_button)
        network_layout.addWidget(protocol_widget)
        
        self.udt_widget = QtGui.QGroupBox("UDT", self)
        udt_layout = QtGui.QGridLayout(self.udt_widget)
        udt_layout.addWidget(QtGui.QLabel("Rate (Mbps)", self.udt_widget), 0, 0)
        udt_layout.addWidget(QtGui.QLabel("MTU", self.udt_widget), 1, 0)
        self.rate_widget = QtGui.QLineEdit(self.udt_widget)
        udt_layout.addWidget(self.rate_widget, 0, 1)
        self.mtu_widget = QtGui.QLineEdit(self.udt_widget)
        self.mtu_widget.setText("9000")
        udt_layout.addWidget(self.mtu_widget, 1, 1)
        network_layout.addWidget(self.udt_widget)

        self.protocol_buttons.buttonClicked.connect(self._protocol_changed)
        tcp_button.setChecked(True)
        self.udt_widget.setEnabled(False)

        master_layout.addLayout(network_layout)

        master_layout.addWidget(QtGui.QLabel("Extra options", self))
        self.extra_widget = QtGui.QLineEdit(self)
        master_layout.addWidget(self.extra_widget)
        self.extra_widget.setText(
            self.options if self.options is not None else "")
        
        replace_layout = QtGui.QHBoxLayout()
        self.do_replace = QtGui.QCheckBox("Rename recording", self)
        replace_layout.addWidget(self.do_replace)
        self.format_regex = QtGui.QLineEdit(self)
        self.format_regex.setText(
            "(.*/)?_?(?P<exp>[a-zA-Z0-9]+)_(?P<st>[a-zA-Z0-9]+)_"\
            "(?P<scan>[a-zA-Z0-9]+).*")
        replace_layout.addWidget(self.format_regex)
        self.replace_format = QtGui.QLineEdit(self)
        self.replace_format.setText("{exp}_{st}_{scan}")
        replace_layout.addWidget(self.replace_format)
        master_layout.addLayout(replace_layout)

        # connect "changed" signals to the slot that changes the apply button's
        # color
        for button in [tcp_button, udt_button, self.do_replace]:
            button.toggled.connect(self._suggest_click_apply)
        for line_edit_widget in [self.rate_widget,
                                 self.mtu_widget,
                                 self.extra_widget,
                                 self.format_regex,
                                 self.replace_format]:
            line_edit_widget.textChanged.connect(self._suggest_click_apply)

    def __init__(self, recordings, destination, from_, to, options, 
                 parent=None):
        self.destination = destination
        self.options = options
        super(M5copy_Dialog, self).__init__(recordings, parent)
        self.setWindowTitle("{s} -> {d}".format(s=from_, d=to))

