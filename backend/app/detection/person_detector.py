"""Person + clothing + movement-direction detection pipeline.

Two operating modes:

1. **Dedicated person model** (``yolov8n.pt`` / COCO): people are located
   directly with a ``person`` box.

2. **Fallback (no person model)**: locate faces with the face detector and
   extrapolate the body box (see :mod:`app.detection.face_detector`). This is
   cheaper on a low-end laptop and still gives a usable person rectangle.

In both modes every detected person gets:
  * ``attributes.clothing`` — colour + garment type via helmet_style heuristics
  * ``attributes.direction`` — N/E/S/W from the subject's trajectory history
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import Any

from app.config import OBJECT_MODEL_PATH
from app.detection.base import BaseDetector
from app.detection.clothing import classify_clothing
from app.detection.direction import DirectionTracker
from app.detection.face_detector import face_detector

# COCO class id for a person.
PERSON_CLASS_ID = 0


class PersonDetector(BaseDetector):
    """Whole-person detector + clothing/direction attribute extraction."""

    model_key = "person"

    def __init__(self) -> None:
        super().__init__(OBJECT_MODEL_PATH)
        self.uses_fallback = not (OBJECT_MODEL_PATH is not None and self.is_loaded)
        if self.uses_fallback:
            print("[PERSON ] running in FACE->BODY fallback mode "
                  "(install yolov8n.pt in backend/ to enable real person boxes)")
        self._direction_trackers: dict[int, DirectionTracker] = {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def detect(
        self,
        image: np.ndarray,
        conf_threshold: float = 0.50,
        frame_height_center: float | None = None,
    ) -> list[dict[str, Any]]:
        """Return person detections with clothing + direction attributes.

        Args:
            image: BGR frame.
            conf_threshold: detection confidence.
            frame_height_center: vertical centre of the frame in pixels, used
                as a crude "scene centre" reference for direction labels.

        Returns:
            Normalised detections. ``attributes`` includes ``clothing`` and
            ``direction``; ``bbox`` is the full person box; ``face_photo`` and
            ``embedding`` are populated (for registration linking) only when
            faces were also visible.
        """
        detections = self._core_detections(image, conf_threshold)
        return self._enrich(image, detections, frame_height_center)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _core_detections(self, image: np.ndarray, conf: float) -> list[dict[str, Any]]:
        """Person boxes from the model or the face->body fallback."""
        if not self.uses_fallback:
            raw = self._run_model(image, conf)
            persons = [d for d in raw if int(d.get("cls_id", -1)) == PERSON_CLASS_ID
                       or d.get("class") == "person"]
            for d in persons:
                d["class"] = "person"
                d["face_photo"] = ""
                d["embedding"] = None
            return persons

        # --- fallback: face detector -> inferred body box ---
        faces = face_detector.detect(image, conf_threshold=conf)
        persons = []
        for face in faces:
            x1, y1, x2, y2 = face["body_bbox"]
            crop = image[y1:y2, x1:x2] if y2 > y1 else image[y1:y1 + 20, x1:x2]
            persons.append(
                {
                    "class": "person",
                    "confidence": face["confidence"],
                    "bbox": [x1, y1, x2, y2],
                    "cls_id": -1,
                    "tracking_id": None,
                    "face_photo": face.get("face_photo", ""),
                    "embedding": face.get("embedding"),
                }
            )
        return persons

    def _enrich(
        self,
        image: np.ndarray,
        persons: list[dict[str, Any]],
        frame_height_center: float | None,
    ) -> list[dict[str, Any]]:
        """Add clothing + direction + tracking-id to every person box."""
        enriched: list[dict[str, Any]] = []
        for i, person in enumerate(persons):
            x1, y1, x2, y2 = person["bbox"]
            crop = image[y1:y2, x1:x2]
            clothing = classify_clothing(person["bbox"], crop)

            # Direction requires a stable id; the tracker assigns ids later,
            # so we compute direction from the *centre* history keyed by a
            # lightweight hash of the box (stable across frames for the same
            # person at 3fps sampling).
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            key = int(hash((round(cx / 8), round(cy / 8))) % 1_000_000)
            tracker = self._direction_trackers.get(key)
            if tracker is None:
                tracker = DirectionTracker()
                self._direction_trackers[key] = tracker
            tracker.push(cx, cy)

            attrs = person.get("attributes") or {}
            attrs.setdefault("clothing", clothing)
            attrs.setdefault("direction", tracker.direction())
            person["attributes"] = attrs
            enriched.append(person)

        # Keep memory bounded — drop trackers for boxes we no longer see in a
        # future call (triggered by caller after a full frame sweep).
        return enriched

    def cleanup_trackers(self, active_keys: set[int]) -> None:
        """Drop direction trackers for keys not seen this frame."""
        for key in [k for k in self._direction_trackers if k not in active_keys]:
            del self._direction_trackers[key]


# Singleton.
person_detector = PersonDetector()