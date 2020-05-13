from shared import Text_Edit_Dialog

import PyQt4.QtGui as QtGui
import PyQt4.QtCore as QtCore

# fix bug of QWIDGETSIZE_MAX not being exported on some versions of Qt
try:
    QtGui.QWIDGETSIZE_MAX
except AttributeError:
    QtGui.QWIDGETSIZE_MAX = ((1 << 24) - 1)

import subprocess
import shlex
import signal
import os

class Message_Box_Resize(QtGui.QMessageBox):
    """
    Default QMessageBox is not resizeable, 
    this is a bit hackish way around that.
    Also resize on clicking Show details.
    """
    def __init__(self, *args, **kwargs):
        super(Message_Box_Resize, self).__init__(*args, **kwargs)
        self.setMouseTracking(True)
        self.setSizeGripEnabled(True)
        self.details_button = None

    def allow_resize(self):
        self.setMaximumSize(QtGui.QWIDGETSIZE_MAX, QtGui.QWIDGETSIZE_MAX)
        text_edit = self.findChild(QtGui.QTextEdit)
        if text_edit:
            text_edit.setMaximumHeight(QtGui.QWIDGETSIZE_MAX)

    def event(self, e):
        res = super(Message_Box_Resize, self).event(e)
        if e.type() in [QtCore.QEvent.MouseMove, 
                        QtCore.QEvent.MouseButtonPress]:
            self.allow_resize()
        return res

    def showEvent(self, e):
        # override to get details button
        res = super(Message_Box_Resize, self).showEvent(e)
        if (self.details_button is None):
            for button in self.buttons():
                if (self.buttonRole(button) == QtGui.QMessageBox.ActionRole \
                    and \
                    button.text() == self.tr("Show Details...")):
                    self.details_button = button;
                    button.clicked.connect(self.resize_for_details)
                    break
        return res
                    
    def resize_for_details(self):
        self.allow_resize()
        if self.details_button.text() != \
           self.tr("Show Details..."):
            size = self.size()
            size.setHeight(size.height() * 2)
            size.setWidth(size.width() * 2)
            self.resize(size)
            

class Command_Progress_Widget(QtGui.QWidget):
    def __init__(self, total_commands, parent=None):
        super(Command_Progress_Widget, self).__init__(parent)
        self.layout = QtGui.QVBoxLayout(self)

        self.label_layout = QtGui.QHBoxLayout()
        self.command_label = QtGui.QLabel(self)
        self.label_layout.addWidget(self.command_label)
        self.layout.addLayout(self.label_layout)
        self.total_commands = total_commands

    def set_command_index(self, index):
        self.command_label.setText("Executing command {n} of {t}".format(
            n=index+1,
            t=self.total_commands))

    def process_output(self, text):
        pass

class Command_Dialog(QtGui.QDialog):
    """
    Abstract class, subclasses should define:
    - self.command, as the shell command to execute.
    - generate_commands: a list of shell commands to execute.
    - self.progress_display_class: a (subclass of) Command_Progress_Widget
    - add_config_widgets: which adds widgets to the given (QVBox) layout
    """
    def _show_help(self):
        output = subprocess.check_output(shlex.split("{command} -h".format(
            command=self.command)))
        dialog = Text_Edit_Dialog(output, self)
        dialog.show()
        dialog.raise_()

    def generate_commands(self):
        raise NotImplementedError()

    def _display_commands(self):
        commands = self.generate_commands()
        
        # set the width of the window such that no horizontal scroll is
        # required for bold text (indicating done)
        font =  self.commands_widget.document().defaultFont()
        font.setWeight(QtGui.QFont.Bold)
        metrics = QtGui.QFontMetrics(font)
        text = "\n".join(commands)
        size = metrics.size(0, text)
        self.commands_widget.setMinimumWidth(size.width() + 30)
        
        self.commands_widget.setText(text)

    def _run_commands(self):
        if self._process:
            return
        self.apply_button.setEnabled(False)
        self.go_button.setEnabled(False)
        self.cancel_button.setText("Abort")
        self.commands_widget.setReadOnly(True)
        self._line_number = 0
        self._continue = True
        self.progress_widget = self.progress_display_class(
            len(str(self.commands_widget.toPlainText()).split("\n")), self)
        self.stop_button = QtGui.QPushButton("Stop on next", self)
        self.stop_button.setCheckable(True)
        # replace stretch with the progress widget and stop on next button
        self.control_layout.takeAt(0)
        self.control_layout.insertWidget(0, self.progress_widget, 1)
        self.control_layout.insertWidget(1, self.stop_button)
        
        self._start_process()

    def _set_command_line_format(self, line_number, format_):
        self.commands_widget.moveCursor(QtGui.QTextCursor.Start)
        for i in xrange(line_number):
            self.commands_widget.moveCursor(QtGui.QTextCursor.Down)
        self.commands_widget.moveCursor(QtGui.QTextCursor.EndOfLine,
                                        QtGui.QTextCursor.KeepAnchor)
        self.commands_widget.mergeCurrentCharFormat(format_)
        self.commands_widget.moveCursor(QtGui.QTextCursor.StartOfLine)
        self.commands_widget.ensureCursorVisible()

    def _start_process(self):
        try:
            commands = str(self.commands_widget.toPlainText()).split("\n")
            if (self._line_number >= len(commands)) or \
               self.stop_button.isChecked():
                self.cancel_button.setText("Done")
                if self.stop_button.isChecked():
                    self.go_button.setText("Reuse")
                    self.go_button.setEnabled(True)
                return
            self.progress_widget.set_command_index(self._line_number)
            
            # highlight current line
            self.commands_widget.moveCursor(QtGui.QTextCursor.Start)
            for i in xrange(self._line_number):
                self.commands_widget.moveCursor(QtGui.QTextCursor.Down)
            line = QtGui.QTextEdit.ExtraSelection()
            line.format.setBackground(
                QtGui.QColor(QtCore.Qt.yellow).lighter(160))
            line.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
            line.cursor = self.commands_widget.textCursor()
            line.cursor.clearSelection()
            self.commands_widget.setExtraSelections([line])

            command = shlex.split(commands[self._line_number])
            self._process = QtCore.QProcess(self)
            # be sure we get all output, merge stdout with stderr
            self._process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
            self._output = [] # list of strings
            self._process.readyReadStandardOutput.connect(self._check_progress)
            self._process.finished.connect(self._process_finished)
            self._process.error.connect(self._process_error)
            self._process.start(command[0], command[1:])
        except Exception as e:
            QtGui.QMessageBox.critical(self, 
                                       "Failed to start {}".format(self.command),
                                       "Exception: {e}".format(e=e))
            self._process = None
            self.cancel_button.setText("Close")

    def _handle_error(self):
        self.cancel_button.setText("Close")
        self.go_button.setText("Reuse")
        self.go_button.setEnabled(True)

    def _process_error(self, error):
        self.commands_widget.setExtraSelections([])
        box = QtGui.QMessageBox(
            QtGui.QMessageBox.Warning,
            "Command failed",
            "Failed to run {}".format(self.command),
            QtGui.QMessageBox.Ok,
            self)
        box.exec_()
        self._process = None

        self._handle_error()

    def _process_finished(self, exit_code, exit_status):
        self.commands_widget.setExtraSelections([])
        if self._process:
            text = str(self._process.readAllStandardOutput())
            self._output.append(text)
        self._process = None
        if (exit_code != 0) or (not self._continue):
            if self._continue:
                # only show error if it's unexpected
                box = Message_Box_Resize(
                    QtGui.QMessageBox.Warning,
                    "Command failed",
                    "{} returned an error, click for all output".format(
                        self.command),
                    QtGui.QMessageBox.Ok,
                    self)
                box.setDetailedText(''.join(self._output))
                box.exec_()
            self._handle_error()
        else:
            # make the just finished line bold
            format_ = QtGui.QTextCharFormat()
            format_.setFontWeight(QtGui.QFont.Bold)
            self._set_command_line_format(self._line_number, format_)
            
            self._line_number += 1
            self._start_process()
            
    def _cancel_button_clicked(self):
        if str(self.cancel_button.text()) == "Abort":
            self._continue = False
            if self._process:
                os.kill(self._process.pid(), signal.SIGINT)
        else:
            # close
            self.deleteLater()
            self.accept()

    def _set_reuse(self):
        # replace progress widget and stop button with stretch
        self.control_layout.takeAt(1)
        self.control_layout.takeAt(0)
        self.stop_button.deleteLater()
        self.progress_widget.deleteLater()
        self.control_layout.insertStretch(0, 1)

        self.apply_button.setEnabled(True)
        self.commands_widget.setReadOnly(False)
        self.go_button.setText("Go")

    def _go_button_clicked(self):
        if str(self.go_button.text()) == "Go":
            self._run_commands()
        else:
            self._set_reuse()

    def stop(self):
        if self._process:
            os.kill(self._process.pid(), signal.SIGINT)
            self._process.waitForFinished(-1)

    def _disconnect_stop(self):
        QtGui.QApplication.instance().lastWindowClosed.disconnect(self.stop)

    def _check_progress(self):
        if self._process:
            text = str(self._process.readAllStandardOutput())
            self._output.append(text)
            self.progress_widget.process_output(text)

    def _suggest_click_apply(self):
        self.apply_button.setStyleSheet("background-color: firebrick")

    def _restore_apply(self):
        self.apply_button.setStyleSheet(self._original_apply_stylesheet)

    def add_config_widgets(self, master_layout):
        raise NotImplementedError()

    def __init__(self, recordings, parent=None):
        super(Command_Dialog, self).__init__(parent)
        self.recordings = recordings

        master_layout = QtGui.QVBoxLayout(self)
        self.add_config_widgets(master_layout)
        
        button_layout = QtGui.QHBoxLayout()
        help_button = QtGui.QPushButton("Help", self)
        button_layout.addWidget(help_button)
        help_button.clicked.connect(self._show_help)
        button_layout.addStretch(1)
        self.apply_button = QtGui.QPushButton("Apply", self)
        button_layout.addWidget(self.apply_button)
        self.apply_button.clicked.connect(self._display_commands)
        master_layout.addLayout(button_layout)

        self.commands_widget = QtGui.QTextEdit(self)
        self.commands_widget.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        master_layout.addWidget(self.commands_widget)

        self.control_layout = QtGui.QHBoxLayout()
        self.control_layout.addStretch(1)
        self.go_button = QtGui.QPushButton("Go", self)
        self.control_layout.addWidget(self.go_button)
        self.go_button.clicked.connect(self._go_button_clicked)
        self.cancel_button = QtGui.QPushButton("Cancel", self)
        self.control_layout.addWidget(self.cancel_button)
        self.cancel_button.clicked.connect(self._cancel_button_clicked)
        
        self._original_apply_stylesheet = self.apply_button.styleSheet()
        self.apply_button.clicked.connect(self._restore_apply)
        
        master_layout.addLayout(self.control_layout)

        self._display_commands()
        self._process = None

        # make sure the process is stopped when the application is
        QtGui.QApplication.instance().lastWindowClosed.connect(self.stop)
        self.destroyed.connect(self._disconnect_stop)

