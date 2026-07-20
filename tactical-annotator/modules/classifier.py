import numpy as np
import cv2
from sklearn.cluster import KMeans

class TeamClassifier:
    def __init__(self, n_clusters: int = 3):
        self.n_clusters = n_clusters
        self.kmeans = None
        self.cluster_to_team = {}

    def _crop_jersey(self, frame, bbox):
        """Crop the top 40% of the bounding box (jersey region)."""
        x1, y1, x2, y2 = bbox
        # Convert to integers for array slicing
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        h = y2 - y1
        # Take the top 40% of the height
        y2_ = int(y1 + 0.4 * h)
        return frame[y1:y2_, x1:x2]

    def _get_mean_hsv(self, crop):
        """Convert crop to HSV, resize to 10x10, compute mean HSV."""
        if crop.size == 0:
            return np.zeros(3)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        resized = cv2.resize(hsv, (10, 10), interpolation=cv2.INTER_AREA)
        return np.mean(resized, axis=(0, 1))

    def fit(self, frame, detections_xyxy):
        """Fit KMeans on jersey regions from detections."""
        # Filter out detections that are too small
        valid_crops = []
        for bbox in detections_xyxy:
            x1, y1, x2, y2 = bbox
            w = x2 - x1
            h = y2 - y1
            if w < 20 or h < 20:
                continue
            crop = self._crop_jersey(frame, bbox)
            if crop.size == 0:
                continue
            mean_hsv = self._get_mean_hsv(crop)
            valid_crops.append(mean_hsv)

        if len(valid_crops) < 3:
            # Not enough samples to fit
            return

        X = np.array(valid_crops)
        self.kmeans = KMeans(n_clusters=self.n_clusters, random_state=42, n_init=10)
        self.kmeans.fit(X)

    def predict(self, frame, bbox):
        """Predict team for a bounding box."""
        if self.kmeans is None:
            return -1
        x1, y1, x2, y2 = bbox
        w = x2 - x1
        h = y2 - y1
        if w < 20 or h < 20:
            return -1
        crop = self._crop_jersey(frame, bbox)
        if crop.size == 0:
            return -1
        mean_hsv = self._get_mean_hsv(crop)
        cluster = self.kmeans.predict([mean_hsv])[0]
        return self.cluster_to_team.get(cluster, -1)

    def set_cluster_map(self, mapping):
        """Set the cluster to team mapping."""
        self.cluster_to_team = mapping