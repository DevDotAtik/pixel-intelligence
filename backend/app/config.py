"""Central configuration for the Pixel Intelligence backend.

All tunables live here and are read from environment variables so the same code
runs on a weak laptop (320px inference, fewer threads) and a beefy GPU box.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_model_path(value: str | None, default_name: str) -> str | None:
    """Resolve a model path from env, falling back to a backend directory file."""
    raw = (value or "").strip()
    if not raw:
        raw = str(BASE_DIR / default_name)
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path) if path.exists() else None


# Compact face detector (default), or the heavier yolov8m-face.pt.
FACE_MODEL_PATH = _resolve_model_path(os.getenv("FACE_MODEL_PATH"), "model.pt")
# COCO-style model exposing a "person" class (e.g. yolov8n.pt). If absent we
# still detect people by inferring the full body from the face box.
OBJECT_MODEL_PATH = _resolve_model_path(os.getenv("OBJECT_MODEL_PATH", ""), "yolov8n.pt")
# License plate YOLO model (optional). If absent we fall back to the pure
# OpenCV plate locator.
PLATE_MODEL_PATH = _resolve_model_path(os.getenv("PLATE_MODEL_PATH", ""), "plate_model.pt")

# ---------------------------------------------------------------------------
# Runtime tuning — tuned for a low-end CPU laptop by default.
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.40"))
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
# Optional network video source (HTTP MJPEG / RTSP). Set only for operators who
# stream a phone/camera over the network instead of a local /dev/videoN device.
CAMERA_URL = os.getenv("CAMERA_URL", "").strip()
IMAGE_WIDTH = int(os.getenv("IMAGE_WIDTH", "640"))
IMAGE_HEIGHT = int(os.getenv("IMAGE_HEIGHT", "480"))
# Model input resolution. 640 is the accuracy sweet spot on CPU (320 misses
# small faces/plates); inference runs off the streaming thread so throughput
# stays smooth. On a very weak laptop, drop to 480 via INFERENCE_SIZE=480.
INFERENCE_SIZE = int(os.getenv("INFERENCE_SIZE", "640"))
PROCESS_EVERY_N_FRAMES = int(os.getenv("PROCESS_EVERY_N_FRAMES", "3"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "85"))
CPU_THREADS = int(
    os.getenv("CPU_THREADS", str(max(1, min(4, os.cpu_count() or 1))))
)

# ---------------------------------------------------------------------------
# Device: prefer CUDA when available, else CPU (limited to CPU_THREADS).
# ---------------------------------------------------------------------------
DEVICE = "cpu"
try:
    import torch

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    if DEVICE == "cpu":
        torch.set_num_threads(CPU_THREADS)
except Exception:  # torch install missing/partial — keep CPU path
    pass

# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "pixel_intelligence")

# ---------------------------------------------------------------------------
# Face recognition
#
# Identity embeddings come from the ArcFace/MobileFaceNet ONNX embedder when
# `models/arc_face.onnx` is present (512-dim, cosine ~0.90 same, <0.45 other),
# otherwise the lightweight histogram fallback is used. The knobs below are
# tuned for the ONNX embedder.  Recognition is intentionally conservative:
# an unknown face is safer than attaching the wrong person's name.
# ---------------------------------------------------------------------------
# Webcam face boxes are not landmark-aligned, so their genuine-match scores are
# lower than a studio reference image. 0.75 is conservative in combination
# with the quality, margin and consecutive-confirmation gates below.
FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.75"))
FACE_EMBED_SIZE = int(os.getenv("FACE_EMBED_SIZE", "64"))
# Minimum margin between the best and the second-best registered match. When
# two enrolments score almost equally the identity is ambiguous — we refuse to
# name anyone rather than guess (multi-enrolment false positives).
FACE_MATCH_MARGIN = float(os.getenv("FACE_MATCH_MARGIN", "0.12"))
# Smallest face bbox side (px) that is worth embedding — below this the crop
# is too noisy to identify and we leave the person unnamed.
FACE_MATCH_MIN_FACE = int(os.getenv("FACE_MATCH_MIN_FACE", "64"))
# Reject small, blurred, underexposed and overexposed crops before embedding.
# Laplacian variance is measured after the crop is normalised to 112px.
FACE_MATCH_MIN_SHARPNESS = float(os.getenv("FACE_MATCH_MIN_SHARPNESS", "45"))
FACE_MATCH_MIN_BRIGHTNESS = float(os.getenv("FACE_MATCH_MIN_BRIGHTNESS", "45"))
FACE_MATCH_MAX_BRIGHTNESS = float(os.getenv("FACE_MATCH_MAX_BRIGHTNESS", "210"))
# How often a subject's identity is re-evaluated (embedding recompute). Keeps
# the heavy ONNX call off the hot path while labels still refresh during a
# conversation/look-around.
IDENTITY_REFRESH_SECONDS = float(os.getenv("IDENTITY_REFRESH_SECONDS", "0.75"))
# A name is only attached after it wins this many *consecutive* independent
# re-evaluations at or above threshold — a stranger whose score briefly spikes
# never gets confirmed.
FACE_MATCH_CONFIRM = int(os.getenv("FACE_MATCH_CONFIRM", "2"))
# A single reference photo is prone to pose/light false positives. A person is
# eligible for live recognition only after this many accepted reference photos.
FACE_ENROLL_MIN_SAMPLES = int(os.getenv("FACE_ENROLL_MIN_SAMPLES", "3"))
FACE_ENROLL_MAX_SAMPLES = int(os.getenv("FACE_ENROLL_MAX_SAMPLES", "5"))
FACE_ENROLL_MIN_FACE = int(os.getenv("FACE_ENROLL_MIN_FACE", "96"))
FACE_ENROLL_MIN_SHARPNESS = float(os.getenv("FACE_ENROLL_MIN_SHARPNESS", "60"))

# ---------------------------------------------------------------------------
# Subject timeline / dedup behaviour
# ---------------------------------------------------------------------------
VANISH_SECONDS = float(os.getenv("VANISH_SECONDS", "5"))
MIN_SIGHTING_SECONDS = float(os.getenv("MIN_SIGHTING_SECONDS", "1"))


# ---------------------------------------------------------------------------
# Model registry (drives the console model select box + /api/models)
# ---------------------------------------------------------------------------
MODEL_REGISTRY: list[dict[str, Any]] = [
    {
        "key": "face",
        "name": "Face Detection",
        "path": FACE_MODEL_PATH,
        "sidecar": "yolov8m-face.pt",
        "classes": ["face"],
        "default_imgsz": INFERENCE_SIZE,
    },
    {
        "key": "person",
        "name": "Person + Clothing Analyst",
        "path": OBJECT_MODEL_PATH,
        "sidecar": "yolov8n.pt",
        "classes": ["person"] + ["car", "truck", "bus", "motorbike"],
        "default_imgsz": INFERENCE_SIZE,
        "note": "Uses face->body inference when no person model is installed.",
    },
    {
        "key": "plate",
        "name": "License Plate",
        "path": PLATE_MODEL_PATH,
        "sidecar": "plate_model.pt",
        "classes": ["plate"],
        "default_imgsz": INT_EXPAND if (INT_EXPAND := INFERENCE_SIZE) else 416,
        "note": "Uses OpenCV plate locator when no plate model is installed.",
    },
]

# Convenience lookups
MODEL_KEYS = ["face", "person", "plate"]


def get_config() -> dict[str, Any]:
    """Return a JSON-safe snapshot of the runtime configuration."""
    return {
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "camera_index": CAMERA_INDEX,
        "camera_url": CAMERA_URL,
        "resolution": f"{IMAGE_WIDTH}x{IMAGE_HEIGHT}",
        "device": DEVICE,
        "inference_size": INFERENCE_SIZE,
        "process_every_n_frames": PROCESS_EVERY_N_FRAMES,
        "cpu_threads": CPU_THREADS,
        "jpeg_quality": JPEG_QUALITY,
        "mongodb": MONGODB_DB,
        "face_match_threshold": FACE_MATCH_THRESHOLD,
        "face_match_margin": FACE_MATCH_MARGIN,
        "face_match_confirm": FACE_MATCH_CONFIRM,
        "vanish_seconds": VANISH_SECONDS,
        "models": {
            item["key"]: {"exists": item["path"] is not None, "path": item["path"]}
            for item in MODEL_REGISTRY
        },
    }
