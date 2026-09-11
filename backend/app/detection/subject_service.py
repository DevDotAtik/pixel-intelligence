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
  * for face detections we consult the registration store: a person is only
    named when the *same* enrolment wins consecutive, unambiguous re-evaluations
    above threshold — so a stranger is left unnamed instead of guessing.

Identity resolution is deliberately defensive (see app.detection.face_embedder):
the heavy embedding runs at most once per subject per ``IDENTITY_REFRESH_SECONDS``
and a name must survive ``FACE_MATCH_CONFIRM`` consecutive evaluations before it
is attached.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

import cv2
import numpy as np

from app.config import (
    FACE_ENROLL_MIN_SAMPLES,
    FACE_MATCH_CONFIRM,
    FACE_MATCH_MARGIN,
    FACE_MATCH_MIN_FACE,
    FACE_MATCH_THRESHOLD,
    IDENTITY_REFRESH_SECONDS,
    VANISH_SECONDS,
)
from app.core import db
from app.detection.face_embedder import (
    best_registered_match,
    embedder_backend,
    extract_embedding,
    face_quality,
)

logger = logging.getLogger(__name__)

# Local cache of "recently vanished at <time>" so we only close each sighting
# once without an extra Mongo read every frame.
_last_click: dict[str, float] = {}


class SubjectService:
    """Owns the open/close lifecycle of sightings + registration matching."""

    def __init__(self) -> None:
        self._registry_cache: list[dict[str, Any]] = []
        self._cache_ts = 0.0
        # Per-subject identity state: key -> {ts, name, score, confirm}
        self._identities: dict[str, dict[str, Any]] = {}
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
        now_t = self._monotonic()
        for det in detections:
            subject_key = det.get("subject_key") or f"{det.get('class')}:anon"
            det["sighting_id"] = None
            det["timeline_action"] = "updated"

            # 1) identity resolution (faces only)
            identity = None
            if det.get("class") == "face" and registrations:
                crop = det.pop("_crop", None)
                identity = self._resolve_identity(subject_key, crop, registrations, now_t)
            else:
                det.pop("_crop", None)
            attrs = det.setdefault("attributes", {})
            if identity:
                attrs["identity"] = identity
                attrs["registered"] = True
            else:
                attrs["registered"] = False
                attrs.pop("identity", None)
            det["identity"] = identity
            det["registered"] = bool(identity)

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

    def refresh_registrations(self) -> None:
        """Discard cached identity decisions after an operator re-enrols someone."""
        self._registry_cache = []
        self._cache_ts = 0.0
        self._identities.clear()

    def reconcile(self) -> None:
        """Close sightings for subjects that have vanished (not seen recently).

        A subject counts as vanished once ``VANISH_SECONDS`` have elapsed since
        its last sighting. Closing flips the Mongo document's ``status`` to
        ``closed``; its *next* appearance will open a fresh timeline entry
        (which is exactly the reappearance behaviour the Analytics tab wants).
        Vanished subjects also drop their identity state so a reappearing
        stranger starts unconfirmed again.
        """
        now_t = self._monotonic()
        for key in list(_last_click):
            if now_t - _last_click[key] < VANISH_SECONDS:
                continue
            sighting = db.get_open_sighting(key)
            if sighting is not None:
                db.close_sighting(sighting["_id"])
            self._identities.pop(key, None)
            del _last_click[key]

    # ------------------------------------------------------------------ #
    # Identity resolution
    # ------------------------------------------------------------------ #
    def _resolve_identity(self, subject_key, crop, registrations, now_t):
        """Return a confirmed identity name for ``subject_key`` or ``None``.

        Rules (defensive against the "anyone is the registered guy" bug):
          * the heavy embedding only runs at most every
            ``IDENTITY_REFRESH_SECONDS`` per subject (reuses the last decision
            in between) so the relaying loop stays smooth;
          * tiny crops (``< FACE_MATCH_MIN_FACE`` px) are never identified;
          * the best match must clear ``FACE_MATCH_THRESHOLD`` (absolute);
          * with multiple enrolments it must also beat the runner-up by
            ``FACE_MATCH_MARGIN`` — a near-tie means "ambiguous, no guess";
          * the same enrolment must win ``FACE_MATCH_CONFIRM`` consecutive
            evaluations before the name is attached.
        """
        cached = self._identities.get(subject_key)
        if cached is not None and now_t - cached["ts"] < IDENTITY_REFRESH_SECONDS:
            # A confirmed name, or a clear rejection, may be safely throttled.
            # Do *not* throttle a promising first candidate: it needs one more
            # observation to confirm, and caching its temporary UNKNOWN state
            # made a real live face keep displaying only "face" for seconds.
            if cached.get("visible") is not None or not cached.get("name"):
                return cached["visible"]

        freshest = {"ts": now_t, "visible": None}
        # The histogram fallback is useful for demos without model weights, but
        # it is not reliable enough to make a claim about a person's identity.
        if embedder_backend() != "onnx":
            logger.warning("Face naming is disabled because ArcFace ONNX is unavailable")
        elif crop is not None and crop.size > 0:
            usable, reason = face_quality(crop, min_side=FACE_MATCH_MIN_FACE)
            if usable:
                try:
                    embedding = extract_embedding(crop)
                    name, score, second = best_registered_match(embedding, registrations)
                    if name is None or not registrations or score < FACE_MATCH_THRESHOLD:
                        freshest["visible"] = None
                    elif len(registrations) > 1 and (score - second) < FACE_MATCH_MARGIN:
                        freshest["visible"] = None  # ambiguous enrolment — no guess
                    else:
                        # confirm only when the identical name keeps winning
                        if cached and cached.get("name") == name:
                            confirm = cached["confirm"] + 1
                        else:
                            confirm = 1
                        freshest.update(
                            {"name": name, "score": score, "confirm": confirm,
                             "visible": name if confirm >= FACE_MATCH_CONFIRM else None}
                        )
                except Exception:
                    logger.exception("identity embedding failed")
            else:
                logger.debug("Skipping face identity for %s: %s", subject_key, reason)
        self._identities[subject_key] = freshest
        return freshest["visible"]

    # ------------------------------------------------------------------ #
    # Registration table
    # ------------------------------------------------------------------ #
    def _registrations(self) -> list[dict[str, Any]]:
        """Cache the registration table for (at most) 30 seconds.

        While the ONNX embedder is active, legacy histogram registrations are
        transparently re-embedded from their stored face photo (and persisted).
        They still need multi-photo re-enrolment before live naming is enabled.
        """
        now_t = self._monotonic()
        if now_t - self._cache_ts > 30 or not self._registry_cache:
            registrations: list[dict[str, Any]] = []
            for reg in db.all_registrations(limit=500):
                # Registrations created before multi-photo enrolment remain in
                # the registry, but cannot label people until re-enrolled.
                # This prevents an old weak single-image reference from
                # overriding the new conservative decision gate.
                if int(reg.get("sample_count", 1)) < FACE_ENROLL_MIN_SAMPLES:
                    continue
                embedding = reg.get("embedding") or []
                # ONNX embedder: re-embed legacy histogram descriptors (64-d)
                # from the stored face photo so existing enrolments match.
                if embedder_backend() == "onnx" and len(embedding) != 512:
                    embedding = self._upgrade_embedding(reg)
                registrations.append({**reg, "embedding": embedding})
            self._registry_cache = registrations
            self._cache_ts = now_t
        return self._registry_cache

    def _upgrade_embedding(self, reg: dict[str, Any]) -> list[float]:
        """Re-embed an old registration from its stored face photo (write-through)."""
        photo = reg.get("face_photo") or ""
        if not photo:
            return []
        try:
            b64 = photo.split("base64,")[-1]
            arr = np.frombuffer(base64.b64decode(b64), np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return []
            embedding = extract_embedding(img).tolist()
            name = reg.get("name")
            if name:
                db.update_registration_embedding(name, embedding)
            return embedding
        except Exception:
            logger.exception("could not upgrade registration embedding for %r", reg.get("name"))
            return []


# Singleton service instance.
subject_service = SubjectService()
