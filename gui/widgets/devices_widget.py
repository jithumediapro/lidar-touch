from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton,
    QCheckBox, QProgressBar, QFormLayout,
)


class DevicesWidget(QWidget):
    """Devices tab: sensor connection, position, filtering, background."""

    connect_requested = pyqtSignal(str, int)
    disconnect_requested = pyqtSignal()
    settings_changed = pyqtSignal(dict)
    learn_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._connected = False
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # --- Connection Group ---
        conn_group = QGroupBox("Sensor Connection")
        conn_layout = QFormLayout()

        self._ip_edit = QLineEdit()
        self._ip_edit.setPlaceholderText("192.168.0.10")
        conn_layout.addRow("IP Address:", self._ip_edit)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(10940)
        conn_layout.addRow("Port:", self._port_spin)

        btn_layout = QHBoxLayout()
        self._connect_btn = QPushButton("Start")
        self._connect_btn.clicked.connect(self._on_connect)
        btn_layout.addWidget(self._connect_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_disconnect)
        btn_layout.addWidget(self._stop_btn)
        conn_layout.addRow(btn_layout)

        self._status_label = QLabel("Disconnected")
        self._status_label.setStyleSheet("color: #888;")
        conn_layout.addRow("Status:", self._status_label)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # --- Position Group ---
        pos_group = QGroupBox("Sensor Position")
        pos_layout = QFormLayout()

        self._x_offset = QDoubleSpinBox()
        self._x_offset.setRange(-10000, 10000)
        self._x_offset.setSuffix(" mm")
        self._x_offset.valueChanged.connect(self._emit_settings)
        pos_layout.addRow("X Offset:", self._x_offset)

        self._y_offset = QDoubleSpinBox()
        self._y_offset.setRange(-10000, 10000)
        self._y_offset.setSuffix(" mm")
        self._y_offset.valueChanged.connect(self._emit_settings)
        pos_layout.addRow("Y Offset:", self._y_offset)

        self._z_rotation = QDoubleSpinBox()
        self._z_rotation.setRange(-180, 180)
        self._z_rotation.setSuffix(" deg")
        self._z_rotation.valueChanged.connect(self._emit_settings)
        pos_layout.addRow("Z Rotation:", self._z_rotation)

        self._x_flip = QCheckBox("X Flip")
        self._x_flip.stateChanged.connect(self._emit_settings)
        self._y_flip = QCheckBox("Y Flip")
        self._y_flip.stateChanged.connect(self._emit_settings)
        flip_layout = QHBoxLayout()
        flip_layout.addWidget(self._x_flip)
        flip_layout.addWidget(self._y_flip)
        pos_layout.addRow("Orientation:", flip_layout)

        pos_group.setLayout(pos_layout)
        layout.addWidget(pos_group)

        # --- Filtering Group ---
        filt_group = QGroupBox("Detection Zone")
        filt_layout = QFormLayout()

        self._min_dist = QDoubleSpinBox()
        self._min_dist.setRange(0, 30000)
        self._min_dist.setSuffix(" mm")
        self._min_dist.setSingleStep(10)
        self._min_dist.valueChanged.connect(self._emit_settings)
        filt_layout.addRow("Min Distance:", self._min_dist)

        self._max_dist = QDoubleSpinBox()
        self._max_dist.setRange(0, 30000)
        self._max_dist.setSuffix(" mm")
        self._max_dist.setSingleStep(10)
        self._max_dist.valueChanged.connect(self._emit_settings)
        filt_layout.addRow("Max Distance:", self._max_dist)

        self._min_angle = QDoubleSpinBox()
        self._min_angle.setRange(-90, 90)
        self._min_angle.setSuffix(" deg")
        self._min_angle.valueChanged.connect(self._emit_settings)
        filt_layout.addRow("Min Angle:", self._min_angle)

        self._max_angle = QDoubleSpinBox()
        self._max_angle.setRange(-90, 90)
        self._max_angle.setSuffix(" deg")
        self._max_angle.valueChanged.connect(self._emit_settings)
        filt_layout.addRow("Max Angle:", self._max_angle)

        filt_group.setLayout(filt_layout)
        layout.addWidget(filt_group)

        # --- Advanced Group ---
        adv_group = QGroupBox("Advanced")
        adv_layout = QFormLayout()

        self._kalman_check = QCheckBox("Enable")
        self._kalman_check.stateChanged.connect(self._emit_settings)
        adv_layout.addRow("Kalman Filter:", self._kalman_check)

        self._smoothing = QDoubleSpinBox()
        self._smoothing.setRange(0.0, 1.0)
        self._smoothing.setSingleStep(0.1)
        self._smoothing.valueChanged.connect(self._emit_settings)
        adv_layout.addRow("Smoothing:", self._smoothing)

        self._min_touch_seg = QSpinBox()
        self._min_touch_seg.setRange(1, 50)
        self._min_touch_seg.valueChanged.connect(self._emit_settings)
        adv_layout.addRow("Min Touch Segments:", self._min_touch_seg)

        self._bg_threshold = QDoubleSpinBox()
        self._bg_threshold.setRange(1, 500)
        self._bg_threshold.setSuffix(" mm")
        self._bg_threshold.valueChanged.connect(self._emit_settings)
        adv_layout.addRow("BG Threshold:", self._bg_threshold)

        adv_group.setLayout(adv_layout)
        layout.addWidget(adv_group)

        # --- Background Group ---
        bg_group = QGroupBox("Background")
        bg_layout = QVBoxLayout()

        bg_form = QFormLayout()
        self._bg_frames = QSpinBox()
        self._bg_frames.setRange(5, 200)
        self._bg_frames.valueChanged.connect(self._emit_settings)
        bg_form.addRow("Learning Frames:", self._bg_frames)
        bg_layout.addLayout(bg_form)

        self._bg_progress = QProgressBar()
        self._bg_progress.setRange(0, 100)
        self._bg_progress.setValue(0)
        bg_layout.addWidget(self._bg_progress)

        bg_btn_layout = QHBoxLayout()
        self._learn_btn = QPushButton("Learn Background")
        self._learn_btn.clicked.connect(self.learn_requested.emit)
        bg_btn_layout.addWidget(self._learn_btn)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.clicked.connect(self.reset_requested.emit)
        bg_btn_layout.addWidget(self._reset_btn)
        bg_layout.addLayout(bg_btn_layout)

        bg_group.setLayout(bg_layout)
        layout.addWidget(bg_group)

        layout.addStretch()

    def _load_settings(self):
        snap = self._settings.get_snapshot()
        self._ip_edit.setText(snap['lidar_ip'])
        self._port_spin.setValue(snap['lidar_port'])
        self._x_offset.setValue(snap['sensor_x_offset'])
        self._y_offset.setValue(snap['sensor_y_offset'])
        self._z_rotation.setValue(snap['sensor_z_rotation'])
        self._x_flip.setChecked(snap['sensor_x_flip'])
        self._y_flip.setChecked(snap['sensor_y_flip'])
        self._min_dist.setValue(snap['min_distance_mm'])
        self._max_dist.setValue(snap['max_distance_mm'])
        self._min_angle.setValue(snap['min_angle_deg'])
        self._max_angle.setValue(snap['max_angle_deg'])
        self._kalman_check.setChecked(snap['kalman_filter'])
        self._smoothing.setValue(snap['smoothing_value'])
        self._min_touch_seg.setValue(snap['min_touch_segments'])
        self._bg_threshold.setValue(snap['bg_subtraction_threshold_mm'])
        self._bg_frames.setValue(snap['bg_learning_frames'])

    def _emit_settings(self):
        changes = {
            'sensor_x_offset': self._x_offset.value(),
            'sensor_y_offset': self._y_offset.value(),
            'sensor_z_rotation': self._z_rotation.value(),
            'sensor_x_flip': self._x_flip.isChecked(),
            'sensor_y_flip': self._y_flip.isChecked(),
            'min_distance_mm': self._min_dist.value(),
            'max_distance_mm': self._max_dist.value(),
            'min_angle_deg': self._min_angle.value(),
            'max_angle_deg': self._max_angle.value(),
            'kalman_filter': self._kalman_check.isChecked(),
            'smoothing_value': self._smoothing.value(),
            'min_touch_segments': self._min_touch_seg.value(),
            'bg_subtraction_threshold_mm': self._bg_threshold.value(),
            'bg_learning_frames': self._bg_frames.value(),
        }
        self.settings_changed.emit(changes)

    def _on_connect(self):
        ip = self._ip_edit.text().strip()
        port = self._port_spin.value()
        self.connect_requested.emit(ip, port)
        self._connect_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_label.setText("Connecting...")
        self._status_label.setStyleSheet("color: #fa0;")

    def _on_disconnect(self):
        self.disconnect_requested.emit()
        self._connect_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("Disconnected")
        self._status_label.setStyleSheet("color: #888;")

    def set_connection_status(self, status):
        self._status_label.setText(status.capitalize())
        if status == "connected" or status == "reconnected":
            self._status_label.setStyleSheet("color: #0f0;")
            self._connect_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
        elif status == "mock":
            self._status_label.setText("Mock")
            self._status_label.setStyleSheet("color: #fa0;")
            self._connect_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
        elif "error" in status:
            self._status_label.setStyleSheet("color: #f00;")
            self._connect_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
        else:
            self._status_label.setStyleSheet("color: #888;")
            self._connect_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)

    def set_bg_progress(self, progress):
        self._bg_progress.setValue(int(progress * 100))
