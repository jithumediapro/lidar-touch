from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QDoubleSpinBox, QFormLayout, QListWidget,
    QPushButton, QCheckBox, QScrollArea,
)


class ScreensWidget(QWidget):
    """Screens tab: multi-screen list with per-screen size/offset configuration."""

    settings_changed = pyqtSignal(dict)
    screen_added = pyqtSignal(int)    # new screen_index
    screen_removed = pyqtSignal(int)  # removed screen_index

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._loading = False
        self._setup_ui()
        self._load_screen_list()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll)

        # --- Screen List Group ---
        list_group = QGroupBox("Screens")
        list_layout = QVBoxLayout()

        self._screen_list = QListWidget()
        self._screen_list.setMaximumHeight(80)
        self._screen_list.currentRowChanged.connect(self._on_screen_selected)
        list_layout.addWidget(self._screen_list)

        btn_layout = QHBoxLayout()
        self._add_screen_btn = QPushButton("Add Screen")
        self._add_screen_btn.clicked.connect(self._on_add_screen)
        btn_layout.addWidget(self._add_screen_btn)

        self._remove_screen_btn = QPushButton("Remove Screen")
        self._remove_screen_btn.clicked.connect(self._on_remove_screen)
        btn_layout.addWidget(self._remove_screen_btn)
        list_layout.addLayout(btn_layout)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # --- Screen Config Group ---
        group = QGroupBox("Screen Configuration")
        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self._emit_settings)
        form.addRow("Screen Name:", self._name_edit)

        self._width = QDoubleSpinBox()
        self._width.setRange(1, 100000)
        self._width.setSuffix(" mm")
        self._width.setSingleStep(10)
        self._width.valueChanged.connect(self._emit_settings)
        form.addRow("Width:", self._width)

        self._height = QDoubleSpinBox()
        self._height.setRange(1, 100000)
        self._height.setSuffix(" mm")
        self._height.setSingleStep(10)
        self._height.valueChanged.connect(self._emit_settings)
        form.addRow("Height:", self._height)

        self._offset_x = QDoubleSpinBox()
        self._offset_x.setRange(-50000, 50000)
        self._offset_x.setSuffix(" mm")
        self._offset_x.valueChanged.connect(self._emit_settings)
        form.addRow("Offset X:", self._offset_x)

        self._offset_y = QDoubleSpinBox()
        self._offset_y.setRange(-50000, 50000)
        self._offset_y.setSuffix(" mm")
        self._offset_y.valueChanged.connect(self._emit_settings)
        form.addRow("Offset Y:", self._offset_y)

        group.setLayout(form)
        layout.addWidget(group)

        # Set screen config defaults (template for next Add)
        self._width.setValue(1920.0)
        self._height.setValue(1080.0)
        self._offset_x.setValue(0.0)
        self._offset_y.setValue(0.0)

        # --- Active Area Group ---
        aa_group = QGroupBox("Active Area")
        aa_form = QFormLayout()

        self._aa_enabled = QCheckBox("Custom Active Area")
        self._aa_enabled.toggled.connect(self._on_aa_toggled)
        aa_form.addRow(self._aa_enabled)

        self._aa_width = QDoubleSpinBox()
        self._aa_width.setRange(1, 100000)
        self._aa_width.setSuffix(" mm")
        self._aa_width.setSingleStep(10)
        self._aa_width.valueChanged.connect(self._emit_settings)
        aa_form.addRow("Width:", self._aa_width)

        self._aa_height = QDoubleSpinBox()
        self._aa_height.setRange(1, 100000)
        self._aa_height.setSuffix(" mm")
        self._aa_height.setSingleStep(10)
        self._aa_height.valueChanged.connect(self._emit_settings)
        aa_form.addRow("Height:", self._aa_height)

        self._aa_offset_x = QDoubleSpinBox()
        self._aa_offset_x.setRange(-50000, 50000)
        self._aa_offset_x.setSuffix(" mm")
        self._aa_offset_x.valueChanged.connect(self._emit_settings)
        aa_form.addRow("Offset X:", self._aa_offset_x)

        self._aa_offset_y = QDoubleSpinBox()
        self._aa_offset_y.setRange(-50000, 50000)
        self._aa_offset_y.setSuffix(" mm")
        self._aa_offset_y.valueChanged.connect(self._emit_settings)
        aa_form.addRow("Offset Y:", self._aa_offset_y)

        aa_group.setLayout(aa_form)
        layout.addWidget(aa_group)

        # --- Exclude Zones Group ---
        ez_group = QGroupBox("Exclude Zones")
        ez_layout = QVBoxLayout()

        self._ez_list = QListWidget()
        self._ez_list.setMaximumHeight(80)
        self._ez_list.currentRowChanged.connect(self._on_ez_selected)
        ez_layout.addWidget(self._ez_list)

        ez_btn_layout = QHBoxLayout()
        self._add_ez_btn = QPushButton("Add Zone")
        self._add_ez_btn.clicked.connect(self._on_add_ez)
        ez_btn_layout.addWidget(self._add_ez_btn)
        self._remove_ez_btn = QPushButton("Remove Zone")
        self._remove_ez_btn.clicked.connect(self._on_remove_ez)
        ez_btn_layout.addWidget(self._remove_ez_btn)
        ez_layout.addLayout(ez_btn_layout)

        ez_form = QFormLayout()
        self._ez_x = QDoubleSpinBox()
        self._ez_x.setRange(-50000, 50000)
        self._ez_x.setSuffix(" mm")
        self._ez_x.valueChanged.connect(self._on_ez_spinbox_changed)
        ez_form.addRow("X:", self._ez_x)

        self._ez_y = QDoubleSpinBox()
        self._ez_y.setRange(-50000, 50000)
        self._ez_y.setSuffix(" mm")
        self._ez_y.valueChanged.connect(self._on_ez_spinbox_changed)
        ez_form.addRow("Y:", self._ez_y)

        self._ez_w = QDoubleSpinBox()
        self._ez_w.setRange(1, 100000)
        self._ez_w.setSuffix(" mm")
        self._ez_w.setSingleStep(10)
        self._ez_w.valueChanged.connect(self._on_ez_spinbox_changed)
        ez_form.addRow("Width:", self._ez_w)

        self._ez_h = QDoubleSpinBox()
        self._ez_h.setRange(1, 100000)
        self._ez_h.setSuffix(" mm")
        self._ez_h.setSingleStep(10)
        self._ez_h.valueChanged.connect(self._on_ez_spinbox_changed)
        ez_form.addRow("Height:", self._ez_h)

        ez_layout.addLayout(ez_form)
        ez_group.setLayout(ez_layout)
        layout.addWidget(ez_group)

        # Set default values for exclude zone spinboxes (template for next Add)
        self._ez_x.setValue(0.0)
        self._ez_y.setValue(0.0)
        self._ez_w.setValue(100.0)
        self._ez_h.setValue(100.0)
        self._remove_ez_btn.setEnabled(False)

        # Info
        info_group = QGroupBox("Info")
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(
            "Screen dimensions define the coordinate space\n"
            "for normalizing touch positions to [0, 1] range.\n\n"
            "Offsets position the screen relative to the sensor."
        ))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        layout.addStretch()

    def _current_screen_index(self):
        row = self._screen_list.currentRow()
        return row if row >= 0 else -1

    def _load_screen_list(self):
        """Reload the screen list widget from settings."""
        self._screen_list.blockSignals(True)
        current = self._screen_list.currentRow()
        self._screen_list.clear()
        snap = self._settings.get_snapshot()
        for screen in snap.get('screens', []):
            self._screen_list.addItem(screen.get('name', 'Screen'))
        if 0 <= current < self._screen_list.count():
            self._screen_list.setCurrentRow(current)
        elif self._screen_list.count() > 0:
            self._screen_list.setCurrentRow(0)
        self._screen_list.blockSignals(False)
        self._remove_screen_btn.setEnabled(self._screen_list.count() > 0)
        self._load_settings()

    def _on_screen_selected(self, row):
        if row >= 0:
            self._load_settings()

    def _load_settings(self):
        """Load settings for the currently selected screen."""
        self._loading = True
        idx = self._current_screen_index()
        screen = self._settings.get_screen(idx)
        has_screen = screen is not None

        if has_screen:
            self._name_edit.setText(screen.get('name', 'Screen'))
            self._width.setValue(screen.get('screen_width_mm', 1920.0))
            self._height.setValue(screen.get('screen_height_mm', 1080.0))
            self._offset_x.setValue(screen.get('screen_offset_x', 0.0))
            self._offset_y.setValue(screen.get('screen_offset_y', 0.0))

            aa_enabled = screen.get('active_area_enabled', False)
            self._aa_enabled.setChecked(aa_enabled)
            self._aa_width.setValue(screen.get('active_area_width_mm', screen.get('screen_width_mm', 1920.0)))
            self._aa_height.setValue(screen.get('active_area_height_mm', screen.get('screen_height_mm', 1080.0)))
            self._aa_offset_x.setValue(screen.get('active_area_offset_x', screen.get('screen_offset_x', 0.0)))
            self._aa_offset_y.setValue(screen.get('active_area_offset_y', screen.get('screen_offset_y', 0.0)))
            for w in (self._aa_width, self._aa_height, self._aa_offset_x, self._aa_offset_y):
                w.setEnabled(aa_enabled)

            # Populate exclude zones list
            self._ez_list.blockSignals(True)
            self._ez_list.clear()
            zones = screen.get('exclude_zones', [])
            for i in range(len(zones)):
                self._ez_list.addItem(f"Zone {i + 1}")
            self._ez_list.blockSignals(False)
            self._remove_ez_btn.setEnabled(len(zones) > 0)
            self._add_ez_btn.setEnabled(True)
        else:
            # No screen selected — clear exclude zone list, keep fields as template
            self._ez_list.blockSignals(True)
            self._ez_list.clear()
            self._ez_list.blockSignals(False)
            self._remove_ez_btn.setEnabled(False)
            self._add_ez_btn.setEnabled(False)

        self._loading = False

    def _on_aa_toggled(self, checked):
        """Handle custom active area checkbox toggle."""
        for w in (self._aa_width, self._aa_height, self._aa_offset_x, self._aa_offset_y):
            w.setEnabled(checked)
        if not self._loading and checked:
            # Pre-fill with screen values when first enabling
            idx = self._current_screen_index()
            screen = self._settings.get_screen(idx)
            if screen and not screen.get('active_area_enabled', False):
                self._loading = True
                self._aa_width.setValue(self._width.value())
                self._aa_height.setValue(self._height.value())
                self._aa_offset_x.setValue(self._offset_x.value())
                self._aa_offset_y.setValue(self._offset_y.value())
                self._loading = False
        self._emit_settings()

    def _emit_settings(self):
        if self._loading:
            return
        idx = self._current_screen_index()
        if idx < 0:
            return
        # Gather current exclude zones from settings (they're updated in-place by spinbox changes)
        screen = self._settings.get_screen(idx)
        current_zones = screen.get('exclude_zones', []) if screen else []
        changes = {
            'name': self._name_edit.text(),
            'screen_width_mm': self._width.value(),
            'screen_height_mm': self._height.value(),
            'screen_offset_x': self._offset_x.value(),
            'screen_offset_y': self._offset_y.value(),
            'active_area_enabled': self._aa_enabled.isChecked(),
            'active_area_width_mm': self._aa_width.value(),
            'active_area_height_mm': self._aa_height.value(),
            'active_area_offset_x': self._aa_offset_x.value(),
            'active_area_offset_y': self._aa_offset_y.value(),
            'exclude_zones': current_zones,
        }
        self._settings.update_screen(idx, **changes)
        # Update list item text in real-time
        item = self._screen_list.currentItem()
        if item and item.text() != self._name_edit.text():
            item.setText(self._name_edit.text())
        self.settings_changed.emit({})

    def _on_add_screen(self):
        idx = self._settings.add_screen()
        # Apply current spinbox values (template) to the new screen
        self._settings.update_screen(idx,
            name=self._name_edit.text() or f'Screen {idx + 1}',
            screen_width_mm=self._width.value(),
            screen_height_mm=self._height.value(),
            screen_offset_x=self._offset_x.value(),
            screen_offset_y=self._offset_y.value(),
            active_area_enabled=self._aa_enabled.isChecked(),
            active_area_width_mm=self._aa_width.value(),
            active_area_height_mm=self._aa_height.value(),
            active_area_offset_x=self._aa_offset_x.value(),
            active_area_offset_y=self._aa_offset_y.value(),
        )
        self._load_screen_list()
        self._screen_list.setCurrentRow(idx)
        self.screen_added.emit(idx)

    def _on_remove_screen(self):
        idx = self._current_screen_index()
        if idx < 0:
            return
        if self._settings.remove_screen(idx):
            self.screen_removed.emit(idx)
            self._load_screen_list()

    def _on_ez_selected(self, row):
        """Load the selected exclude zone's values into spinboxes."""
        idx = self._current_screen_index()
        screen = self._settings.get_screen(idx)
        if screen is None:
            return
        zones = screen.get('exclude_zones', [])
        has_selection = 0 <= row < len(zones)
        self._remove_ez_btn.setEnabled(has_selection)
        if has_selection:
            self._loading = True
            zone = zones[row]
            self._ez_x.setValue(zone.get('x', 0.0))
            self._ez_y.setValue(zone.get('y', 0.0))
            self._ez_w.setValue(zone.get('width', 100.0))
            self._ez_h.setValue(zone.get('height', 100.0))
            self._loading = False

    def _on_add_ez(self):
        """Add a new exclude zone using current spinbox values as template."""
        idx = self._current_screen_index()
        screen = self._settings.get_screen(idx)
        if screen is None:
            return
        zones = screen.get('exclude_zones', [])
        zones.append({
            'x': self._ez_x.value(),
            'y': self._ez_y.value(),
            'width': self._ez_w.value(),
            'height': self._ez_h.value(),
        })
        self._settings.update_screen(idx, exclude_zones=zones)
        # Refresh list
        self._ez_list.blockSignals(True)
        self._ez_list.addItem(f"Zone {len(zones)}")
        self._ez_list.blockSignals(False)
        self._ez_list.setCurrentRow(len(zones) - 1)
        self._remove_ez_btn.setEnabled(True)
        self.settings_changed.emit({})

    def _on_remove_ez(self):
        """Remove the currently selected exclude zone."""
        ez_row = self._ez_list.currentRow()
        idx = self._current_screen_index()
        screen = self._settings.get_screen(idx)
        if screen is None or ez_row < 0:
            return
        zones = screen.get('exclude_zones', [])
        if ez_row < len(zones):
            zones.pop(ez_row)
            self._settings.update_screen(idx, exclude_zones=zones)
            # Refresh list
            self._ez_list.blockSignals(True)
            self._ez_list.clear()
            for i in range(len(zones)):
                self._ez_list.addItem(f"Zone {i + 1}")
            self._ez_list.blockSignals(False)
            if zones:
                new_row = min(ez_row, len(zones) - 1)
                self._ez_list.setCurrentRow(new_row)
            else:
                self._remove_ez_btn.setEnabled(False)
            self.settings_changed.emit({})

    def _on_ez_spinbox_changed(self):
        """Update the selected exclude zone when spinbox values change."""
        if self._loading:
            return
        idx = self._current_screen_index()
        ez_row = self._ez_list.currentRow()
        screen = self._settings.get_screen(idx)
        if screen is None or ez_row < 0:
            return
        zones = screen.get('exclude_zones', [])
        if ez_row >= len(zones):
            return
        zones[ez_row] = {
            'x': self._ez_x.value(),
            'y': self._ez_y.value(),
            'width': self._ez_w.value(),
            'height': self._ez_h.value(),
        }
        self._settings.update_screen(idx, exclude_zones=zones)
        self.settings_changed.emit({})

    def get_screen_names(self):
        """Return list of screen names for use by outputs widget."""
        snap = self._settings.get_snapshot()
        return [s.get('name', f'Screen {i+1}') for i, s in enumerate(snap.get('screens', []))]
