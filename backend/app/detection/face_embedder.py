"""Face embedding + matching for recognition.

The YOLO face models only *locate* faces; they cannot identify who a face
belongs to. To give the app a real "show name of registered person" feature we
embed aligned face crops and match against embeddings stored during
Registration.

Embedder (primary): a pretrained ArcFace ONNX model (`models/arc_face.onnx`,
insightface-compatible preprocessing) run through onnxruntime — 512-dim,
cosine ~0.90 for the same person and <0.45 for different people, which is what
makes "not registered" actually stay unregistered.

Fallback (no ONNX model): a pure OpenCV/Numpy HSV-colour + coarse-texture
descriptor. It is far less discriminative, so matching with it should rely on
the stricter thresholds + confirmation in SubjectService.

Swap-in point: the public functions here are the only place a smarter model
needs to be wired when accuracy matters more than CPU cost.
"""
from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from app.config import (
    BASE_DIR,
    FACE_EMBED_SIZE,
    FACE_MATCH_MAX_BRIGHTNESS,
    FACE_MATCH_MIN_BRIGHTNESS,
    FACE_MATCH_MIN_FACE,
    FACE_MATCH_MIN_SHARPNESS,
)

logger = logging.getLogger(__name__)

# Where the ONNX embedder may live.
_ONNX_PATH = Path(BASE_DIR) / "models" / "arc_face.onnx"

_ONNX_INPUT_HW = 112
_ONNX_DIM = 512


# --------------------------------------------------------------------------- #
# ONNX (ArcFace) embedder
# --------------------------------------------------------------------------- #
def _load_onnx_session():
    """Load the onnxruntime session for the ArcFace embedder, if present."""
    if not _ONNX_PATH.exists():
        logger.info("No %s — using the lightweight histogram face embedder.", _ONNX_PATH)
        return None
    try:
        import onnxruntime as ort

        sess = ort.InferenceSession(
            str(_ONNX_PATH), providers=["CPUExecutionProvider"]
        )
        inp = sess.get_inputs()[0]
        nhwc = bool(inp.shape) and int(inp.shape[-1]) in (1, 3) and int(inp.shape[1]) in (112, 224)
        logger.info("Loaded face embedder %s (input %s, output %s)",
                    _ONNX_PATH.name, inp.shape, sess.get_outputs()[0].shape)
        return {"session": sess, "input_name": inp.name,
                "output_name": sess.get_outputs()[0].name, "nhwc": nhwc}
    except Exception as error:  # model present but unreadable — keep fallback path
        logger.warning("Face embedder failed to load (%s); falling back to histograms.", error)
        return None


_onnx = _load_onnx_session()


def _embed_onnx(face_crop_bgr: np.ndarray) -> np.ndarray:
    """ArcFace embedding: BGR crop -> normalised 512-dim descriptor."""
    x = cv2.resize(face_crop_bgr, (_ONNX_INPUT_HW, _ONNX_INPUT_HW))
    x = (x.astype(np.float32) - 127.5) * (1.0 / 128.0)
    if _onnx["nhwc"]:
        blob = x[np.newaxis, ...]
    else:
        blob = x[np.newaxis, ...].transpose(0, 3, 1, 2)
    embed = _onnx["session"].run([_onnx["output_name"]], {_onnx["input_name"]: blob})[0]
    embed = np.asarray(embed, dtype=np.float32).reshape(-1)
    norm = np.linalg.norm(embed) or 1.0
    return (embed / norm).astype(np.float32)


# --------------------------------------------------------------------------- #
# Histogram fallback embedder (kept for setups without the ONNX model)
# --------------------------------------------------------------------------- #
_H_BINS = 4
_S_BINS = 3
_V_BINS = 3
_HIST_DIM = _H_BINS + _S_BINS + _V_BINS  # 10


def _embed_histogram(face_crop_bgr: np.ndarray) -> np.ndarray:
    """64-dim descriptor from an *already detected* face crop (fallback)."""
    if face_crop_bgr is None or face_crop_bgr.size == 0:
        return np.zeros(FACE_EMBED_SIZE, dtype=np.float32)

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

    small = cv2.resize(face_crop_bgr, (12, 12), interpolation=cv2.INTER_AREA)
    grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    fused = np.concatenate([hist, grey.ravel()]).astype(np.float32)

    rng = np.random.default_rng(42)
    projection = rng.standard_normal((len(fused), FACE_EMBED_SIZE)).astype(np.float32)
    embed = fused @ projection
    norm = np.linalg.norm(embed) or 1.0
    return (embed / norm).astype(np.float32)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def embedder_backend() -> str:
    """Which embedder is active — 'onnx' (ArcFace) or 'histogram'."""
    return "onnx" if _onnx is not None else "histogram"


def extract_embedding(face_crop_bgr: np.ndarray) -> np.ndarray:
    """Build a normalised identity descriptor from an aligned face crop."""
    if _onnx is not None:
        return _embed_onnx(face_crop_bgr)
    return _embed_histogram(face_crop_bgr)


def face_quality(
    face_crop_bgr: np.ndarray,
    *,
    min_side: int = FACE_MATCH_MIN_FACE,
    min_sharpness: float = FACE_MATCH_MIN_SHARPNESS,
) -> tuple[bool, str]:
    """Check whether a crop is trustworthy enough for identity matching.

    Detection only tells us that a face-shaped region exists.  This cheap gate
    avoids making an identity decision from a tiny, motion-blurred or badly lit
    crop, where even a strong embedder can produce misleading similarities.
    """
    if face_crop_bgr is None or face_crop_bgr.size == 0:
        return False, "no face crop"
    if face_crop_bgr.ndim < 2:
        return False, "invalid face crop"
    height, width = face_crop_bgr.shape[:2]
    if min(height, width) < min_side:
        return False, f"face is smaller than {min_side}px"
    gray = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    if brightness < FACE_MATCH_MIN_BRIGHTNESS:
        return False, "face is too dark"
    if brightness > FACE_MATCH_MAX_BRIGHTNESS:
        return False, "face is too bright"
    # Normalising the crop makes this threshold meaningful across face sizes.
    standard = cv2.resize(gray, (_ONNX_INPUT_HW, _ONNX_INPUT_HW), interpolation=cv2.INTER_AREA)
    sharpness = float(cv2.Laplacian(standard, cv2.CV_64F).var())
    if sharpness < min_sharpness:
        return False, "face is too blurred"
    return True, "ok"


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity in [0, 1] between two normalised embeddings."""
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    if a.size != b.size or a.size == 0:
        return 0.0
    denom = (np.linalg.norm(a) or 1.0) * (np.linalg.norm(b) or 1.0)
    return float(np.dot(a, b) / denom)


def best_registered_match(
    embedding: np.ndarray, registrations: list[dict]
) -> tuple[str | None, float, float]:
    """Closest registered person.

    Returns:
        ``(name, best_score, second_score)`` — name is ``None`` (and best_score
        below threshold) when nothing matches. The caller enforces the relative
        margin so ambiguous enrolment pairs never get named.
    """
    from app.config import FACE_MATCH_THRESHOLD

    best_name, best_score, second_score = None, 0.0, 0.0
    for reg in registrations:
        # Newer enrolments retain all reference vectors, not just their mean.
        # A live face can resemble one valid pose much more than the average of
        # front/left/right poses; accepting the best reference gives reliable
        # recognition on a webcam without weakening the stranger safeguards.
        references = reg.get("reference_embeddings") or []
        if not references and reg.get("embedding"):
            references = [reg["embedding"]]
        scores = [
            cosine_similarity(embedding, np.asarray(reference, dtype=np.float32))
            for reference in references
        ]
        if not scores:
            continue
        score = max(scores)
        if score > best_score:
            second_score = best_score
            best_name, best_score = reg.get("name"), score
        elif score > second_score:
            second_score = score
    if best_score < FACE_MATCH_THRESHOLD:
        return None, best_score, second_score
    return best_name, best_score, second_score
