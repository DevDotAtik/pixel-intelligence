"""License plate detector — pure OpenCV box locator + best-effort OCR.

There is no dedicated plate YOLO model installed, so the box localisation is
done with classic computer vision (morphological close + contour analysis +
aspect-ratio/contrast screening), which is *extremely* cheap on CPU.

OCR (reading the actual characters) requires the optional system package
``tesseract-ocr`` + the pip package ``pytesseract``. When those are missing the
module still returns the located plate rectangle with ``plate_text: null`` —
the bounding box + confidence is still useful for the timeline/Analytics tab.
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import Any, Optional

from app.detection.base import BaseDetector

try:  # optional OCR dependency
    import pytesseract  # type: ignore

    _OCR_AVAILABLE = True
except Exception:
    _OCR_AVAILABLE = False

# A license plate is roughly 2:1 to 4:1 (w/h), depends on country.
_MIN_AREA_RATIO = 0.0006     # must cover at least this % of the frame
_MAX_AREA_RATIO = 0.08       # and no more
_MIN_ASPECT = 1.6
_MAX_ASPECT = 5.5

# When a vehicle/person model exists we feed it here; for now we only offer
# the OpenCV fallback so the plate module runs out-of-the-box.
PLATE_MODEL_PATH = None  # optional: point at a YOLO plate detector


class PlateDetector(BaseDetector):
    """Detects plate-like rectangles and, when possible, OCRs them."""

    model_key = "plate"

    def __init__(self, model_path: str | None = None) -> None:
        # Only try to load a YOLO model if a real path is supplied.
        super().__init__(model_path or None)
        self.use_opencv = not self.is_loaded

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def detect(self, image: np.ndarray, conf_threshold: float = 0.40) -> list[dict[str, Any]]:
        """Return plate detections.

        Each detection: ``bbox`` (plate box), ``plate_text`` (str or None),
        ``confidence``, and ``read_attempted`` bool.
        """
        if self.is_loaded:
            plates = self._run_model(image, conf_threshold)
        else:
            plates = self._locate_plates(image, conf_threshold)

        for plate in plates:
            text, ocr_conf = self._ocr_plate(image, plate["bbox"])
            plate["plate_text"] = text
            plate["read_attempted"] = ocr_conf is not None
            plate["attributes"] = {
                "plate_text": text,
                "ocr_confidence": ocr_conf,
            }
        return plates

    # ------------------------------------------------------------------ #
    # OpenCV box locator
    # ------------------------------------------------------------------ #
    def _locate_plates(self, image: np.ndarray, conf: float) -> list[dict[str, Any]]:
        """Find plate-like regions via morphology + contour screening."""
        frame_area = float(image.shape[0] * image.shape[1])
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # 1) emphasise edges + text blocks.
        blur = cv2.bilateralFilter(gray, 11, 17, 17)
        edges = cv2.Canny(blur, 30, 90)
        # 2) fuse horizontal text lines into solid blocks.
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        closed = cv2.dilate(closed, kernel2, iterations=2)

        contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        results: list[dict[str, Any]] = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area_ratio = (w * h) / frame_area
            aspect = w / float(max(1, h))
            if area_ratio < _MIN_AREA_RATIO or area_ratio > _MAX_AREA_RATIO:
                continue
            if aspect < _MIN_ASPECT or aspect > _MAX_ASPECT:
                continue
            # low fill ratio => text block, not a solid blob (door, etc.)
            fill = cv2.contourArea(cnt) / float(max(1, w * h))
            if fill > 0.65:
                continue
            # score ~ how "plate-like" the block is.
            score = 0.5 + 0.3 * (min(aspect, 3.0) / 3.0) + 0.2 * (1.0 - abs(fill - 0.35))
            if score < conf:
                continue
            results.append(
                {
                    "class": "plate",
                    "confidence": round(min(score, 0.98), 2),
                    "bbox": [x, y, x + w, y + h],
                    "cls_id": -1,
                    "tracking_id": None,
                    "plate_text": None,
                    "read_attempted": False,
                }
            )
        return results[:8]  # cap to a sane number

    # ------------------------------------------------------------------ #
    # OCR
    # ------------------------------------------------------------------ #
    def _ocr_plate(self, image: np.ndarray, bbox: list[int]) -> tuple[Optional[str], Optional[float]]:
        """Read characters inside a plate box; returns (text, confidence)."""
        if not _OCR_AVAILABLE:
            return None, None
        x1, y1, x2, y2 = bbox
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return None, None
        try:
            # binarise to help tesseract.
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            _, thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text = pytesseract.image_to_string(
                thr,
                config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            )
            text = "".join(ch for ch in text if ch.isalnum()).upper()
            if len(text) < 3:
                return None, None
            return text, 0.7  # heuristic confidence for a successful read
        except Exception:
            return None, None


# Singleton.
plate_detector = PlateDetector()