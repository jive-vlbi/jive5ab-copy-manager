from import_proxy import Bunch, Hashable_Bunch
from shared import format_bytes, wait_cursor, Text_Edit_Dialog
import m5copy_widget

import PyQt4.QtGui as QtGui
import PyQt4.QtCore as QtCore

class Invalid_Selection_Exception(RuntimeError):
    pass

class Target_Thread(QtCore.QThread):
    def __init__(self, target, parent=None):
        super(Target_Thread, self).__init__(parent)
        self.target = target
        
    def run(self):
        self.target()

class Tree_Widget_Item(QtGui.QTreeWidgetItem):
    """
    In automatic column resizing mode (good), columns are close together (bad)
    I (Bob) couldn't find a way to set spacing, so instead this class will
    add spaces around the text and remove them on retrieval
    """
    spaces = 2
    def text(self, column):
        text = str(super(Tree_Widget_Item, self).text(column))
        if not text:
            return text
        return text[2:-2]

    def setText(self, column, text):
        if text:
            add = self.spaces * " "
            new_text = add + text + add
        else:
            new_text = text
        super(Tree_Widget_Item, self).setText(column, new_text)

class Abstract_Machine_View(QtGui.QWidget):
    # how many characters for a size string
    bytes_print_size = 6

    # source name, list of m5copy style (source, recording) tuples
    copy_from = QtCore.pyqtSignal(str, list)

    # probably want to overwrite these in subclass
    header_labels = []
    check_text = "Scan check"

    def _get_selection(self):
        """
        return list of selections, type of list items is free
        """
        raise NotImplementedError()
        
    def _check_selection(self, selection):
        """
        Pre: it's a valid, non-empty, selection
        return text to display
        """
        raise NotImplementedError()

    def _emit_copy(self, selection):
        """
        Pre: it's a valid, non-empty, selection
        """
        raise NotImplementedError()

    def _get_m5copy_to(self):
        """
        Pre: it's valid to copy to this machine view
        return (host name, m5copy recording destination)
        """
        raise NotImplementedError()

    def _selection_size(self, selection):
        """
        Pre: it's a valid, non-empty, selection
        return number of bytes in selected recordings
        """
        raise NotImplementedError()

    def _create_view_widget(self):
        """
        return QWidget, create a self.view QTreeWidget
        """
        raise NotImplementedError()

    def copy_to(self, from_, recordings):
        try:
            (to, recording_base) = self._get_m5copy_to()
        except Exception as e:
             QtGui.QMessageBox.critical(
                self, "Cannot copy", str(e))
             return
           
        # make the base widget the parent, such that the dialog lives on and
        # is centered properly
        grandparent = self
        while grandparent.parentWidget():
            grandparent = grandparent.parentWidget()

        options = self._get_m5copy_options()

        dialog = m5copy_widget.M5copy_Dialog(
            recordings, recording_base, from_, to, options, grandparent)
        dialog.show()
        dialog.raise_()

    def _get_m5copy_options(self):
        return "-t 120"

    def _do_check(self):
        try:
            selection = self._get_selection()
        except Invalid_Selection_Exception as e:
            QtGui.QMessageBox.critical(self, "Invalid selection", str(e))
            return
        if not selection:
            return
        with wait_cursor(QtGui.QApplication):
            text = self._check_selection(selection)
        box = Text_Edit_Dialog(text, self)
        box.show()
        box.raise_()
            
    def _do_copy(self):
        try:
            selection = self._get_selection()
        except Invalid_Selection_Exception as e:
            QtGui.QMessageBox.critical(self, "Invalid selection", str(e))
            return

        if not selection:
            return

        try:
            self._emit_copy(selection)
        except Exception as e:
            QtGui.QMessageBox.critical(self, "Cannot copy", str(e))


    def _update_selection_label(self):
        try:
            selection = self._get_selection()
        except Invalid_Selection_Exception:
            self.selection_label.setText("invalid selection")
            return

        if not selection:
            self.selection_label.setText("no selection")
            return
            
        self.selection_label.setText("{size} ({n} items)".format(
            size=format_bytes(self._selection_size(selection), 
                              self.bytes_print_size),
            n=len(selection)))

    def _deselect_children(self, index):
        item = self.view.itemFromIndex(index)
        # disconnect update selection label and call manually, 
        # otherwise it might be called many times
        self.view.itemSelectionChanged.disconnect(self._update_selection_label)
        for child in [item.child(i) for i in xrange(item.childCount())]:
            child.setSelected(False)
        self._update_selection_label()
        self.view.itemSelectionChanged.connect(self._update_selection_label)

    def _cleanup_background_loading(self, root):
        del self.background_data[root]

    def load_in_background(self, root, compute_func, display_func):
        """
        root: QTreeWidget or QTreeWidgetItem
        compute_func, display_func: callables, 
            can use self.background_data[root] Bunch as storage
        compute func shouldn't do anything with Qt as it's run in a thread
        """
        if root in self.background_data:
            # already loading
            return
            
        load_item = QtGui.QTreeWidgetItem(root)
        load_item.setFirstColumnSpanned(True)
        load_item.setText(0 , "Loading")

        thread = Target_Thread(compute_func, self)
        if isinstance(root, QtGui.QTreeWidget):
            remove_load_item = lambda: root.takeTopLevelItem(
                root.topLevelItemCount() - 1)
        elif isinstance(root, QtGui.QTreeWidgetItem):
            remove_load_item = lambda: root.removeChild(load_item)
        else:
            raise TypeError("root has to be a QTreeWidget or QTreeWidgetItem, "
                            "not {t}".format(t=type(root)))
        thread.finished.connect(remove_load_item, QtCore.Qt.QueuedConnection)
        thread.finished.connect(display_func, QtCore.Qt.QueuedConnection)
        cleanup = lambda: self._cleanup_background_loading(root)
        thread.finished.connect(cleanup, QtCore.Qt.QueuedConnection)

        self.background_data[root] = Bunch(
            _thread=thread,
            # store functions, as a reference will prevent them from being 
            # garbage collected
            _functions=(remove_load_item, cleanup, compute_func, display_func))

        thread.start()

    def await_threads(self):
        for data in self.background_data.values():
            print "waiting on background thread"
            data._thread.wait()
    
    def __init__(self, parent=None):
        super(Abstract_Machine_View, self).__init__(parent)

        self.background_data = {} # {root item: Bunch}

        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(self._create_view_widget())

        self.selection_layout = QtGui.QHBoxLayout()
        self.selection_layout.addWidget(QtGui.QLabel("Selection size: ", self))
        self.selection_label = QtGui.QLabel("no selection", self)
        self.selection_layout.addWidget(self.selection_label)
        self.selection_layout.addStretch(1)
        layout.addLayout(self.selection_layout)

        add_spacing = Tree_Widget_Item.spaces * " "
        self.view.setHeaderLabels([add_spacing + l + add_spacing for l in \
                                   self.header_labels])
        self.view.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.view.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        self.view.header().setResizeMode(
            QtGui.QHeaderView.ResizeToContents)
        self.check_action = QtGui.QAction(self.check_text, self)
        self.check_action.triggered.connect(self._do_check)
        self.view.addAction(self.check_action)
        self.copy_action = QtGui.QAction("Copy to ...", self)
        self.copy_action.triggered.connect(self._do_copy)
        self.view.addAction(self.copy_action)
        self.clear_selection_action = QtGui.QAction("Clear selection", self)
        self.clear_selection_action.setShortcuts(
            QtGui.QKeySequence(QtCore.Qt.Key_Escape))
        self.clear_selection_action.setShortcutContext(
            QtCore.Qt.WidgetWithChildrenShortcut)
        self.clear_selection_action.triggered.connect(self.view.clearSelection)
        self.view.addAction(self.clear_selection_action)
        self.view.itemSelectionChanged.connect(self._update_selection_label)
        self.view.collapsed.connect(self._deselect_children)

