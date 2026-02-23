from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QSpinBox, QCheckBox, QFormLayout,
    QPushButton, QListWidget, QComboBox,
)


class OutputsWidget(QWidget):
    """Outputs tab: multi-output TUIO configuration with linked screen."""

    settings_changed = pyqtSignal(dict)
    tuio_target_changed = pyqtSignal(int, str, int)  # output_index, host, port
    tuio_enabled_changed = pyqtSignal(int, bool)     # output_index, enabled
    output_added = pyqtSignal(int)                    # new output_index
    output_removed = pyqtSignal(int)                  # removed output_index

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._loading = False
        self._setup_ui()
        self._load_output_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Output List Group ---
        list_group = QGroupBox("Outputs")
        list_layout = QVBoxLayout()

        self._output_list = QListWidget()
        self._output_list.setMaximumHeight(80)
        self._output_list.currentRowChanged.connect(self._on_output_selected)
        list_layout.addWidget(self._output_list)

        btn_layout = QHBoxLayout()
        self._add_output_btn = QPushButton("Add Output")
        self._add_output_btn.clicked.connect(self._on_add_output)
        btn_layout.addWidget(self._add_output_btn)

        self._remove_output_btn = QPushButton("Remove Output")
        self._remove_output_btn.clicked.connect(self._on_remove_output)
        btn_layout.addWidget(self._remove_output_btn)
        list_layout.addLayout(btn_layout)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # --- Name ---
        name_layout = QFormLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Output name")
        self._name_edit.textChanged.connect(self._on_name_changed)
        name_layout.addRow("Name:", self._name_edit)
        layout.addLayout(name_layout)

        # --- TUIO Output group ---
        tuio_group = QGroupBox("TUIO 1.1 Output")
        tuio_form = QFormLayout()

        self._tuio_enabled = QCheckBox("Enable TUIO Output")
        self._tuio_enabled.stateChanged.connect(self._on_tuio_enabled)
        tuio_form.addRow(self._tuio_enabled)

        self._screen_combo = QComboBox()
        self._screen_combo.currentIndexChanged.connect(self._on_screen_link_changed)
        tuio_form.addRow("Linked Screen:", self._screen_combo)

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
            "Profile: /tuio/2Dcur\n\n"
            "Compatible with:\n"
            "- TUIO clients\n"
            "- reacTIVision\n"
            "- CCV / Community Core Vision\n"
            "- Any TUIO 1.1 receiver"
        ))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        layout.addStretch()

    def _current_output_index(self):
        row = self._output_list.currentRow()
        return row if row >= 0 else -1

    def _load_output_list(self):
        """Reload the output list widget from settings."""
        self._output_list.blockSignals(True)
        current = self._output_list.currentRow()
        self._output_list.clear()
        snap = self._settings.get_snapshot()
        for output in snap.get('outputs', []):
            self._output_list.addItem(output.get('name', 'Output'))
        if 0 <= current < self._output_list.count():
            self._output_list.setCurrentRow(current)
        elif self._output_list.count() > 0:
            self._output_list.setCurrentRow(0)
        self._output_list.blockSignals(False)
        self._remove_output_btn.setEnabled(self._output_list.count() > 0)
        self._load_settings()

    def _on_output_selected(self, row):
        if row >= 0:
            self._load_settings()

    def refresh_screen_list(self):
        """Refresh the linked screen combo box from current settings."""
        self._screen_combo.blockSignals(True)
        current_screen = self._screen_combo.currentIndex()
        self._screen_combo.clear()
        snap = self._settings.get_snapshot()
        for i, screen in enumerate(snap.get('screens', [])):
            self._screen_combo.addItem(screen.get('name', f'Screen {i+1}'))
        # Restore selection
        idx = self._current_output_index()
        output = self._settings.get_output(idx)
        if output:
            si = output.get('screen_index', 0)
            if 0 <= si < self._screen_combo.count():
                self._screen_combo.setCurrentIndex(si)
        self._screen_combo.blockSignals(False)

    def _load_settings(self):
        """Load settings for the currently selected output."""
        self._loading = True
        idx = self._current_output_index()
        output = self._settings.get_output(idx)
        has_output = output is not None
        for widget in (self._name_edit, self._tuio_enabled, self._screen_combo,
                       self._tuio_host, self._tuio_port, self._apply_btn):
            widget.setEnabled(has_output)
        if not has_output:
            self._tuio_status.setText("No outputs")
            self._tuio_status.setStyleSheet("color: #888;")
            self._loading = False
            return

        self._name_edit.setText(output.get('name', 'Output'))
        self._tuio_enabled.setChecked(output.get('tuio_enabled', True))
        self._tuio_host.setText(output.get('tuio_host', '127.0.0.1'))
        self._tuio_port.setValue(output.get('tuio_port', 3333))

        # Refresh screen combo
        self.refresh_screen_list()

        enabled = output.get('tuio_enabled', True)
        self._tuio_status.setText("Enabled" if enabled else "Disabled")
        self._tuio_status.setStyleSheet("color: #0f0;" if enabled else "color: #888;")
        self._loading = False

    def _on_name_changed(self, name):
        if self._loading:
            return
        idx = self._current_output_index()
        if idx < 0:
            return
        self._settings.update_output(idx, name=name)
        self._output_list.currentItem().setText(name)

    def _on_tuio_enabled(self, state):
        if self._loading:
            return
        idx = self._current_output_index()
        if idx < 0:
            return
        enabled = self._tuio_enabled.isChecked()
        self._settings.update_output(idx, tuio_enabled=enabled)
        self.tuio_enabled_changed.emit(idx, enabled)
        self.settings_changed.emit({})
        self._tuio_status.setText("Enabled" if enabled else "Disabled")
        self._tuio_status.setStyleSheet("color: #0f0;" if enabled else "color: #888;")

    def _on_screen_link_changed(self, screen_index):
        if self._loading:
            return
        idx = self._current_output_index()
        if idx < 0:
            return
        if screen_index >= 0:
            self._settings.update_output(idx, screen_index=screen_index)
            self.settings_changed.emit({})

    def _on_apply(self):
        idx = self._current_output_index()
        if idx < 0:
            return
        host = self._tuio_host.text().strip()
        port = self._tuio_port.value()
        self._settings.update_output(idx, tuio_host=host, tuio_port=port)
        self.tuio_target_changed.emit(idx, host, port)
        self.settings_changed.emit({})
        self._tuio_status.setText(f"Sending to {host}:{port}")
        self._tuio_status.setStyleSheet("color: #0f0;")

    def _on_add_output(self):
        idx = self._settings.add_output()
        self._load_output_list()
        self._output_list.setCurrentRow(idx)
        self.output_added.emit(idx)

    def _on_remove_output(self):
        idx = self._current_output_index()
        if idx < 0:
            return
        if self._settings.remove_output(idx):
            self.output_removed.emit(idx)
            self._load_output_list()
