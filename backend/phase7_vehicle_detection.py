"""Phase 7: Vehicle Detection - simplified and robust"""
import cv2
import time
from pathlib import Path
from ultralytics import YOLO

from config import (
    FACE_MODEL_PATH, OBJECT_MODEL_PATH, PLATE_MODEL_PATH,
    CONFIDENCE_THRESHOLD, VEHICLE_CLASSES, DEVICE
)


def load_model_safe(model_path, model_name):
    """Load a YOLO model, returning None if not found or error."""
    if not model_path or not Path(model_path).exists():
        print(f"[INFO] {model_name} model not found at {model_path}. {model_name} DISABLED.")
        return None
    
    try:
        model = YOLO(model_path)
        print(f"[SUCCESS] {model_name} model loaded: {model_path}")
        return model
    except Exception as e:
        print(f"[ERROR] Failed to load {model_name} model: {e}")
        return None


def get_model_class_info(model):
    """Get class name mapping from a loaded model."""
    if model is None:
        return {}, {}
    
    # Handle different model naming formats
    names = model.names
    # Convert all keys to strings for consistent handling
    class_names = {str(k): v for k, v in names.items()}
    
    # Build lowercase lookup
    class_lower_lookup = {str(k).lower(): str(v).lower() for k, v in names.items()}
    
    return class_names, class_lower_lookup


def detect_objects_in_frame(frame, model, conf_threshold):
    """Run object detection on a single frame."""
    if model is None: return [], 0
    
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
            
            # Normalize class name to string for consistent handling
            class_name_str = str(class_name).lower()
            
            detections.append({
                "class": class_name_str,
                "class_original": str(class_name),
                "confidence": conf,
                "bbox": [int(x1), int(y1), int(x2), int(y2)]
            })
    
    return detections, inference_time


def count_vehicles_by_classes(detections, class_lower_lookup, vehicle_classes_requested):
    """Count vehicles from detections based on model classes and requested vehicle classes."""
    # Build set of vehicle class names that exist in THIS model
    vehicle_classes_available = set()
    
    for requested_cls in vehicle_classes_requested:
        requested_lower = requested_cls.lower()
        # Check if this vehicle class exists in the model's classes
        for model_cls_lower in class_lower_lookup.keys():
            if requested_lower == model_cls_lower:
                vehicle_classes_available.add(requested_cls)
                break
    
    # Count detections per available vehicle class
    counts = {cls: 0 for cls in vehicle_classes_available}
    
    for det in detections:
        cls = det["class"]
        if cls in vehicle_classes_available:
            counts[cls] += 1
    
    total_vehicles = sum(counts.values())
    
    return counts, total_vehicles


def draw_vehicle_info(frame, vehicle_counts, total_vehicles, position=(15, 35)):
    """Draw vehicle counting information on frame."""
    output = frame.copy()
    
    # Draw background panel
    cv2.rectangle(output, (10, 10), (450, 120), (0, 0, 0), -1)
    cv2.addWeighted(output, 0.3, frame, 0.7, 0, frame)
    
    # Title
    cv2.putText(output, "VEHICLE DETECTION", (15, 35), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    
    # Vehicle counts
    y = 70
    for cls, count in vehicle_counts.items():
        # Capitalize first letter
        display_name = cls.capitalize()
        color = (255, 255, 255)  # default white
        
        cv2.putText(output, f"{display_name}: {count}", (15, y), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        y += 30
    
    # Total
    cv2.putText(output, f"Total Vehicles: {total_vehicles}", (15, y + 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    return frame


def test_vehicle_detection():
    """Test vehicle detection with available models."""
    print("=" * 60)
    print("VEHICLE DETECTION TEST")
    print("=" * 60)
    
    # Load face model
    face_model = load_model_safe(FACE_MODEL_PATH, "Face")
    
    # Load object model
    object_model = load_model_safe(OBJECT_MODEL_PATH, "Object")
    
    # Get model class info
    if object_model:
        class_names, class_lower_lookup = get_model_class_info(object_model)
        print(f"[INFO] Object model class info:")
        print(f"  - Class names: {class_names}")
        print(f"  - Lower lookup keys: {list(class_lower_lookup.keys())[:10]}")
    
    # Load plate model (expected to be missing)
    plate_model = load_model_safe(PLATE_MODEL_PATH, "Plate")
    
    print()
    
    # Test on sample image
    image_path = "/home/atik-pathan/Desktop/project/pixel-intelligence/backend/test.jpeg"
    
    if face_model:
        print(f"[INFO] Running face detection on: {image_path}")
        img = cv2.imread(str(image_path))
        if img is not None:
            detections, inference_time = detect_objects_in_frame(img, face_model, CONFIDENCE_THRESHOLD)
            print(f"[FACE DETECTION] Found {len(detections)} detection(s)")
            for d in detections:
                print(f"  - {d['class_original']} (lower: {d['class']}) conf={d['confidence']:.2f}")
    
    if object_model:
        print(f"[INFO] Running object detection on: {image_path}")
        img = cv2.imread(str(image_path))
        if img is not None:
            detections, inference_time = detect_objects_in_frame(img, object_model, CONFIDENCE_THRESHOLD)
            print(f"[OBJECT DETECTION] Found {len(detections)} detection(s)")
            
            for d in detections:
                print(f"  - {d['class_original']} (lower: {d['class']}) conf={d['confidence']:.2f}")
            
            # Count vehicles based on available classes
            vehicle_counts, total_vehicles = count_vehicles_by_classes(
                detections, class_lower_lookup, VEHICLE_CLASSES
            )
            print(f"[VEHICLE COUNT] Total: {total_vehicles}")
            for cls, count in vehicle_counts.items():
                print(f"  - {cls.capitalize()}: {count}")
    
    if plate_model is None:
        print("[INFO] Plate model not available - plate detection will be disabled (as expected)")
    
    # Draw vehicle info on image
    if object_model:
        img = cv2.imread(str(image_path))
        if img is not None:
            detections, inference_time = detect_objects_in_frame(img, object_model, CONFIDENCE_THRESHOLD)
            output = draw_vehicle_info(img, vehicle_counts, total_vehicles)
            output_path = "/tmp/phase7_vehicle_output.jpg"
            cv2.imwrite(output_path, output)
            print(f"[SUCCESS] Output saved to: {output_path}")
    
    print()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_vehicle_detection()