"""Lightweight IoU tracker — assigns stable tracking IDs across frames.

Kept deliberately simple (per-class IoU association with Hungarian-free greedy
matching) because the target hardware is a low-end laptop and detections only
arrive every N frames. History supports the "subject reappeared after vanish"
detection used by the timeline.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

# Small module-local counter so IDs stay unique across classes without
# clashing when multiple detectors share the tracker.
_id_counter = 0


def _next_tracking_id() -> int:
    global _id_counter
    _id_counter += 1
    return _id_counter


@dataclass
class Tracklet:
    """A single tracked object."""

    tracking_id: int
    class_name: str
    bbox: list[int]  # [x1,y1,x2,y2]
    last_frame: int
    confidence: float = 0.0
    history: list = field(default_factory=list)  # recent bboxes

    @property
    def centre(self) -> tuple[float, float]:
        return (self.bbox[0] + self.bbox[2]) / 2.0, (self.bbox[1] + self.bbox[3]) / 2.0


def _iou(a: list[int], b: list[int]) -> float:
    """Intersection-over-union of two [x1,y1,x2,y2] boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / max(1.0, union)


class IoUTracker:
    """Greedy IoU tracker with per-class tracklet pools."""

    def __init__(self, iou_threshold: float = 0.25, max_missed: int = 12) -> None:
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self.tracklets: dict[str, list[Tracklet]] = defaultdict(list)
        self.frame = 0

    def update(
        self,
        detections: list[dict[str, Any]],
        class_name: str = "person",
        frame: int | None = None,
    ) -> list[dict[str, Any]]:
        """Associate detections with tracklets and return enriched detections.

        Adds ``tracking_id`` and a stable ``subject_key`` (class + id) to each
        detection. Subjects whose tracklet has been absent for long are treated
        as new when they reappear (so the timeline logs a fresh sighting).
        """
        if frame is not None:
            self.frame = frame
        else:
            self.frame += 1

        pool = self.tracklets[class_name]

        matched: dict[int, Tracklet] = {}  # tracklet_idx -> update mask
        used = set()
        for det in detections:
            best_idx, best_score = -1, 0.0
            for i, trk in enumerate(pool):
                if i in used:
                    continue
                score = _iou(trk.bbox, det["bbox"])
                if score > best_score:
                    best_idx, best_score = i, score
            if best_idx != -1 and best_score >= self.iou_threshold:
                trk = pool[best_idx]
                trk.bbox = det["bbox"]
                trk.confidence = det["confidence"]
                trk.last_frame = self.frame
                trk.history = (trk.history + [det["bbox"]])[-30:]
                det["tracking_id"] = trk.tracking_id
                det["subject_key"] = f"{class_name}:{trk.tracking_id}"
                used.add(best_idx)
            else:
                det["tracking_id"] = _next_tracking_id()
                det["subject_key"] = f"{class_name}:{det['tracking_id']}"
                pool.append(
                    Tracklet(
                        tracking_id=det["tracking_id"],
                        class_name=class_name,
                        bbox=det["bbox"],
                        last_frame=self.frame,
                        confidence=det["confidence"],
                        history=[det["bbox"]],
                    )
                )

        # Cleanup tracklets that have been missing for too long (they become
        # "new" subjects on their next appearance).
        alive = [t for t in pool if self.frame - t.last_frame <= self.max_missed]
        self.tracklets[class_name] = alive
        return detections

    def seen_frames(self, class_name: str) -> int:
        return self.frame


# Singleton tracker shared by all detectors.
tracker = IoUTracker()