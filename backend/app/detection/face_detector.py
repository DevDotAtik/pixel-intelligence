"""Face detection module.

Responsibilities:
  * locate every face with a YOLO face model
  * infer the surrounding whole-person bounding box (used as the Person
    detector fallback so we can draw a full-body rectangle on cheap laptops)
  * build a compact embedding + face photo from a crop, which the
    SubjectService uses to resolve a registered person's name.

Both configured face models (``model.pt`` compact and ``yolov8m-face.pt``)
only expose a ``face`` class, so result classes are normalised to ``face``.
"""
from __future__ import annotations

import base64
import cv2
import numpy as np
from typing import Any

from app.config import FACE_MODEL_PATH
from app.detection.base import BaseDetector

# Typical body/face proportions for a standing person. When we only have a face
# box we extrapolate the body below it; these are used as camera-agnostic ratios
# (subject to frame geometry and impossible to make perfect — good enough to
# draw a person rectangle on a demo webcam).
BODY_HEIGHT_RATIO = 5.6      # total body height / face height
BODY_WIDTH_RATIO = 2.6       # torso width / face width
FACE_TO_TOP_RATIO = 0.18     # fraction of body height between head-top and face-top


def _box_iou(a: list[int], b: list[int]) -> float:
    """Intersection-over-union for duplicate face-box suppression."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if not intersection:
        return 0.0
    area_a = max(1, ax2 - ax1) * max(1, ay2 - ay1)
    area_b = max(1, bx2 - bx1) * max(1, by2 - by1)
    return intersection / max(1, area_a + area_b - intersection)


class FaceDetector(BaseDetector):
    """YOLO face detector with body-inference and embedding helpers."""

    model_key = "face"

    def __init__(self) -> None:
        super().__init__(FACE_MODEL_PATH)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def detect(self, image: np.ndarray, conf_threshold: float = 0.50) -> list[dict[str, Any]]:
        """Return face detections plus an inferred body box per face.

Each returned detection carries:
          bbox: the face box [x1,y1,x2,y2]
          body_bbox: the inferred whole-person box (used by Person mode)
          face_photo: base64 JPEG crop (for the Analytics subject photo)
          _crop: the raw BGR crop (in-process only) — SubjectService embeds
                 it lazily (throttled per subject) for registration matching.
    """
        raw_faces = self._run_model(image, conf_threshold)
        # Some face weights occasionally emit two heavily-overlapping boxes for
        # one person. Keeping only the higher-confidence box stabilises the
        # tracking key, so confirmation can reach the person's name instead of
        # being repeatedly reset on a duplicate `face` track.
        faces: list[dict[str, Any]] = []
        for candidate in sorted(raw_faces, key=lambda item: item["confidence"], reverse=True):
            if any(_box_iou(candidate["bbox"], kept["bbox"]) >= 0.45 for kept in faces):
                continue
            faces.append(candidate)
        face_detections: list[dict[str, Any]] = []
        for face in faces:
            x1, y1, x2, y2 = face["bbox"]
            fw, fh = max(1, x2 - x1), max(1, y2 - y1)
            # Whole-body box extrapolated down from the face.
            body_h = fh * BODY_HEIGHT_RATIO
            body_w = fw * BODY_WIDTH_RATIO
            body_top = max(0, y1 - body_h * FACE_TO_TOP_RATIO)
            body_bottom = min(image.shape[0] - 1, body_top + body_h)
            body_left = max(0, (x1 + x2) // 2 - body_w // 2)
            body_right = min(image.shape[1] - 1, body_left + body_w)

            crop = image[max(0, y1):y2, max(0, x1):x2]
            face_detections.append(
                {
                    **face,
                    "class": "face",
                    "body_bbox": [int(body_left), int(body_top), int(body_right), int(body_bottom)],
                    "embedding": None,
                    "_crop": crop,
                    "face_photo": encode_face_photo(crop, 160),
                    "attributes": {},  # filled by SubjectService (registration match)
                }
            )
        return face_detections

    def largest_face_crop(self, image: np.ndarray, conf_threshold: float = 0.5):
        """Return (bgr_crop, bbox) of the biggest detected face — for Registration.

        Returns ``(None, None)`` when no face is visible.
        """
        faces = self._run_model(image, conf_threshold)
        if not faces:
            return None, None
        face = max(faces, key=lambda f: (f["bbox"][2] - f["bbox"][0]) * (f["bbox"][3] - f["bbox"][1]))
        x1, y1, x2, y2 = face["bbox"]
        crop = image[y1:y2, x1:x2] if y2 > y1 and x2 > x1 else None
        return crop, [x1, y1, x2, y2]


def encode_face_photo(crop_bgr: np.ndarray, size: int = 160) -> str | None:
    """Encode a face crop as a small base64 JPEG (for storing in Mongo).

    Returns an empty string if the crop is invalid.
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return ""
    try:
        resized = cv2.resize(crop_bgr, (size, size), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            return ""
        return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")
    except Exception:
        return ""


# Singleton — one loaded model per process.
face_detector = FaceDetector()
