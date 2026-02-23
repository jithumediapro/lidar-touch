import math
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSlot
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QPolygonF
from PyQt5.QtWidgets import QWidget


# Cluster colors for visualization
CLUSTER_COLORS = [
    QColor(255, 100, 100),
    QColor(100, 255, 100),
    QColor(100, 100, 255),
    QColor(255, 255, 100),
    QColor(255, 100, 255),
    QColor(100, 255, 255),
    QColor(255, 180, 100),
    QColor(180, 100, 255),
]


class LidarView(QWidget):
    """QPainter-based LiDAR scan visualization widget."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._frame = None
        self._dirty = False
        self._show_screen_area = True

        # Canvas pan state
        self._pan_offset_x = 0.0
        self._pan_offset_y = 0.0
        self._panning = False
        self._pan_start = None

        self.setMinimumSize(400, 400)
        self.setStyleSheet("background-color: #1a1a2e;")

        # Repaint throttle timer (~30 FPS)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._timer.start(33)

    @pyqtSlot(object)
    def update_frame(self, frame):
        """Receive processed frame data from pipeline."""
        self._frame = frame
        self._dirty = True

    def _on_timer(self):
        if self._dirty:
            self._dirty = False
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_offset_x += delta.x()
            self._pan_offset_y += delta.y()
            self._pan_start = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pan_offset_x = 0.0
            self._pan_offset_y = 0.0
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Dark background
        painter.fillRect(0, 0, w, h, QColor(26, 26, 46))

        if self._frame is None:
            painter.setPen(QColor(100, 100, 100))
            painter.setFont(QFont("Arial", 14))
            painter.drawText(self.rect(), Qt.AlignCenter, "Waiting for scan data...")
            painter.end()
            return

        frame = self._frame
        # Use polar view: sensor is the origin, scan fans upward
        snap = self._settings.get_snapshot()
        max_dist = snap['max_distance_mm']
        min_dist = snap['min_distance_mm']
        scale = min(w * 0.45, h * 0.85) / max_dist

        # Base origin at bottom-center + pan offset
        cx = w / 2.0 + self._pan_offset_x
        cy = h - 30.0 + self._pan_offset_y

        # Draw distance rings
        self._draw_distance_rings(painter, cx, cy, scale, max_dist)

        # Draw angle grid lines
        self._draw_angle_grid(painter, cx, cy, scale, max_dist)

        # Draw detection zone overlay
        self._draw_detection_zone(painter, cx, cy, scale, snap)

        # Draw screen area overlay
        if self._show_screen_area:
            self._draw_screen_area(painter, cx, cy, scale, snap)
            self._draw_active_area(painter, cx, cy, scale, snap)

        # Draw scan points
        self._draw_scan_points(painter, cx, cy, scale, frame)

        # Draw foreground points
        self._draw_foreground_points(painter, cx, cy, scale, frame)

        # Draw touch markers
        self._draw_touch_markers(painter, cx, cy, scale, frame)

        # Draw sensor icon
        self._draw_sensor(painter, cx, cy, scale, snap)

        # Draw info overlay
        self._draw_info(painter, frame)

        painter.end()

    def _draw_distance_rings(self, painter, cx, cy, scale, max_dist):
        pen = QPen(QColor(40, 40, 80), 1, Qt.DotLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        font = QFont("Arial", 8)
        painter.setFont(font)

        ring_step = 200.0  # mm between rings
        dist = ring_step
        while dist <= max_dist:
            r = dist * scale
            painter.drawArc(
                QRectF(cx - r, cy - r, 2 * r, 2 * r),
                0 * 16, 180 * 16,  # Upper semicircle
            )
            # Label
            painter.setPen(QColor(60, 60, 100))
            painter.drawText(QPointF(cx + r + 2, cy - 2), f"{int(dist)}mm")
            painter.setPen(pen)
            dist += ring_step

    def _draw_angle_grid(self, painter, cx, cy, scale, max_dist):
        pen = QPen(QColor(40, 40, 70), 1, Qt.DotLine)
        painter.setPen(pen)

        r = max_dist * scale
        for angle_deg in range(-90, 91, 45):
            angle_rad = math.radians(angle_deg)
            # In our view: 0 deg = straight up, angles go CW
            # Convert: screen_angle = -angle + 90 deg (since 0 is up)
            sx = cx + r * math.cos(math.radians(90 - angle_deg))
            sy = cy - r * math.sin(math.radians(90 - angle_deg))
            painter.drawLine(QPointF(cx, cy), QPointF(sx, sy))

    def _build_detection_zone_path(self, cx, cy, scale, snap):
        """Build QPainterPath for the detection zone."""
        min_angle = snap['min_angle_deg']
        max_angle = snap['max_angle_deg']
        min_dist = snap['min_distance_mm']
        max_dist = snap['max_distance_mm']

        path = QPainterPath()
        r_min = min_dist * scale
        r_max = max_dist * scale

        start_angle = 90 - max_angle  # Qt angles: 0=right, CCW
        span_angle = max_angle - min_angle

        outer_rect = QRectF(cx - r_max, cy - r_max, 2 * r_max, 2 * r_max)
        inner_rect = QRectF(cx - r_min, cy - r_min, 2 * r_min, 2 * r_min)

        path.arcMoveTo(outer_rect, start_angle)
        path.arcTo(outer_rect, start_angle, span_angle)

        inner_end_angle = start_angle + span_angle
        ix = cx + r_min * math.cos(math.radians(inner_end_angle))
        iy = cy - r_min * math.sin(math.radians(inner_end_angle))
        path.lineTo(QPointF(ix, iy))

        path.arcTo(inner_rect, inner_end_angle, -span_angle)
        path.closeSubpath()
        return path

    def _draw_detection_zone(self, painter, cx, cy, scale, snap):
        path = self._build_detection_zone_path(cx, cy, scale, snap)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(30, 60, 120, 40)))
        painter.drawPath(path)

        # Zone boundary
        painter.setPen(QPen(QColor(60, 120, 200, 100), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def _angle_to_screen(self, angle_rad, dist, cx, cy, scale):
        """Convert polar (angle, distance) to screen coordinates."""
        angle_deg = math.degrees(angle_rad)
        screen_angle_deg = 90 - angle_deg
        screen_angle_rad = math.radians(screen_angle_deg)
        r = dist * scale
        sx = cx + r * math.cos(screen_angle_rad)
        sy = cy - r * math.sin(screen_angle_rad)
        return sx, sy

    def _draw_scan_points(self, painter, cx, cy, scale, frame):
        """Draw raw filtered scan points as dim blue dots."""
        angles = frame.raw_angles
        distances = frame.raw_distances
        mask = frame.filtered_mask

        if len(angles) == 0:
            return

        pen = QPen(QColor(60, 80, 140), 2)
        painter.setPen(pen)

        # Downsample for performance (draw every Nth point)
        step = max(1, len(angles) // 400)
        for i in range(0, len(angles), step):
            if mask[i] and distances[i] > 0:
                sx, sy = self._angle_to_screen(
                    angles[i], distances[i], cx, cy, scale
                )
                painter.drawPoint(QPointF(sx, sy))

    def _draw_foreground_points(self, painter, cx, cy, scale, frame):
        """Draw foreground (detected) points as bright colored dots."""
        fg_xy = frame.foreground_points_xy
        labels = frame.cluster_labels

        if len(fg_xy) == 0:
            return

        for i in range(len(fg_xy)):
            x_mm, y_mm = fg_xy[i]
            # Convert Cartesian back to polar for screen display
            dist = math.sqrt(x_mm * x_mm + y_mm * y_mm)
            angle = math.atan2(y_mm, x_mm)
            sx, sy = self._angle_to_screen(angle, dist, cx, cy, scale)

            label = labels[i] if i < len(labels) else -1
            if label >= 0:
                color = CLUSTER_COLORS[label % len(CLUSTER_COLORS)]
            else:
                color = QColor(0, 200, 0)

            painter.setPen(QPen(color, 4))
            painter.drawPoint(QPointF(sx, sy))

    def _draw_touch_markers(self, painter, cx, cy, scale, frame):
        """Draw touch centroids as labeled red circles."""
        for touch in frame.touches:
            x_mm, y_mm = touch.centroid_xy
            dist = math.sqrt(x_mm * x_mm + y_mm * y_mm)
            angle = math.atan2(y_mm, x_mm)
            sx, sy = self._angle_to_screen(angle, dist, cx, cy, scale)

            # Red circle
            r = 12
            painter.setPen(QPen(QColor(255, 50, 50), 2))
            painter.setBrush(QBrush(QColor(255, 50, 50, 80)))
            painter.drawEllipse(QPointF(sx, sy), r, r)

            # Session ID label
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(
                QRectF(sx - 20, sy - r - 18, 40, 16),
                Qt.AlignCenter,
                f"#{touch.session_id}"
            )

            # Normalized position label
            painter.setFont(QFont("Arial", 7))
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(
                QRectF(sx - 30, sy + r + 2, 60, 14),
                Qt.AlignCenter,
                f"({touch.normalized_pos[0]:.2f}, {touch.normalized_pos[1]:.2f})"
            )

    def set_show_screen_area(self, visible):
        """Toggle screen area overlay visibility."""
        self._show_screen_area = visible
        self.update()

    def _cartesian_to_screen(self, x_mm, y_mm, cx, cy, scale):
        """Convert Cartesian mm coordinates to screen pixel coordinates."""
        dist = math.sqrt(x_mm * x_mm + y_mm * y_mm)
        angle = math.atan2(y_mm, x_mm)
        return self._angle_to_screen(angle, dist, cx, cy, scale)

    def _build_screen_area_path(self, cx, cy, scale, snap):
        """Build QPainterPath for the screen rectangle."""
        width_mm = snap.get('screen_width_mm', 0)
        height_mm = snap.get('screen_height_mm', 0)
        offset_x = snap.get('screen_offset_x', 0)
        offset_y = snap.get('screen_offset_y', 0)

        if width_mm <= 0 or height_mm <= 0:
            return QPainterPath()

        half_w = width_mm / 2.0
        half_h = height_mm / 2.0

        corners = [
            (offset_x - half_w, offset_y - half_h),
            (offset_x + half_w, offset_y - half_h),
            (offset_x + half_w, offset_y + half_h),
            (offset_x - half_w, offset_y + half_h),
        ]

        segments = 25
        path = QPainterPath()
        first = True
        for edge_idx in range(4):
            x0, y0 = corners[edge_idx]
            x1, y1 = corners[(edge_idx + 1) % 4]
            for j in range(segments):
                t = j / segments
                ix = x0 + (x1 - x0) * t
                iy = y0 + (y1 - y0) * t
                sx, sy = self._cartesian_to_screen(ix, iy, cx, cy, scale)
                if first:
                    path.moveTo(sx, sy)
                    first = False
                else:
                    path.lineTo(sx, sy)
        path.closeSubpath()
        return path

    def _draw_screen_area(self, painter, cx, cy, scale, snap):
        """Draw the configured screen rectangle as an overlay."""
        screen_path = self._build_screen_area_path(cx, cy, scale, snap)
        if screen_path.isEmpty():
            return

        screen_name = snap.get('screen_name', 'Screen')
        offset_x = snap.get('screen_offset_x', 0)
        offset_y = snap.get('screen_offset_y', 0)
        half_h = snap.get('screen_height_mm', 0) / 2.0

        # Semi-transparent orange fill
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 165, 0, 30)))
        painter.drawPath(screen_path)

        # Dashed orange outline
        pen = QPen(QColor(255, 165, 0, 180), 1.5, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(screen_path)

        # Screen name label at top-center
        lx, ly = self._cartesian_to_screen(offset_x, offset_y + half_h, cx, cy, scale)
        painter.setPen(QColor(255, 165, 0, 220))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(
            QRectF(lx - 50, ly - 18, 100, 16),
            Qt.AlignCenter,
            screen_name,
        )

    def _draw_active_area(self, painter, cx, cy, scale, snap):
        """Draw the active area (intersection of screen and detection zone)."""
        screen_path = self._build_screen_area_path(cx, cy, scale, snap)
        if screen_path.isEmpty():
            return
        zone_path = self._build_detection_zone_path(cx, cy, scale, snap)
        active_path = screen_path.intersected(zone_path)
        if active_path.isEmpty():
            return

        # Semi-transparent green fill
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 255, 0, 35)))
        painter.drawPath(active_path)

        # Green dashed outline
        painter.setPen(QPen(QColor(0, 255, 0, 140), 1.5, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(active_path)

        # "Active Area" label at center of the active region
        bounds = active_path.boundingRect()
        painter.setPen(QColor(0, 255, 0, 200))
        painter.setFont(QFont("Arial", 7))
        painter.drawText(bounds, Qt.AlignCenter, "Active Area")

    def _draw_sensor(self, painter, cx, cy, scale, snap):
        """Draw the sensor as a 50x50mm (5x5cm) red square."""
        sensor_x = snap.get('sensor_x_offset', 0.0)
        sensor_y = snap.get('sensor_y_offset', 0.0)

        # Position sensor icon using offset
        if abs(sensor_x) < 0.001 and abs(sensor_y) < 0.001:
            sx, sy = cx, cy
        else:
            sx, sy = self._cartesian_to_screen(sensor_x, sensor_y, cx, cy, scale)

        # 50mm sensor size, with minimum 20px for visibility
        sensor_size_px = max(50.0 * scale, 20.0)
        half = sensor_size_px / 2.0

        rect = QRectF(sx - half, sy - half, sensor_size_px, sensor_size_px)

        # Red sensor body
        painter.setPen(QPen(QColor(255, 60, 60, 220), 2.0))
        painter.setBrush(QBrush(QColor(255, 40, 40, 80)))
        painter.drawRect(rect)

        # Sensor label
        painter.setPen(QColor(255, 200, 200))
        painter.setFont(QFont("Arial", 7, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, "LiDAR")

    def _draw_info(self, painter, frame):
        """Draw info overlay in top-left corner."""
        painter.setPen(QColor(180, 180, 200))
        painter.setFont(QFont("Arial", 9))
        y = 15
        texts = [
            f"Frame: {frame.frame_seq}",
            f"Touches: {len(frame.touches)}",
            f"Proc: {frame.processing_time_ms:.1f}ms",
        ]
        if frame.bg_is_learned:
            texts.append("BG: Learned")
        elif frame.bg_learning_progress > 0:
            texts.append(f"BG Learning: {frame.bg_learning_progress * 100:.0f}%")
        else:
            texts.append("BG: Not learned")

        for text in texts:
            painter.drawText(10, y, text)
            y += 16
