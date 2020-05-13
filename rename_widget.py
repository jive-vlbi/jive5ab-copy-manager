from command_widget import Command_Progress_Widget, Command_Dialog

import PyQt4.QtGui as QtGui

import re

class Rename_Dialog(Command_Dialog):
    command = "vbs_rename"
    progress_display_class = Command_Progress_Widget
    
    def generate_commands(self):
        commands = []
        for flexbuff, recording in self.recordings:
            match = re.match(str(self.format_regex.text()), recording.recording)
            if match:
                try:
                    dest = str(self.replace_format.text()).format(
                        **match.groupdict())
                    commands.append("vbs_rename -f {f} {src} {dest}".format(
                        f=flexbuff.machine,
                        src=recording.recording,
                        dest=dest.lower()))
                except Exception as e:
                    commands.append("# failed to process '{r}': {e}".format(
                        r=recording.recording, e=e))
            else:
                commands.append("# recording '{r}' does not match regular "\
                                "expression".format(r=recording.recording))
        return commands

    def add_config_widgets(self, master_layout):
        replace_layout = QtGui.QHBoxLayout()
        self.format_regex = QtGui.QLineEdit(self)
        self.format_regex.setText(
            "(?P<exp>[a-zA-Z0-9]+)_(?P<st>[a-zA-Z0-9]+)_"
            "(?P<scan>[a-zA-Z0-9]+).*")
        replace_layout.addWidget(self.format_regex)
        self.replace_format = QtGui.QLineEdit(self)
        self.replace_format.setText("{exp}_{st}_{scan}")
        replace_layout.addWidget(self.replace_format)
        master_layout.addLayout(replace_layout)

        # connect "changed" signals to the slot that changes the apply button's
        # color
        for line_edit_widget in [self.format_regex,
                                 self.replace_format]:
            line_edit_widget.textChanged.connect(self._suggest_click_apply)

    def __init__(self, recordings, parent=None):
        super(Rename_Dialog, self).__init__(recordings, parent)
        self.setWindowTitle("Rename recordings")

