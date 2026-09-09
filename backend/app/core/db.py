"""MongoDB persistence layer.

This is the single source of truth for the whole app: registered people,
subject sightings (the "person shown timeline"), cumulative stats and cameras.

Collections (database: ``pixel_intelligence``):
  * ``registrations`` — people enrolled via the Registration tab. Each record
    stores a face photo, a compact face embedding and personal details so the
    Face model can greet them by name.
  * ``sightings``     — one document per continuous "appearance" of a subject
    on a camera (opened on first sight, updated while seen, closed when the
    subject vanishes for ``VANISH_SECONDS``). This replaces the old event spam.
  * ``subjects``      — per-identity aggregation fed by sightings. The Analytics
    tab reads this to render the person timeline with photos and names.
  * ``counters``      — last-24h / total volume counters.
  * ``cameras``       — camera registry (code, name, zone, status).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, MongoClient

from app.config import MONGODB_DB, MONGODB_URI

# ---------------------------------------------------------------------------
# Connection (lazy singleton — safe to import before Mongo is reachable)
# ---------------------------------------------------------------------------
_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    """Return the shared Mongo client, creating it on first use."""
    global _client
    if _client is None:
        _client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=int(os.getenv("MONGO_TIMEOUT_MS", "2500")),
        )
    return _client


def get_db():
    """Return the application database handle."""
    return get_client()[MONGODB_DB]


def is_connected() -> bool:
    """Cheap reachability probe used by /api/health and camera status checks."""
    try:
        get_client().admin.command("ping")
        return True
    except Exception:
        return False


def now() -> str:
    """Consistent ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Indexes — created once at startup.
# ---------------------------------------------------------------------------
def ensure_indexes() -> None:
    """Create the indexes the queries rely on (idempotent)."""
    db = get_db()
    db.registrations.create_index([("name", ASCENDING)], unique=True)
    db.registrations.create_index([("created_at", DESCENDING)])

    db.sightings.create_index([("subject_key", ASCENDING), ("status", ASCENDING)])
    db.sightings.create_index(
        [("camera_code", ASCENDING), ("first_seen", DESCENDING)]
    )
    db.sightings.create_index([("class_name", ASCENDING), ("last_seen", DESCENDING)])

    db.subjects.create_index([("updated_at", DESCENDING)])
    db.subjects.create_index([("registered", ASCENDING)])

    db.cameras.create_index([("code", ASCENDING)], unique=True)


# ---------------------------------------------------------------------------
# Camera helpers
# ---------------------------------------------------------------------------
DEFAULT_CAMERAS = [
    {"code": "CAM-01", "name": "Live Webcam", "zone": "Workstation", "status": "active",
     "stream_type": "webcam", "resolution": "640x480", "fps": 20},
    {"code": "CAM-02", "name": "Gate Checkpoint 4", "zone": "Crossing Point",
     "status": "offline", "stream_type": "rtsp", "resolution": "1280x720", "fps": 30},
    {"code": "CAM-03", "name": "Watchtower Echo", "zone": "Sector 7",
     "status": "offline", "stream_type": "rtsp", "resolution": "1280x720", "fps": 30},
    {"code": "CAM-04", "name": "Causeway Freight", "zone": "Sector 2",
     "status": "offline", "stream_type": "rtsp", "resolution": "1280x720", "fps": 30},
]


def seed_cameras() -> None:
    """Insert the default camera fleet if the collection is empty."""
    for cam in DEFAULT_CAMERAS:
        get_db().cameras.update_one({"code": cam["code"]}, {"$setOnInsert": cam}, upsert=True)


def list_cameras() -> list[dict[str, Any]]:
    """All cameras with 24h sighting counts."""
    db = get_db()
    cams = list(db.cameras.find({}, {"_id": 0}).sort("code", 1))
    cutoff = ObjectId.from_datetime(
        datetime.now(timezone.utc) - timedelta(hours=24)
    )
    for cam in cams:
        cam["events_24h"] = db.sightings.count_documents(
            {"camera_code": cam["code"], "_id": {"$gte": cutoff}}
        )
    return cams


def update_camera_status(code: str, status: str) -> Optional[dict[str, Any]]:
    """Set active/maintenance/offline for a camera. Returns the updated row."""
    if status not in {"active", "maintenance", "offline"}:
        return None
    result = get_db().cameras.find_one_and_update(
        {"code": code}, {"$set": {"status": status}}, return_document=True
    )
    if result:
        result.pop("_id", None)
    return result


# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------
def insert_registration(doc: dict[str, Any]) -> dict[str, Any]:
    """Register a person. ``doc`` must include name, embedding and face photo."""
    doc["_id"] = doc.get("_id")
    doc.setdefault("created_at", now())
    doc.setdefault("notes", "")
    get_db().registrations.insert_one(doc)
    doc.pop("_id", None)
    return doc


def find_registration_by_name(name: str) -> Optional[dict[str, Any]]:
    return _clean(find_one_filtered("registrations", {"name": name}))


def all_registrations(limit: int = 200) -> list[dict[str, Any]]:
    return [
        _clean(doc)
        for doc in get_db().registrations.find({}, {"_id": 0}).sort("created_at", DESCENDING).limit(limit)
    ]


def find_one_filtered(collection: str, query: dict[str, Any]) -> Optional[dict[str, Any]]:
    return get_db()[collection].find_one(query)


def _clean(doc: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Subject / sighting helpers (the analytics timeline)
# ---------------------------------------------------------------------------
def open_sighting(subject_key: str, payload: dict[str, Any]) -> str:
    """Start a continuous sighting for a subject_key on a camera."""
    doc = {
        "subject_key": subject_key,
        "camera_code": payload.get("camera_code", "CAM-01"),
        "class_name": payload.get("class_name", "person"),
        "identity": payload.get("identity"),           # matched registration name or None
        "registered": payload.get("registered", False),
        "attributes": payload.get("attributes", {}),   # clothing, colour, direction, plate
        "first_seen": now(),
        "last_seen": now(),
        "total_detections": 1,
        "max_confidence": payload.get("confidence", 0.0),
        "status": "open",
    }
    res = get_db().sightings.insert_one(doc)
    return str(res.inserted_id)


def update_sighting(sighting_id: str, payload: dict[str, Any]) -> None:
    """Refresh an open sighting with the latest frame attribute."""
    get_db().sightings.update_one(
        {"_id": sighting_id},
        {
            "$set": {
                "last_seen": now(),
                "attributes": payload.get("attributes", {}),
                "identity": payload.get("identity"),
                "registered": payload.get("registered", False),
            },
            "$inc": {"total_detections": 1},
            "$max": {"max_confidence": payload.get("confidence", 0.0)},
        },
    )


def close_sighting(sighting_id: str) -> None:
    """Mark a sighting closed (subject vanished from the camera)."""
    get_db().sightings.update_one(
        {"_id": sighting_id}, {"$set": {"status": "closed", "closed_at": now()}}
    )


def get_open_sighting(subject_key: str) -> Optional[dict[str, Any]]:
    """Return the currently-open sighting for a subject key, if any."""
    return get_db().sightings.find_one({"subject_key": subject_key, "status": "open"})


def close_stale_sightings(grace_seconds: float | None = None) -> int:
    """Safety net that closes sightings we have not refreshed for a while.

    The primary close path runs inside the detection loop; this is used on
    startup to clean up sightings that were left "open" by a crashed server.
    """
    from app.config import VANISH_SECONDS

    grace = grace_seconds or VANISH_SECONDS
    cutoff = ObjectId.from_datetime(
        datetime.now(timezone.utc) - timedelta(seconds=grace)
    )
    stale = get_db().sightings.find(
        {"status": "open", "_id": {"$lte": cutoff}}
    )
    closed = 0
    for sighting in stale:
        get_db().sightings.update_one(
            {"_id": sighting["_id"]},
            {"$set": {"status": "closed", "closed_at": now()}},
        )
        closed += 1
    return closed


def finalize_subject_aggregate(identity: str, attributes: dict[str, Any]) -> None:
    """Upsert the identity row used by the Analytics subject timeline."""
    db = get_db()
    db.subjects.update_one(
        {"identity": identity},
        {
            "$set": {
                "identity": identity,
                "registered": attributes.get("registered", False),
                "attributes": attributes,
                "updated_at": now(),
            },
            "$inc": {"sighting_count": 1},
        },
        upsert=True,
    )


# ---------------------------------------------------------------------------
# Event / stats helpers
# ---------------------------------------------------------------------------
def recent_sightings(camera: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    query = {} if not camera else {"camera_code": camera}
    return [
        _clean(doc)
        for doc in get_db().sightings.find(query, {"_id": 0})
        .sort("first_seen", DESCENDING)
        .skip(offset)
        .limit(limit)
    ]


def sighting_counts() -> dict[str, Any]:
    """Total + last-24h counts grouped by class for the header gauges."""
    db = get_db()
    total = db.sightings.count_documents({})
    cutoff = ObjectId.from_datetime(
        datetime.now(timezone.utc) - timedelta(hours=24)
    )
    last24 = db.sightings.count_documents({"_id": {"$gte": cutoff}})
    counts_by_type: dict[str, int] = {}
    for doc in db.sightings.find({}, {"class_name": 1, "_id": 0}):
        key = doc.get("class_name", "unknown")
        counts_by_type[key] = counts_by_type.get(key, 0) + 1
    return {"total": total, "by_class": counts_by_type, "last_24h": last24}