"""Shared base class for all detector modules.

Handles the common concerns:
  * lazy model loading (nothing fails at import if the weights are missing)
  * one-time warm-up so the first webcam frame is not painfully slow
  * normalising detection output into the internal detection dict format
"""
from __future__ import annotations

import cv2
from typing import Any

from app.config import CONFIDENCE_THRESHOLD, DEVICE, INFERENCE_SIZE


class BaseDetector:
    """Base YOLO detector wrapper used by Face / Person / Plate detectors."""

    model_key = "generic"

    def __init__(self, model_path: str | None) -> None:
        """Store the path; the model itself is loaded lazily on first use."""
        self.model_path = model_path
        self.model = None
        self.is_loaded = False
        self.class_names: dict[int, str] = {}

        if self.model_path:
            try:
                self._load()
            except Exception as error:  # keep service alive on bad weights
                print(f"[{self.model_key.upper()}] model load failed: {error}")
        else:
            print(
                f"[{self.model_key.upper()}] no installed weights — "
                f"module will run in OPTIONAL/fallback mode"
            )

    # ------------------------------------------------------------------ #
    # Hooks
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        """Load the underlying YOLO model. Override for custom loading."""
        from ultralytics import YOLO

        self.model = YOLO(self.model_path)
        self.class_names = {int(k): str(v) for k, v in self.model.names.items()}
        self.is_loaded = True
        self._warm_up()

    def _warm_up(self) -> None:
        """Spend the one-time CPU graph build at startup, not on the first frame."""
        try:
            import numpy as np

            self.model.predict(
                source=np.zeros((INFERENCE_SIZE, INFERENCE_SIZE, 3), dtype=np.uint8),
                conf=CONFIDENCE_THRESHOLD,
                imgsz=INFERENCE_SIZE,
                device=DEVICE,
                max_det=20,
                verbose=False,
            )
            print(f"[{self.model_key.upper()}] model warmed up.")
        except Exception as error:
            print(f"[{self.model_key.upper()}] warm-up skipped: {error}")

    # ------------------------------------------------------------------ #
    # Inference helpers
    # ------------------------------------------------------------------ #
    def _run_model(self, image: Any, conf: float) -> list[dict[str, Any]]:
        """Run YOLO predict and normalise boxes into the internal format."""
        if not self.is_loaded or self.model is None:
            return []
        try:
            results = self.model.predict(
                source=image,
                conf=conf,
                imgsz=INFERENCE_SIZE,
                device=DEVICE,
                max_det=20,
                verbose=False,
            )
        except Exception as error:
            print(f"[{self.model_key.upper()}] inference error: {error}")
            return []

        detections: list[dict[str, Any]] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                cls_id = int(box.cls[0])
                detections.append(
                    {
                        "class": self.class_names.get(cls_id, "unknown").lower(),
                        "confidence": float(box.conf[0]),
                        "bbox": [x1, y1, x2, y2],
                        "cls_id": cls_id,
                        "tracking_id": None,  # filled in by the tracker
                    }
                )
        return detections