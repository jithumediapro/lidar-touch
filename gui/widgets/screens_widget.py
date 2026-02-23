from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel,
    QLineEdit, QDoubleSpinBox, QFormLayout,
)


class ScreensWidget(QWidget):
    """Screens tab: screen size/offset configuration."""

    settings_changed = pyqtSignal(dict)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Screen config group
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

    def _load_settings(self):
        snap = self._settings.get_snapshot()
        self._name_edit.setText(snap['screen_name'])
        self._width.setValue(snap['screen_width_mm'])
        self._height.setValue(snap['screen_height_mm'])
        self._offset_x.setValue(snap['screen_offset_x'])
        self._offset_y.setValue(snap['screen_offset_y'])

    def _emit_settings(self):
        changes = {
            'screen_name': self._name_edit.text(),
            'screen_width_mm': self._width.value(),
            'screen_height_mm': self._height.value(),
            'screen_offset_x': self._offset_x.value(),
            'screen_offset_y': self._offset_y.value(),
        }
        self.settings_changed.emit(changes)
