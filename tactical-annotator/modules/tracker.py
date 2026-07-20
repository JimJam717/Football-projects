import supervision as sv

class PlayerTracker:
    def __init__(self, lost_track_buffer: int, min_matching_threshold: float):
        self.tracker = sv.ByteTrack(
            track_activation_threshold=0.25,
            lost_track_buffer=lost_track_buffer,
            minimum_matching_threshold=min_matching_threshold,
            frame_rate=30  # Assuming 30 FPS, but could be made configurable
        )

    def update(self, detections: sv.Detections) -> sv.Detections:
        return self.tracker.update_with_detections(detections)