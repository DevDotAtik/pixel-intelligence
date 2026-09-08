import cv2
import numpy as np
from ultralytics import YOLO


model = YOLO('./model.pt')

def detect_faces(image_path):
    results = model(image_path)  
    detections = []

    for r in results:
        boxes = r.boxes
        for box in boxes:
            x1,y1,x2,y2 = box.xyxy[0]
            conf = box.conf[0]

            detections.append({
                "bbox": [int(x1),int(y1),int(x2),int(y2)],
                "confidence": float(conf)
            })
            
    return detections