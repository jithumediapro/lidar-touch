import math
import numpy as np


class ScanFilter:
    """Filters scan data by distance and angular range."""

    def __init__(self, min_dist_mm=20.0, max_dist_mm=1500.0,
                 min_angle_deg=-135.0, max_angle_deg=135.0):
        self.min_dist_mm = min_dist_mm
        self.max_dist_mm = max_dist_mm
        self.min_angle_rad = math.radians(min_angle_deg)
        self.max_angle_rad = math.radians(max_angle_deg)

    def update_params(self, min_dist_mm=None, max_dist_mm=None,
                      min_angle_deg=None, max_angle_deg=None):
        if min_dist_mm is not None:
            self.min_dist_mm = min_dist_mm
        if max_dist_mm is not None:
            self.max_dist_mm = max_dist_mm
        if min_angle_deg is not None:
            self.min_angle_rad = math.radians(min_angle_deg)
        if max_angle_deg is not None:
            self.max_angle_rad = math.radians(max_angle_deg)

    def apply(self, angles, distances):
        """Return boolean mask: True for valid points within detection zone."""
        valid_dist = (distances > self.min_dist_mm) & (distances < self.max_dist_mm)
        valid_angle = (angles >= self.min_angle_rad) & (angles <= self.max_angle_rad)
        valid_reading = distances > 0
        return valid_dist & valid_angle & valid_reading
