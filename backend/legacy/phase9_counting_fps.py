"""Phase 9: Counting and FPS - comprehensive module"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import time
from pathlib import Path
from ultralytics import YOLO

from legacy.config import (
    FACE_MODEL_PATH, OBJECT_MODEL_PATH, PLATE_MODEL_PATH,
    CONFIDENCE_THRESHOLD, VEHICLE_CLASSES, IMAGE_WIDTH, IMAGE_HEIGHT, DEVICE,
    PROCESS_EVERY_N_FRAMES, CAMERA_INDEX
)


class FaceDetector:
    """Face detection wrapper with tracking support."""
    
    def __init__(self):
        self.model = None
        self.is_loaded = False
        
        if FACE_MODEL_PATH and Path(FACE_MODEL_PATH).exists():
            try:
                self.model = YOLO(FACE_MODEL_PATH)
                self.is_loaded = True
                print(f"[SUCCESS] Face model loaded")
            except Exception as e:
                print(f"[ERROR] Failed to load face model: {e}")
        else:
            print(f"[INFO] Face model not found at {FACE_MODEL_PATH}. Face detection DISABLED.")
    
    def detect(self, frame, conf_threshold=CONFIDENCE_THRESHOLD):
        """Detect faces in a frame. Returns list of detections with tracking IDs."""
        if not self.is_loaded or self.model is None:
            return []
        
        start_time = time.time()
        results = self.model.track(frame, conf=conf_threshold, persist=True, device=DEVICE)
        inference_time = time.time() - start_time
        
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
                        "tracking_id": track_id,
                        "source": "face"
                    })
        
        return detections, inference_time


class ObjectDetector:
    """General object detection wrapper with tracking support."""
    
    def __init__(self):
        self.model = None
        self.is_loaded = False
        self.class_names = {}
        self.class_lower_lookup = {}
        self.vehicle_classes_available = []
        self.vehicle_counts_template = {}
        
        if OBJECT_MODEL_PATH and Path(OBJECT_MODEL_PATH).exists():
            try:
                self.model = YOLO(OBJECT_MODEL_PATH)
                self.is_loaded = True
                # Get class info
                names = self.model.names
                self.class_names = {str(k): v for k, v in names.items()}
                self.class_lower_lookup = {str(k).lower(): str(v).lower() for k, v in names.items()}
                
                # Determine available vehicle classes
                vehicle_classes_requested = [c.lower() for c in VEHICLE_CLASSES]
                for requested_cls in vehicle_classes_requested:
                    for model_cls_lower in self.class_lower_lookup.keys():
                        if requested_cls == model_cls_lower:
                            self.vehicle_classes_available.append(requested_cls.capitalize())
                            break
                
                if not self.vehicle_classes_available:
                    print("[INFO] No requested vehicle classes found in model. Will count all classes.")
                
                print(f"[SUCCESS] Object model loaded, classes: {list(self.class_names.values())}")
            except Exception as e:
                print(f"[ERROR] Failed to load object model: {e}")
        else:
            print(f"[INFO] Object model not found at {OBJECT_MODEL_PATH}. Object detection DISABLED.")
    
    def detect(self, frame, conf_threshold=CONFIDENCE_THRESHOLD):
        """Detect objects in a frame. Returns list of detections with tracking IDs."""
        if not self.is_loaded or self.model is None:
            return []
        
        start_time = time.time()
        results = self.model.track(frame, conf=conf_threshold, persist=True, device=DEVICE)
        inference_time = time.time() - start_time
        
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
                        "tracking_id": track_id,
                        "source": "object"
                    })
        
        return detections, inference_time


class CountingSystem:
    """Counting system that separates current count from event count."""
    
    def __init__(self):
        # Current counts - objects currently visible
        self.current_counts = {}  # e.g., {"face": 2, "person": 1}
        self.unique_tracking_ids_per_class = {}  # e.g., {"face": {1, 2, 3}}
        
        # Event counts - unique detection events
        self.face_events = 0
        self.object_events = 0
        self.total_unique_tracking_ids = set()
        
        # Per-class event tracking
        self.class_event_counts = {}  # e.g., {"face": 8, "person": 12}
        
        # Tracking state across frames
        self.previous_tracking_ids = set()
        self.frame_count = 0
    
    def update(self, detections):
        """Update counting state with new detections from a frame."""
        self.frame_count += 1
        
        # Get current tracking IDs and class counts
        current_counts, unique_counts = self._count_current(detections)
        
        # Update current counts
        self.current_counts = current_counts
        self.unique_tracking_ids_per_class = unique_counts
        
        # Count new unique events
        new_event_count, current_unique_count = self._count_new_events(detections)
        
        # Accumulate event counts
        for cls in new_event_count:
            if cls not in self.class_event_counts:
                self.class_event_counts[cls] = 0
            self.class_event_counts[cls] += new_event_count[cls]
        
        # Update total unique tracking IDs
        self.total_unique_tracking_ids.update(current_unique_count)
        
        # Accumulate per-class event counts
        for det in detections:
            cls = det["class"]
            tid = det.get("tracking_id")
            if tid is not None:
                if cls not in self.class_event_counts:
                    self.class_event_counts[cls] = 0
                self.class_event_counts[cls] += 1
        
        return self.current_counts, self.class_event_counts
    
    def _count_current(self, detections):
        """Count currently visible objects (not accumulated)."""
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
        
        # Return both total count per class and unique ID count per class
        unique_counts = {}
        for cls in counts:
            unique_counts[cls] = len(tracking_ids_per_class.get(cls, set()))
        
        return counts, unique_counts
    
    def _count_new_events(self, detections):
        """Count new unique detection events based on tracking IDs."""
        current_ids = set()
        new_ids = set()
        
        for det in detections:
            tid = det.get("tracking_id")
            if tid is not None:
                current_ids.add(tid)
        
        # New IDs are those we haven't seen in previous frames
        for tid in current_ids:
            if tid not in self.previous_tracking_ids:
                new_ids.add(tid)
        
        # Update previous tracking IDs
        self.previous_tracking_ids.clear()
        self.previous_tracking_ids.update(current_ids)
        
        # Return per-class new event counts
        new_event_count = {}
        for det in detections:
            cls = det["class"]
            tid = det.get("tracking_id")
            if tid is not None and tid in new_ids:
                if cls not in new_event_count:
                    new_event_count[cls] = 0
                new_event_count[cls] += 1
        
        return new_event_count, current_ids
    
    def get_summary(self):
        """Get a summary of current and event counts."""
        return {
            "current_counts": self.current_counts,
            "unique_tracking_ids_per_class": {k: len(v) for k, v in self.unique_tracking_ids_per_class.items()},
            "class_event_counts": self.class_event_counts,
            "total_unique_tracking_ids": len(self.total_unique_tracking_ids)
        }


class FPSCounter:
    """FPS calculator class."""
    
    def __init__(self, process_every_n_frames=1):
        self.process_every_n_frames = process_every_n_frames
        self.frame_counter = 0
        self.fps_start_time = time.time()
        self.fps = 0
        self.inference_times = []
        self.max_inference_samples = 10
    
    def tick(self):
        """Call once per frame."""
        self.frame_counter += 1
    
    def tick_fps(self):
        """Calculate and return FPS. Call once per second."""
        current_time = time.time()
        elapsed = current_time - self.fps_start_time
        
        if elapsed >= 1.0:
            self.fps = self.frame_counter / elapsed
            self.frame_counter = 0
            self.fps_start_time = current_time
        
        return self.fps
    
    def record_inference_time(self, inference_time_ms):
        """Record inference time for a frame."""
        self.inference_times.append(inference_time_ms)
        if len(self.inference_times) > self.max_inference_samples:
            self.inference_times.pop(0)
    
    def get_average_inference_time(self):
        """Get average inference time in ms."""
        if not self.inference_times:
            return 0
        return sum(self.inference_times) / len(self.inference_times)


def run_counting_fps_demo():
    """Run combined counting and FPS demo."""
    print("=" * 60)
    print("PHASE 9: COUNTING AND FPS DEMO")
    print("=" * 60)
    
    # Initialize detectors
    face_detector = FaceDetector()
    object_detector = ObjectDetector()
    
    # Initialize counting system
    counter = CountingSystem()
    
    # Initialize FPS counter
    fps_counter = FPSCounter(PROCESS_EVERY_N_FRAMES)
    
    # Open webcam
    cap = cv2.VideoCapture(CAMERA_INDEX)
    
    if not cap.isOpened():
        print(f"[ERROR] Cannot open webcam with index {CAMERA_INDEX}")
        return
    
    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_HEIGHT)
    
    print(f"[INFO] Starting counting+FPS demo (press Ctrl+C to stop)")
    print(f"[INFO] Resolution: {IMAGE_WIDTH}x{IMAGE_HEIGHT}")
    print(f"[INFO] Process every {PROCESS_EVERY_N_FRAMES} frame(s)")
    
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            
            # Resize frame
            frame = cv2.resize(frame, (IMAGE_WIDTH, IMAGE_HEIGHT))
            
            # Process every Nth frame
            fps_counter.frame_counter += 1
            if fps_counter.frame_counter % PROCESS_EVERY_N_FRAMES != 0:
                # Still update counting state but skip detection
                # Use previous counts
                pass
            else:
                # Run face detection
                face_dets, face_inf_time = face_detector.detect(frame, CONFIDENCE_THRESHOLD)
                
                # Run object detection
                obj_dets, obj_inf_time = object_detector.detect(frame, CONFIDENCE_THRESHOLD)
                
                # Record inference times
                fps_counter.record_inference_time(face_inf_time * 1000)
                fps_counter.record_inference_time(obj_inf_time * 1000)
                
                # Update counting system
                all_dets = face_dets + obj_dets
                counter.update(all_dets)
            
            # Calculate FPS every second
            current_fps = fps_counter.tick_fps()
            
            # Get counting summary
            summary = counter.get_summary()
            
            # Print status every 10 frames
            frame_count += 1
            if frame_count % 10 == 0:
                print(f"[FRAME {frame_count}] FPS: {current_fps:.1f}")
                print(f"  Current: {summary['current_counts']}")
                print(f"  Events: {summary['class_event_counts']}")
                print(f"  Avg inference: {fps_counter.get_average_inference_time():.1f} ms")
            
            # Save sample outputs every 30 frames
            if frame_count % 30 == 0:
                print(f"[SAMPLE] Frame {frame_count}: FPS={current_fps:.1f}, "
                      f"Current counts={summary['current_counts']}, "
                      f"Events={summary['class_event_counts']}")
    
    except KeyboardInterrupt:
        print("[INFO] Stopped by user")
    
    # Release resources
    cap.release()
    
    # Print final summary
    final_summary = counter.get_summary()
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"Total frames processed: {frame_count}")
    print(f"Average FPS: {fps_counter.fps:.1f}" if fps_counter.fps > 0 else "Average FPS: N/A")
    print(f"Average inference time: {fps_counter.get_average_inference_time():.1f} ms")
    print(f"Current counts: {final_summary['current_counts']}")
    print(f"Unique tracking IDs: {final_summary['total_unique_tracking_ids']}")
    print(f"Class event counts: {final_summary['class_event_counts']}")
    print("=" * 60)


if __name__ == "__main__":
    run_counting_fps_demo()