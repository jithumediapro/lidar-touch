import math
import numpy as np
from dataclasses import dataclass, field


@dataclass
class TrackedTouch:
    session_id: int
    centroid_xy: tuple  # (x_mm, y_mm)
    velocity_xy: tuple = (0.0, 0.0)  # mm/s
    normalized_pos: tuple = (0.0, 0.0)  # 0..1 range for TUIO
    age_frames: int = 1
    num_points: int = 0


class _Track:
    """Internal track state."""

    def __init__(self, session_id, centroid_xy, num_points):
        self.session_id = session_id
        self.centroid_xy = centroid_xy
        self.velocity_xy = (0.0, 0.0)
        self.num_points = num_points
        self.age_frames = 1
        self.frames_unseen = 0


class BlobTracker:
    """Greedy nearest-neighbor blob tracker with persistent session IDs."""

    def __init__(self, max_distance_mm=50.0, timeout_frames=3, min_age_frames=1):
        self.max_distance_mm = max_distance_mm
        self.timeout_frames = timeout_frames
        self.min_age_frames = min_age_frames
        self._tracks = []
        self._next_id = 1

    def _alloc_id(self):
        sid = self._next_id
        self._next_id += 1
        return sid

    @staticmethod
    def _distance(a, b):
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        return math.sqrt(dx * dx + dy * dy)

    def update(self, blobs, dt):
        """
        Match new blobs to existing tracks using greedy nearest-neighbor.
        Returns list of active TrackedTouch.
        """
        if dt <= 0:
            dt = 0.025  # Default ~40Hz

        # Build cost pairs
        pairs = []
        for ti, track in enumerate(self._tracks):
            # Predict position using velocity
            pred_x = track.centroid_xy[0] + track.velocity_xy[0] * dt
            pred_y = track.centroid_xy[1] + track.velocity_xy[1] * dt
            for bi, blob in enumerate(blobs):
                dist = self._distance((pred_x, pred_y), blob.centroid_xy)
                if dist <= self.max_distance_mm:
                    pairs.append((dist, ti, bi))

        # Sort by distance ascending
        pairs.sort(key=lambda x: x[0])

        # Greedy assignment
        matched_tracks = set()
        matched_blobs = set()
        assignments = {}  # track_idx -> blob_idx

        for dist, ti, bi in pairs:
            if ti not in matched_tracks and bi not in matched_blobs:
                assignments[ti] = bi
                matched_tracks.add(ti)
                matched_blobs.add(bi)

        # Update matched tracks
        for ti, bi in assignments.items():
            track = self._tracks[ti]
            blob = blobs[bi]
            old_xy = track.centroid_xy
            new_xy = blob.centroid_xy

            # Compute velocity
            vx = (new_xy[0] - old_xy[0]) / dt
            vy = (new_xy[1] - old_xy[1]) / dt

            track.centroid_xy = new_xy
            track.velocity_xy = (vx, vy)
            track.num_points = blob.num_points
            track.age_frames += 1
            track.frames_unseen = 0

        # Age unmatched existing tracks (before adding new ones)
        num_existing = len(self._tracks)
        for ti in range(num_existing):
            if ti not in matched_tracks:
                self._tracks[ti].frames_unseen += 1

        # Create new tracks for unmatched blobs
        for bi, blob in enumerate(blobs):
            if bi not in matched_blobs:
                track = _Track(
                    session_id=self._alloc_id(),
                    centroid_xy=blob.centroid_xy,
                    num_points=blob.num_points,
                )
                self._tracks.append(track)

        # Remove timed-out tracks
        self._tracks = [
            t for t in self._tracks if t.frames_unseen <= self.timeout_frames
        ]

        # Build output (only emit touches that have been alive long enough)
        result = []
        for track in self._tracks:
            if track.frames_unseen == 0 and track.age_frames >= self.min_age_frames:
                result.append(TrackedTouch(
                    session_id=track.session_id,
                    centroid_xy=track.centroid_xy,
                    velocity_xy=track.velocity_xy,
                    age_frames=track.age_frames,
                    num_points=track.num_points,
                ))
        return result

    def reset(self):
        self._tracks = []
        self._next_id = 1
