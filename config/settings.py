import json
from dataclasses import dataclass, fields
from threading import Lock


@dataclass
class AppSettings:
    # LiDAR connection
    lidar_ip: str = "192.168.0.10"
    lidar_port: int = 10940

    # Sensor position
    sensor_x_offset: float = 0.0
    sensor_y_offset: float = 0.0
    sensor_z_rotation: float = 0.0
    sensor_x_flip: bool = False
    sensor_y_flip: bool = False

    # Detection zone
    min_distance_mm: float = 20.0
    max_distance_mm: float = 1500.0
    min_angle_deg: float = -90.0
    max_angle_deg: float = 90.0

    # Background
    bg_learning_frames: int = 30
    bg_subtraction_threshold_mm: float = 40.0

    # Clustering
    cluster_eps_mm: float = 30.0
    cluster_min_samples: int = 3
    min_cluster_size: int = 3
    min_touch_segments: int = 2

    # Tracking
    max_tracking_distance_mm: float = 50.0
    touch_timeout_frames: int = 3
    merge_distance_mm: float = 20.0

    # Screen
    screen_name: str = "Screen 1"
    screen_width_mm: float = 1920.0
    screen_height_mm: float = 1080.0
    screen_offset_x: float = 0.0
    screen_offset_y: float = 0.0

    # TUIO output
    tuio_host: str = "127.0.0.1"
    tuio_port: int = 3333
    tuio_enabled: bool = True

    # Smoothing
    kalman_filter: bool = False
    smoothing_value: float = 0.5

    # Lock for thread-safe access
    _lock: Lock = None

    def __post_init__(self):
        object.__setattr__(self, '_lock', Lock())

    def get_snapshot(self):
        """Return a dict copy of current settings (thread-safe)."""
        with self._lock:
            return {f.name: getattr(self, f.name) for f in fields(self) if f.name != '_lock'}

    def update(self, **kwargs):
        """Update settings thread-safely."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key) and key != '_lock':
                    setattr(self, key, value)

    def save(self, path: str = "settings.json"):
        with self._lock:
            d = {f.name: getattr(self, f.name) for f in fields(self) if f.name != '_lock'}
        with open(path, 'w') as f:
            json.dump(d, f, indent=2)

    @classmethod
    def load(cls, path: str = "settings.json"):
        with open(path, 'r') as f:
            data = json.load(f)
        data.pop('_lock', None)
        return cls(**data)
