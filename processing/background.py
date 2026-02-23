import numpy as np


class BackgroundModel:
    """Learns background distances and detects foreground objects."""

    def __init__(self, num_learning_frames=30, threshold_mm=40.0):
        self._num_frames = num_learning_frames
        self._threshold = threshold_mm
        self._accumulator = []
        self._background = None
        self._is_learning = False

    @property
    def is_learned(self):
        return self._background is not None

    @property
    def is_learning(self):
        return self._is_learning

    @property
    def learning_progress(self):
        if not self._is_learning:
            return 1.0 if self.is_learned else 0.0
        return len(self._accumulator) / self._num_frames

    @property
    def threshold(self):
        return self._threshold

    @threshold.setter
    def threshold(self, value):
        self._threshold = value

    @property
    def num_frames(self):
        return self._num_frames

    @num_frames.setter
    def num_frames(self, value):
        self._num_frames = max(1, value)

    def start_learning(self):
        self._accumulator = []
        self._background = None
        self._is_learning = True

    def feed_learning_frame(self, angles, distances):
        """Feed a frame during learning. Returns True when learning is complete."""
        if not self._is_learning:
            return False

        self._accumulator.append(distances.copy())

        if len(self._accumulator) >= self._num_frames:
            stacked = np.stack(self._accumulator, axis=0)
            stacked_clean = stacked.astype(np.float64)
            stacked_clean[stacked_clean == 0] = np.nan
            self._background = np.nanmedian(stacked_clean, axis=0)
            self._is_learning = False
            self._accumulator = []
            return True
        return False

    def subtract(self, angles, distances):
        """Return boolean mask: True where object is closer than background."""
        if self._background is None:
            return np.zeros(len(distances), dtype=bool)

        delta = self._background - distances
        foreground = (delta > self._threshold) & (distances > 0)
        return foreground

    def get_background_distances(self):
        """Return learned background array for visualization."""
        return self._background

    def reset(self):
        self._background = None
        self._accumulator = []
        self._is_learning = False
