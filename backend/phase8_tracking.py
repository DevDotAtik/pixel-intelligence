"""Phase 8: Object Tracking - headless compatible"""
import cv2
import time
from pathlib import Path
from ultralytics import YOLO

from config import (
    FACE_MODEL_PATH, OBJECT_MODEL_PATH, PLATE_MODEL_PATH,
    CONFIDENCE_THRESHOLD, DEVICE
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


def detect_and_track(frame, face_model, object_model, conf_threshold):
    """Run detection and tracking on a single frame.
    
    Returns detections with tracking IDs.
    """
    detections_with_ids = []
    
    # Run face detection with tracking if face model exists
    if face_model:
        try:
            face_results = face_model.track(frame, conf=conf_threshold, persist=True, device=DEVICE)
            for r in face_results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        class_name = face_model.names[cls_id]
                        track_id = int(box.id[0]) if box.id is not None else None
                        
                        detections_with_ids.append({
                            "source": "face",
                            "class": class_name,
                            "confidence": conf,
                            "bbox": [int(x1), int(y1), int(x2), int(y2)],
                            "tracking_id": track_id
                        })
        except Exception as e:
            print(f"[WARN] Face tracking error: {e}")
    
    # Run object detection with tracking if object model exists
    if object_model:
        try:
            obj_results = object_model.track(frame, conf=conf_threshold, persist=True, device=DEVICE)
            for r in obj_results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        class_name = object_model.names[cls_id]
                        track_id = int(box.id[0]) if box.id is not None else None
                        
                        detections_with_ids.append({
                            "source": "object",
                            "class": class_name,
                            "confidence": conf,
                            "bbox": [int(x1), int(y1), int(x2), int(y2)],
                            "tracking_id": track_id
                        })
        except Exception as e:
            print(f"[WARN] Object tracking error: {e}")
    
    return detections_with_ids


def count_current_objects(detections):
    """Count currently visible objects (based on current frame detections)."""
    # Group by class, count unique tracking IDs per class
    counts = {}
    tracking_ids_per_class = {}
    
    for det in detections:
        cls = det["class"]
        tid = det.get("tracking_id")
        
        if cls not in counts:
            counts[cls] = 0
            tracking_ids_per_class[cls] = set()
        
        counts[cls] += 1
        if tid is not None:
            tracking_ids_per_class[cls].add(tid)
    
    # Return current count (total detections) and unique ID count
    unique_counts = {}
    for cls in counts:
        unique_counts[cls] = len(tracking_ids_per_class.get(cls, set()))
    
    return counts, unique_counts


def count_unique_events(detections, previous_tracking_ids):
    """Count unique detection events based on tracking IDs.
    
    Returns the number of new/different tracking IDs seen.
    """
    current_ids = set()
    new_ids = set()
    
    for det in detections:
        tid = det.get("tracking_id")
        if tid is not None:
            current_ids.add(tid)
    
    # New IDs are those we haven't seen before
    for tid in current_ids:
        if tid not in previous_tracking_ids:
            new_ids.add(tid)
    
    # Update previous tracking IDs
    previous_tracking_ids.clear()
    previous_tracking_ids.update(current_ids)
    
    return len(new_ids), len(current_ids)


def draw_tracking_overlay(frame, detections, unique_event_count, current_counts):
    """Draw tracking and counting information on frame.
    
    Returns the frame with overlay drawn. In headless mode, this just returns
    the original frame with detections counted.
    """
    output = frame.copy()
    
    # Try to draw - will work if GUI is available
    try:
        # Draw background panel
        cv2.rectangle(output, (10, 10), (500, 180), (0, 0, 0), -1)
        cv2.addWeighted(output, 0.3, frame, 0.7, 0, frame)
        
        # Title
        cv2.putText(output, "OBJECT TRACKING", (15, 35), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Current counts
        y = 70
        for cls, count in current_counts.items():
            display_name = cls.capitalize() if cls else "Unknown"
            cv2.putText(output, f"Current {display_name}: {count}", (15, y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y += 30
        
        # Unique event count
        cv2.putText(output, f"Unique Events: {unique_event_count}", (15, y), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Individual detections with tracking IDs
        y = 155
        for i, det in enumerate(detections[:5]):  # Show max 5 detections
            tid = det.get("tracking_id", "N/A")
            cls = det["class"]
            conf = det["confidence"]
            label = f"ID:{tid} {cls} {conf:.2f}"
            cv2.putText(output, label, (15, y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            y += 25
        
        if len(detections) > 5:
            cv2.putText(output, f"... and {len(detections) - 5} more", (15, y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)
    
    except cv2.error:
        # Headless mode - we'll just track counts internally, no drawing needed
        pass
    
    return output if True else frame  # Always return something useful


def test_tracking_headless():
    """Test tracking in headless mode (no GUI required)."""
    print("=" * 60)
    print("OBJECT TRACKING TEST (HEADLESS MODE)")
    print("=" * 60)
    
    # Load models
    face_model = load_model_safe(FACE_MODEL_PATH, "Face")
    object_model = load_model_safe(OBJECT_MODEL_PATH, "Object")
    
    # Open webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam")
        return
    
    print("[INFO] Starting tracking in headless mode... Press Ctrl+C to stop")
    
    # Tracking state
    previous_tracking_ids = set()
    face_event_count = 0
    vehicle_event_count = 0
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            
            # Detect and track
            detections = detect_and_track(frame, face_model, object_model, CONFIDENCE_THRESHOLD)
            
            # Calculate counts
            current_counts, unique_counts = count_current_objects(detections)
            unique_event_count, _ = count_unique_events(detections, previous_tracking_ids)
            
            # Accumulate event counts
            for det in detections:
                tid = det.get("tracking_id")
                cls = det["class"]
                if cls == "face":
                    face_event_count += 1  # Count each detection as an event
                # Vehicle events would be counted similarly
            
            # Print status every 10 frames
            frame_count += 1
            if frame_count % 10 == 0:
                print(f"[FRAME {frame_count}] Current counts: {unique_counts}")
                print(f"  Unique face events: {face_event_count}")
                print(f"  Unique tracking IDs: {len(previous_tracking_ids)}")
                for det in detections[:3]:
                    tid = det.get("tracking_id", "N/A")
                    print(f"  Detection: ID={tid} class={det['class']} conf={det['confidence']:.2f}")
            
    except KeyboardInterrupt:
        print("[INFO] Stopped by user")
    
    # Release resources
    cap.release()
    print(f"[INFO] Tracking test complete")
    print(f"  Total frames processed: {frame_count}")
    print(f"  Total unique face events: {face_event_count}")
    print(f"  Final unique tracking IDs: {len(previous_tracking_ids)}")


if __name__ == "__main__":
    test_tracking_headless()