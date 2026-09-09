"""Phase 4: YOLO Face Detection on Image"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import time
from pathlib import Path
from ultralytics import YOLO
from legacy.config import CONFIDENCE_THRESHOLD


def load_face_model(model_path):
    """Load the YOLO face detection model."""
    if not Path(model_path).exists():
        raise FileNotFoundError(f"Face model not found: {model_path}")
    
    model = YOLO(model_path)
    print(f"[SUCCESS] Face model loaded: {model_path}")
    print(f"[INFO] Model task: {model.task}")
    print(f"[INFO] Class names: {model.names}")
    
    return model


def detect_faces(image_path, model, conf_threshold=0.50):
    """Run face detection on a single image."""
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot load image: {image_path}")
    
    # Run inference
    start_time = time.time()
    results = model(img, conf=conf_threshold)
    inference_time = time.time() - start_time
    
    detections = []
    
    for r in results:
        boxes = r.boxes
        for box in boxes:
            # Get bounding box coordinates
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            class_name = model.names[cls_id]
            
            detections.append({
                "class": class_name,
                "confidence": conf,
                "bbox": [int(x1), int(y1), int(x2), int(y2)]
            })
    
    print(f"[INFO] Detections: {len(detections)}")
    print(f"[INFO] Inference time: {inference_time*1000:.1f} ms")
    
    for det in detections:
        print(f"  - {det['class']} confidence={det['confidence']:.2f} bbox={det['bbox']}")
    
    return detections, inference_time


def draw_detections(image, detections):
    """Draw bounding boxes and labels on image."""
    output = image.copy()
    
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        class_name = det["class"]
        confidence = det["confidence"]
        
        # Draw rectangle
        cv2.rectangle(output, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        
        # Draw label background
        label = f"{class_name} {confidence:.2f}"
        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(output, (int(x1), int(y1) - label_h - 10), (int(x1) + label_w, int(y1)), (0, 255, 0), -1)
        
        # Draw label text
        cv2.putText(output, label, (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    return output


def test_face_detection():
    """Test face detection on the sample image."""
    model_path = "/home/atik-pathan/Desktop/project/pixel-intelligence/backend/yolov8m-face.pt"
    image_path = "/home/atik-pathan/Desktop/project/pixel-intelligence/backend/test.jpeg"
    
    # Load model
    model = load_face_model(model_path)
    
    # Detect faces
    detections, inference_time = detect_faces(image_path, model, CONFIDENCE_THRESHOLD)
    
    # Load image for drawing
    img = cv2.imread(str(image_path))
    output = draw_detections(img, detections)
    
    # Save output
    output_path = "/tmp/phase4_face_detection.jpg"
    cv2.imwrite(output_path, output)
    print(f"[SUCCESS] Output saved to: {output_path}")
    
    return len(detections)


if __name__ == "__main__":
    test_face_detection()