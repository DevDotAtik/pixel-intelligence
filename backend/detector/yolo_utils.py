"""Detection helpers for the Django app — now a FastAPI proxy.

Previously this file loaded a YOLO model directly (hardcoded ``./model.pt``),
which duplicated the FastAPI pipeline and made the two backends drift apart.
All inference now lives in the ``app`` FastAPI package; this module only
forwards frames to it.
"""
from __future__ import annotations

import os

import requests

FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def detect_faces(image_bytes: bytes, model: str = "face", camera_code: str = "CAM-01") -> list:
    """Run detection on an uploaded image via the FastAPI service.

    Returns the ``detections`` list (each: class, confidence, bbox, tracking_id,
    identity, attributes).
    """
    try:
        resp = requests.post(
            f"{FASTAPI_BASE_URL}/api/detect",
            files={"image_data": ("frame.jpg", image_bytes, "image/jpeg")},
            data={"model": model, "camera_code": camera_code},
            timeout=20,
        )
        if resp.status_code == 200:
            return resp.json().get("detections", [])
    except requests.RequestException:
        pass
    return []