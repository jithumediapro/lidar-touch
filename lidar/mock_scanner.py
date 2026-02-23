import time
import math
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal


class MockLidarScanner(QThread):
    """Simulated UST-10LX scanner for development/testing."""

    scan_ready = pyqtSignal(float, object, object)  # timestamp, angles, distances
    connection_status = pyqtSignal(str)

    NUM_POINTS = 1081
    ANGLE_MIN = math.radians(-135)
    ANGLE_MAX = math.radians(135)
    SCAN_HZ = 40
    WALL_DISTANCE = 1000.0  # mm
    NOISE_SIGMA = 3.0  # mm

    def __init__(self, num_touches=2, parent=None):
        super().__init__(parent)
        self._running = False
        self._num_touches = num_touches

        # Pre-compute fixed angles (matching UST-10LX 270 deg FOV)
        self._angles = np.linspace(self.ANGLE_MIN, self.ANGLE_MAX, self.NUM_POINTS)

        # Touch simulation state
        self._touch_angles = []
        self._touch_speeds = []
        self._touch_widths = []
        self._touch_depths = []
        self._init_touches()

    def _init_touches(self):
        """Initialize random moving touch blobs."""
        rng = np.random.default_rng(42)
        self._touch_angles = []
        self._touch_speeds = []
        self._touch_widths = []
        self._touch_depths = []
        for _ in range(self._num_touches):
            self._touch_angles.append(rng.uniform(-0.5, 0.5))
            self._touch_speeds.append(rng.uniform(0.3, 0.8) * rng.choice([-1, 1]))
            self._touch_widths.append(rng.uniform(0.02, 0.06))  # radians
            self._touch_depths.append(rng.uniform(60, 150))  # mm closer than wall

    def run(self):
        self._running = True
        self.connection_status.emit("mock")
        frame_interval = 1.0 / self.SCAN_HZ
        start_time = time.monotonic()
        frame_count = 0

        while self._running:
            t = time.monotonic() - start_time

            # Base wall with noise
            distances = np.full(self.NUM_POINTS, self.WALL_DISTANCE)
            distances += np.random.normal(0, self.NOISE_SIGMA, self.NUM_POINTS)

            # Add moving touch blobs
            for i in range(self._num_touches):
                # Oscillate touch position
                center = self._touch_angles[i] + 0.4 * math.sin(
                    self._touch_speeds[i] * t
                )
                # Clamp to valid range
                center = max(self.ANGLE_MIN + 0.1, min(self.ANGLE_MAX - 0.1, center))
                width = self._touch_widths[i]
                depth = self._touch_depths[i]

                # Gaussian blob profile
                blob = depth * np.exp(
                    -0.5 * ((self._angles - center) / width) ** 2
                )
                distances -= blob

            # Clamp to valid range
            distances = np.clip(distances, 20.0, 5000.0)

            timestamp = t
            self.scan_ready.emit(timestamp, self._angles.copy(), distances)

            frame_count += 1
            # Sleep to maintain scan rate
            next_time = start_time + frame_count * frame_interval
            sleep_time = next_time - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.connection_status.emit("disconnected")

    def stop(self):
        self._running = False
        self.wait(2000)

    def update_connection(self, ip, port):
        pass  # Mock scanner ignores connection params
