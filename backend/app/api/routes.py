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
import json
import subprocess
import sys
from typing import Any, Optional

import cv2
import numpy as np
from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile

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
    image_data: list[UploadFile] = File(...),
) -> dict[str, Any]:
    """Register or refresh a person from several high-quality face photos."""
    from app.config import (
        FACE_ENROLL_MAX_SAMPLES,
        FACE_ENROLL_MIN_FACE,
        FACE_ENROLL_MIN_SAMPLES,
        FACE_ENROLL_MIN_SHARPNESS,
    )
    from app.detection.face_embedder import embedder_backend, face_quality

    if not name.strip():
        raise HTTPException(status_code=422, detail="Name is required")
    if embedder_backend() != "onnx":
        raise HTTPException(status_code=503, detail="ArcFace recognition model is unavailable; face naming is disabled")
    if not FACE_ENROLL_MIN_SAMPLES <= len(image_data) <= FACE_ENROLL_MAX_SAMPLES:
        raise HTTPException(
            status_code=422,
            detail=f"Upload {FACE_ENROLL_MIN_SAMPLES} to {FACE_ENROLL_MAX_SAMPLES} clear photos of the same person",
        )

    embeddings: list[np.ndarray] = []
    face_photo: str = ""
    for number, upload in enumerate(image_data, start=1):
        nparr = np.frombuffer(await upload.read(), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail=f"Photo {number} is not a valid image")
        faces = face_detector.detect(img)
        if len(faces) != 1:
            detail = "No face found" if not faces else "More than one face found"
            raise HTTPException(status_code=422, detail=f"{detail} in photo {number}; upload one clear face per photo")
        crop = faces[0].get("_crop")
        usable, reason = face_quality(
            crop, min_side=FACE_ENROLL_MIN_FACE, min_sharpness=FACE_ENROLL_MIN_SHARPNESS
        )
        if not usable:
            raise HTTPException(status_code=422, detail=f"Photo {number}: {reason}. Use a sharp, front-facing, well-lit face.")
        embeddings.append(extract_embedding(crop))
        from app.detection.face_detector import encode_face_photo

        if not face_photo:
            face_photo = encode_face_photo(crop, 160)

    if not embeddings:
        raise HTTPException(status_code=422, detail="Could not build face embedding")
    average = np.mean(np.stack(embeddings), axis=0)
    average /= np.linalg.norm(average) or 1.0
    embedding = average.astype(np.float32).tolist()

    try:
        doc = db.save_registration(
            {"name": name.strip(), "notes": notes, "embedding": embedding,
             "face_photo": face_photo, "sample_count": len(embeddings),
             "embedding_backend": "arcface",
             "reference_embeddings": [item.astype(np.float32).tolist() for item in embeddings]}
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Registration failed: {error}")

    # The normal registration cache lives for 30 seconds; clear it so a
    # successful enrolment or re-enrolment takes effect on the very next frame.
    subject_service.subject_service.refresh_registrations()
    return {"registration": doc, "status": "registered"}


@router.get("/registrations")
async def list_registrations() -> dict[str, Any]:
    """All registered people (Analytics tab + face recognition lookup)."""
    registrations = db.all_registrations()
    from app.config import FACE_ENROLL_MIN_SAMPLES

    return {
        "registrations": registrations,
        "count": len(registrations),
        "required_samples": FACE_ENROLL_MIN_SAMPLES,
    }


# ---------------------------------------------------------------------------
# Camera endpoints (CCTV registry CRUD — operators add RTSP/MJPEG sources)
# ---------------------------------------------------------------------------
@router.get("/cameras")
async def list_cameras() -> dict[str, Any]:
    """Camera fleet with 24-hour volume."""
    return {"cameras": db.list_cameras()}


@router.post("/cameras", status_code=201)
async def create_camera(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Add a camera to the registry (name, zone, RTSP/MJPEG URL, ...).

    ``code`` is optional — the next sequential ``CAM-NN`` is assigned when
    omitted. ``stream_type`` defaults to a guess from the URL (rtsp/mjpeg).
    """
    if not str(payload.get("name", "")).strip():
        raise HTTPException(status_code=422, detail="Camera name is required")
    try:
        cam = db.create_camera(payload)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Camera creation failed: {error}")
    return {"camera": cam, "status": "created"}


@router.get("/cameras/{code}")
async def get_camera(code: str) -> dict[str, Any]:
    """Single camera record."""
    cam = db.get_camera_rec(code)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"camera": cam}


@router.patch("/cameras/{code}")
async def update_camera(
    code: str,
    payload: Optional[dict[str, Any]] = Body(None),
    status: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Update a camera. Accepts a partial JSON body (name, zone, stream_url,
    username, password, resolution, fps, enabled, notes, ...) or the legacy
    ``?status=`` query form used by the console status toggle."""
    if db.get_camera_rec(code) is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    if status is not None:
        cam = db.update_camera_status(code, status)
        if cam is None:
            raise HTTPException(status_code=400, detail="Invalid status value")
        return {"camera": cam}

    cam = db.patch_camera(code, payload or {})
    if cam is None:
        raise HTTPException(status_code=400, detail="No editable fields supplied")
    return {"camera": cam}


@router.delete("/cameras/{code}")
async def delete_camera(code: str) -> dict[str, Any]:
    """Remove a camera from the registry."""
    if not db.delete_camera(code):
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"deleted": code, "status": "deleted"}


_PROBE_SCRIPT = r"""
import json, os, sys
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
import cv2
url = sys.argv[1]
out = {"ok": False, "code": "refused", "detail": "URL refused the RTSP handshake (DESCRIBE/SETUP failed). Check host, port, path and that the server allows TCP transport."}
try:
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if cap.isOpened():
        ret, _ = cap.read()
        cap.release()
        if ret:
            out = {"ok": True, "code": "streaming", "detail": "streaming"}
        else:
            out = {"ok": False, "code": "no_frame",
                   "detail": "URL opened but delivered no frame. Check the video path (e.g. /h264, /stream1), codec and FPS."}
    else:
        out = {"ok": False, "code": "refused",
               "detail": "URL refused the RTSP handshake (DESCRIBE/SETUP failed). Check host, port, path and that the server allows TCP transport."}
except Exception as error:
    out = {"ok": False, "code": "error", "detail": str(error)}
print(json.dumps(out))
"""


@router.post("/cameras/test")
async def test_camera_stream(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Probe a stream URL without saving it — returns reachability of the
    RTSP/MJPEG source so the operator can test a URL before registering it.

    RTSP is opened through FFmpeg with TCP transport forced (UDP silently fails
    on many Wi-Fi / NAT setups). The open+read runs in a **subprocess** with a
    bounded timeout: a hung host hangs its own child, never the event loop or
    the GIL — so probing a dead camera cannot stall the live detection feed.
    """
    url = str(payload.get("stream_url") or "").strip()
    if not url:
        raise HTTPException(status_code=422, detail="stream_url is required")

    try:
        return await _run_probe(url)
    except Exception as error:
        import traceback
        print("[cameras/test] unexpected error:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Probe crashed: {error}") from error


async def _run_probe(url: str) -> dict[str, Any]:
    proc: subprocess.CompletedProcess[str] | None = None
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _PROBE_SCRIPT, url],
            capture_output=True, text=True, timeout=9,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "stream_type": db.guess_stream_type(url),
                "detail": "Connection timed out after 9s. Is the host reachable and the RTSP server running?"}

    detail_map = {
        "streaming": "Reachable — OpenCV opened the stream and decoded a frame.",
        "no_frame": ("URL opened but delivered no frame. "
                     "Check the video path (e.g. /h264, /stream1), codec and FPS."),
        "refused": ("URL refused the RTSP/HTTP handshake. "
                    "Check host, port, path and that the server allows TCP transport."),
    }
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()
        tail = tail[-1].strip() if tail else "exit code %d" % proc.returncode
        return {"ok": False, "stream_type": db.guess_stream_type(url),
                "detail": f"Probe process failed: {tail}"}
    try:
        result = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (IndexError, ValueError):
        return {"ok": False, "stream_type": db.guess_stream_type(url),
                "detail": "Probe produced no usable result."}
    ok = bool(result.get("ok"))
    detail = detail_map.get(result.get("code"), result.get("detail") or "Unreachable.")
    return {"ok": ok, "stream_type": db.guess_stream_type(url), "detail": detail}


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
