from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel,
    QLineEdit, QSpinBox, QCheckBox, QFormLayout,
    QPushButton, QHBoxLayout, QListWidget, QListWidgetItem,
)


class OutputsWidget(QWidget):
    """Outputs tab: TUIO output configuration."""

    settings_changed = pyqtSignal(dict)
    tuio_target_changed = pyqtSignal(str, int)
    tuio_enabled_changed = pyqtSignal(bool)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # TUIO Output group
        tuio_group = QGroupBox("TUIO 1.1 Output")
        tuio_form = QFormLayout()

        self._tuio_enabled = QCheckBox("Enable TUIO Output")
        self._tuio_enabled.stateChanged.connect(self._on_tuio_enabled)
        tuio_form.addRow(self._tuio_enabled)

        self._tuio_host = QLineEdit()
        self._tuio_host.setPlaceholderText("127.0.0.1")
        tuio_form.addRow("Host:", self._tuio_host)

        self._tuio_port = QSpinBox()
        self._tuio_port.setRange(1, 65535)
        self._tuio_port.setValue(3333)
        tuio_form.addRow("Port:", self._tuio_port)

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._on_apply)
        tuio_form.addRow(self._apply_btn)

        self._tuio_status = QLabel("Ready")
        self._tuio_status.setStyleSheet("color: #888;")
        tuio_form.addRow("Status:", self._tuio_status)

        tuio_group.setLayout(tuio_form)
        layout.addWidget(tuio_group)

        # Protocol info
        info_group = QGroupBox("Protocol Info")
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(
            "TUIO 1.1 / OSC Protocol\n"
            "Profile: /tuio/2Dcur\n"
            "Source: HokuyoTouch\n\n"
            "Compatible with:\n"
            "- TUIO clients\n"
            "- reacTIVision\n"
            "- CCV / Community Core Vision\n"
            "- Any TUIO 1.1 receiver"
        ))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        layout.addStretch()

    def _load_settings(self):
        snap = self._settings.get_snapshot()
        self._tuio_enabled.setChecked(snap['tuio_enabled'])
        self._tuio_host.setText(snap['tuio_host'])
        self._tuio_port.setValue(snap['tuio_port'])

    def _on_tuio_enabled(self, state):
        enabled = self._tuio_enabled.isChecked()
        self.tuio_enabled_changed.emit(enabled)
        self.settings_changed.emit({'tuio_enabled': enabled})
        self._tuio_status.setText("Enabled" if enabled else "Disabled")
        self._tuio_status.setStyleSheet(
            "color: #0f0;" if enabled else "color: #888;"
        )

    def _on_apply(self):
        host = self._tuio_host.text().strip()
        port = self._tuio_port.value()
        self.tuio_target_changed.emit(host, port)
        self.settings_changed.emit({
            'tuio_host': host,
            'tuio_port': port,
        })
        self._tuio_status.setText(f"Sending to {host}:{port}")
        self._tuio_status.setStyleSheet("color: #0f0;")
