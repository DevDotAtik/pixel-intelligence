"""FastAPI routes — detection + analytics + registration + timeline APIs.

Every endpoint lives under ``/api`` and is consumed by the Next.js console and
the Django camera gateway.

Detection selection:
  * ``POST /api/detect?model=face|person|plate`` runs the chosen detector.
    The ``model`` query param mirrors the console's model select box.
  * Responses include a ``model`` key so analytics can show which detector ran.
"""
from __future__ import annotations

import base64
import io
from typing import Any, Optional

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

import app.core.db as db
from app.analytics.counter import counting_system
from app.config import (CAMERA_INDEX, CONFIDENCE_THRESHOLD, MODEL_REGISTRY,
                        get_config)
from app.detection import subject_service
from app.detection.face_detector import face_detector
from app.detection.face_embedder import extract_embedding
from app.detection.person_detector import person_detector
from app.detection.plate_detector import plate_detector
from app.detection.tracker import tracker

router = APIRouter()

SUPPORTED_MODELS = {"face": face_detector, "person": person_detector, "plate": plate_detector}


# ---------------------------------------------------------------------------
# Info endpoints
# ---------------------------------------------------------------------------
@router.get("/models")
async def get_models() -> dict[str, Any]:
    """Available detectors + whether their weights are installed."""
    return {
        "models": MODEL_REGISTRY,
        "runtime": get_config(),
    }


@router.get("/config")
async def runtime_config() -> dict[str, Any]:
    """Runtime configuration snapshot (used by the console settings)."""
    return get_config()


# ---------------------------------------------------------------------------
# Detection endpoint (Django proxies every Nth webcam frame here)
# ---------------------------------------------------------------------------
@router.post("/detect")
async def detect_image(
    image_data: UploadFile = File(...),
    model: str = Form("face"),
    camera_code: str = Form("CAM-01"),
) -> dict[str, Any]:
    """Run the requested model against one uploaded frame.

    Args:
        image_data: JPEG/PNG upload (Django sends the raw webcam frame).
        model: ``face``, ``person`` or ``plate`` (default: ``face``).
        camera_code: logical camera identity used for timeline attribution.

    Returns:
        ``detections`` (with bboxes, attributes, timeline action),
        ``analytics`` (per-class counts) and ``model`` echo.
    """
    try:
        if model not in SUPPORTED_MODELS:
            raise HTTPException(status_code=400, detail=f"Unknown model '{model}'. "
                                f"Choose from {sorted(SUPPORTED_MODELS)}")

        image_bytes = await image_data.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image data")

        # --- 1) run the selected detector ---
        detector = SUPPORTED_MODELS[model]
        detections = detector.detect(img, conf_threshold=CONFIDENCE_THRESHOLD)

        # --- 2) assign stable tracking IDs ---
        detections = tracker.update(detections, class_name=model)

        # --- 3) feed subject service (timeline + identity) ---
        detections = subject_service.subject_service.process_detections(
            detections, camera_code=camera_code
        )
        subject_service.subject_service.mark_seen([d["subject_key"] for d in detections])
        subject_service.subject_service.reconcile()

        # --- 4) live counters ---
        counting_system.update(detections)

        # --- 5) serialisable payload ---
        payload_detections = []
        for det in detections:
            sighting_id = det.get("sighting_id")
            payload_detections.append(
                {
                    "class": det.get("class"),
                    "confidence": round(det.get("confidence", 0.0), 3),
                    "bbox": det.get("bbox"),
                    "tracking_id": det.get("tracking_id"),
                    "identity": det.get("identity"),
                    "attributes": det.get("attributes") or {},
                    "timeline_action": det.get("timeline_action"),
                    "sighting_id": str(sighting_id) if sighting_id else None,
                }
            )

        summary = counting_system.get_summary()
        response = {
            "model": model,
            "detections": payload_detections,
            "analytics": {
                "current_counts": summary["current_counts"],
                "class_event_counts": summary["class_event_counts"],
                "total_unique_detections": summary["total_unique_tracking_ids"],
            },
        }
        return response

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


# ---------------------------------------------------------------------------
# Timeline / analytics endpoints
# ---------------------------------------------------------------------------
@router.get("/events")
async def get_events(limit: int = 50, offset: int = 0, camera: Optional[str] = None) -> dict[str, Any]:
    """Recent subject sightings (closed/open) — one entry per reappearance."""
    sightings = db.recent_sightings(camera=camera, limit=min(max(limit, 1), 200), offset=max(offset, 0))
    total = db.get_db().sightings.count_documents(
        {} if not camera else {"camera_code": camera}
    )
    return {"events": sightings, "count": len(sightings), "total": total,
            "limit": min(max(limit, 1), 200), "offset": max(offset, 0)}


@router.get("/event-counts")
async def get_event_counts() -> dict[str, Any]:
    """Total + last-24h counts grouped by class."""
    return {"counts": db.sighting_counts()}


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Dashboard stats — total detections, cameras, registered people, uptime."""
    return {
        "total_table": db.sighting_counts(),
        "cameras": len(db.list_cameras()),
        "registrations": len(db.all_registrations()),
        "active_sightings": 0,
        "runtime": get_config()["models"],
    }


# ---------------------------------------------------------------------------
# Subject endpoint (the Analytics subject timeline API)
# ---------------------------------------------------------------------------
@router.get("/subjects")
async def get_subjects(limit: int = 50) -> dict[str, Any]:
    """Subjects summarised for the Analytics tab (photo + name + stats)."""
    db_handle = db.get_db()
    cursor = db_handle.subjects.find({}, {"_id": 0}).sort("updated_at", -1).limit(
        min(max(limit, 1), 100)
    )
    subjects = list(cursor)
    for sub in subjects:
        # attach the most recent sighting for that identity for timeline use
        sub["recent_sightings"] = list(
            db_handle.sightings.find(
                {"identity": sub["identity"]}, {"_id": 0, "attributes": 1,
                                                "first_seen": 1, "last_seen": 1,
                                                "camera_code": 1, "status": 1}
            ).sort("first_seen", -1).limit(5)
        )
    return {"subjects": subjects}


# ---------------------------------------------------------------------------
# Registration endpoints
# ---------------------------------------------------------------------------
@router.post("/registrations")
async def register_person(
    name: str = Form(...),
    notes: str = Form(""),
    image_data: Optional[UploadFile] = File(None),
) -> dict[str, Any]:
    """Register a person: store name + notes + face photo + embedding.

    At least one of ``image_data`` (a face photo) is required to compute the
    identity embedding used for later face recognition.
    """
    if not name.strip():
        raise HTTPException(status_code=422, detail="Name is required")

    embedding: list[float] = []
    face_photo: str = ""
    if image_data is not None:
        nparr = np.frombuffer(await image_data.read(), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid face photo")
        crop, bbox = face_detector.largest_face_crop(img)
        if crop is None:
            raise HTTPException(status_code=422, detail="No face found in the photo")
        embedding = extract_embedding(crop).tolist()
        from app.detection.face_detector import encode_face_photo

        face_photo = encode_face_photo(crop, 160)

    if not embedding:
        raise HTTPException(status_code=422, detail="Could not build face embedding")

    try:
        doc = db.insert_registration(
            {"name": name.strip(), "notes": notes, "embedding": embedding,
             "face_photo": face_photo}
        )
    except Exception as error:
        raise HTTPException(status_code=409, detail=f"Registration failed: {error}")

    return {"registration": doc, "status": "registered"}


@router.get("/registrations")
async def list_registrations() -> dict[str, Any]:
    """All registered people (Analytics tab + face recognition lookup)."""
    registrations = db.all_registrations()
    return {"registrations": registrations, "count": len(registrations)}


# ---------------------------------------------------------------------------
# Camera endpoints
# ---------------------------------------------------------------------------
@router.get("/cameras")
async def list_cameras() -> dict[str, Any]:
    """Camera fleet with 24-hour volume."""
    return {"cameras": db.list_cameras()}


@router.patch("/cameras/{code}")
async def update_camera(code: str, status: str = "active") -> dict[str, Any]:
    """Flip a camera's status (active/maintenance/offline)."""
    cam = db.update_camera_status(code, status)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"camera": cam}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Backend + MongoDB health."""
    return {
        "status": "ok",
        "mongodb": db.is_connected(),
        "models": {m["key"]: m["path"] is not None for m in MODEL_REGISTRY},
    }