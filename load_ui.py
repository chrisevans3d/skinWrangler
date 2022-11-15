from PySide2 import QtCore, QtUiTools
import os
import importlib


def load_ui(uifile, baseinstance=None):
    """
    a function to load an ui file to self like this

    class CreateAssetGui(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super(CreateAssetGui, self).__init__(parent)
            load_ui(__file__[:__file__.rfind('.')] + '.ui', self)

    this helps to customize widget's behaviour

    derived from https://github.com/mottosso/Qt.py
    by ilya radovilsky https://github.com/blockinhead/
    """

    class _UiLoader(QtUiTools.QUiLoader):
        def __init__(self, baseinstance):
            super(_UiLoader, self).__init__(baseinstance)
            self.baseinstance = baseinstance
            self.custom_widgets = {}

        def _loadCustomWidgets(self, etree):
            def headerToModule(header):
                module = os.path.splitext(header)[0]
                return module.replace("/", ".").replace("\\", ".")

            custom_widgets = etree.find("customwidgets")

            if custom_widgets is None:
                return

            for custom_widget in custom_widgets:
                class_name = custom_widget.find("class").text
                header = custom_widget.find("header").text
                module = importlib.import_module(headerToModule(header))
                self.custom_widgets[class_name] = getattr(module, class_name)

        def load(self, uifile, *args, **kwargs):
            from xml.etree.ElementTree import ElementTree
            etree = ElementTree()
            etree.parse(uifile)
            self._loadCustomWidgets(etree)

            widget = QtUiTools.QUiLoader.load(self, uifile, *args, **kwargs)
            widget.parentWidget()

            return widget

        def createWidget(self, class_name, parent=None, name=""):
            if parent is None and self.baseinstance:
                return self.baseinstance

            if class_name in self.availableWidgets() + ["Line"]:
                widget = QtUiTools.QUiLoader.createWidget(self, class_name, parent, name)
            elif class_name in self.custom_widgets:
                widget = self.custom_widgets[class_name](parent=parent)
            else:
                raise Exception("Custom widget '%s' not supported" % class_name)

            if self.baseinstance:
                setattr(self.baseinstance, name, widget)

            return widget

    widget_ = _UiLoader(baseinstance).load(uifile)
    QtCore.QMetaObject.connectSlotsByName(widget_)

    return widget_
