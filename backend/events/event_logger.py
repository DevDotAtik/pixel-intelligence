"""Event logging module for detection events."""
import json
from datetime import datetime, timezone
from pathlib import Path


EVENTS_FILE = Path(__file__).resolve().with_name("events.json")


def _load_events():
    """Load events from the JSON file."""
    if EVENTS_FILE.exists():
        try:
            with open(EVENTS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_events(events):
    """Save events to the JSON file."""
    try:
        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=2)
    except IOError as e:
        print(f"[ERROR] Failed to save events: {e}")


def log_event(event_type, class_name, confidence, tracking_id=None):
    """Log a detection event.
    
    Args:
        event_type: Type of event (FACE_DETECTED, PERSON_DETECTED, etc.)
        class_name: Detected class name
        confidence: Detection confidence score
        tracking_id: Optional tracking ID
    
    Returns:
        The logged event dictionary
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_type": event_type,
        "class_name": class_name,
        "confidence": confidence,
        "tracking_id": tracking_id
    }
    
    events = _load_events()
    events.append(event)
    
    # Keep only last 1000 events to prevent unbounded growth
    if len(events) > 1000:
        events = events[-1000:]
    
    _save_events(events)
    return event


def log_face_detected(confidence, tracking_id=None):
    """Log a face detection event."""
    return log_event("FACE_DETECTED", "face", confidence, tracking_id)


def log_person_detected(confidence, tracking_id=None):
    """Log a person detection event."""
    return log_event("PERSON_DETECTED", "person", confidence, tracking_id)


def log_vehicle_detected(confidence, tracking_id=None, vehicle_class="car"):
    """Log a vehicle detection event."""
    return log_event("VEHICLE_DETECTED", vehicle_class, confidence, tracking_id)


def log_plate_detected(confidence, tracking_id=None, plate_text=None):
    """Log a number plate detection event."""
    event = log_event("PLATE_DETECTED", "plate", confidence, tracking_id)
    if plate_text:
        event["plate_text"] = plate_text
    return event


def get_recent_events(limit=50):
    """Get the most recent events.
    
    Args:
        limit: Maximum number of events to return
    
    Returns:
        List of event dictionaries, most recent first
    """
    events = _load_events()
    return list(reversed(events[-limit:]))


def get_events_by_type(event_type, limit=50):
    """Get recent events filtered by type.
    
    Args:
        event_type: Event type to filter by
        limit: Maximum number of events to return
    
    Returns:
        List of matching event dictionaries
    """
    events = _load_events()
    filtered = [e for e in events if e.get("event_type") == event_type]
    return list(reversed(filtered[-limit:]))


def get_event_counts():
    """Get counts of events by type."""
    events = _load_events()
    counts = {}
    for event in events:
        etype = event.get("event_type", "unknown")
        counts[etype] = counts.get(etype, 0) + 1
    return counts


def clear_events():
    """Clear all events from the log."""
    _save_events([])


if __name__ == "__main__":
    # Quick test
    print("[TEST] Logging sample events...")
    log_face_detected(0.94, tracking_id=1)
    log_person_detected(0.88, tracking_id=2)
    log_vehicle_detected(0.91, tracking_id=4, vehicle_class="car")
    
    print("[TEST] Recent events:")
    for event in get_recent_events(limit=5):
        print(f"  {event['event_type']}: {event['class_name']} "
              f"conf={event['confidence']} id={event['tracking_id']}")
    
    print(f"[TEST] Event counts: {get_event_counts()}")
