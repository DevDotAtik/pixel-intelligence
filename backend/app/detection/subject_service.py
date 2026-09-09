"""SubjectService — the heart of the Analytics timeline.

It solves the user's core requirement:

> "a person should show up on the timeline when they are first seen, and again
> only when they *reappear* after being gone — not on every single frame."

Behaviour:
  * every detection is attributed to a ``subject_key`` (class + tracking id).
  * when a subject_key has no *open* sighting in Mongo, we open one
    (first_seen / status=open) → this is exactly one timeline entry per
    continuous appearance.
  * while it keeps getting seen we just increment counters on the same document.
  * when it vanishes for ``VANISH_SECONDS`` the sighting is closed. Its next
    appearance (any camera) opens a brand-new timeline entry.
  * for face detections we also consult the registration store: if the
    embedding matches a registered person we attach their name.
"""
from __future__ import annotations

from typing import Any

from app.config import MIN_SIGHTING_SECONDS, VANISH_SECONDS
from app.core import db
from app.detection.face_embedder import best_registered_match

# Local cache of "recently vanished at <time>" so we only close each sighting
# once without an extra Mongo read every frame.
_last_click: dict[str, float] = {}


class SubjectService:
    """Owns the open/close lifecycle of sightings + registration matching."""

    def __init__(self) -> None:
        self._registry_cache: list[dict[str, Any]] = []
        self._cache_ts = 0.0
        from time import monotonic

        self._monotonic = monotonic

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def process_detections(
        self,
        detections: list[dict[str, Any]],
        camera_code: str = "CAM-01",
    ) -> list[dict[str, Any]]:
        """Feed one frame's detections; returns them enriched/annotated.

        Enrichment adds ``sighting_id`` and a ``timeline_action`` per detection
        (``opened`` | ``updated``) so the API layer can flag new appearances.
        """
        registrations = self._registrations()
        for det in detections:
            subject_key = det.get("subject_key") or f"{det.get('class')}:anon"
            det["sighting_id"] = None
            det["timeline_action"] = "updated"

            # 1) identity resolution (faces)
            if det.get("embedding"):
                name, score = best_registered_match(det["embedding"], registrations)
                attrs = det.setdefault("attributes", {})
                if name:
                    attrs["identity"] = name
                    attrs["registered"] = True
                else:
                    attrs["registered"] = False
                    attrs.pop("identity", None)
                det["identity"] = name
                det["registered"] = bool(name)

            # 2) open or keep the sighting
            open_sighting = db.get_open_sighting(subject_key)
            if open_sighting is None:
                det["sighting_id"] = db.open_sighting(
                    subject_key,
                    {
                        "camera_code": camera_code,
                        "class_name": det.get("class", "unknown"),
                        "identity": det.get("identity"),
                        "registered": det.get("registered", False),
                        "attributes": det.get("attributes", {}),
                        "confidence": det.get("confidence", 0.0),
                    },
                )
                det["timeline_action"] = "opened"
            else:
                det["sighting_id"] = open_sighting["_id"]
                db.update_sighting(
                    det["sighting_id"],
                    {
                        "identity": det.get("identity"),
                        "registered": det.get("registered", False),
                        "attributes": det.get("attributes", {}),
                        "confidence": det.get("confidence", 0.0),
                    },
                )

            # 3) aggregate the identity row for the Analytics subject list
            if det.get("identity"):
                db.finalize_subject_aggregate(det["identity"], det.get("attributes", {}))
        return detections

    def mark_seen(self, subject_keys: list[str]) -> None:
        """Record that these subject keys were located on the *current* frame.

        Called once per processed frame with every key that had a detection.
        Keys absent from this call are treated as "not seen"; when they stay
        absent for :data:`VANISH_SECONDS` they get unregistered as gone (the
        closing happens inside :meth:`reconcile`).
        """
        now_t = self._monotonic()
        for key in subject_keys:
            _last_click[key] = now_t

    def reconcile(self) -> None:
        """Close sightings for subjects that have vanished (not seen recently).

        A subject counts as vanished once ``VANISH_SECONDS`` have elapsed since
        its last sighting. Closing flips the Mongo document's ``status`` to
        ``closed``; its *next* appearance will open a fresh timeline entry
        (which is exactly the reappearance behaviour the Analytics tab wants).
        """
        now_t = self._monotonic()
        for key in list(_last_click):
            if now_t - _last_click[key] < VANISH_SECONDS:
                continue
            sighting = db.get_open_sighting(key)
            if sighting is not None:
                db.close_sighting(sighting["_id"])
            del _last_click[key]

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _registrations(self) -> list[dict[str, Any]]:
        """Cache the registration table for (at most) 30 seconds."""
        now_t = self._monotonic()
        if now_t - self._cache_ts > 30 or not self._registry_cache:
            self._registry_cache = [
                {**r, "embedding": r.get("embedding")}
                for r in db.all_registrations(limit=500)
            ]
            self._cache_ts = now_t
        return self._registry_cache


# Singleton service instance.
subject_service = SubjectService()