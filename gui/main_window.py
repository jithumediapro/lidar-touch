import os
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QAction, QStatusBar, QLabel,
    QFileDialog, QMessageBox,
)

from gui.lidar_view import LidarView
from gui.control_panel import ControlPanel


class MainWindow(QMainWindow):
    """Main application window with OptiTUIO-style layout."""

    def __init__(self, settings, scanner, pipeline, tuio_sender, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._scanner = scanner
        self._pipeline = pipeline
        self._tuio_sender = tuio_sender
        self._settings_path = "settings.json"

        self.setWindowTitle("LiDAR Touch - OptiTUIO-style")
        self.resize(1200, 700)

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._connect_signals()

    def _setup_ui(self):
        # Central widget with splitter
        splitter = QSplitter(Qt.Horizontal)

        # LiDAR visualization (left, larger)
        self.lidar_view = LidarView(self._settings)
        splitter.addWidget(self.lidar_view)

        # Control panel (right, smaller)
        self.control_panel = ControlPanel(self._settings)
        self.control_panel.setMinimumWidth(300)
        self.control_panel.setMaximumWidth(450)
        splitter.addWidget(self.control_panel)

        # Set initial splitter sizes (70/30 split)
        splitter.setSizes([700, 350])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        self.setCentralWidget(splitter)

    def _setup_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        save_action = QAction("&Save Settings", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_settings)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save Settings &As...", self)
        save_as_action.triggered.connect(self._save_settings_as)
        file_menu.addAction(save_as_action)

        load_action = QAction("&Load Settings...", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self._load_settings)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        self._show_bg_action = QAction("Show Background", self, checkable=True)
        self._show_bg_action.setChecked(True)
        view_menu.addAction(self._show_bg_action)

        self._show_filtered_action = QAction("Show Filtered Points", self, checkable=True)
        self._show_filtered_action.setChecked(True)
        view_menu.addAction(self._show_filtered_action)

        self._show_touches_action = QAction("Show Touch Markers", self, checkable=True)
        self._show_touches_action.setChecked(True)
        view_menu.addAction(self._show_touches_action)

        self._show_screen_action = QAction("Show Screen Area", self, checkable=True)
        self._show_screen_action.setChecked(True)
        self._show_screen_action.toggled.connect(self.lidar_view.set_show_screen_area)
        view_menu.addAction(self._show_screen_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_statusbar(self):
        self._status_fps = QLabel("FPS: --")
        self._status_touches = QLabel("Touches: 0")
        self._status_connection = QLabel("Disconnected")
        self._status_scanning = QLabel("")

        sb = self.statusBar()
        sb.addPermanentWidget(self._status_fps)
        sb.addPermanentWidget(self._status_touches)
        sb.addPermanentWidget(self._status_connection)
        sb.addPermanentWidget(self._status_scanning)

    def _connect_signals(self):
        # Control panel -> settings/pipeline
        cp = self.control_panel

        cp.connect_requested.connect(self._on_connect_requested)
        cp.disconnect_requested.connect(self._on_disconnect_requested)
        cp.learn_requested.connect(self._pipeline.start_learning)
        cp.reset_requested.connect(self._pipeline.reset_background)
        cp.tuio_target_changed.connect(self._tuio_sender.update_target)
        cp.tuio_enabled_changed.connect(self._on_tuio_enabled)

        # Scanner -> status
        self._scanner.connection_status.connect(self._on_connection_status)

        # Pipeline -> GUI
        self._pipeline.frame_processed.connect(self._on_frame_processed)
        self._pipeline.learning_progress.connect(
            cp.devices.set_bg_progress
        )

    @pyqtSlot(str, int)
    def _on_connect_requested(self, ip, port):
        self._scanner.update_connection(ip, port)
        self._settings.update(lidar_ip=ip, lidar_port=port)
        if not self._scanner.isRunning():
            self._scanner.start()
        self._status_scanning.setText("Scanning")

    @pyqtSlot()
    def _on_disconnect_requested(self):
        self._scanner.stop()
        self._status_scanning.setText("")

    @pyqtSlot(str)
    def _on_connection_status(self, status):
        self._status_connection.setText(status.capitalize())
        self.control_panel.devices.set_connection_status(status)

    @pyqtSlot(object)
    def _on_frame_processed(self, frame):
        # Update lidar view
        self.lidar_view.update_frame(frame)

        # Update status bar
        self._status_touches.setText(f"Touches: {len(frame.touches)}")

        # Update status widget
        self.control_panel.status.update_from_frame(frame)

        # Update FPS in status bar
        fps_text = self.control_panel.status._fps_label.text()
        self._status_fps.setText(f"FPS: {fps_text}")

    @pyqtSlot(bool)
    def _on_tuio_enabled(self, enabled):
        self._tuio_sender.enabled = enabled

    def _save_settings(self):
        try:
            self._settings.save(self._settings_path)
            self.statusBar().showMessage("Settings saved", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save: {e}")

    def _save_settings_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Settings", "", "JSON Files (*.json);;All Files (*)"
        )
        if path:
            self._settings_path = path
            self._save_settings()

    def _load_settings(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Settings", "", "JSON Files (*.json);;All Files (*)"
        )
        if path:
            try:
                from config.settings import AppSettings
                loaded = AppSettings.load(path)
                snap = loaded.get_snapshot()
                self._settings.update(**snap)
                self._settings_path = path
                # Refresh GUI
                self.control_panel.devices._load_settings()
                self.control_panel.screens._load_settings()
                self.control_panel.outputs._load_settings()
                self.statusBar().showMessage("Settings loaded", 3000)
            except Exception as e:
                QMessageBox.warning(self, "Load Error", f"Failed to load: {e}")

    def _show_about(self):
        QMessageBox.about(
            self,
            "About LiDAR Touch",
            "LiDAR Touch - OptiTUIO-style Application\n\n"
            "Converts Hokuyo UST-10LX LiDAR scan data\n"
            "into multi-touch input via TUIO 1.1 protocol.\n\n"
            "Features:\n"
            "- Real-time scan visualization\n"
            "- Background learning & subtraction\n"
            "- DBSCAN blob detection\n"
            "- Persistent touch tracking\n"
            "- TUIO 1.1 /tuio/2Dcur output"
        )

    def closeEvent(self, event):
        """Graceful shutdown on window close."""
        self._scanner.stop()
        self._pipeline.stop()
        try:
            self._settings.save(self._settings_path)
        except Exception:
            pass
        event.accept()
