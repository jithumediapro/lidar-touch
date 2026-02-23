import math
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSlot, pyqtSignal
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

# Per-model detection zone colors
MODEL_COLORS = {
    'UST-10LX': (QColor(200, 120, 60, 100), QColor(120, 60, 30, 40)),   # Orange
    'UST-20LX': (QColor(60, 120, 200, 100), QColor(30, 60, 120, 40)),   # Blue
}
DEFAULT_SENSOR_COLOR = (QColor(60, 200, 120, 100), QColor(30, 120, 60, 40))  # Green

# Per-screen colors
SCREEN_COLORS = [
    QColor(255, 165, 0),    # Orange
    QColor(0, 200, 255),    # Cyan
    QColor(255, 100, 200),  # Pink
    QColor(200, 255, 0),    # Lime
]


class LidarView(QWidget):
    """QPainter-based LiDAR scan visualization widget with multi-sensor/screen support."""

    object_moved = pyqtSignal()  # emitted after drag-move completes

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._frames = {}  # sensor_index -> FrameResult
        self._dirty = False
        self._show_screen_area = True

        # Canvas pan state
        self._pan_offset_x = 0.0
        self._pan_offset_y = 0.0
        self._panning = False
        self._pan_start = None

        # Canvas zoom state
        self._zoom_factor = 1.0

        # Move mode state (hold M to drag sensors/screens)
        self._move_mode = False
        self._drag_target = None   # None, 'sensor', or 'screen'
        self._drag_index = -1
        self._drag_start_offset = None  # (x_mm, y_mm) original offset at drag start
        self._drag_start_mouse = None   # QPoint at drag start

        self.setMinimumSize(400, 400)
        self.setStyleSheet("background-color: #1a1a2e;")
        self.setFocusPolicy(Qt.StrongFocus)

        # Repaint throttle timer (~30 FPS)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._timer.start(33)

    @pyqtSlot(object)
    def update_frame(self, frame):
        """Receive processed frame data from pipeline. Stores by sensor_index."""
        self._frames[frame.sensor_index] = frame
        self._dirty = True

    def _on_timer(self):
        if self._dirty:
            self._dirty = False
            self.update()

    def _compute_canvas_params(self):
        """Compute cx, cy, scale — same logic as paintEvent."""
        w = self.width()
        h = self.height()
        snap = self._settings.get_snapshot()
        sensors = snap.get('sensors', [])
        max_dist = 0.0
        for sensor in sensors:
            md = sensor.get('max_distance_mm', 10000.0)
            if md > max_dist:
                max_dist = md
        if max_dist <= 0:
            max_dist = 10000.0
        scale = min(w * 0.45, h * 0.85) / max_dist * self._zoom_factor
        cx = w / 2.0 + self._pan_offset_x
        cy = h - 30.0 + self._pan_offset_y
        return cx, cy, scale, snap

    def _hit_test_sensor(self, sx, sy, cx, cy, scale, sensors):
        """Return sensor index if (sx, sy) hits a sensor icon, else -1."""
        for i, sensor in enumerate(sensors):
            sensor_snap = self._make_sensor_snap(sensor)
            scx, scy = self._sensor_origin(cx, cy, scale, sensor_snap)
            sensor_size_px = max(50.0 * scale, 20.0)
            half = sensor_size_px / 2.0
            if (scx - half <= sx <= scx + half and
                    scy - half <= sy <= scy + half):
                return i
        return -1

    def _hit_test_screen(self, sx, sy, cx, cy, scale, screens):
        """Return screen index if (sx, sy) hits a screen area, else -1."""
        for i, screen in enumerate(screens):
            screen_snap = self._make_screen_snap(screen)
            path = self._build_screen_area_path(cx, cy, scale, screen_snap)
            if path.contains(QPointF(sx, sy)):
                return i
        return -1

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._move_mode:
                cx, cy, scale, snap = self._compute_canvas_params()
                sensors = snap.get('sensors', [])
                screens = snap.get('screens', [])
                mx, my = event.pos().x(), event.pos().y()

                # Hit test sensors first (smaller targets, higher priority)
                si = self._hit_test_sensor(mx, my, cx, cy, scale, sensors)
                if si >= 0:
                    self._drag_target = 'sensor'
                    self._drag_index = si
                    self._drag_start_offset = (
                        sensors[si].get('sensor_x_offset', 0.0),
                        sensors[si].get('sensor_y_offset', 0.0),
                    )
                    self._drag_start_mouse = event.pos()
                    self.setCursor(Qt.ClosedHandCursor)
                    return

                # Hit test screens
                sci = self._hit_test_screen(mx, my, cx, cy, scale, screens)
                if sci >= 0:
                    self._drag_target = 'screen'
                    self._drag_index = sci
                    self._drag_start_offset = (
                        screens[sci].get('screen_offset_x', 0.0),
                        screens[sci].get('screen_offset_y', 0.0),
                    )
                    self._drag_start_mouse = event.pos()
                    self.setCursor(Qt.ClosedHandCursor)
                    return

            # Fall through to normal pan
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def _snap_to_screen_edges(self, x_mm, y_mm, snap_threshold_mm=200.0):
        """Snap position to the nearest screen edge midpoint if within threshold."""
        snap = self._settings.get_snapshot()
        screens = snap.get('screens', [])
        best_dist = snap_threshold_mm
        snap_x, snap_y = x_mm, y_mm
        for screen in screens:
            ox = screen.get('screen_offset_x', 0.0)
            oy = screen.get('screen_offset_y', 0.0)
            half_w = screen.get('screen_width_mm', 0.0) / 2.0
            half_h = screen.get('screen_height_mm', 0.0) / 2.0
            # Four edge midpoints
            edges = [
                (ox - half_w, oy),   # bottom edge (closest to sensor)
                (ox + half_w, oy),   # top edge (farthest from sensor)
                (ox, oy - half_h),   # left edge
                (ox, oy + half_h),   # right edge
            ]
            for ex, ey in edges:
                dx = x_mm - ex
                dy = y_mm - ey
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < best_dist:
                    best_dist = dist
                    snap_x, snap_y = ex, ey
        return snap_x, snap_y

    def mouseMoveEvent(self, event):
        if self._drag_target is not None and self._drag_start_mouse is not None:
            cx, cy, scale, _snap = self._compute_canvas_params()
            if scale <= 0:
                return
            delta = event.pos() - self._drag_start_mouse
            # Screen up = +x_mm (forward), screen right = +y_mm (right)
            delta_x_mm = -delta.y() / scale
            delta_y_mm = delta.x() / scale
            new_x = self._drag_start_offset[0] + delta_x_mm
            new_y = self._drag_start_offset[1] + delta_y_mm

            if self._drag_target == 'sensor':
                self._settings.update_sensor(
                    self._drag_index,
                    sensor_x_offset=round(new_x, 1),
                    sensor_y_offset=round(new_y, 1),
                )
            elif self._drag_target == 'screen':
                self._settings.update_screen(
                    self._drag_index,
                    screen_offset_x=round(new_x, 1),
                    screen_offset_y=round(new_y, 1),
                )
            self.update()
            return

        if self._panning and self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_offset_x += delta.x()
            self._pan_offset_y += delta.y()
            self._pan_start = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._drag_target is not None:
                # Snap sensor to nearest screen edge on release
                if self._drag_target == 'sensor' and self._drag_index >= 0:
                    sensor = self._settings.get_sensor(self._drag_index)
                    if sensor:
                        sx = sensor.get('sensor_x_offset', 0.0)
                        sy = sensor.get('sensor_y_offset', 0.0)
                        snapped_x, snapped_y = self._snap_to_screen_edges(sx, sy)
                        self._settings.update_sensor(
                            self._drag_index,
                            sensor_x_offset=round(snapped_x, 1),
                            sensor_y_offset=round(snapped_y, 1),
                        )
                self._drag_target = None
                self._drag_index = -1
                self._drag_start_offset = None
                self._drag_start_mouse = None
                self.setCursor(Qt.CrossCursor if self._move_mode else Qt.ArrowCursor)
                self.object_moved.emit()
                self.update()
                return
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.CrossCursor if self._move_mode else Qt.ArrowCursor)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom_factor *= 1.1
        elif delta < 0:
            self._zoom_factor /= 1.1
        self._zoom_factor = max(0.1, min(10.0, self._zoom_factor))
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._reset_view()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R:
            self._reset_view()
        elif event.key() == Qt.Key_M and not event.isAutoRepeat():
            self._move_mode = True
            self.setCursor(Qt.CrossCursor)
            self.update()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_M and not event.isAutoRepeat():
            self._move_mode = False
            # Cancel any in-progress drag
            if self._drag_target is not None:
                self._drag_target = None
                self._drag_index = -1
                self._drag_start_offset = None
                self._drag_start_mouse = None
            self.setCursor(Qt.ArrowCursor)
            self.update()
        else:
            super().keyReleaseEvent(event)

    def _reset_view(self):
        """Reset view to fit and center all sensors on the canvas."""
        snap = self._settings.get_snapshot()
        sensors = snap.get('sensors', [])

        if not sensors:
            self._pan_offset_x = 0.0
            self._pan_offset_y = 0.0
            self._zoom_factor = 1.0
            self.update()
            return

        w = self.width()
        h = self.height()

        # First pass: reset to compute screen positions of all sensor origins
        self._zoom_factor = 1.0
        self._pan_offset_x = 0.0
        self._pan_offset_y = 0.0

        max_dist = max(s.get('max_distance_mm', 10000.0) for s in sensors)
        scale = min(w * 0.45, h * 0.85) / max_dist

        # Base origin
        cx = w / 2.0
        cy = h - 30.0

        # Compute bounding box of all sensors in screen coords
        min_sx = float('inf')
        max_sx = float('-inf')
        min_sy = float('inf')
        max_sy = float('-inf')
        for sensor in sensors:
            sensor_snap = self._make_sensor_snap(sensor)
            scx, scy = self._sensor_origin(cx, cy, scale, sensor_snap)
            r = sensor.get('max_distance_mm', 10000.0) * scale
            min_sx = min(min_sx, scx - r)
            max_sx = max(max_sx, scx + r)
            min_sy = min(min_sy, scy - r)
            max_sy = max(max_sy, scy)

        # Center of bounding box in screen coords
        bbox_cx = (min_sx + max_sx) / 2.0
        bbox_cy = (min_sy + max_sy) / 2.0
        bbox_w = max_sx - min_sx
        bbox_h = max_sy - min_sy

        # Zoom to fit
        if bbox_w > 0 and bbox_h > 0:
            margin = 0.85
            zoom_x = (w * margin) / bbox_w
            zoom_y = (h * margin) / bbox_h
            self._zoom_factor = max(0.1, min(10.0, min(zoom_x, zoom_y)))

        # Recompute with new zoom
        scale = min(w * 0.45, h * 0.85) / max_dist * self._zoom_factor
        cx = w / 2.0
        cy = h - 30.0

        min_sx = float('inf')
        max_sx = float('-inf')
        min_sy = float('inf')
        max_sy = float('-inf')
        for sensor in sensors:
            sensor_snap = self._make_sensor_snap(sensor)
            scx, scy = self._sensor_origin(cx, cy, scale, sensor_snap)
            r = sensor.get('max_distance_mm', 10000.0) * scale
            min_sx = min(min_sx, scx - r)
            max_sx = max(max_sx, scx + r)
            min_sy = min(min_sy, scy - r)
            max_sy = max(max_sy, scy)

        bbox_cx = (min_sx + max_sx) / 2.0
        bbox_cy = (min_sy + max_sy) / 2.0

        # Pan to center the bounding box
        self._pan_offset_x = (w / 2.0) - bbox_cx
        self._pan_offset_y = (h / 2.0) - bbox_cy

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Dark background
        painter.fillRect(0, 0, w, h, QColor(26, 26, 46))

        if not self._frames:
            painter.setPen(QColor(100, 100, 100))
            painter.setFont(QFont("Arial", 14))
            painter.drawText(self.rect(), Qt.AlignCenter, "Waiting for scan data...")
            painter.end()
            return

        snap = self._settings.get_snapshot()
        sensors = snap.get('sensors', [])
        screens = snap.get('screens', [])

        # Compute max_dist across all sensors for scale
        max_dist = 0.0
        for sensor in sensors:
            md = sensor.get('max_distance_mm', 10000.0)
            if md > max_dist:
                max_dist = md
        if max_dist <= 0:
            max_dist = 10000.0

        scale = min(w * 0.45, h * 0.85) / max_dist * self._zoom_factor

        # Base origin at bottom-center + pan offset
        cx = w / 2.0 + self._pan_offset_x
        cy = h - 30.0 + self._pan_offset_y

        # Draw per-sensor detection zones and distance rings
        for si, sensor in enumerate(sensors):
            sensor_snap = self._make_sensor_snap(sensor)
            scx, scy = self._sensor_origin(cx, cy, scale, sensor_snap)
            model = sensor.get('model', 'UST-10LX')
            border_color, fill_color = MODEL_COLORS.get(model, DEFAULT_SENSOR_COLOR)

            # Apply rotation + flip around sensor origin
            painter.save()
            self._apply_sensor_transform(painter, scx, scy, sensor_snap)

            # Distance rings and angle grid per sensor
            sensor_max = sensor.get('max_distance_mm', 10000.0)
            self._draw_distance_rings(painter, scx, scy, scale, sensor_max)
            self._draw_angle_grid(painter, scx, scy, scale, sensor_max)

            self._draw_detection_zone(painter, scx, scy, scale, sensor_snap,
                                      border_color, fill_color)
            painter.restore()

        # Draw all screen area overlays
        if self._show_screen_area:
            for si, screen in enumerate(screens):
                screen_snap = self._make_screen_snap(screen)
                color = SCREEN_COLORS[si % len(SCREEN_COLORS)]
                self._draw_screen_area(painter, cx, cy, scale, screen_snap, color)
                # Draw active area per sensor+screen pair
                for sensor in sensors:
                    sensor_snap = self._make_sensor_snap(sensor)
                    self._draw_active_area(painter, cx, cy, scale, screen_snap, sensor_snap)

        # Draw per-sensor scan data
        for si, frame in self._frames.items():
            if si < len(sensors):
                sensor_snap = self._make_sensor_snap(sensors[si])
                scx, scy = self._sensor_origin(cx, cy, scale, sensor_snap)
            else:
                sensor_snap = None
                scx, scy = cx, cy

            # Apply rotation + flip around sensor origin
            painter.save()
            if sensor_snap:
                self._apply_sensor_transform(painter, scx, scy, sensor_snap)

            self._draw_scan_points(painter, scx, scy, scale, frame)
            self._draw_foreground_points(painter, scx, scy, scale, frame)
            self._draw_touch_markers(painter, scx, scy, scale, frame, screens)
            painter.restore()

        # Draw per-sensor icons
        for si, sensor in enumerate(sensors):
            sensor_snap = self._make_sensor_snap(sensor)
            label = sensor.get('name', f'LiDAR {si+1}')
            self._draw_sensor(painter, cx, cy, scale, sensor_snap, label)

        # Draw info overlay using first available frame
        first_frame = next(iter(self._frames.values()))
        total_touches = sum(len(f.touches) for f in self._frames.values())
        self._draw_info(painter, first_frame, total_touches, len(self._frames))

        painter.end()

    @staticmethod
    def _make_sensor_snap(sensor_dict):
        """Create a snap-like dict from a sensor config for legacy methods."""
        return {
            'min_angle_deg': sensor_dict.get('min_angle_deg', -90.0),
            'max_angle_deg': sensor_dict.get('max_angle_deg', 90.0),
            'min_distance_mm': sensor_dict.get('min_distance_mm', 20.0),
            'max_distance_mm': sensor_dict.get('max_distance_mm', 10000.0),
            'sensor_x_offset': sensor_dict.get('sensor_x_offset', 0.0),
            'sensor_y_offset': sensor_dict.get('sensor_y_offset', 0.0),
            'sensor_z_rotation': sensor_dict.get('sensor_z_rotation', 0.0),
            'sensor_x_flip': sensor_dict.get('sensor_x_flip', False),
            'sensor_y_flip': sensor_dict.get('sensor_y_flip', False),
        }

    @staticmethod
    def _make_screen_snap(screen_dict):
        """Create a snap-like dict from a screen config for legacy methods."""
        return {
            'screen_width_mm': screen_dict.get('screen_width_mm', 1920.0),
            'screen_height_mm': screen_dict.get('screen_height_mm', 1080.0),
            'screen_offset_x': screen_dict.get('screen_offset_x', 0.0),
            'screen_offset_y': screen_dict.get('screen_offset_y', 0.0),
            'name': screen_dict.get('name', 'Screen'),
            'active_area_enabled': screen_dict.get('active_area_enabled', False),
            'active_area_width_mm': screen_dict.get('active_area_width_mm', screen_dict.get('screen_width_mm', 1920.0)),
            'active_area_height_mm': screen_dict.get('active_area_height_mm', screen_dict.get('screen_height_mm', 1080.0)),
            'active_area_offset_x': screen_dict.get('active_area_offset_x', screen_dict.get('screen_offset_x', 0.0)),
            'active_area_offset_y': screen_dict.get('active_area_offset_y', screen_dict.get('screen_offset_y', 0.0)),
        }

    def _draw_distance_rings(self, painter, cx, cy, scale, max_dist):
        pen = QPen(QColor(40, 40, 80), 1, Qt.DotLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        ring_step = 1000.0  # 1m apart
        dist = ring_step
        while dist <= max_dist:
            r = dist * scale
            painter.drawArc(
                QRectF(cx - r, cy - r, 2 * r, 2 * r),
                0 * 16, 180 * 16,
            )
            dist += ring_step

    def _draw_angle_grid(self, painter, cx, cy, scale, max_dist):
        pen = QPen(QColor(40, 40, 70), 1, Qt.DotLine)
        painter.setPen(pen)

        r = max_dist * scale
        for angle_deg in range(-90, 91, 45):
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

    def _draw_detection_zone(self, painter, cx, cy, scale, snap,
                             border_color=None, fill_color=None):
        path = self._build_detection_zone_path(cx, cy, scale, snap)

        if fill_color is None:
            fill_color = QColor(30, 60, 120, 40)
        if border_color is None:
            border_color = QColor(60, 120, 200, 100)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(fill_color))
        painter.drawPath(path)

        # Zone boundary
        painter.setPen(QPen(border_color, 1))
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

    def _is_touch_in_any_screen(self, x_mm, y_mm, screens):
        """Check if a touch point falls within any screen's active area."""
        for screen in screens:
            if screen.get('active_area_enabled', False):
                w = screen.get('active_area_width_mm', 0)
                h = screen.get('active_area_height_mm', 0)
                ox = screen.get('active_area_offset_x', 0)
                oy = screen.get('active_area_offset_y', 0)
            else:
                w = screen.get('screen_width_mm', 0)
                h = screen.get('screen_height_mm', 0)
                ox = screen.get('screen_offset_x', 0)
                oy = screen.get('screen_offset_y', 0)
            if w <= 0 or h <= 0:
                continue
            half_w = w / 2.0
            half_h = h / 2.0
            if (ox - half_w <= x_mm <= ox + half_w and
                    oy - half_h <= y_mm <= oy + half_h):
                return True
        return False

    def _draw_touch_markers(self, painter, cx, cy, scale, frame, screens):
        """Draw touch centroids -- red if inside any screen, gray if outside."""
        for touch in frame.touches:
            x_mm, y_mm = touch.centroid_xy
            dist = math.sqrt(x_mm * x_mm + y_mm * y_mm)
            angle = math.atan2(y_mm, x_mm)
            sx, sy = self._angle_to_screen(angle, dist, cx, cy, scale)

            inside = self._is_touch_in_any_screen(x_mm, y_mm, screens)

            r = 12
            if inside:
                # Red circle for active touches
                painter.setPen(QPen(QColor(255, 50, 50), 2))
                painter.setBrush(QBrush(QColor(255, 50, 50, 80)))
            else:
                # Gray circle for outside touches
                painter.setPen(QPen(QColor(120, 120, 120), 2))
                painter.setBrush(QBrush(QColor(120, 120, 120, 50)))
            painter.drawEllipse(QPointF(sx, sy), r, r)

            # Session ID label
            label_color = QColor(255, 255, 255) if inside else QColor(150, 150, 150)
            painter.setPen(label_color)
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(
                QRectF(sx - 20, sy - r - 18, 40, 16),
                Qt.AlignCenter,
                f"#{touch.session_id}"
            )

            # Normalized position label
            painter.setFont(QFont("Arial", 7))
            painter.setPen(QColor(200, 200, 200) if inside else QColor(130, 130, 130))
            painter.drawText(
                QRectF(sx - 30, sy + r + 2, 60, 14),
                Qt.AlignCenter,
                f"({touch.normalized_pos[0]:.2f}, {touch.normalized_pos[1]:.2f})"
            )

    def set_show_screen_area(self, visible):
        """Toggle screen area overlay visibility."""
        self._show_screen_area = visible
        self.update()

    def _apply_sensor_transform(self, painter, scx, scy, sensor_snap):
        """Apply rotation and flip transforms around sensor origin. Call painter.save() before this."""
        z_rot = sensor_snap.get('sensor_z_rotation', 0.0)
        x_flip = sensor_snap.get('sensor_x_flip', False)
        y_flip = sensor_snap.get('sensor_y_flip', False)

        has_transform = abs(z_rot) > 0.001 or x_flip or y_flip
        if has_transform:
            painter.translate(scx, scy)
            if abs(z_rot) > 0.001:
                painter.rotate(-z_rot)
            if x_flip or y_flip:
                # X flip mirrors the forward/backward axis (vertical on screen)
                # Y flip mirrors the left/right axis (horizontal on screen)
                sx = -1.0 if y_flip else 1.0
                sy = -1.0 if x_flip else 1.0
                painter.scale(sx, sy)
            painter.translate(-scx, -scy)

    def _sensor_origin(self, cx, cy, scale, sensor_snap):
        """Compute the screen origin for a sensor based on its X/Y offset."""
        ox = sensor_snap.get('sensor_x_offset', 0.0)
        oy = sensor_snap.get('sensor_y_offset', 0.0)
        if abs(ox) < 0.001 and abs(oy) < 0.001:
            return cx, cy
        return self._cartesian_to_screen(ox, oy, cx, cy, scale)

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

    def _draw_screen_area(self, painter, cx, cy, scale, snap, color=None):
        """Draw the configured screen rectangle as an overlay."""
        screen_path = self._build_screen_area_path(cx, cy, scale, snap)
        if screen_path.isEmpty():
            return

        if color is None:
            color = QColor(255, 165, 0)

        screen_name = snap.get('name', 'Screen')
        offset_x = snap.get('screen_offset_x', 0)
        offset_y = snap.get('screen_offset_y', 0)
        half_h = snap.get('screen_height_mm', 0) / 2.0

        # Semi-transparent fill
        fill_color = QColor(color)
        fill_color.setAlpha(30)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(fill_color))
        painter.drawPath(screen_path)

        # Dashed outline
        outline_color = QColor(color)
        outline_color.setAlpha(180)
        pen = QPen(outline_color, 1.5, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(screen_path)

        # Screen name label at top-center
        lx, ly = self._cartesian_to_screen(offset_x, offset_y + half_h, cx, cy, scale)
        label_color = QColor(color)
        label_color.setAlpha(220)
        painter.setPen(label_color)
        painter.setFont(QFont("Arial", 8))
        painter.drawText(
            QRectF(lx - 50, ly - 18, 100, 16),
            Qt.AlignCenter,
            screen_name,
        )

    def _draw_active_area(self, painter, cx, cy, scale, screen_snap, sensor_snap):
        """Draw the active area overlay in green.

        Draws the exact rectangle that matches CoordinateMapper.is_in_screen_area
        (no sensor angular range clipping). When active_area_enabled is True, uses
        the custom active area dimensions; when False, uses the screen dimensions.
        """
        if screen_snap.get('active_area_enabled', False):
            aa_snap = {
                'screen_width_mm': screen_snap['active_area_width_mm'],
                'screen_height_mm': screen_snap['active_area_height_mm'],
                'screen_offset_x': screen_snap['active_area_offset_x'],
                'screen_offset_y': screen_snap['active_area_offset_y'],
            }
            active_path = self._build_screen_area_path(cx, cy, scale, aa_snap)
        else:
            active_path = self._build_screen_area_path(cx, cy, scale, screen_snap)

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

    def _draw_sensor(self, painter, cx, cy, scale, snap, label="LiDAR"):
        """Draw the sensor as a 50x50mm (5x5cm) red square, rotated to match sensor orientation."""
        sx, sy = self._sensor_origin(cx, cy, scale, snap)

        # 50mm sensor size, with minimum 20px for visibility
        sensor_size_px = max(50.0 * scale, 20.0)
        half = sensor_size_px / 2.0

        painter.save()
        self._apply_sensor_transform(painter, sx, sy, snap)

        rect = QRectF(sx - half, sy - half, sensor_size_px, sensor_size_px)

        # Red sensor body
        painter.setPen(QPen(QColor(255, 60, 60, 220), 2.0))
        painter.setBrush(QBrush(QColor(255, 40, 40, 80)))
        painter.drawRect(rect)

        # Sensor label
        painter.setPen(QColor(255, 200, 200))
        painter.setFont(QFont("Arial", 7, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, label)
        painter.restore()

    def _draw_info(self, painter, frame, total_touches=None, num_sensors=1):
        """Draw info overlay in top-left corner."""
        painter.setPen(QColor(180, 180, 200))
        painter.setFont(QFont("Arial", 9))
        y = 15
        touches = total_touches if total_touches is not None else len(frame.touches)
        texts = [
            f"Frame: {frame.frame_seq}",
            f"Sensors: {num_sensors}",
            f"Touches: {touches}",
            f"Proc: {frame.processing_time_ms:.1f}ms",
        ]
        if frame.bg_is_learned:
            texts.append("BG: Learned")
        elif frame.bg_learning_progress > 0:
            texts.append(f"BG Learning: {frame.bg_learning_progress * 100:.0f}%")
        else:
            texts.append("BG: Not learned")

        texts.append(f"Zoom: {self._zoom_factor:.1f}x")

        if self._move_mode:
            texts.append("Move Mode (M)")

        for text in texts:
            painter.drawText(10, y, text)
            y += 16
