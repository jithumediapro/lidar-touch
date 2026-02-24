import numpy as np
from dataclasses import dataclass
from sklearn.cluster import DBSCAN


@dataclass
class DetectedBlob:
    centroid_xy: tuple  # (x_mm, y_mm)
    num_points: int
    point_indices: np.ndarray
    extent_mm: float  # max distance from centroid to any point


class BlobDetector:
    """DBSCAN-based blob detection on Cartesian foreground points."""

    def __init__(self, eps_mm=30.0, min_samples=3, min_cluster_size=3, max_extent_mm=None):
        self.eps_mm = eps_mm
        self.min_samples = min_samples
        self.min_cluster_size = min_cluster_size
        self.max_extent_mm = max_extent_mm

    def update_params(self, eps_mm=None, min_samples=None, min_cluster_size=None, max_extent_mm=None):
        if eps_mm is not None:
            self.eps_mm = eps_mm
        if min_samples is not None:
            self.min_samples = min_samples
        if min_cluster_size is not None:
            self.min_cluster_size = min_cluster_size
        if max_extent_mm is not None:
            self.max_extent_mm = max_extent_mm

    def detect(self, points_xy):
        """
        Cluster foreground points and return detected blobs.

        Args:
            points_xy: Nx2 numpy array of (x, y) in mm

        Returns:
            list of DetectedBlob
        """
        if len(points_xy) < self.min_samples:
            return []

        db = DBSCAN(eps=self.eps_mm, min_samples=self.min_samples)
        labels = db.fit_predict(points_xy)

        blobs = []
        unique_labels = set(labels)
        unique_labels.discard(-1)  # Remove noise label

        for label in unique_labels:
            indices = np.where(labels == label)[0]
            if len(indices) < self.min_cluster_size:
                continue

            cluster_points = points_xy[indices]
            centroid = cluster_points.mean(axis=0)

            # Compute extent (max distance from centroid)
            diffs = cluster_points - centroid
            dists = np.sqrt((diffs ** 2).sum(axis=1))
            extent = float(dists.max())

            # Skip blobs that are too large (e.g. books, hands)
            if self.max_extent_mm is not None and extent > self.max_extent_mm:
                continue

            blobs.append(DetectedBlob(
                centroid_xy=(float(centroid[0]), float(centroid[1])),
                num_points=len(indices),
                point_indices=indices,
                extent_mm=extent,
            ))

        return blobs
