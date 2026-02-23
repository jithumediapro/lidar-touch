from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from gui.widgets.devices_widget import DevicesWidget
from gui.widgets.screens_widget import ScreensWidget
from gui.widgets.outputs_widget import OutputsWidget
from gui.widgets.status_widget import StatusWidget


class ControlPanel(QWidget):
    """Tabbed control panel: Devices, Screens, Outputs."""

    settings_changed = pyqtSignal(dict)
    connect_requested = pyqtSignal(str, int)
    disconnect_requested = pyqtSignal()
    learn_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    tuio_target_changed = pyqtSignal(str, int)
    tuio_enabled_changed = pyqtSignal(bool)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()

        # Devices tab
        self.devices = DevicesWidget(self._settings)
        self.devices.settings_changed.connect(self._on_settings_changed)
        self.devices.connect_requested.connect(self.connect_requested.emit)
        self.devices.disconnect_requested.connect(self.disconnect_requested.emit)
        self.devices.learn_requested.connect(self.learn_requested.emit)
        self.devices.reset_requested.connect(self.reset_requested.emit)
        self._tabs.addTab(self.devices, "Devices")

        # Screens tab
        self.screens = ScreensWidget(self._settings)
        self.screens.settings_changed.connect(self._on_settings_changed)
        self._tabs.addTab(self.screens, "Screens")

        # Outputs tab
        self.outputs = OutputsWidget(self._settings)
        self.outputs.settings_changed.connect(self._on_settings_changed)
        self.outputs.tuio_target_changed.connect(self.tuio_target_changed.emit)
        self.outputs.tuio_enabled_changed.connect(self.tuio_enabled_changed.emit)
        self._tabs.addTab(self.outputs, "Outputs")

        # Status tab
        self.status = StatusWidget()
        self._tabs.addTab(self.status, "Status")

        layout.addWidget(self._tabs)

    def _on_settings_changed(self, changes):
        self._settings.update(**changes)
        self.settings_changed.emit(changes)
