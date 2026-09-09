"""Clothing analysis — dominant colour and a lightweight garment classifier.

The garments are classified from an *already cropped* person/body region using
image heuristics (aspect ratio + colour-zone analysis). This is intentionally
rule based: it is fast on a CPU, does not need a segmentation model, and is
accurate enough for the demo. The colour naming uses a small HSL lookup table.

Regions are interpreted as (viewed from the camera):
  * upper body (torso): top ~45% of the body box below the head
  * lower body (legs): bottom ~45% of the body box
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import Any

# ---------------------------------------------------------------------------
# Colour naming (BGR -> friendly label)
# ---------------------------------------------------------------------------
_COLOR_NAMES: list[tuple[str, tuple[int, int, int]]] = [
    ("red", (0, 0, 200)),
    ("maroon", (0, 0, 128)),
    ("orange", (0, 128, 255)),
    ("yellow", (0, 255, 255)),
    ("green", (0, 170, 0)),
    ("teal", (128, 200, 0)),
    ("cyan", (200, 200, 0)),
    ("blue", (255, 0, 0)),
    ("navy", (128, 0, 0)),
    ("purple", (200, 0, 150)),
    ("pink", (200, 120, 220)),
    ("brown", (60, 80, 140)),
    ("white", (245, 245, 245)),
    ("grey", (128, 128, 128)),
    ("black", (20, 20, 20)),
]


def _nearest_colour(bgr: tuple[int, int, int]) -> str:
    """Map a BGR triplet to the nearest friendly colour name."""
    best_name, best_dist = "grey", float("inf")
    for name, ref in _COLOR_NAMES:
        dist = (bgr[0] - ref[0]) ** 2 + (bgr[1] - ref[1]) ** 2 + (bgr[2] - ref[2]) ** 2
        if dist < best_dist:
            best_name, best_dist = name, dist
    return best_name


def _dominant_colour(region: np.ndarray) -> tuple[int, int, int]:
    """Return the dominant BGR colour of a region (median to resist noise)."""
    if region is None or region.size == 0:
        return (128, 128, 128)
    # Median per channel is robust against background bleed.
    bgr = np.median(region.reshape(-1, 3), axis=0).astype(int)
    return (int(bgr[0]), int(bgr[1]), int(bgr[2]))


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
    if h < 8 or w < 8:
        return {"colour": "unknown", "top_colour": "unknown",
                "bottom_colour": "unknown", "type": "unknown", "confidence": 0.0}

    # Head strip (top ~14%) excluded; torso & legs from the remainder.
    head_end = int(h * 0.18)
    torso_end = int(h * 0.55)
    torso = body_crop[head_end:torso_end, :]
    legs = body_crop[max(head_end, torso_end):int(h * 0.98), :]

    top_bgr = _dominant_colour(torso)
    bottom_bgr = _dominant_colour(legs)
    overall_bgr = _dominant_colour(body_crop)

    top_name = _nearest_colour(top_bgr)
    bottom_name = _nearest_colour(bottom_bgr)
    overall_name = _nearest_colour(overall_bgr)

    aspect = w / max(1, h)
    # Uniform colour over the whole body => likely a dress / kurta / overalls.
    same_zone = top_name == bottom_name
    # Legs visible and shorter than torso => skirts/dresses.
    bottom_active = int(np.mean(cv2.cvtColor(legs, cv2.COLOR_BGR2GRAY)) > 40)

    garment = "unknown"
    confidence = 0.45
    if bottom_active == 0:
        garment = "body-suit/overalls"
    elif same_zone and aspect < 0.55:
        garment = "dress / kurta" if h > w * 1.6 else "one-piece"
        confidence = 0.62
    elif aspect >= 0.55 and not same_zone:
        garment = "shirt + trousers" if bottom_name in {"blue", "black", "grey", "brown"} else "shirt + shorts"
        confidence = 0.58
    elif same_zone:
        garment = "tracksuit / hoodie"
        confidence = 0.6
    else:
        garment = "t-shirt + trousers"
        confidence = 0.5

    return {
        "colour": overall_name,
        "top_colour": f"{top_name}' top",
        "bottom_colour": f"{bottom_name}'s bottom",
        "type": garment,
        "confidence": round(confidence, 2),
    }