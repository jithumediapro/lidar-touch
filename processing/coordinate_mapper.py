import math
import numpy as np


class CoordinateMapper:
    """Converts between polar, Cartesian, and normalized coordinate systems."""

    def __init__(self, screen_width_mm=1920.0, screen_height_mm=1080.0,
                 screen_offset_x=0.0, screen_offset_y=0.0,
                 sensor_x_offset=0.0, sensor_y_offset=0.0,
                 sensor_z_rotation=0.0, x_flip=False, y_flip=False,
                 min_angle_deg=-135.0, max_angle_deg=135.0,
                 min_dist_mm=20.0, max_dist_mm=1500.0):
        self.screen_width_mm = screen_width_mm
        self.screen_height_mm = screen_height_mm
        self.screen_offset_x = screen_offset_x
        self.screen_offset_y = screen_offset_y
        self.sensor_x_offset = sensor_x_offset
        self.sensor_y_offset = sensor_y_offset
        self.sensor_z_rotation = math.radians(sensor_z_rotation)
        self.x_flip = x_flip
        self.y_flip = y_flip
        self.min_angle_rad = math.radians(min_angle_deg)
        self.max_angle_rad = math.radians(max_angle_deg)
        self.min_dist_mm = min_dist_mm
        self.max_dist_mm = max_dist_mm

    def update_params(self, **kwargs):
        for key, value in kwargs.items():
            if key in ('sensor_z_rotation',):
                setattr(self, key, math.radians(value))
            elif key in ('min_angle_deg',):
                self.min_angle_rad = math.radians(value)
            elif key in ('max_angle_deg',):
                self.max_angle_rad = math.radians(value)
            elif hasattr(self, key):
                setattr(self, key, value)

    @staticmethod
    def polar_to_cartesian(angles, distances):
        """Convert polar coordinates to Cartesian (x, y) in mm."""
        x = distances * np.cos(angles)
        y = distances * np.sin(angles)
        return np.column_stack((x, y))

    def apply_transform(self, x_mm, y_mm):
        """Apply sensor position offset and rotation."""
        # Apply rotation
        cos_r = math.cos(self.sensor_z_rotation)
        sin_r = math.sin(self.sensor_z_rotation)
        rx = x_mm * cos_r - y_mm * sin_r
        ry = x_mm * sin_r + y_mm * cos_r

        # Apply offset
        rx += self.sensor_x_offset
        ry += self.sensor_y_offset

        return rx, ry

    def to_normalized(self, x_mm, y_mm):
        """
        Map Cartesian point (mm) to normalized [0, 1] coordinates for TUIO.

        Uses the screen rectangle (active area) for normalization:
        - X: horizontal position mapped to [0, 1] across screen width
        - Y: vertical position mapped to [0, 1] across screen height
        """
        # Apply sensor transform
        tx, ty = self.apply_transform(x_mm, y_mm)

        # Normalize relative to screen rectangle
        # Screen left/right edges
        half_w = self.screen_width_mm / 2.0
        half_h = self.screen_height_mm / 2.0
        screen_left = self.screen_offset_x - half_w
        screen_bottom = self.screen_offset_y - half_h

        if self.screen_width_mm > 0:
            nx = (tx - screen_left) / self.screen_width_mm
        else:
            nx = 0.5

        if self.screen_height_mm > 0:
            ny = (ty - screen_bottom) / self.screen_height_mm
        else:
            ny = 0.5

        # Apply flips
        if self.x_flip:
            nx = 1.0 - nx
        if self.y_flip:
            ny = 1.0 - ny

        # Clamp
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))

        return nx, ny

    def is_in_screen_area(self, x_mm, y_mm):
        """Check if a Cartesian point falls within the screen rectangle."""
        tx, ty = self.apply_transform(x_mm, y_mm)

        half_w = self.screen_width_mm / 2.0
        half_h = self.screen_height_mm / 2.0

        return (self.screen_offset_x - half_w <= tx <= self.screen_offset_x + half_w and
                self.screen_offset_y - half_h <= ty <= self.screen_offset_y + half_h)
