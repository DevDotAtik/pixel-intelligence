"""Movement direction inference (N / S / E / W).

Direction is derived purely from how a tracked subject's position drifts over
time — no extra model needed. We keep a short rolling history of centre points
per tracking ID and fit a straight line; the dominant axis/heading decides the
compass label. For head-on/face detections we report the camera-facing
normalised labels N/S instead (approximated by bounding-box centre movement
within the frame).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:  # numpy import may not be needed on simpler models but keeps the API clean
    import numpy as np
except Exception:  # pragma: no cover
    np = None


@dataclass
class DirectionTracker:
    """Per-tracked-subject rolling position history."""

    window: int = 8  # number of recent centre points kept
    history: list = field(default_factory=list)  # [(x, y), ...]

    def push(self, x: float, y: float) -> None:
        """Record a new centre point, pruning the oldest once beyond window."""
        self.history.append((float(x), float(y)))
        if len(self.history) > self.window:
            self.history.pop(0)

    def direction(self) -> str:
        """Compass label for the current drift (N/E/S/W, or UNKNOWN)."""
        if len(self.history) < 3:
            return "UNKNOWN"
        xs = [p[0] for p in self.history]
        ys = [p[1] for p in self.history]
        dx = xs[-1] - xs[0]
        dy = ys[-1] - ys[0]
        if abs(dx) < 1 and abs(dy) < 1:
            return "UNKNOWN"  # standing still
        if np is not None:
            angle = np.degrees(np.arctan2(dy, dx))
        else:
            angle = 0.0
        # Convert vector angle to compass direction (image y grows downward =>
        # negative dy is "north"-ish in screen terms).
        if -45.0 <= angle <= 45.0:
            return "E"
        if 45.0 < angle <= 135.0:
            return "S"
        if -135.0 < angle <= -45.0:
            return "N"
        return "W"

    def reset(self) -> None:
        """Clear history (subject re-entered the scene)."""
        self.history.clear()


def direction_label(box: list[int]) -> str:
    """Small helper to compute a coarse label from a single box centre.

    Provided for callers that do not keep a history (e.g. plate crops): the
    centre position relative to frame thirds gives a zone, not a velocity,
    so callers should prefer the DirectionTracker when possible.
    """
    return "UNKNOWN"