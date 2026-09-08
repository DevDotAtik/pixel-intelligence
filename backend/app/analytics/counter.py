"""Analytics counter module for FastAPI."""
from typing import Dict, Set, Optional
from pathlib import Path


class CountingSystem:
    """Separates current count from event count as specified in requirements.
    
    Current Count: Number of objects currently visible.
    Event Count: Number of unique detection events occurred.
    """
    
    def __init__(self):
        # Current counts - objects currently visible in latest frame
        self.current_counts: Dict[str, int] = {}
        self.unique_tracking_ids_per_class: Dict[str, Set[int]] = {}
        
        # Event counts - accumulated unique detection events
        self.class_event_counts: Dict[str, int] = {}
        self.total_unique_tracking_ids: Set[int] = set()
        
        # Tracking state across frames
        self.previous_tracking_ids: Set[int] = set()
    
    def update(self, detections: list):
        """Update counting state with new detections from a frame.
        
        Args:
            detections: List of dicts with 'class' and 'tracking_id' keys
        """
        # Get current frame counts
        current_counts, unique_counts = self._count_current(detections)
        
        # Update current counts
        self.current_counts = current_counts
        self.unique_tracking_ids_per_class = unique_counts
        
        # Count new unique events
        new_event_counts, current_unique_ids = self._count_new_events(detections)
        
        # Accumulate event counts
        for cls, count in new_event_counts.items():
            if cls not in self.class_event_counts:
                self.class_event_counts[cls] = 0
            self.class_event_counts[cls] += count
        
        # Update total unique tracking IDs
        self.total_unique_tracking_ids.update(current_unique_ids)
        
        # Update previous tracking IDs for next frame
        self.previous_tracking_ids = current_unique_ids
    
    def _count_current(self, detections: list) -> tuple:
        """Count currently visible objects (not accumulated)."""
        counts = {}
        tracking_ids_per_class = {}
        
        for det in detections:
            cls = det.get("class", "unknown")
            tid = det.get("tracking_id")
            
            if cls not in counts:
                counts[cls] = 0
                tracking_ids_per_class[cls] = set()
            
            counts[cls] += 1
            if tid is not None:
                tracking_ids_per_class[cls].add(tid)
        
        # Return unique ID counts per class
        unique_counts = {}
        for cls in counts:
            unique_counts[cls] = len(tracking_ids_per_class.get(cls, set()))
        
        return counts, unique_counts
    
    def _count_new_events(self, detections: list) -> tuple:
        """Count new unique detection events based on tracking IDs."""
        current_ids = set()
        new_ids = set()
        
        for det in detections:
            tid = det.get("tracking_id")
            if tid is not None:
                current_ids.add(tid)
        
        # New IDs are those we haven't seen before
        for tid in current_ids:
            if tid not in self.previous_tracking_ids:
                new_ids.add(tid)
        
        # Update previous tracking IDs
        self.previous_tracking_ids = set(current_ids)
        
        # Count new events per class
        new_event_count = {}
        for det in detections:
            cls = det.get("class", "unknown")
            tid = det.get("tracking_id")
            if tid is not None and tid in new_ids:
                if cls not in new_event_count:
                    new_event_count[cls] = 0
                new_event_count[cls] += 1
        
        return new_event_count, current_ids
    
    def get_summary(self) -> dict:
        """Get a summary of current and event counts."""
        return {
            "current_counts": self.current_counts,
            # _count_current already converts each class set to its size.
            "unique_tracking_ids_per_class": self.unique_tracking_ids_per_class.copy(),
            "class_event_counts": self.class_event_counts,
            "total_unique_tracking_ids": len(self.total_unique_tracking_ids)
        }


# Create singleton instance
counting_system = CountingSystem()
