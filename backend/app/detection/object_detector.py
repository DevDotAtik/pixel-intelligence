"""Object detection module for FastAPI."""
import cv2
from pathlib import Path
from ultralytics import YOLO

from app.config import FACE_MODEL_PATH, OBJECT_MODEL_PATH


class ObjectDetector:
    """General object detector using YOLO model."""
    
    def __init__(self):
        self.model = None
        self.is_loaded = False
        self.class_names = {}
        self.class_lower_lookup = {}
        self.vehicle_classes_available = []
        self.supports_general_objects = False

        # The compact fallback model is also the configured face model. Do not
        # load it a second time as an object detector on low-resource systems.
        if OBJECT_MODEL_PATH == FACE_MODEL_PATH:
            print("[INFO] Object detector disabled: object and face paths are identical.")
            return
        
        if OBJECT_MODEL_PATH and Path(OBJECT_MODEL_PATH).exists():
            try:
                self.model = YOLO(OBJECT_MODEL_PATH)
                self.is_loaded = True
                # Get class info
                names = self.model.names
                self.class_names = {str(k): v for k, v in names.items()}
                self.class_lower_lookup = {str(k).lower(): str(v).lower() for k, v in names.items()}
                supported_classes = {"person", "car", "truck", "bus", "motorcycle", "bicycle"}
                self.supports_general_objects = bool(set(self.class_lower_lookup.values()) & supported_classes)
                
                print(f"[SUCCESS] Object detector model loaded: {OBJECT_MODEL_PATH}")
                print(f"[INFO] Object classes: {self.class_names}")
                if not self.supports_general_objects:
                    print("[INFO] Object detection DISABLED: model has no supported person/vehicle classes.")
            except Exception as e:
                print(f"[ERROR] Failed to load object detector: {e}")
        else:
            print(f"[INFO] Object model not found at {OBJECT_MODEL_PATH}. Object detection DISABLED.")
    
    def detect(self, image, conf_threshold=0.50):
        """Detect objects in an image.
        
        Args:
            image: numpy array (OpenCV image)
            conf_threshold: Confidence threshold for detections
        
        Returns:
            Tuple of (detections list, inference_time in seconds)
        """
        if not self.is_loaded or self.model is None or not self.supports_general_objects:
            return [], 0.0
        
        start_time = cv2.getTickCount()
        
        try:
            results = self.model(image, conf=conf_threshold)
        except Exception as e:
            print(f"[WARN] Object detection inference error: {e}")
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
                    
                    # Normalize class name to lowercase for consistent handling
                    class_name_lower = str(class_name).lower()
                    
                    detections.append({
                        "class": class_name_lower,
                        "class_original": str(class_name),
                        "confidence": conf,
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "tracking_id": track_id
                    })
        
        return detections, inference_time


# Create singleton instance
object_detector = ObjectDetector()
