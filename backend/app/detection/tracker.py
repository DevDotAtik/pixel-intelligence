"""Object tracking module for FastAPI."""
from typing import List, Dict


class TrackingManager:
    """Simple object tracking manager.
    
    Assigns and maintains tracking IDs for detected objects across frames.
    When a detector does not provide IDs itself, the manager matches boxes of
    the same class using Intersection over Union (IoU). This is intentionally
    lightweight for the prototype; it is not person identification.
    """
    
    def __init__(self):
        # Map of tracking_id -> latest class, bounding box and frame number.
        self.tracked_objects: Dict[int, Dict] = {}
        self.next_id: int = 1
        self.frame_count: int = 0
    
    def update(self, detections: List[Dict]) -> List[Dict]:
        """Update tracking state with new detections.
        
        Args:
            detections: List of dicts with 'class', 'confidence', 'bbox' keys
            
        Returns:
            Detections with added tracking_id keys
        """
        self.frame_count += 1
        
        result_detections = []
        matched_ids = set()
        
        for det in detections:
            cls = det.get("class", "unknown")
            tid = det.get("tracking_id")
            
            # If a tracker supplied an ID, preserve it.
            if tid is not None:
                tid = int(tid)
            else:
                tid = self._find_best_match(cls, det.get("bbox", []), matched_ids)
                if tid is None:
                    tid = self.next_id
                    self.next_id += 1

            self.tracked_objects[tid] = {
                "class": cls,
                "bbox": det.get("bbox", []),
                "last_seen": self.frame_count,
            }
            matched_ids.add(tid)
            result_detections.append({**det, "tracking_id": tid})
        
        # Clean up IDs that haven't been seen for a while
        # Remove IDs not seen in the last 30 frames
        ids_to_remove = [
            tid for tid, state in self.tracked_objects.items()
            if self.frame_count - state["last_seen"] > 30
        ]
        for tid in ids_to_remove:
            del self.tracked_objects[tid]
        
        return result_detections

    def _find_best_match(self, class_name: str, bbox: list, matched_ids: set) -> int | None:
        """Return the best unmatched same-class track whose box overlaps."""
        best_id, best_iou = None, 0.30
        for tid, state in self.tracked_objects.items():
            if tid in matched_ids or state["class"] != class_name:
                continue
            score = self._iou(bbox, state["bbox"])
            if score > best_iou:
                best_id, best_iou = tid, score
        return best_id

    @staticmethod
    def _iou(first: list, second: list) -> float:
        if len(first) != 4 or len(second) != 4:
            return 0.0
        ax1, ay1, ax2, ay2 = first
        bx1, by1, bx2, by2 = second
        intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
        union = max(0, ax2 - ax1) * max(0, ay2 - ay1) + max(0, bx2 - bx1) * max(0, by2 - by1) - intersection
        return intersection / union if union else 0.0
    
    def get_active_ids(self) -> List[int]:
        """Get list of currently active tracking IDs."""
        return list(self.tracked_objects.keys())
    
    def get_object_count(self, class_name: str = None) -> int:
        """Get count of tracked objects, optionally filtered by class.
        
        Note: This basic implementation doesn't filter by class since
        tracking IDs are assigned independent of class.
        """
        return len(self.tracked_objects)


# Create singleton instance
tracking_manager = TrackingManager()
