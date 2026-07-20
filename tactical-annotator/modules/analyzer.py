from collections import deque
from typing import Tuple, List, Optional
import numpy as np

class MovementAnalyzer:
    def __init__(self, history_len: int = 15, run_threshold: float = 8.0):
        self.history_len = history_len
        self.run_threshold = run_threshold
        self.history = {}  # tracker_id -> deque of (x, y)

    def update(self, tracker_id: int, centroid: Tuple[int, int]):
        if tracker_id not in self.history:
            self.history[tracker_id] = deque(maxlen=self.history_len)
        self.history[tracker_id].append(centroid)

    def get_velocity_vector(self, tracker_id: int) -> Optional[Tuple[float, float]]:
        if tracker_id not in self.history or len(self.history[tracker_id]) < 5:
            return None
        pts = self.history[tracker_id]
        # Convert to numpy for easier computation
        pts_array = np.array(list(pts))
        # Oldest to newest
        start = pts_array[0]
        end = pts_array[-1]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        return (float(dx), float(dy))

    def is_running(self, tracker_id: int) -> bool:
        vel = self.get_velocity_vector(tracker_id)
        if vel is None:
            return False
        dx, dy = vel
        return (dx**2 + dy**2) ** 0.5 > self.run_threshold

    def get_run_arrow(self, tracker_id: int, current_pos: Tuple[int, int]) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        if not self.is_running(tracker_id):
            return None
        vel = self.get_velocity_vector(tracker_id)
        if vel is None:
            return None
        dx, dy = vel
        # Scale the velocity vector to get the arrow end point
        scale = 3.0
        end_x = int(current_pos[0] + dx * scale)
        end_y = int(current_pos[1] + dy * scale)
        return (current_pos, (end_x, end_y))