from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton,
    QCheckBox, QProgressBar, QFormLayout, QListWidget,
    QComboBox,
)

from config.settings import LIDAR_MODELS


class DevicesWidget(QWidget):
    """Devices tab: multi-sensor list with per-sensor connection, position, filtering, background."""

    connect_requested = pyqtSignal(int, str, int)   # sensor_index, ip, port
    disconnect_requested = pyqtSignal(int)           # sensor_index
    settings_changed = pyqtSignal(dict)
    learn_requested = pyqtSignal(int)                # sensor_index
    reset_requested = pyqtSignal(int)                # sensor_index
    sensor_added = pyqtSignal(int)                   # new sensor_index
    sensor_removed = pyqtSignal(int)                 # removed sensor_index

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._loading = False
        self._setup_ui()
        self._load_sensor_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # --- Sensor List Group ---
        list_group = QGroupBox("Sensors")
        list_layout = QVBoxLayout()

        self._sensor_list = QListWidget()
        self._sensor_list.setMaximumHeight(80)
        self._sensor_list.currentRowChanged.connect(self._on_sensor_selected)
        list_layout.addWidget(self._sensor_list)

        btn_layout = QHBoxLayout()
        self._add_sensor_btn = QPushButton("Add Sensor")
        self._add_sensor_btn.clicked.connect(self._on_add_sensor)
        btn_layout.addWidget(self._add_sensor_btn)

        self._remove_sensor_btn = QPushButton("Remove Sensor")
        self._remove_sensor_btn.clicked.connect(self._on_remove_sensor)
        btn_layout.addWidget(self._remove_sensor_btn)
        list_layout.addLayout(btn_layout)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # --- Name ---
        name_layout = QFormLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Sensor name")
        self._name_edit.textChanged.connect(self._on_name_changed)
        name_layout.addRow("Name:", self._name_edit)
        layout.addLayout(name_layout)

        # --- Connection Group ---
        conn_group = QGroupBox("Sensor Connection")
        conn_layout = QFormLayout()

        self._model_combo = QComboBox()
        for model_name, model_info in LIDAR_MODELS.items():
            self._model_combo.addItem(model_name)
        self._model_combo.currentTextChanged.connect(self._on_model_changed)
        conn_layout.addRow("Model:", self._model_combo)

        self._ip_edit = QLineEdit()
        self._ip_edit.setPlaceholderText("192.168.0.10")
        conn_layout.addRow("IP Address:", self._ip_edit)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(10940)
        conn_layout.addRow("Port:", self._port_spin)

        ctrl_layout = QHBoxLayout()
        self._connect_btn = QPushButton("Start")
        self._connect_btn.clicked.connect(self._on_connect)
        ctrl_layout.addWidget(self._connect_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_disconnect)
        ctrl_layout.addWidget(self._stop_btn)
        conn_layout.addRow(ctrl_layout)

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
        self._x_offset.valueChanged.connect(self._emit_sensor_settings)
        pos_layout.addRow("X Offset:", self._x_offset)

        self._y_offset = QDoubleSpinBox()
        self._y_offset.setRange(-10000, 10000)
        self._y_offset.setSuffix(" mm")
        self._y_offset.valueChanged.connect(self._emit_sensor_settings)
        pos_layout.addRow("Y Offset:", self._y_offset)

        self._z_rotation = QDoubleSpinBox()
        self._z_rotation.setRange(-180, 180)
        self._z_rotation.setSuffix(" deg")
        self._z_rotation.valueChanged.connect(self._emit_sensor_settings)
        pos_layout.addRow("Z Rotation:", self._z_rotation)

        self._x_flip = QCheckBox("X Flip")
        self._x_flip.stateChanged.connect(self._emit_sensor_settings)
        self._y_flip = QCheckBox("Y Flip")
        self._y_flip.stateChanged.connect(self._emit_sensor_settings)
        self._rot90_btn = QPushButton("90\u00b0")
        self._rot90_btn.setFixedWidth(40)
        self._rot90_btn.setToolTip("Rotate sensor 90 degrees")
        self._rot90_btn.clicked.connect(self._on_rotate_90)
        flip_layout = QHBoxLayout()
        flip_layout.addWidget(self._x_flip)
        flip_layout.addWidget(self._y_flip)
        flip_layout.addWidget(self._rot90_btn)
        pos_layout.addRow("Orientation:", flip_layout)

        pos_group.setLayout(pos_layout)
        layout.addWidget(pos_group)

        # --- Advanced Group ---
        adv_group = QGroupBox("Advanced")
        adv_layout = QFormLayout()

        self._kalman_check = QCheckBox("Enable")
        self._kalman_check.stateChanged.connect(self._emit_global_settings)
        adv_layout.addRow("Kalman Filter:", self._kalman_check)

        self._smoothing = QDoubleSpinBox()
        self._smoothing.setRange(0.0, 1.0)
        self._smoothing.setSingleStep(0.1)
        self._smoothing.valueChanged.connect(self._emit_global_settings)
        adv_layout.addRow("Smoothing:", self._smoothing)

        self._min_touch_seg = QSpinBox()
        self._min_touch_seg.setRange(1, 50)
        self._min_touch_seg.valueChanged.connect(self._emit_global_settings)
        adv_layout.addRow("Min Touch Segments:", self._min_touch_seg)

        self._bg_threshold = QDoubleSpinBox()
        self._bg_threshold.setRange(1, 500)
        self._bg_threshold.setSuffix(" mm")
        self._bg_threshold.valueChanged.connect(self._emit_global_settings)
        adv_layout.addRow("BG Threshold:", self._bg_threshold)

        adv_group.setLayout(adv_layout)
        layout.addWidget(adv_group)

        # --- Background Group ---
        bg_group = QGroupBox("Background")
        bg_layout = QVBoxLayout()

        bg_form = QFormLayout()
        self._bg_frames = QSpinBox()
        self._bg_frames.setRange(5, 200)
        self._bg_frames.valueChanged.connect(self._emit_global_settings)
        bg_form.addRow("Learning Frames:", self._bg_frames)
        bg_layout.addLayout(bg_form)

        self._bg_progress = QProgressBar()
        self._bg_progress.setRange(0, 100)
        self._bg_progress.setValue(0)
        bg_layout.addWidget(self._bg_progress)

        bg_btn_layout = QHBoxLayout()
        self._learn_btn = QPushButton("Learn Background")
        self._learn_btn.clicked.connect(self._on_learn)
        bg_btn_layout.addWidget(self._learn_btn)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.clicked.connect(self._on_reset)
        bg_btn_layout.addWidget(self._reset_btn)
        bg_layout.addLayout(bg_btn_layout)

        bg_group.setLayout(bg_layout)
        layout.addWidget(bg_group)

        layout.addStretch()

    def _current_sensor_index(self):
        row = self._sensor_list.currentRow()
        return row if row >= 0 else -1

    def _load_sensor_list(self):
        """Reload the sensor list widget from settings."""
        self._sensor_list.blockSignals(True)
        current = self._sensor_list.currentRow()
        self._sensor_list.clear()
        snap = self._settings.get_snapshot()
        for sensor in snap.get('sensors', []):
            self._sensor_list.addItem(sensor.get('name', 'Sensor'))
        if 0 <= current < self._sensor_list.count():
            self._sensor_list.setCurrentRow(current)
        elif self._sensor_list.count() > 0:
            self._sensor_list.setCurrentRow(0)
        self._sensor_list.blockSignals(False)
        self._remove_sensor_btn.setEnabled(self._sensor_list.count() > 0)
        self._load_settings()

    def _on_sensor_selected(self, row):
        if row >= 0:
            self._load_settings()

    def _load_settings(self):
        """Load settings for the currently selected sensor."""
        self._loading = True
        idx = self._current_sensor_index()
        sensor = self._settings.get_sensor(idx)
        has_sensor = sensor is not None
        # Enable/disable per-sensor controls based on whether a sensor exists
        # Model combo stays enabled so user can pre-select before adding
        for widget in (self._name_edit, self._ip_edit, self._port_spin,
                       self._connect_btn, self._stop_btn,
                       self._x_offset, self._y_offset, self._z_rotation,
                       self._x_flip, self._y_flip, self._rot90_btn,
                       self._learn_btn, self._reset_btn):
            widget.setEnabled(has_sensor)
        self._model_combo.setEnabled(True)
        if not has_sensor:
            self._status_label.setText("No sensors")
            self._status_label.setStyleSheet("color: #888;")

        # Load global settings regardless of sensor selection
        snap = self._settings.get_snapshot()
        self._kalman_check.setChecked(snap.get('kalman_filter', False))
        self._smoothing.setValue(snap.get('smoothing_value', 0.5))
        self._min_touch_seg.setValue(snap.get('min_touch_segments', 2))
        self._bg_threshold.setValue(snap.get('bg_subtraction_threshold_mm', 40.0))
        self._bg_frames.setValue(snap.get('bg_learning_frames', 30))

        if not has_sensor:
            self._loading = False
            return

        self._name_edit.setText(sensor.get('name', 'Sensor'))

        model = sensor.get('model', 'UST-10LX')
        idx_in_combo = self._model_combo.findText(model)
        if idx_in_combo >= 0:
            self._model_combo.setCurrentIndex(idx_in_combo)

        self._ip_edit.setText(sensor.get('lidar_ip', '192.168.0.10'))
        self._port_spin.setValue(sensor.get('lidar_port', 10940))
        self._x_offset.setValue(sensor.get('sensor_x_offset', 0.0))
        self._y_offset.setValue(sensor.get('sensor_y_offset', 0.0))
        self._z_rotation.setValue(sensor.get('sensor_z_rotation', 0.0))
        self._x_flip.setChecked(sensor.get('sensor_x_flip', False))
        self._y_flip.setChecked(sensor.get('sensor_y_flip', False))
        self._loading = False

    def _on_rotate_90(self):
        """Rotate the sensor by 90 degrees (wraps at 180/-180)."""
        idx = self._current_sensor_index()
        if idx < 0:
            return
        current = self._z_rotation.value()
        new_val = current + 90.0
        if new_val > 180.0:
            new_val -= 360.0
        self._z_rotation.setValue(new_val)

    def _emit_sensor_settings(self):
        """Save per-sensor settings changes."""
        if self._loading:
            return
        idx = self._current_sensor_index()
        if idx < 0:
            return
        changes = {
            'sensor_x_offset': self._x_offset.value(),
            'sensor_y_offset': self._y_offset.value(),
            'sensor_z_rotation': self._z_rotation.value(),
            'sensor_x_flip': self._x_flip.isChecked(),
            'sensor_y_flip': self._y_flip.isChecked(),
        }
        self._settings.update_sensor(idx, **changes)
        self.settings_changed.emit({})

    def _emit_global_settings(self):
        """Save global processing settings changes."""
        if self._loading:
            return
        changes = {
            'kalman_filter': self._kalman_check.isChecked(),
            'smoothing_value': self._smoothing.value(),
            'min_touch_segments': self._min_touch_seg.value(),
            'bg_subtraction_threshold_mm': self._bg_threshold.value(),
            'bg_learning_frames': self._bg_frames.value(),
        }
        self._settings.update(**changes)
        self.settings_changed.emit(changes)

    def _on_name_changed(self, name):
        if self._loading:
            return
        idx = self._current_sensor_index()
        if idx < 0:
            return
        self._settings.update_sensor(idx, name=name)
        self._sensor_list.currentItem().setText(name)

    def _on_model_changed(self, model_name):
        """Update the sensor model and adjust max distance to match model range."""
        if self._loading:
            return
        idx = self._current_sensor_index()
        if idx < 0:
            return
        max_range = LIDAR_MODELS.get(model_name, {}).get('max_range_mm', 10000.0)
        self._settings.update_sensor(idx, model=model_name, max_distance_mm=max_range)
        self.settings_changed.emit({})

    def _on_add_sensor(self):
        model = self._model_combo.currentText()
        max_range = LIDAR_MODELS.get(model, {}).get('max_range_mm', 10000.0)
        idx = self._settings.add_sensor()
        self._settings.update_sensor(idx, model=model, max_distance_mm=max_range)
        self._load_sensor_list()
        self._sensor_list.setCurrentRow(idx)
        self.sensor_added.emit(idx)

    def _on_remove_sensor(self):
        idx = self._current_sensor_index()
        if idx < 0:
            return
        if self._settings.remove_sensor(idx):
            self.sensor_removed.emit(idx)
            self._load_sensor_list()

    def _on_connect(self):
        idx = self._current_sensor_index()
        if idx < 0:
            return
        ip = self._ip_edit.text().strip()
        port = self._port_spin.value()
        self._settings.update_sensor(idx, lidar_ip=ip, lidar_port=port)
        self.connect_requested.emit(idx, ip, port)
        self._connect_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_label.setText("Connecting...")
        self._status_label.setStyleSheet("color: #fa0;")

    def _on_disconnect(self):
        idx = self._current_sensor_index()
        if idx < 0:
            return
        self.disconnect_requested.emit(idx)
        self._connect_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("Disconnected")
        self._status_label.setStyleSheet("color: #888;")

    def _on_learn(self):
        idx = self._current_sensor_index()
        if idx < 0:
            return
        self.learn_requested.emit(idx)

    def _on_reset(self):
        idx = self._current_sensor_index()
        if idx < 0:
            return
        self.reset_requested.emit(idx)

    def set_connection_status(self, status, sensor_index=0):
        if sensor_index != self._current_sensor_index():
            return
        self._status_label.setText(status.capitalize())
        if status in ("connected", "reconnected"):
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

    def set_bg_progress(self, progress, sensor_index=0):
        if sensor_index == self._current_sensor_index():
            self._bg_progress.setValue(int(progress * 100))
