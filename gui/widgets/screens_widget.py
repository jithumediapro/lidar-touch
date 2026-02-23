from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QDoubleSpinBox, QFormLayout, QListWidget,
    QPushButton,
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
        layout = QVBoxLayout(self)

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
        for widget in (self._name_edit, self._width, self._height,
                       self._offset_x, self._offset_y):
            widget.setEnabled(has_screen)
        if not has_screen:
            self._loading = False
            return

        self._name_edit.setText(screen.get('name', 'Screen'))
        self._width.setValue(screen.get('screen_width_mm', 1920.0))
        self._height.setValue(screen.get('screen_height_mm', 1080.0))
        self._offset_x.setValue(screen.get('screen_offset_x', 0.0))
        self._offset_y.setValue(screen.get('screen_offset_y', 0.0))
        self._loading = False

    def _emit_settings(self):
        if self._loading:
            return
        idx = self._current_screen_index()
        if idx < 0:
            return
        changes = {
            'name': self._name_edit.text(),
            'screen_width_mm': self._width.value(),
            'screen_height_mm': self._height.value(),
            'screen_offset_x': self._offset_x.value(),
            'screen_offset_y': self._offset_y.value(),
        }
        self._settings.update_screen(idx, **changes)
        # Update list item text in real-time
        item = self._screen_list.currentItem()
        if item and item.text() != self._name_edit.text():
            item.setText(self._name_edit.text())
        self.settings_changed.emit({})

    def _on_add_screen(self):
        idx = self._settings.add_screen()
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

    def get_screen_names(self):
        """Return list of screen names for use by outputs widget."""
        snap = self._settings.get_snapshot()
        return [s.get('name', f'Screen {i+1}') for i, s in enumerate(snap.get('screens', []))]
