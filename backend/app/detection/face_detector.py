"""Face detection module for FastAPI."""
import numpy as np
import cv2
from pathlib import Path
from ultralytics import YOLO

from app.config import CONFIDENCE_THRESHOLD, DEVICE, FACE_MODEL_PATH, INFERENCE_SIZE


class FaceDetector:
    """Face detector using YOLO face model."""
    
    def __init__(self):
        self.model = None
        self.is_loaded = False
        
        if FACE_MODEL_PATH and Path(FACE_MODEL_PATH).exists():
            try:
                self.model = YOLO(FACE_MODEL_PATH)
                self.is_loaded = True
                print(f"[SUCCESS] Face detector model loaded: {FACE_MODEL_PATH}")
                self._warm_up()
            except Exception as e:
                print(f"[ERROR] Failed to load face detector: {e}")
        else:
            print(f"[INFO] Face model not found at {FACE_MODEL_PATH}. Face detection DISABLED.")

    def _warm_up(self):
        """Pay the one-time CPU graph setup cost during service startup."""
        try:
            sample = np.zeros((480, 640, 3), dtype=np.uint8)
            self.model.predict(
                source=sample,
                conf=CONFIDENCE_THRESHOLD,
                imgsz=INFERENCE_SIZE,
                device=DEVICE,
                max_det=20,
                verbose=False,
            )
            print("[READY] Face detector warmed up for live inference.")
        except Exception as error:
            print(f"[WARN] Face detector warm-up skipped: {error}")
    
    def detect(self, image, conf_threshold=CONFIDENCE_THRESHOLD):
        """Detect faces in an image.
        
        Args:
            image: numpy array (OpenCV image)
            conf_threshold: Confidence threshold for detections
        
        Returns:
            Tuple of (detections list, inference_time in seconds)
        """
        if not self.is_loaded or self.model is None:
            return [], 0.0
        
        start_time = cv2.getTickCount()
        
        try:
            results = self.model.predict(
                source=image,
                conf=conf_threshold,
                imgsz=INFERENCE_SIZE,
                device=DEVICE,
                max_det=20,
                verbose=False,
            )
        except Exception as e:
            print(f"[WARN] Face detection inference error: {e}")
            return [], 0.0
        
        inference_time = (cv2.getTickCount() - start_time) / cv2.getTickFrequency()
        
        detections = []
        
        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    class_name = self.model.names[cls_id]
                    track_id = int(box.id[0]) if box.id is not None else None
                    
                    detections.append({
                        "class": class_name,
                        "confidence": conf,
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "tracking_id": track_id
                    })
        
        return detections, inference_time


# Create singleton instance
face_detector = FaceDetector()
