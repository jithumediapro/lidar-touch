from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from processing.coordinate_mapper import CoordinateMapper
from processing.tracking import TrackedTouch


class TouchRouter(QObject):
    """Routes touches from all sensors to the correct screen + TUIO output.

    Each pipeline emits raw mm-coordinate touches. This router checks
    each touch against every screen's area, normalizes coordinates,
    and emits per-screen touch lists.
    """

    # Signal: (screen_index, list[TrackedTouch], frame_seq)
    screen_touches = pyqtSignal(int, object, int)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._mappers = {}  # (sensor_index, screen_index) -> CoordinateMapper

    def _get_mapper(self, sensor_index, screen_index, sensor_cfg, screen_cfg):
        """Get or create a CoordinateMapper for a sensor+screen pair."""
        key = (sensor_index, screen_index)
        active_area_kwargs = {
            'active_area_enabled': screen_cfg.get('active_area_enabled', False),
            'active_area_width_mm': screen_cfg.get('active_area_width_mm'),
            'active_area_height_mm': screen_cfg.get('active_area_height_mm'),
            'active_area_offset_x': screen_cfg.get('active_area_offset_x'),
            'active_area_offset_y': screen_cfg.get('active_area_offset_y'),
            'exclude_zones': screen_cfg.get('exclude_zones', []),
        }
        mapper = self._mappers.get(key)
        if mapper is None:
            mapper = CoordinateMapper(
                screen_width_mm=screen_cfg['screen_width_mm'],
                screen_height_mm=screen_cfg['screen_height_mm'],
                screen_offset_x=screen_cfg['screen_offset_x'],
                screen_offset_y=screen_cfg['screen_offset_y'],
                sensor_x_offset=sensor_cfg.get('sensor_x_offset', 0.0),
                sensor_y_offset=sensor_cfg.get('sensor_y_offset', 0.0),
                sensor_z_rotation=sensor_cfg.get('sensor_z_rotation', 0.0),
                x_flip=sensor_cfg.get('sensor_x_flip', False),
                y_flip=sensor_cfg.get('sensor_y_flip', False),
                min_angle_deg=sensor_cfg.get('min_angle_deg', -90.0),
                max_angle_deg=sensor_cfg.get('max_angle_deg', 90.0),
                min_dist_mm=sensor_cfg.get('min_distance_mm', 20.0),
                max_dist_mm=sensor_cfg.get('max_distance_mm', 1500.0),
                **active_area_kwargs,
            )
            self._mappers[key] = mapper
        else:
            # Update params in case settings changed
            mapper.update_params(
                screen_width_mm=screen_cfg['screen_width_mm'],
                screen_height_mm=screen_cfg['screen_height_mm'],
                screen_offset_x=screen_cfg['screen_offset_x'],
                screen_offset_y=screen_cfg['screen_offset_y'],
                sensor_x_offset=sensor_cfg.get('sensor_x_offset', 0.0),
                sensor_y_offset=sensor_cfg.get('sensor_y_offset', 0.0),
                sensor_z_rotation=sensor_cfg.get('sensor_z_rotation', 0.0),
                x_flip=sensor_cfg.get('sensor_x_flip', False),
                y_flip=sensor_cfg.get('sensor_y_flip', False),
                min_angle_deg=sensor_cfg.get('min_angle_deg', -90.0),
                max_angle_deg=sensor_cfg.get('max_angle_deg', 90.0),
                min_dist_mm=sensor_cfg.get('min_distance_mm', 20.0),
                max_dist_mm=sensor_cfg.get('max_distance_mm', 1500.0),
                **active_area_kwargs,
            )
        return mapper

    @pyqtSlot(object, int, int)
    def route_touches(self, touches, sensor_index, frame_seq):
        """Called when a pipeline produces touches. Routes to screens."""
        snap = self._settings.get_snapshot()
        sensors = snap.get('sensors', [])
        screens = snap.get('screens', [])

        if sensor_index >= len(sensors):
            return

        sensor_cfg = sensors[sensor_index]

        for si, screen_cfg in enumerate(screens):
            mapper = self._get_mapper(sensor_index, si, sensor_cfg, screen_cfg)
            screen_touches = []

            for touch in touches:
                x_mm, y_mm = touch.centroid_xy
                if mapper.is_in_screen_area(x_mm, y_mm):
                    nx, ny = mapper.to_normalized(x_mm, y_mm)
                    touch_copy = TrackedTouch(
                        session_id=touch.session_id,
                        centroid_xy=touch.centroid_xy,
                        velocity_xy=touch.velocity_xy,
                        normalized_pos=(nx, ny),
                        age_frames=touch.age_frames,
                        num_points=touch.num_points,
                    )
                    screen_touches.append(touch_copy)

            # Always emit (even empty) so TUIO sends alive=[] for empty frames
            self.screen_touches.emit(si, screen_touches, frame_seq)

    def invalidate_mappers(self):
        """Clear cached mappers when sensor/screen config changes."""
        self._mappers.clear()
