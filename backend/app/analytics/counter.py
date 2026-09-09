"""Analytics counters for the FastAPI backend.

Separates *current* counts (what this frame shows) from *event* counts
(cumulative unique subjects), matching the Analytics-tab gauges. The data here
is live runtime state; the durable timeline + statistics live in MongoDB via
:mod:`app.core.db`.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


class CountingSystem:
    """Tracks per-class current and cumulative event counts."""

    def __init__(self) -> None:
        self.current_counts: Counter = Counter()
        self.unique_ids_per_class: dict[str, set[int]] = {}
        self.class_event_counts: Counter = Counter()
        self.previous_frame_ids: set[int] = set()

    def update(self, detections: list[dict[str, Any]]) -> None:
        """Refresh counters from one frame's enriched detections."""
        current = Counter()
        by_class: dict[str, set[int]] = {}
        current_ids: set[int] = set()

        for det in detections:
            cls = det.get("class", "unknown")
            tid = det.get("tracking_id")
            current[cls] += 1
            if tid is not None:
                current_ids.add(tid)
                by_class.setdefault(cls, set()).add(tid)

        # Count *brand-new* tracking IDs as events (matching the behaviour of
        # the old event_logger but now per unique object).
        new_ids = current_ids - self.previous_frame_ids
        for det in detections:
            tid = det.get("tracking_id")
            if tid in new_ids:
                self.class_event_counts[det.get("class", "unknown")] += 1

        self.current_counts = current
        self.unique_ids_per_class = {k: len(v) for k, v in by_class.items()}
        self.previous_frame_ids = current_ids

    def get_summary(self) -> dict[str, Any]:
        """JSON-safe snapshot for API responses."""
        return {
            "current_counts": dict(self.current_counts),
            "unique_tracking_ids_per_class": dict(self.unique_ids_per_class),
            "class_event_counts": dict(self.class_event_counts),
            "total_unique_tracking_ids": len(self.previous_frame_ids),
        }


counting_system = CountingSystem()