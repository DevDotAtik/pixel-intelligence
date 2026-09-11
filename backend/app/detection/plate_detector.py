"""License plate detector — OpenCV box locator + template-matching OCR.

There is no dedicated plate YOLO model installed, so box localisation is done
with classic computer vision:
  * CLAHE + edge emphasis + horizontal morphology to fuse text rows into blocks
  * aspect / area / fill-ratio screening
  * a "is it a plate?" vote that requires the block to actually contain several
    small character-like components, and
  * colour screening that prefers white/yellow (Indian) plate backgrounds.

OCR reads the characters with ``pytesseract`` (tesseract LSTM OCR) when the
binary is installed, falling back to a self-contained template matcher: fonts
are rendered once with Pillow (Liberation Sans Bold, an Arial clone used by
plates) and each extracted character is matched with normalised cross
correlation.

When the COCO object model (``yolov8n.pt``) is installed, every detected plate
is attributed to the nearest car / truck / bus / motorcycle, and the bbox
metadata is enriched with vehicle type + dominant colour.
"""
from __future__ import annotations

import os
import re
import shutil
from typing import Any, Optional

import cv2
import numpy as np

try:
    import pytesseract as _pytesseract
except ImportError:  # pragma: no cover - optional dependency
    _pytesseract = None

from app.detection import clothing as clothing_module
from app.detection.base import BaseDetector
from app.detection.person_detector import person_detector

_OCR_TESSERACT_CONFIG = (
    "--oem 1 --psm 7 "
    "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)


def _tesseract_ready() -> bool:
    """True when the wrapper is importable and the native binary exists."""
    return (
        _pytesseract is not None
        and shutil.which("tesseract") is not None
    )


def _tesseract_ocr(gray: np.ndarray) -> tuple[Optional[str], Optional[float]]:
    """Read a plate crop with tesseract; returns (text, confidence) or (None, None)."""
    if not _tesseract_ready():
        return None, None
    try:
        data = _pytesseract.image_to_data(
            gray,
            config=_OCR_TESSERACT_CONFIG,
            output_type=_pytesseract.Output.DICT,
            timeout=8,
        )
    except Exception:
        return None, None
    text = "".join(
        str(t) for t in data.get("text", []) if str(t).strip()
    ).upper()
    text = re.sub(r"[^A-Z0-9]", "", text)
    confs = [float(c) for c in data.get("conf", []) if c is not None and c >= 0]
    if len(text) < 4 or not confs:
        return None, None
    conf = float(np.clip(np.mean(confs) / 100.0, 0.45, 0.99))
    return text, round(conf, 2)

# A license plate is roughly 2:1 to 4.5:1 (w/h); a full 10-character row reads
# much wider once each tight bbox is padded to include its background.
_MAX_AREA_RATIO = 0.20       # plate may cover up to 20% of the frame (close-ups)
_MIN_ASPECT = 1.2
_MAX_ASPECT = 12.0

# COCO vehicle classes attributed to a nearby plate (id -> friendly name).
_VEHICLE_IDS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

_OCR_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_TEMPLATE_HEIGHT = 44
# Multiple fonts/weights give the template matcher a chance on real plate typefaces.
_TEMPLATES: dict[str, list[np.ndarray]] | None = None
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _build_templates() -> dict[str, list[np.ndarray]]:
    """Render one normalised template per character per font (A-Z, 0-9).

    Each char gets a list of variants (one per available font/weight); OCR
    matches against the best variant so real Indian/European plate typefaces
    (Liberation/DejaVu Sans variants) are recognised instead of only the
    first installed font.
    """
    from PIL import Image, ImageDraw, ImageFont

    templates: dict[str, list[np.ndarray]] = {ch: [] for ch in _OCR_CHARS}
    for font_path in _FONT_CANDIDATES:
        if not os.path.exists(font_path):
            continue
        font = ImageFont.truetype(font_path, 80)
        for ch in _OCR_CHARS:
            img = Image.new("L", (120, 120), 0)
            ImageDraw.Draw(img).text((8, 6), ch, fill=255, font=font)
            arr = np.asarray(img)
            ys, xs = np.nonzero(arr)
            if len(xs) == 0:
                continue
            crop = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            scale = _TEMPLATE_HEIGHT / float(crop.shape[0])
            crop = cv2.resize(
                crop, (max(1, int(crop.shape[1] * scale)), _TEMPLATE_HEIGHT),
                interpolation=cv2.INTER_AREA,
            )
            templates[ch].append(crop.astype(np.float32) / 255.0)
    return {ch: variants for ch, variants in templates.items() if variants}


def _char_score(candidate: np.ndarray, template: np.ndarray) -> float:
    """Best normalised correlation between a candidate char and a template.

    Both images are resized to a common height while preserving their natural
    width (so ``M``/``W`` keep their wide aspect instead of being squashed),
    then the candidate is slid across the template with ``TM_CCOEFF_NORMED``.
    Per-window normalisation makes the score a shape match rather than a
    measure of painted-background overlap, so dissimilar glyphs score low.
    """
    a = candidate.astype(np.float32)
    b = template.astype(np.float32)
    if a.max() > 1.0:
        a /= 255.0
    if b.max() > 1.0:
        b /= 255.0
    scale = _TEMPLATE_HEIGHT / float(a.shape[0])
    a = cv2.resize(a, (max(1, int(a.shape[1] * scale)), _TEMPLATE_HEIGHT), interpolation=cv2.INTER_AREA)
    b = cv2.resize(b, (max(1, int(b.shape[1] * scale)), _TEMPLATE_HEIGHT), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((_TEMPLATE_HEIGHT, a.shape[1] + b.shape[1]), np.float32)
    canvas[:, :b.shape[1]] = b
    result = cv2.matchTemplate(canvas, a, cv2.TM_CCOEFF_NORMED)
    return float(result.max()) if result.size else 0.0


class PlateDetector(BaseDetector):
    """Detects plate-like rectangles and reads them when pixels allow."""

    model_key = "plate"

    def __init__(self, model_path: str | None = None) -> None:
        # Only try to load a YOLO model if a real path is supplied.
        super().__init__(model_path or None)
        self.use_opencv = not self.is_loaded
        global _TEMPLATES
        if _TEMPLATES is None:
            _TEMPLATES = _build_templates()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def detect(self, image: np.ndarray, conf_threshold: float = 0.40) -> list[dict[str, Any]]:
        """Return plate detections.

        Each detection carries ``bbox``, ``plate_text`` (str or None),
        ``read_attempted`` and ``attributes`` with plate + vehicle metadata.
        """
        if self.is_loaded:
            plates = self._run_model(image, conf_threshold)
        else:
            plates = self._locate_plates(image, conf_threshold)

        vehicles = self._detect_vehicles(image)
        for plate in plates:
            text, ocr_conf = self._ocr_plate(image, plate["bbox"])
            plate["plate_text"] = text
            plate["read_attempted"] = ocr_conf is not None
            attrs: dict[str, Any] = {
                "plate_text": text,
                "ocr_confidence": ocr_conf,
            }
            if vehicles:
                vehicle = self._nearest_vehicle(plate["bbox"], vehicles)
                if vehicle is not None:
                    attrs["vehicle_type"] = vehicle["type"]
                    attrs["vehicle_colour"] = self._vehicle_colour(
                        image, vehicle["bbox"]
                    )
            plate["attributes"] = attrs
        return plates

    # ------------------------------------------------------------------ #
    # Vehicle attribution (reuses the installed COCO person/object model)
    # ------------------------------------------------------------------ #
    def _detect_vehicles(self, image: np.ndarray) -> list[dict[str, Any]]:
        if not person_detector.is_loaded:
            return []
        raw = person_detector._run_model(image, 0.45)
        vehicles = []
        for det in raw:
            if det.get("cls_id") in _VEHICLE_IDS:
                det["type"] = _VEHICLE_IDS[det["cls_id"]]
                vehicles.append(det)
        return vehicles

    @staticmethod
    def _nearest_vehicle(plate_bbox: list[int], vehicles: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Pick the vehicle box whose centre is closest to the plate centre."""
        px = (plate_bbox[0] + plate_bbox[2]) / 2.0
        py = (plate_bbox[1] + plate_bbox[3]) / 2.0
        best: Optional[dict[str, Any]] = None
        best_d = float("inf")
        for vehicle in vehicles:
            vx = (vehicle["bbox"][0] + vehicle["bbox"][2]) / 2.0
            vy = (vehicle["bbox"][1] + vehicle["bbox"][3]) / 2.0
            d = (vx - px) ** 2 + (vy - py) ** 2
            if d < best_d:
                best, best_d = vehicle, d
        return best

    def _vehicle_colour(self, image: np.ndarray, bbox: list[int]) -> str:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        crop = image[max(0, y1):y2, max(0, x1):x2]
        if crop.size == 0:
            return "unknown"
        colour = clothing_module._dominant_colour(crop)
        return clothing_module._nearest_colour(colour)

    # ------------------------------------------------------------------ #
    # OpenCV box locator (text-cluster based)
    # ------------------------------------------------------------------ #
    def _locate_plates(self, image: np.ndarray, conf: float) -> list[dict[str, Any]]:
        """Find plates by clustering character blobs instead of box morphology.

        This copes far better with real car photos than edge-morphology --
        the vehicle outline, door seams and grille all fuse into huge contours,
        but the plate's characters are reliably small, evenly-spaced blobs that
        group nicely into a left-to-right run.

        Plates are physically bright (white or yellow background, dark text),
        so every candidate character must sit inside a bright mask; that alone
        removes specks and lettering found on dark/coloured surfaces.
        """
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        gray = cv2.medianBlur(gray, 3)

        # Bright plate-background mask: white, or the yellow rear-ride plates.
        bright = gray > 150
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h_ch, s_ch, v_ch = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        yellow = (h_ch >= 18) & (h_ch <= 45) & (s_ch > 90) & (v_ch > 140)
        bright_support = (bright | yellow)
        plate_mask = cv2.morphologyEx(
            bright_support.astype(np.uint8), cv2.MORPH_ERODE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)),
        ).astype(bool)

        # Dark text on the bright plate.
        block = max(15, min(51, (w // 8) | 1))
        thr = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, block, 7,
        )

        contours, _ = cv2.findContours(thr, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

        min_ch_h, max_ch_h = 8, max(10, int(h * 0.35))
        chars: list[tuple[int, int, int, int]] = []
        for cnt in contours:
            cx, cy, cw, chh = cv2.boundingRect(cnt)
            if chh < min_ch_h or chh > max_ch_h:
                continue
            if cw < 3 or cw > int(w * 0.12):
                continue
            aspect = cw / float(max(1, chh))
            if aspect >= 1.3 or aspect < 0.22:
                continue  # merged row or dot / slash
            # Real characters sit on bright (white/yellow) plate material all
            # around them. Sample a ring of pixels just outside the glyph --
            # specks in dark clutter fail this because nothing around them is
            # bright. The radius stays under a full character height so the
            # outermost plate characters (whose ring would reach past the plate
            # edge onto dark bodywork) are not wrongly rejected.
            cx0 = cx + cw // 2
            cy0 = cy + chh // 2
            radius = max(4, int(chh * 0.6))
            ring_hits = 0
            ring_total = 0
            for angle in range(8):
                px = int(cx0 + radius * np.cos(angle * np.pi / 4))
                py = int(cy0 + radius * np.sin(angle * np.pi / 4))
                if 0 <= px < w and 0 <= py < h:
                    ring_total += 1
                    if bright_support[py, px]:
                        ring_hits += 1
            if ring_total >= 6 and ring_hits < 3:
                continue  # not surrounded by plate material
            chars.append((cx, cy, cw, chh))
        if len(chars) < 4:
            return []

        runs = self._group_char_runs(chars)
        candidates: list[dict[str, Any]] = []
        for run in runs:
            min_x = min(c[0] for c in run)
            min_y = min(c[1] for c in run)
            max_x = max(c[0] + c[2] for c in run)
            max_y = max(c[1] + c[3] for c in run)
            run_h = max_y - min_y
            # slight outward pad so the bbox hugs the plate border; the vertical
            # pad is generous so small plates still cover most of the box with
            # bright background (their characters fill nearly all the plate).
            pad_x, pad_y = int(run_h * 0.10), int(run_h * 0.40)
            x1, y1 = max(0, min_x - pad_x), max(0, min_y - pad_y)
            x2, y2 = min(w, max_x + pad_x), min(h, max_y + pad_y)

            box_w, box_h = x2 - x1, y2 - y1
            aspect = box_w / float(max(1, box_h))
            if aspect < 1.3 or aspect > _MAX_ASPECT:
                continue
            if (box_w * box_h) / (h * w) > _MAX_AREA_RATIO:
                continue

            candidate = image[y1:y2, x1:x2]
            mask = plate_mask[y1:y2, x1:x2]
            if mask.size and mask.mean() < 0.35:
                continue  # dominant background must be bright plate material
            hue = cv2.cvtColor(candidate, cv2.COLOR_BGR2HSV)
            sat_mean = float(np.mean(hue[:, :, 1]))
            val_mean = float(np.mean(hue[:, :, 2]))
            if val_mean < 60 or sat_mean > 200:
                continue  # must look like a bright white/yellow plate

            count = len(run)
            score = min(0.98, 0.5 + 0.35 * (min(count, 10) / 9.0))
            if score < conf:
                continue
            candidates.append((count, {
                "class": "plate",
                "confidence": round(score, 2),
                "bbox": [x1, y1, x2, y2],
                "cls_id": -1,
                "tracking_id": None,
                "plate_text": None,
                "read_attempted": False,
            }))

        # drop near-duplicate runs (same plate detected from two rows)
        candidates.sort(key=lambda item: item[0], reverse=True)
        kept: list[dict[str, Any]] = []
        for count, det in candidates:
            bx1, by1, bx2, by2 = det["bbox"]
            overlap = False
            for other in kept:
                ox1, oy1, ox2, oy2 = other["bbox"]
                ix = max(0, min(bx2, ox2) - max(bx1, ox1))
                iy = max(0, min(by2, oy2) - max(by1, oy1))
                inter = ix * iy
                small = min((bx2 - bx1) * (by2 - by1), (ox2 - ox1) * (oy2 - oy1))
                if small and inter / small > 0.6:
                    overlap = True
                    break
            if not overlap:
                kept.append(det)
        return kept[:8]

    @staticmethod
    def _group_char_runs(chars: list[tuple[int, int, int, int]]) -> list[list[tuple[int, int, int, int]]]:
        """Group character blobs into left-to-right single-line plate runs.

        Two passes: first cluster the blobs into text *lines* (so isolated
        specks sitting on the same pixel row can never seed a run before the
        real characters), then walk each line left-to-right and split at gaps
        that are far larger than an inter-character space.
        """
        chars = sorted(chars, key=lambda c: (c[1], c[0]))
        lines: list[list[tuple[int, int, int, int]]] = []
        for ch in chars:
            placed = False
            for line in lines:
                y0 = min(c[1] for c in line)
                y1 = max(c[1] + c[3] for c in line)
                same_row = (ch[1] < y1) and (ch[1] + ch[3] > y0)
                if same_row and (y1 - y0) < 2.2 * ch[3]:
                    line.append(ch)
                    placed = True
                    break
            if not placed:
                lines.append([ch])

        runs: list[list[tuple[int, int, int, int]]] = []
        for line in lines:
            line_sorted = sorted(line, key=lambda c: c[0])
            current: list[tuple[int, int, int, int]] = []
            for ch in line_sorted:
                if not current:
                    current = [ch]
                    continue
                ref_h = current[-1][3]
                gap = ch[0] - (current[-1][0] + current[-1][2])
                if -0.3 * ref_h <= gap <= 3.2 * ref_h:
                    current.append(ch)
                else:
                    if len(current) >= 4:
                        runs.append(current)
                    current = [ch]
            if len(current) >= 4:
                runs.append(current)
        return runs

    # ------------------------------------------------------------------ #
    # OCR (template matching — no tesseract dependency)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _project_chars(thr: np.ndarray) -> list[tuple[int, int]]:
        """Split thresholded text into character column-ranges by vertical ink.

        Column projection separates neighbouring glyphs reliably even when a
        coarse adaptive threshold welds their bottoms together (the letter tops
        still leave ink-free columns). Adjacent runs whose gap is smaller than
        ~1/5 of a character height are merged (e.g. ``numberplate``-style pairs
        or broken strokes), while the wide intra-word spaces stay as separators.
        """
        h, w = thr.shape[:2]
        ink = thr > 0
        profile = ink.sum(axis=0).astype(float)
        peak = profile.max()
        if peak <= 0:
            return []
        active = profile > max(2.0, 0.12 * peak)
        merge_gap = max(2.0, (h * 0.6) * 0.18)
        runs: list[tuple[int, int]] = []
        start: int | None = None
        for x in range(w):
            if active[x]:
                if start is None:
                    start = x
                continue
            if start is not None:  # ink run just ended
                if runs and (start - runs[-1][1]) <= merge_gap:
                    runs[-1] = (runs[-1][0], x)
                else:
                    runs.append((start, x + 1))
                start = None
        if start is not None:
            if runs and (start - runs[-1][1]) <= merge_gap:
                runs[-1] = (runs[-1][0], w)
            else:
                runs.append((start, w))

        # Any run clearly wider than one character usually holds two fused
        # glyphs (bleeding strokes). Split it at the deepest interior valley of
        # the ink profile, provided both halves are large enough to be letters.
        split: list[tuple[int, int]] = []
        for a, b in runs:
            width = b - a
            if width > 0.85 * max(10.0, h * 0.6):
                seg = profile[a:b].copy()
                lo_cut, hi_cut = int(width * 0.18), int(width * 0.82)
                if hi_cut <= lo_cut + 2:
                    split.append((a, b))
                    continue
                valley = lo_cut + int(np.argmin(seg[lo_cut:hi_cut]))
                if seg[valley] < 0.7 * seg.max():
                    split.append((a, a + valley))
                    split.append((a + valley + 1, b))
                else:
                    split.append((a, b))
            else:
                split.append((a, b))
        return [r for r in split if r[1] - r[0] >= 2]

    def _ocr_plate(self, image: np.ndarray, bbox: list[int]) -> tuple[Optional[str], Optional[float]]:
        """Read characters inside a plate box; returns (text, confidence)."""
        x1, y1, x2, y2 = bbox
        # The locator box hugs the glyphs; pad so edge characters are not cut.
        py = int((y2 - y1) * 0.15)
        px = max(py, int((y2 - y1) * 0.10))
        frame_h, frame_w = image.shape[:2]
        crop = image[max(0, y1 - py):min(frame_h, y2 + py),
                     max(0, x1 - px):min(frame_w, x2 + px)]
        if crop.size == 0 or crop.shape[0] < 12:
            return None, None

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        h, w = gray.shape[:2]

        # Fast, robust path when tesseract is installed: small crops are
        # upscaled (LSTM OCR needs a decent x-height) and read as one line.
        if _tesseract_ready():
            up = gray
            if w < 320:
                sc = max(1.0, 320.0 / w)
                up = cv2.resize(gray, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
            text, conf = _tesseract_ocr(up)
            if text is not None:
                return text, conf

        if _TEMPLATES is None or len(_TEMPLATES) < 10:
            return None, None

        # Otsu binarisation (self-scaling to the plate's own brightness) keeps
        # letter-spaced glyphs separate; a light opening splits minor fusions
        # caused by bleeding strokes/noise on real photos.
        thr = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )[1]
        ink_frac = float((thr > 0).mean())
        if ink_frac < 0.02 or ink_frac > 0.7:
            # Otsu mis-split (all-bright or all-ink crop) — fall back to adaptive.
            block = max(15, (min(h, w) // 3) | 1)
            thr = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, block, 7,
            )
        thr = cv2.morphologyEx(thr, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

        char_h = h
        raw_candidates: list[dict[str, Any]] = []
        # Column projection ranges; genuinely wide ranges (two glyphs fused
        # after the opening) are split at their deepest ink valley.
        for x0, x1_ in self._project_chars(thr):
            cw = x1_ - x0
            if cw < 0.06 * h or cw > 0.95 * h:
                continue  # noise speck or a full-width blob (plate border)
            window = thr[:, x0:x1_]
            ys, xs = np.nonzero(window)
            if len(xs) < 4:
                continue
            cy0, cy1 = int(ys.min()), int(ys.max()) + 1
            chh = cy1 - cy0
            if chh < 0.28 * h or (cw / float(max(1, chh))) > 1.3:
                continue  # a speck / merged wall / dash
            char = window[cy0:cy1, :]
            best_ch, best_score = "", 0.0
            for ch, variants in _TEMPLATES.items():
                for template in variants:
                    score = _char_score(char, template)
                    if score > best_score:
                        best_ch, best_score = ch, score
            if best_score >= 0.40:
                raw_candidates.append({
                    "x": x0, "w": cw, "ch": best_ch, "score": best_score,
                })

        # Greedily accept the strongest characters; drop weak fragments that
        # sit inside an already-accepted (higher confidence) character box.
        raw_candidates.sort(key=lambda c: c["score"], reverse=True)
        accepted: list[dict[str, Any]] = []
        for cand in raw_candidates:
            overlap = False
            for other in accepted:
                iw = min(cand["x"] + cand["w"], other["x"] + other["w"]) - max(cand["x"], other["x"])
                if iw > 0.6 * min(cand["w"], other["w"]):
                    overlap = True
                    break
            if not overlap:
                accepted.append(cand)
        accepted.sort(key=lambda c: c["x"])
        if len(accepted) < 4:
            return None, None

        text = "".join(c["ch"] for c in accepted)
        confidence = round(float(np.mean([c["score"] for c in accepted])) * 0.9, 2)
        return text, confidence


# Singleton.
plate_detector = PlateDetector()