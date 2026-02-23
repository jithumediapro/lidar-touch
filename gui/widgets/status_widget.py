from PyQt5.QtCore import pyqtSlot, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QLabel, QFormLayout
from collections import deque
import time


class StatusWidget(QWidget):
    """Status display: FPS, touch count, latency."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame_times = deque(maxlen=60)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("Status")
        form = QFormLayout()

        self._fps_label = QLabel("0")
        form.addRow("FPS:", self._fps_label)

        self._scan_count_label = QLabel("0")
        form.addRow("Frame:", self._scan_count_label)

        self._touch_count_label = QLabel("0")
        form.addRow("Active Touches:", self._touch_count_label)

        self._latency_label = QLabel("0 ms")
        form.addRow("Processing:", self._latency_label)

        self._bg_status_label = QLabel("Not learned")
        form.addRow("Background:", self._bg_status_label)

        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()

    def update_from_frame(self, frame):
        """Update status from a FrameResult."""
        now = time.monotonic()
        self._frame_times.append(now)

        # Compute FPS from recent frame timestamps
        if len(self._frame_times) >= 2:
            dt = self._frame_times[-1] - self._frame_times[0]
            if dt > 0:
                fps = (len(self._frame_times) - 1) / dt
                self._fps_label.setText(f"{fps:.1f}")

        self._scan_count_label.setText(str(frame.frame_seq))
        self._touch_count_label.setText(str(len(frame.touches)))
        self._latency_label.setText(f"{frame.processing_time_ms:.1f} ms")

        if frame.bg_is_learned:
            self._bg_status_label.setText("Learned")
            self._bg_status_label.setStyleSheet("color: #0f0;")
        elif frame.bg_learning_progress > 0 and frame.bg_learning_progress < 1.0:
            pct = frame.bg_learning_progress * 100
            self._bg_status_label.setText(f"Learning ({pct:.0f}%)")
            self._bg_status_label.setStyleSheet("color: #fa0;")
        else:
            self._bg_status_label.setText("Not learned")
            self._bg_status_label.setStyleSheet("color: #888;")
