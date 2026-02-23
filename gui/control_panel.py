from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from gui.widgets.devices_widget import DevicesWidget
from gui.widgets.screens_widget import ScreensWidget
from gui.widgets.outputs_widget import OutputsWidget
from gui.widgets.status_widget import StatusWidget


class ControlPanel(QWidget):
    """Tabbed control panel: Devices, Screens, Outputs."""

    settings_changed = pyqtSignal(dict)
    connect_requested = pyqtSignal(int, str, int)    # sensor_index, ip, port
    disconnect_requested = pyqtSignal(int)            # sensor_index
    learn_requested = pyqtSignal(int)                 # sensor_index
    reset_requested = pyqtSignal(int)                 # sensor_index
    sensor_added = pyqtSignal(int)                    # sensor_index
    sensor_removed = pyqtSignal(int)                  # sensor_index
    screen_added = pyqtSignal(int)                    # screen_index
    screen_removed = pyqtSignal(int)                  # screen_index
    output_added = pyqtSignal(int)                    # output_index
    output_removed = pyqtSignal(int)                  # output_index
    tuio_target_changed = pyqtSignal(int, str, int)   # output_index, host, port
    tuio_enabled_changed = pyqtSignal(int, bool)      # output_index, enabled

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
        self.devices.sensor_added.connect(self.sensor_added.emit)
        self.devices.sensor_removed.connect(self.sensor_removed.emit)
        self._tabs.addTab(self.devices, "Devices")

        # Screens tab
        self.screens = ScreensWidget(self._settings)
        self.screens.settings_changed.connect(self._on_settings_changed)
        self.screens.screen_added.connect(self._on_screen_list_changed)
        self.screens.screen_added.connect(self.screen_added.emit)
        self.screens.screen_removed.connect(self._on_screen_list_changed)
        self.screens.screen_removed.connect(self.screen_removed.emit)
        self._tabs.addTab(self.screens, "Screens")

        # Outputs tab
        self.outputs = OutputsWidget(self._settings)
        self.outputs.settings_changed.connect(self._on_settings_changed)
        self.outputs.tuio_target_changed.connect(self.tuio_target_changed.emit)
        self.outputs.tuio_enabled_changed.connect(self.tuio_enabled_changed.emit)
        self.outputs.output_added.connect(self.output_added.emit)
        self.outputs.output_removed.connect(self.output_removed.emit)
        self._tabs.addTab(self.outputs, "Outputs")

        # Status tab
        self.status = StatusWidget()
        self._tabs.addTab(self.status, "Status")

        layout.addWidget(self._tabs)

    def _on_settings_changed(self, changes):
        if changes:
            self._settings.update(**changes)
        self.settings_changed.emit(changes)

    def _on_screen_list_changed(self, _index):
        """When screens are added/removed, refresh the outputs screen combo."""
        self.outputs.refresh_screen_list()
