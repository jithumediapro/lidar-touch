import copy
import json
from dataclasses import dataclass, field, fields
from threading import Lock


LIDAR_MODELS = {
    'UST-10LX': {'max_range_mm': 10000.0, 'description': 'Hokuyo UST-10LX (10m range)'},
    'UST-20LX': {'max_range_mm': 20000.0, 'description': 'Hokuyo UST-20LX (20m range)'},
}


def _default_sensor():
    return {
        'name': 'Sensor 1',
        'model': 'UST-10LX',
        'lidar_ip': '192.168.0.10',
        'lidar_port': 10940,
        'sensor_x_offset': 0.0,
        'sensor_y_offset': 0.0,
        'sensor_z_rotation': 0.0,
        'sensor_x_flip': False,
        'sensor_y_flip': False,
        'min_distance_mm': 20.0,
        'max_distance_mm': 10000.0,
        'min_angle_deg': -90.0,
        'max_angle_deg': 90.0,
    }


def _default_screen():
    return {
        'name': 'Screen 1',
        'screen_width_mm': 1920.0,
        'screen_height_mm': 1080.0,
        'screen_offset_x': 0.0,
        'screen_offset_y': 0.0,
        'active_area_enabled': False,
        'active_area_width_mm': 1920.0,
        'active_area_height_mm': 1080.0,
        'active_area_offset_x': 0.0,
        'active_area_offset_y': 0.0,
    }


def _default_output():
    return {
        'name': 'Output 1',
        'screen_index': 0,
        'tuio_host': '127.0.0.1',
        'tuio_port': 3333,
        'tuio_enabled': True,
    }


@dataclass
class AppSettings:
    # Lists of configs (each item is a dict)
    sensors: list = field(default_factory=list)
    screens: list = field(default_factory=list)
    outputs: list = field(default_factory=list)

    # Global processing settings (shared across sensors)
    bg_learning_frames: int = 30
    bg_subtraction_threshold_mm: float = 40.0
    cluster_eps_mm: float = 30.0
    cluster_min_samples: int = 3
    min_cluster_size: int = 3
    min_touch_segments: int = 2
    max_tracking_distance_mm: float = 50.0
    touch_timeout_frames: int = 3
    merge_distance_mm: float = 20.0
    kalman_filter: bool = False
    smoothing_value: float = 0.5

    # Lock for thread-safe access
    _lock: Lock = None

    def __post_init__(self):
        object.__setattr__(self, '_lock', Lock())

    def get_snapshot(self):
        """Return a dict copy of current settings (thread-safe)."""
        with self._lock:
            d = {}
            for f in fields(self):
                if f.name == '_lock':
                    continue
                val = getattr(self, f.name)
                if isinstance(val, list):
                    d[f.name] = copy.deepcopy(val)
                else:
                    d[f.name] = val
            return d

    def update(self, **kwargs):
        """Update settings thread-safely."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key) and key != '_lock':
                    if isinstance(value, list):
                        setattr(self, key, copy.deepcopy(value))
                    else:
                        setattr(self, key, value)

    # --- Per-item accessors ---

    def get_sensor(self, index):
        with self._lock:
            if 0 <= index < len(self.sensors):
                return copy.deepcopy(self.sensors[index])
            return None

    def get_screen(self, index):
        with self._lock:
            if 0 <= index < len(self.screens):
                return copy.deepcopy(self.screens[index])
            return None

    def get_output(self, index):
        with self._lock:
            if 0 <= index < len(self.outputs):
                return copy.deepcopy(self.outputs[index])
            return None

    def update_sensor(self, index, **kwargs):
        with self._lock:
            if 0 <= index < len(self.sensors):
                self.sensors[index].update(kwargs)

    def update_screen(self, index, **kwargs):
        with self._lock:
            if 0 <= index < len(self.screens):
                self.screens[index].update(kwargs)

    def update_output(self, index, **kwargs):
        with self._lock:
            if 0 <= index < len(self.outputs):
                self.outputs[index].update(kwargs)

    def add_sensor(self):
        with self._lock:
            idx = len(self.sensors)
            s = _default_sensor()
            s['name'] = f'Sensor {idx + 1}'
            self.sensors.append(s)
            return idx

    def remove_sensor(self, index):
        with self._lock:
            if 0 <= index < len(self.sensors):
                self.sensors.pop(index)
                return True
            return False

    def add_screen(self):
        with self._lock:
            idx = len(self.screens)
            s = _default_screen()
            s['name'] = f'Screen {idx + 1}'
            self.screens.append(s)
            return idx

    def remove_screen(self, index):
        with self._lock:
            if 0 <= index < len(self.screens):
                self.screens.pop(index)
                return True
            return False

    def add_output(self):
        with self._lock:
            idx = len(self.outputs)
            o = _default_output()
            o['name'] = f'Output {idx + 1}'
            o['tuio_port'] = 3333 + idx
            self.outputs.append(o)
            return idx

    def remove_output(self, index):
        with self._lock:
            if 0 <= index < len(self.outputs):
                self.outputs.pop(index)
                return True
            return False

    def sensor_count(self):
        with self._lock:
            return len(self.sensors)

    def screen_count(self):
        with self._lock:
            return len(self.screens)

    def output_count(self):
        with self._lock:
            return len(self.outputs)

    def save(self, path: str = "settings.json"):
        with self._lock:
            d = {}
            for f in fields(self):
                if f.name == '_lock':
                    continue
                val = getattr(self, f.name)
                if isinstance(val, list):
                    d[f.name] = copy.deepcopy(val)
                else:
                    d[f.name] = val
        with open(path, 'w') as f:
            json.dump(d, f, indent=2)

    @classmethod
    def load(cls, path: str = "settings.json"):
        with open(path, 'r') as f:
            data = json.load(f)
        data.pop('_lock', None)

        # Migration: detect old flat format (has 'lidar_ip' at top level)
        if 'lidar_ip' in data and 'sensors' not in data:
            data = cls._migrate_flat(data)

        return cls(**data)

    @staticmethod
    def _migrate_flat(data):
        """Convert old flat settings format to new list-based format."""
        sensor = _default_sensor()
        sensor_keys = {
            'lidar_ip', 'lidar_port',
            'sensor_x_offset', 'sensor_y_offset', 'sensor_z_rotation',
            'sensor_x_flip', 'sensor_y_flip',
            'min_distance_mm', 'max_distance_mm',
            'min_angle_deg', 'max_angle_deg',
        }
        for key in sensor_keys:
            if key in data:
                sensor[key] = data.pop(key)
        sensor['name'] = 'Sensor 1'

        screen = _default_screen()
        screen_keys = {'screen_width_mm', 'screen_height_mm', 'screen_offset_x', 'screen_offset_y'}
        for key in screen_keys:
            if key in data:
                screen[key] = data.pop(key)
        if 'screen_name' in data:
            screen['name'] = data.pop('screen_name')

        output = _default_output()
        output_keys = {'tuio_host', 'tuio_port', 'tuio_enabled'}
        for key in output_keys:
            if key in data:
                output[key] = data.pop(key)
        output['name'] = 'Output 1'
        output['screen_index'] = 0

        data['sensors'] = [sensor]
        data['screens'] = [screen]
        data['outputs'] = [output]

        return data
