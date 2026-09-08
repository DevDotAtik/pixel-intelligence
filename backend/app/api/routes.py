"""FastAPI routes for detection and analytics."""
from fastapi import APIRouter, File, HTTPException, UploadFile
import numpy as np
import cv2

from app.detection.face_detector import face_detector
from app.detection.object_detector import object_detector
from app.detection.tracker import tracking_manager
from app.analytics.counter import counting_system
from events.event_logger import log_event, get_recent_events, get_event_counts

router = APIRouter()


@router.get("/")
async def root():
    """Root endpoint."""
    from app.config import get_config
    return {
        "message": "AI Video Analytics API",
        "version": "1.0.0",
        "status": "operational",
        "configuration": get_config()
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/models")
async def get_models():
    """Return loaded model information."""
    from app.config import FACE_MODEL_PATH, OBJECT_MODEL_PATH, PLATE_MODEL_PATH
    from pathlib import Path
    
    return {
        "face_model": {
            "exists": Path(FACE_MODEL_PATH).exists() if FACE_MODEL_PATH else False,
            "path": FACE_MODEL_PATH
        },
        "object_model": {
            "exists": Path(OBJECT_MODEL_PATH).exists() if OBJECT_MODEL_PATH else False,
            "path": OBJECT_MODEL_PATH
        },
        "plate_model": {
            "exists": Path(PLATE_MODEL_PATH).exists() if PLATE_MODEL_PATH else False,
            "path": PLATE_MODEL_PATH
        }
    }


@router.get("/events")
async def get_events(limit: int = 50):
    """Get recent detection events."""
    events = get_recent_events(max(1, min(limit, 100)))
    return {"events": events, "count": len(events)}


@router.get("/event-counts")
async def get_event_counts_endpoint():
    """Get event counts by type."""
    counts = get_event_counts()
    return {"counts": counts}


@router.post("/detect")
async def detect_image(image_data: UploadFile = File(...)):
    """Detect objects in an uploaded image.
    
    Accepts an uploaded image in the multipart field ``image_data`` and
    returns detection results with analytics. Django sends each webcam frame
    using this exact field name.
    """
    try:
        if image_data.content_type and not image_data.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="Upload must be an image")

        image_bytes = await image_data.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Uploaded image is empty")

        # Decode image from bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image data")
        
        # Run face detection
        face_dets, face_inf_time = face_detector.detect(img, 0.50)
        
        # The installed object model is only used when it contains a supported
        # general-object class. This avoids running the same face-only model twice.
        obj_dets, obj_inf_time = object_detector.detect(img, 0.50)
        
        # Combine detections
        all_dets = face_dets + obj_dets
        
        # Update tracking and counting
        all_dets = tracking_manager.update(all_dets)
        counting_system.update(all_dets)
        
        # Log events for face and object detections
        for det in face_dets:
            log_event("FACE_DETECTED", det["class"], det["confidence"], det.get("tracking_id"))
        
        for det in obj_dets:
            log_event("OBJECT_DETECTED", det["class"], det["confidence"], det.get("tracking_id"))
        
        # Prepare detection response
        detections = []
        for det in all_dets:
            detections.append({
                "class": det["class"],
                "confidence": det["confidence"],
                "bbox": det["bbox"],
                "tracking_id": det.get("tracking_id")
            })
        
        # Get analytics from counting system
        summary = counting_system.get_summary()
        
        analytics = {
            "face_count": summary["current_counts"].get("face", 0),
            "object_count": summary["current_counts"].get("person", 0) + summary["current_counts"].get("car", 0) + summary["current_counts"].get("truck", 0) + summary["current_counts"].get("bus", 0),
            "total_detections": len(all_dets),
            "unique_events": summary["total_unique_tracking_ids"],
            "class_event_counts": summary["class_event_counts"],
            "inference_ms": round((face_inf_time + obj_inf_time) * 1000, 1),
        }
        
        # Add per-class current counts
        for cls in summary["current_counts"]:
            analytics[f"current_{cls}"] = summary["current_counts"][cls]
        
        # Add per-class event counts
        for cls in summary["class_event_counts"]:
            analytics[f"events_{cls}"] = summary["class_event_counts"][cls]
        
        return {
            "detections": detections,
            "analytics": analytics
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
