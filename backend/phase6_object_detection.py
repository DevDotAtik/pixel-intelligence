"""Phase 6: Object Detection Addition"""
import cv2
import time
from pathlib import Path
from ultralytics import YOLO

from config import (
    FACE_MODEL_PATH, OBJECT_MODEL_PATH, PLATE_MODEL_PATH,
    CONFIDENCE_THRESHOLD, VEHICLE_CLASSES, DEVICE
)


def load_model(model_path, model_name):
    """Load a YOLO model with validation."""
    if not model_path or not Path(model_path).exists():
        print(f"[INFO] {model_name} model not found at {model_path}. {model_name} detection DISABLED.")
        return None
    
    try:
        model = YOLO(model_path)
        print(f"[SUCCESS] {model_name} model loaded: {model_path}")
        print(f"[INFO] {model_name} class names: {model.names}")
        return model
    except Exception as e:
        print(f"[ERROR] Failed to load {model_name} model: {e}")
        return None


def get_model_class_names(model):
    """Get class names from a loaded model, handling different formats."""
    if model is None:
        return {}
    try:
        return model.names
    except Exception:
        return {}


def detect_objects_in_frame(frame, model, conf_threshold):
    """Run object detection on a single frame."""
    if model is None:
        return [], 0
    
    start_time = time.time()
    results = model(frame, conf=conf_threshold)
    inference_time = time.time() - start_time
    
    detections = []
    
    for r in results:
        boxes = r.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            class_name = model.names[cls_id]
            
            detections.append({
                "class": class_name,
                "confidence": conf,
                "bbox": [int(x1), int(y1), int(x2), int(y2)]
            })
    
    return detections, inference_time


def filter_vehicle_detections(detections, vehicle_classes, model_names):
    """Filter detections to only include vehicle classes that exist in the model."""
    if not model_names:
        return []
    
    # Build a set of lowercase class names that exist in the model
    model_class_set = {k.lower() for k in model_names.keys()}
    
    vehicle_detections = []
    counts = {cls: 0 for cls in vehicle_classes}
    
    for det in detections:
        class_name = det["class"].lower()
        # Check if this class is in the vehicle classes list AND exists in the model
        if class_name in vehicle_classes and class_name in model_class_set:
            vehicle_detections.append(det)
            counts[class_name] += 1
    
    return vehicle_detections, counts


def draw_detections(frame, detections, show_confidence=True):
    """Draw bounding boxes and labels on frame."""
    output = frame.copy()
    
    color_map = {
        "face": (0, 255, 0),       # green
        "person": (255, 0, 0),     # blue
        "car": (0, 0, 255),        # red
        "truck": (0, 0, 255),
        "bus": (0, 0, 255),
        "motorcycle": (255, 0, 255), # magenta
        "bicycle": (255, 0, 255),
    }
    
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        class_name = det["class"]
        confidence = det["confidence"]
        
        color = color_map.get(class_name, (128, 128, 128))
        
        # Draw rectangle
        cv2.rectangle(output, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        
        # Draw label
        label = class_name
        if show_confidence:
            label = f"{class_name} {confidence:.2f}"
        
        # Get text size for background
        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        
        # Draw label background rectangle
        cv2.rectangle(output, 
                      (int(x1), int(y1) - label_h - 8), 
                      (int(x1) + label_w, int(y1)), 
                      color, -1)
        
        # Draw label text
        cv2.putText(output, label, (int(x1), int(y1) - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return output


def test_object_detection():
    """Test object detection on sample image."""
    print("=" * 60)
    print("OBJECT DETECTION TEST")
    print("=" * 60)
    
    # Load face model
    face_model = load_model(FACE_MODEL_PATH, "Face")
    
    # Load object model
    object_model = load_model(OBJECT_MODEL_PATH, "Object")
    
    # Check if object model has vehicle classes
    if object_model:
        object_class_names = get_model_class_names(object_model)
        print(f"[INFO] Object model classes: {object_class_names}")
    
    # Load plate model (expected to be missing)
    plate_model = load_model(PLATE_MODEL_PATH, "Plate")
    
    print()
    
    # Test on sample image
    image_path = "/home/atik-pathan/Desktop/project/pixel-intelligence/backend/test.jpeg"
    
    if face_model:
        print(f"[INFO] Running face detection on: {image_path}")
        img = cv2.imread(str(image_path))
        if img is not None:
            detections, inference_time = detect_objects_in_frame(img, face_model, CONFIDENCE_THRESHOLD)
            face_dets = [d for d in detections if d["class"] == "face"]
            print(f"[FACE DETECTION] Found {len(face_dets)} face(s)")
            for d in face_dets:
                print(f"  - {d['class']} conf={d['confidence']:.2f} bbox={d['bbox']}")
    
    if object_model:
        print(f"[INFO] Running object detection on: {image_path}")
        img = cv2.imread(str(image_path))
        if img is not None:
            detections, inference_time = detect_objects_in_frame(img, object_model, CONFIDENCE_THRESHOLD)
            print(f"[OBJECT DETECTION] Found {len(detections)} object(s)")
            for d in detections:
                print(f"  - {d['class']} conf={d['confidence']:.2f} bbox={d['bbox']}")
    
    if plate_model is None:
        print("[INFO] Plate model not available - plate detection will be disabled")
    
    print()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_object_detection()