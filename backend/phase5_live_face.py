"""Phase 5: Live Face Detection (headless compatible)"""
import cv2
import time
from pathlib import Path
from ultralytics import YOLO

from config import (
    FACE_MODEL_PATH, CONFIDENCE_THRESHOLD, CAMERA_INDEX,
    IMAGE_WIDTH, IMAGE_HEIGHT, DEVICE
)


def load_face_model(model_path):
    """Load the YOLO face detection model."""
    if not Path(model_path).exists():
        raise FileNotFoundError(f"Face model not found: {model_path}")
    
    model = YOLO(model_path)
    print(f"[SUCCESS] Face model loaded: {model_path}")
    print(f"[INFO] Model task: {model.task}")
    print(f"[INFO] Class names: {model.names}")
    
    return model


def detect_faces_in_frame(frame, model, conf_threshold):
    """Detect faces in a single frame."""
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


def live_face_detection(headless=True):
    """Live face detection from webcam."""
    # Load face model
    model = load_face_model(FACE_MODEL_PATH)
    
    # Open webcam
    cap = cv2.VideoCapture(CAMERA_INDEX)
    
    if not cap.isOpened():
        print(f"[ERROR] Cannot open webcam with index {CAMERA_INDEX}")
        return
    
    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_HEIGHT)
    
    print(f"[INFO] Starting live face detection (headless={headless})...")
    print("[INFO] Processing frames, press Ctrl+C to stop...")
    
    # FPS tracking
    fps_start_time = time.time()
    fps_frame_count = 0
    face_event_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("[ERROR] Failed to grab frame")
                break
            
            # Resize frame
            frame = cv2.resize(frame, (IMAGE_WIDTH, IMAGE_HEIGHT))
            
            # Detect faces
            detections, inference_time = detect_faces_in_frame(frame, model, CONFIDENCE_THRESHOLD)
            face_count = sum(1 for d in detections if d["class"] == "face")
            
            # Count face events (new detections)
            face_event_count += face_count
            
            # Calculate FPS every second
            fps_frame_count += 1
            if time.time() - fps_start_time >= 1.0:
                fps_now = fps_frame_count / (time.time() - fps_start_time)
                fps_frame_count = 0
                fps_start_time = time.time()
            else:
                fps_now = fps_frame_count / max(time.time() - fps_start_time, 0.001)
            
            # Print status every 5 frames
            if fps_frame_count % 5 == 0:
                print(f"[FRAME] Faces: {face_count}, FPS: {fps_now:.1f}, Inference: {inference_time*1000:.1f}ms, "
                      f"Total face events: {face_event_count}")
            
            # Save sample frame with detections every 15 frames
            if fps_frame_count % 15 == 0 and detections:
                output_path = Path(f"/tmp/phase5_frame_{fps_frame_count}.jpg")
                output = frame.copy()
                for det in detections:
                    x1, y1, x2, y2 = det["bbox"]
                    cv2.rectangle(output, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    label = f"{det['class']} {det['confidence']:.2f}"
                    cv2.putText(output, label, (int(x1), int(y1) - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.imwrite(str(output_path), output)
                print(f"[SAMPLE] Saved frame with {len(detections)} faces to {output_path}")
            
    except KeyboardInterrupt:
        print("[INFO] Stopped by user")
    
    # Release resources
    cap.release()
    print(f"[INFO] Processed frames, total face events: {face_event_count}")


if __name__ == "__main__":
    live_face_detection(headless=True)