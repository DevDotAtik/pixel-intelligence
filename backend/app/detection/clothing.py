"""Clothing analysis — dominant colour and a lightweight garment classifier.

The garments are classified from an *already cropped* person/body region using
image heuristics (aspect ratio + colour-zone analysis). This is intentionally
rule based: it is fast on a CPU, does not need a segmentation model, and is
accurate enough for the demo.

Colour naming is HSV based: brightness and saturation short-circuit first so
dark fabrics resolve to ``black`` (not wash-out grey) and light pastels to
``white``, and only then is hue compared against a small reference table.

Regions are interpreted as (viewed from the camera):
  * upper body (torso): top ~45% of the body box below the head
  * lower body (legs): bottom ~45% of the body box
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import Any

# ---------------------------------------------------------------------------
# Colour naming (BGR -> friendly label) using HSV hue references
# ---------------------------------------------------------------------------
# OpenCV HSV hue lives in [0, 180); these are the anchor hues per colour.
_COLOR_HUES: list[tuple[str, int]] = [
    ("red", 0),
    ("orange", 10),
    ("yellow", 24),
    ("green", 60),
    ("teal", 85),
    ("cyan", 95),
    ("blue", 118),
    ("purple", 140),
    ("pink", 170),
    ("brown", 14),
    ("maroon", 178),
    ("navy", 112),
]


def _hue_dist(h1: int, h2: int) -> int:
    """Circular distance between two OpenCV hue values [0, 180)."""
    d = abs(h1 - h2) % 180
    return min(d, 180 - d)


def _nearest_colour(bgr: tuple[int, int, int]) -> str:
    """Map a BGR triplet to the nearest friendly colour name (HSV aware)."""
    b, g, r = (max(0, min(255, int(c))) for c in bgr)
    v = max(r, g, b)
    mn = min(r, g, b)
    s = int(255 * (v - mn) / max(1, v))
    # Hue via the standard RGB max/min rule (OpenCV-style, in degrees/2).
    if v == mn:
        h = 0
    elif v == r:
        h = int((60 * (g - b) / max(1, v - mn)) % 360) // 2
    elif v == g:
        h = int((120 + 60 * (b - r) / max(1, v - mn)) % 360) // 2
    else:
        h = int((240 + 60 * (r - g) / max(1, v - mn)) % 360) // 2

    # 1) Dark fabric short-circuit — the biggest complaint (black -> grey) is
    #    caused by webcam black reading as a mid-grey. Assume "black" for any
    #    fabric whose brightness is below a generous ceiling.
    if v < 55:
        return "black"

    # 2) Achromatic / pastel short-circuit. Neutral fabrics with only modest
    #    brightness are interpreted as black (webcam "black" rarely reads < 50);
    #    only clearly-lit neutrals climb to grey/white.
    if s < 45:
        return "black" if v < 90 else ("white" if v > 205 else "grey")

    # 3) Dark chromatic shades get their own names instead of bubbling to the
    #    generic hue bucket (navy, maroon, brown are all low-value colours).
    if v < 95:
        if _hue_dist(h, 112) < 26 or _hue_dist(h, 95) < 14:
            return "navy"
        if _hue_dist(h, 178) < 18 or _hue_dist(h, 0) < 18:
            return "maroon"
        if _hue_dist(h, 14) < 24:
            return "brown"

    # 4) General hue lookup, with brightness/context renames.
    name = min(_COLOR_HUES, key=lambda ref: _hue_dist(h, ref[1]))[0]
    if name in {"yellow", "orange"} and v < 150:
        name = "brown"
    if name == "red" and v > 200 and s < 120:
        name = "pink"
    return name


def _dominant_colour(region: np.ndarray) -> tuple[int, int, int]:
    """Return the dominant BGR colour of a region (median to resist noise).

    Near-black background pixels (walls/floors bleeding into a loose person
    box) are excluded from the median so a genuinely dark garment is not
    dragged towards black by darker surroundings.
    """
    if region is None or region.size == 0:
        return (128, 128, 128)
    flat = region.reshape(-1, 3).astype(int)
    keep = flat.max(axis=1) > 20
    if float(keep.mean()) < 0.25:
        keep = np.ones(flat.shape[0], dtype=bool)
    sel = flat[keep]
    if len(sel) == 0:
        return (128, 128, 128)
    bgr = np.median(sel, axis=0).astype(int)
    return (int(bgr[0]), int(bgr[1]), int(bgr[2]))


def _brightness(region: np.ndarray) -> float:
    if region is None or region.size == 0:
        return 0.0
    return float(np.mean(cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)))


def _value(region: np.ndarray) -> float:
    """Mean HSV value (max channel) — a purer measure of how dark a fabric is."""
    if region is None or region.size == 0:
        return 0.0
    return float(np.max(region.reshape(-1, 3), axis=1).mean())


def _top_garment(torso: np.ndarray) -> tuple[str, float]:
    """Name the upper garment.

    1. A collar creates a noticeably lighter band just under the neckline, so a
       brightness difference between the shoulder strip and the rest of the
       torso implies a collared shirt.
    2. Otherwise a very dark, uniform torso is a hoodie/jacket (bulky, sleeves
       share the body colour); a lighter one is a plain t-shirt.
    """
    h, w = torso.shape[:2]
    if h < 8 or w < 8:
        return "top", 0.4
    strip_h = max(1, int(h * 0.16))
    shoulder = torso[0:strip_h, :]
    body = torso[strip_h:, :]
    if body.size == 0:
        return "top", 0.4
    diff = abs(_brightness(shoulder) - _brightness(body))
    if diff > 28:
        return "shirt", 0.6
    if _value(body) < 90:
        return "hoodie / jacket", 0.6
    return "t-shirt", 0.55


def _skin_fraction(region: np.ndarray) -> float:
    """Fraction of pixels matching the classic (r > g > b) skin heuristic."""
    if region is None or region.size == 0 or region.shape[2] != 3:
        return 0.0
    b = region[:, :, 0].astype(int)
    g = region[:, :, 1].astype(int)
    r = region[:, :, 2].astype(int)
    mask = (r > 90) & (g > 40) & (b > 10) & (r >= g) & (g >= b) \
        & ((r - g) > 12) & ((r - b) > 24)
    return float(mask.mean())


def _has_leg_split(legs: np.ndarray) -> bool:
    """True when the lower-body strip shows two legs with a gap between them.

    Trousers/jeans produce two fabric columns separated by a quasi-uniform
    inter-leg strip (crotch shadow → darker, floor → brighter). A dress or
    other one-piece stays continuous across the width, so the centre band
    matches the sides.
    """
    h, w = legs.shape[:2]
    if min(h, w) < 8:
        return False
    row = int(h * 0.7)
    gray = cv2.cvtColor(legs, cv2.COLOR_BGR2GRAY)
    if min(gray.shape[0], gray.shape[1]) < 8:
        return False
    gray = gray[row].astype(float)
    third = max(1, w // 3)
    centre = float(gray[third:(2 * third)].mean())
    sides = float(np.concatenate([gray[:third], gray[2 * third:]]).mean())
    if max(sides, centre) < 18:
        return False
    return min(sides, centre) / max(sides, centre) < 0.9


def _bottom_garment(legs: np.ndarray, bottom_name: str) -> tuple[str, float]:
    """Name the lower garment — shorts (skin) vs jeans/trousers."""
    if legs.size > 0 and _skin_fraction(legs) > 0.25:
        return "shorts", 0.55
    if bottom_name in {"blue", "navy"}:
        return "jeans", 0.62
    return "trousers", 0.55


# ---------------------------------------------------------------------------
# Garment classifier (heuristics on colour zones + geometry)
# ---------------------------------------------------------------------------
def classify_clothing(body_box: list[int], body_crop: np.ndarray) -> dict[str, Any]:
    """Analyse clothing for a person bounding box.

    Args:
        body_box: [x1, y1, x2, y2] of the person in the original frame.
        body_crop: the BGR crop of the person region.

    Returns:
        dict with ``colour``, ``top_colour``, ``bottom_colour``, ``type`` and
        ``confidence``.
    """
    if body_crop is None or body_crop.size == 0:
        return {"colour": "unknown", "top_colour": "unknown",
                "bottom_colour": "unknown", "type": "unknown", "confidence": 0.0}

    h, w = body_crop.shape[:2]
    # A tiny crop (distant subject) carries no reliable fabric signal — report
    # "unknown" instead of guessing a plausible-looking but wrong outfit.
    if h < 28 or w < 14:
        return {"colour": "unknown", "top_colour": "unknown",
                "bottom_colour": "unknown", "type": "unknown", "confidence": 0.0}

    # Head strip (top ~18%) excluded; torso & legs from the remainder.
    head_end = int(h * 0.18)
    torso_end = int(h * 0.55)
    torso = body_crop[head_end:torso_end, :]
    legs = body_crop[max(head_end, torso_end):int(h * 0.98), :]

    top_bgr = _dominant_colour(torso)
    bottom_bgr = _dominant_colour(legs) if legs.size else top_bgr
    overall_bgr = _dominant_colour(body_crop)

    top_name = _nearest_colour(top_bgr)
    bottom_name = _nearest_colour(bottom_bgr)
    overall_name = _nearest_colour(overall_bgr)

    aspect = w / max(1, h)
    same_zone = top_name == bottom_name
    top_kind, top_conf = _top_garment(torso)
    bottom_kind, bottom_conf = _bottom_garment(legs, bottom_name)
    confidence = round(max(top_conf, bottom_conf), 2)

    if same_zone:
        if aspect < 0.5 and not _has_leg_split(legs):
            garment = "dress / kurta"
            confidence = 0.62
        else:
            # A single-colour top+bottom is a one-piece; dark fabrics usually
            # mean a hoodie/jacket rather than a tracksuit.
            if overall_bgr[0] + overall_bgr[1] + overall_bgr[2] < 420:
                garment = "hoodie + trousers"
            else:
                garment = "tracksuit"
            confidence = 0.6
    else:
        garment = f"{top_kind} + {bottom_kind}"

    return {
        "colour": overall_name,
        "top_colour": f"{top_name} top",
        "bottom_colour": f"{bottom_name} bottom",
        "type": garment,
        "confidence": confidence,
    }