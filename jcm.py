#!/usr/bin/env python

import machine_widget

import PyQt4.QtGui as QtGui
import PyQt4.QtCore as QtCore

import sys
import logging

class Main_Window(QtGui.QSplitter):
    def __init__(self, parent=None):
        super(Main_Window, self).__init__(QtCore.Qt.Horizontal, parent)
        # two widgets to allow copying
        self.left = machine_widget.Machine_Widget(self)
        self.right = machine_widget.Machine_Widget(self)
        self.left.copy_from.connect(self.right.copy_to)
        self.right.copy_from.connect(self.left.copy_to)
        self.addWidget(self.left)
        self.addWidget(self.right)

    def await_machine_threads(self):
        for widget in [self.left, self.right]:
            widget.await_threads()
        
               
if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(filename)s@%(lineno)s: "
               "%(message)s",
        level=logging.DEBUG)
    app = QtGui.QApplication(sys.argv)
    window = Main_Window()
    size = window.size()
    size.setHeight(800)
    window.resize(size)
    app.lastWindowClosed.connect(window.await_machine_threads)
    window.setWindowTitle("Jive5ab Copy Manager")
    window.show()
    sys.exit(app.exec_())
