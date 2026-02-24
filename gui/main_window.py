import os
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QAction, QStatusBar, QLabel,
    QFileDialog, QMessageBox, QShortcut,
)

from gui.lidar_view import LidarView
from gui.control_panel import ControlPanel


class MainWindow(QMainWindow):
    """Main application window with multi-sensor/screen/output support."""

    def __init__(self, settings, scanners, pipelines, tuio_senders, touch_router, mock_mode=False, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._scanners = scanners        # list of scanner instances
        self._pipelines = pipelines      # list of ProcessingPipeline instances
        self._tuio_senders = tuio_senders  # list of TuioSender instances
        self._touch_router = touch_router
        self._mock_mode = mock_mode
        self._settings_path = "settings.json"

        self.setWindowTitle("M-Touch")
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

        # Global shortcut: R to reset/center view
        reset_shortcut = QShortcut(QKeySequence(Qt.Key_R), self)
        reset_shortcut.activated.connect(self.lidar_view._reset_view)

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
        cp = self.control_panel

        # Per-sensor control signals
        cp.connect_requested.connect(self._on_connect_requested)
        cp.disconnect_requested.connect(self._on_disconnect_requested)
        cp.learn_requested.connect(self._on_learn_requested)
        cp.reset_requested.connect(self._on_reset_requested)

        # Per-output TUIO signals
        cp.tuio_target_changed.connect(self._on_tuio_target_changed)
        cp.tuio_enabled_changed.connect(self._on_tuio_enabled_changed)

        # Sensor/screen/output add/remove
        cp.sensor_added.connect(self._on_sensor_added)
        cp.sensor_removed.connect(self._on_sensor_removed)
        cp.output_added.connect(self._on_output_added)
        cp.output_removed.connect(self._on_output_removed)

        # Drag-move on canvas refreshes control panel spinboxes
        self.lidar_view.object_moved.connect(self.control_panel.devices._load_settings)
        self.lidar_view.object_moved.connect(self.control_panel.screens._load_settings)

        # Connect all scanners' connection_status
        for i, scanner in enumerate(self._scanners):
            # Use default arg to capture i
            scanner.connection_status.connect(
                lambda status, si=i: self._on_connection_status(status, si)
            )

        # Connect all pipelines' frame_processed to lidar view
        for i, pipeline in enumerate(self._pipelines):
            pipeline.frame_processed.connect(self._on_frame_processed)
            pipeline.learning_progress.connect(
                lambda progress, si=i: cp.devices.set_bg_progress(progress, sensor_index=si)
            )

    @pyqtSlot(int, str, int)
    def _on_connect_requested(self, sensor_index, ip, port):
        if sensor_index < len(self._scanners):
            scanner = self._scanners[sensor_index]
            scanner.update_connection(ip, port)
            if not scanner.isRunning():
                scanner.start()
            self._status_scanning.setText("Scanning")

    @pyqtSlot(int)
    def _on_disconnect_requested(self, sensor_index):
        if sensor_index < len(self._scanners):
            self._scanners[sensor_index].stop()
            # Check if any scanner is still running
            if not any(s.isRunning() for s in self._scanners):
                self._status_scanning.setText("")

    @pyqtSlot(int)
    def _on_learn_requested(self, sensor_index):
        if sensor_index < len(self._pipelines):
            self._pipelines[sensor_index].start_learning()

    @pyqtSlot(int)
    def _on_reset_requested(self, sensor_index):
        if sensor_index < len(self._pipelines):
            self._pipelines[sensor_index].reset_background()

    def _on_connection_status(self, status, sensor_index):
        self._status_connection.setText(f"S{sensor_index+1}: {status.capitalize()}")
        self.control_panel.devices.set_connection_status(status, sensor_index=sensor_index)

    @pyqtSlot(object)
    def _on_frame_processed(self, frame):
        # Update lidar view (stores by sensor_index)
        self.lidar_view.update_frame(frame)

        # Update status bar
        self._status_touches.setText(f"Touches: {len(frame.touches)}")

        # Update status widget
        self.control_panel.status.update_from_frame(frame)

        # Update FPS in status bar
        fps_text = self.control_panel.status._fps_label.text()
        self._status_fps.setText(f"FPS: {fps_text}")

    @pyqtSlot(int, str, int)
    def _on_tuio_target_changed(self, output_index, host, port):
        if output_index < len(self._tuio_senders):
            self._tuio_senders[output_index].update_target(host, port)

    @pyqtSlot(int, bool)
    def _on_tuio_enabled_changed(self, output_index, enabled):
        if output_index < len(self._tuio_senders):
            self._tuio_senders[output_index].enabled = enabled

    @pyqtSlot(int)
    def _on_sensor_added(self, sensor_index):
        """Create a new scanner + pipeline for the added sensor."""
        from processing.pipeline import ProcessingPipeline
        from lidar.mock_scanner import MockLidarScanner

        sensor = self._settings.get_sensor(sensor_index)
        if sensor is None:
            return

        # Determine if we're in mock mode (check if existing scanners are mock)
        is_mock = any(hasattr(s, '_num_touches') for s in self._scanners) if self._scanners else self._mock_mode

        if is_mock:
            scanner = MockLidarScanner(num_touches=2)
        else:
            from lidar.scanner import LidarScanner
            scanner = LidarScanner(sensor['lidar_ip'], sensor['lidar_port'])

        pipeline = ProcessingPipeline(self._settings, sensor_index=sensor_index)
        scanner.scan_ready.connect(pipeline.enqueue_scan)

        # Connect signals
        scanner.connection_status.connect(
            lambda status, si=sensor_index: self._on_connection_status(status, si)
        )
        pipeline.frame_processed.connect(self._on_frame_processed)
        pipeline.learning_progress.connect(
            lambda progress, si=sensor_index: self.control_panel.devices.set_bg_progress(
                progress, sensor_index=si
            )
        )
        pipeline.touches_updated.connect(self._touch_router.route_touches)

        self._scanners.append(scanner)
        self._pipelines.append(pipeline)

        # Start pipeline
        pipeline.start()

        # Auto-start if mock
        if is_mock:
            scanner.start()
            self.control_panel.devices.set_connection_status("mock", sensor_index=sensor_index)

    @pyqtSlot(int)
    def _on_sensor_removed(self, sensor_index):
        """Stop and remove scanner + pipeline for the removed sensor."""
        if sensor_index < len(self._scanners):
            self._scanners[sensor_index].stop()
            self._pipelines[sensor_index].stop()
            self._scanners.pop(sensor_index)
            self._pipelines.pop(sensor_index)
            # Remove frame data for this sensor
            self.lidar_view._frames.pop(sensor_index, None)

    @pyqtSlot(int)
    def _on_output_added(self, output_index):
        """Create a new TUIO sender for the added output."""
        from tuio.sender import TuioSender
        output = self._settings.get_output(output_index)
        if output is None:
            return
        sender = TuioSender(
            output['tuio_host'],
            output['tuio_port'],
            source_name=output.get('name', 'HokuyoTouch'),
        )
        sender.enabled = output.get('tuio_enabled', True)
        self._tuio_senders.append(sender)

    @pyqtSlot(int)
    def _on_output_removed(self, output_index):
        """Remove TUIO sender for the removed output."""
        if output_index < len(self._tuio_senders):
            self._tuio_senders.pop(output_index)

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
                self.control_panel.devices._load_sensor_list()
                self.control_panel.screens._load_screen_list()
                self.control_panel.outputs._load_output_list()
                self.statusBar().showMessage("Settings loaded", 3000)
            except Exception as e:
                QMessageBox.warning(self, "Load Error", f"Failed to load: {e}")

    def _show_about(self):
        QMessageBox.about(
            self,
            "About M-Touch",
            "M-Touch - Multi-Touch LiDAR Application\n\n"
            "Converts Hokuyo LiDAR scan data\n"
            "into multi-touch input via TUIO 1.1 protocol.\n\n"
            "Features:\n"
            "- Real-time scan visualization\n"
            "- Multi-sensor support\n"
            "- Multi-screen support\n"
            "- Multi-TUIO output\n"
            "- Background learning & subtraction\n"
            "- DBSCAN blob detection\n"
            "- Persistent touch tracking\n"
            "- TUIO 1.1 /tuio/2Dcur output"
        )

    def closeEvent(self, event):
        """Graceful shutdown on window close."""
        for scanner in self._scanners:
            scanner.stop()
        for pipeline in self._pipelines:
            pipeline.stop()
        try:
            self._settings.save(self._settings_path)
        except Exception:
            pass
        event.accept()
