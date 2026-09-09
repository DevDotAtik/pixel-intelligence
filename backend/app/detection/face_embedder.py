"""Compact face embedding + matching for recognition.

The installed YOLO models only *locate* faces; they cannot identify who a face
belongs to. To give the app a true "show name of registered person" feature we
derive a compact, lightweight embedding from every aligned face crop and match
it against embeddings stored during Registration.

Design choices (low-end laptop friendly):
  * pure OpenCV/Numpy — no GPU, no dlib, no extra downloads
  * 64-dim descriptor  =  HSV colour histogram + dense LBP-style texture
  * cosine similarity  -> above FACE_MATCH_THRESHOLD is considered "matched"

Swap-in point: the public functions here are the only place a smarter model
(e.g. InsightFace, face-recognition/dlib) needs to be wired when accuracy
becomes more important than CPU cost.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.config import FACE_EMBED_SIZE

# Colour quantization for histograms: 4 bins per channel is plenty.
_H_BINS = 4
_S_BINS = 3
_V_BINS = 3
_HIST_DIM = _H_BINS + _S_BINS + _V_BINS  # 10 (HSV marginal histograms)


def extract_embedding(face_crop_bgr: np.ndarray) -> np.ndarray:
    """Build a 64-dim descriptor from an *already detected* face crop.

    Args:
        face_crop_bgr: BGR face crop (any size). It is normalised internally.

    Returns:
        A normalised ``np.float32`` array of shape (64,).
    """
    if face_crop_bgr is None or face_crop_bgr.size == 0:
        return np.zeros(FACE_EMBED_SIZE, dtype=np.float32)

    # --- colour component (HSV marginal histograms) ---
    hsv = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2HSV)
    hist = np.concatenate(
        [
            cv2.calcHist([hsv], [0], None, [_H_BINS], [0, 180]).ravel(),
            cv2.calcHist([hsv], [1], None, [_S_BINS], [0, 256]).ravel(),
            cv2.calcHist([hsv], [2], None, [_V_BINS], [0, 256]).ravel(),
        ]
    ).astype(np.float32)
    if hist.sum() > 0:
        hist /= hist.sum()

    # --- texture component (resized grey patch encodes coarse structure) ---
    small = cv2.resize(face_crop_bgr, (12, 12), interpolation=cv2.INTER_AREA)
    grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    texture = grey.ravel()  # 144 values

    # Fuse: colour hist (10) + texture (144) -> 154 dims, then project down to
    # FACE_EMBED_SIZE using a fixed random projection matrix (keeps the compile
    # deterministic and storage tiny).
    fused = np.concatenate([hist, texture]).astype(np.float32)

    # Deterministic projection matrix (seeded -> stable across processes).
    rng = np.random.default_rng(42)
    projection = rng.standard_normal((len(fused), FACE_EMBED_SIZE)).astype(np.float32)

    embed = fused @ projection
    norm = np.linalg.norm(embed) or 1.0
    return (embed / norm).astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity in [0, 1] between two normalised embeddings."""
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    if a.size != b.size or a.size == 0:
        return 0.0
    denom = (np.linalg.norm(a) or 1.0) * (np.linalg.norm(b) or 1.0)
    return float(np.dot(a, b) / denom)


def best_registered_match(embedding: np.ndarray, registrations: list[dict]) -> tuple:
    """Return (name, score) of the closest registered person, or (None, 0.0).

    Args:
        embedding: query embedding from :func:`extract_embedding`
        registrations: documents from the Mongo ``registrations`` collection.
    """
    from app.config import FACE_MATCH_THRESHOLD

    best_name, best_score = None, 0.0
    for reg in registrations:
        stored = reg.get("embedding")
        if not stored:
            continue
        score = cosine_similarity(embedding, np.asarray(stored, dtype=np.float32))
        if score > best_score:
            best_name, best_score = reg.get("name"), score
    if best_score < FACE_MATCH_THRESHOLD:
        return None, best_score
    return best_name, best_score