from ultralytics import YOLO
import supervision as sv
import numpy as np

class PlayerDetector:
    def __init__(self, model_path: str, conf: float):
        self.model = YOLO(model_path)
        self.conf = conf

    def detect(self, frame: np.ndarray) -> sv.Detections:
        results = self.model(frame, conf=self.conf)[0]
        return sv.Detections.from_ultralytics(results)