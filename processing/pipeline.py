import time
import queue
from dataclasses import dataclass, field

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot

from processing.filtering import ScanFilter
from processing.background import BackgroundModel
from processing.clustering import BlobDetector
from processing.tracking import BlobTracker, TrackedTouch
from processing.coordinate_mapper import CoordinateMapper


@dataclass
class FrameResult:
    timestamp: float = 0.0
    raw_angles: np.ndarray = field(default_factory=lambda: np.array([]))
    raw_distances: np.ndarray = field(default_factory=lambda: np.array([]))
    filtered_mask: np.ndarray = field(default_factory=lambda: np.array([], dtype=bool))
    foreground_mask: np.ndarray = field(default_factory=lambda: np.array([], dtype=bool))
    foreground_points_xy: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))
    cluster_labels: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))
    touches: list = field(default_factory=list)
    bg_learning_progress: float = 0.0
    bg_is_learned: bool = False
    processing_time_ms: float = 0.0
    frame_seq: int = 0
    sensor_index: int = 0


class ProcessingPipeline(QThread):
    """Chains all processing stages: Filter -> Background -> Cluster -> Track.

    Emits raw mm-coordinate touches. Normalization and screen filtering
    are handled by the TouchRouter.
    """

    frame_processed = pyqtSignal(object)  # FrameResult
    touches_updated = pyqtSignal(object, int, int)  # list[TrackedTouch], sensor_index, frame_seq
    learning_progress = pyqtSignal(float)  # 0.0 to 1.0

    def __init__(self, settings, sensor_index=0, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._sensor_index = sensor_index
        self._queue = queue.Queue(maxsize=2)
        self._running = False
        self._frame_seq = 0
        self._last_timestamp = 0.0
        self._learn_requested = False
        self._reset_requested = False

        # Processing components — read per-sensor settings
        sensor = settings.get_sensor(sensor_index) or {}
        snap = settings.get_snapshot()

        self._filter = ScanFilter(
            min_dist_mm=sensor.get('min_distance_mm', 20.0),
            max_dist_mm=sensor.get('max_distance_mm', 1500.0),
            min_angle_deg=sensor.get('min_angle_deg', -90.0),
            max_angle_deg=sensor.get('max_angle_deg', 90.0),
        )
        self._background = BackgroundModel(
            num_learning_frames=snap['bg_learning_frames'],
            threshold_mm=snap['bg_subtraction_threshold_mm'],
        )
        self._detector = BlobDetector(
            eps_mm=snap['cluster_eps_mm'],
            min_samples=snap['cluster_min_samples'],
            min_cluster_size=snap['min_cluster_size'],
        )
        self._tracker = BlobTracker(
            max_distance_mm=snap['max_tracking_distance_mm'],
            timeout_frames=snap['touch_timeout_frames'],
        )

    @pyqtSlot(float, object, object)
    def enqueue_scan(self, timestamp, angles, distances):
        """Slot connected to scanner's scan_ready signal."""
        try:
            # Drop oldest if full
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
            self._queue.put_nowait((timestamp, angles, distances))
        except queue.Full:
            pass

    def start_learning(self):
        self._learn_requested = True

    def reset_background(self):
        self._reset_requested = True

    def _sync_settings(self):
        """Read current settings and update processing components."""
        sensor = self._settings.get_sensor(self._sensor_index) or {}
        snap = self._settings.get_snapshot()

        self._filter.update_params(
            min_dist_mm=sensor.get('min_distance_mm', 20.0),
            max_dist_mm=sensor.get('max_distance_mm', 1500.0),
            min_angle_deg=sensor.get('min_angle_deg', -90.0),
            max_angle_deg=sensor.get('max_angle_deg', 90.0),
        )
        self._background.threshold = snap['bg_subtraction_threshold_mm']
        self._background.num_frames = snap['bg_learning_frames']
        self._detector.update_params(
            eps_mm=snap['cluster_eps_mm'],
            min_samples=snap['cluster_min_samples'],
            min_cluster_size=snap['min_cluster_size'],
        )
        self._tracker.max_distance_mm = snap['max_tracking_distance_mm']
        self._tracker.timeout_frames = snap['touch_timeout_frames']

    def run(self):
        self._running = True
        # Auto-learn background on start
        self._learn_requested = True

        while self._running:
            try:
                data = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            proc_start = time.monotonic()
            timestamp, angles, distances = data

            # Handle background learn/reset requests
            if self._reset_requested:
                self._background.reset()
                self._tracker.reset()
                self._reset_requested = False

            if self._learn_requested:
                self._background.start_learning()
                self._learn_requested = False

            # Sync settings from GUI
            self._sync_settings()

            # Compute dt
            dt = timestamp - self._last_timestamp if self._last_timestamp > 0 else 0.025
            self._last_timestamp = timestamp

            # 1. Filter
            filtered_mask = self._filter.apply(angles, distances)

            # 2. Background learning or subtraction
            foreground_mask = np.zeros(len(distances), dtype=bool)
            if self._background.is_learning:
                done = self._background.feed_learning_frame(angles, distances)
                self.learning_progress.emit(self._background.learning_progress)
            elif self._background.is_learned:
                # Apply foreground detection only on filtered points
                bg_mask = self._background.subtract(angles, distances)
                foreground_mask = filtered_mask & bg_mask

            # 3. Convert foreground to Cartesian
            fg_indices = np.where(foreground_mask)[0]
            if len(fg_indices) > 0:
                fg_angles = angles[fg_indices]
                fg_distances = distances[fg_indices]
                fg_points_xy = CoordinateMapper.polar_to_cartesian(fg_angles, fg_distances)
            else:
                fg_points_xy = np.empty((0, 2))

            # 4. Cluster
            blobs = self._detector.detect(fg_points_xy)

            # 5. Track
            touches = self._tracker.update(blobs, dt)

            # Build cluster labels for visualization
            cluster_labels = np.full(len(fg_points_xy), -1, dtype=int)
            for i, blob in enumerate(blobs):
                cluster_labels[blob.point_indices] = i

            proc_time = (time.monotonic() - proc_start) * 1000.0

            # Build frame result
            self._frame_seq += 1
            result = FrameResult(
                timestamp=timestamp,
                raw_angles=angles,
                raw_distances=distances,
                filtered_mask=filtered_mask,
                foreground_mask=foreground_mask,
                foreground_points_xy=fg_points_xy,
                cluster_labels=cluster_labels,
                touches=touches,
                bg_learning_progress=self._background.learning_progress,
                bg_is_learned=self._background.is_learned,
                processing_time_ms=proc_time,
                frame_seq=self._frame_seq,
                sensor_index=self._sensor_index,
            )

            self.frame_processed.emit(result)

            # Emit raw mm-coordinate touches + sensor_index (routing done by TouchRouter)
            self.touches_updated.emit(touches, self._sensor_index, self._frame_seq)

    def stop(self):
        self._running = False
        self.wait(2000)
