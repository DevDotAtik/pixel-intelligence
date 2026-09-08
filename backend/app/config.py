"""FastAPI application configuration."""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Model paths - configurable
FACE_MODEL_PATH = os.getenv("FACE_MODEL_PATH", str(BASE_DIR / "model.pt"))
OBJECT_MODEL_PATH = os.getenv("OBJECT_MODEL_PATH", str(BASE_DIR / "model.pt"))
PLATE_MODEL_PATH = str(BASE_DIR / "plate_model.pt")

# Configuration defaults
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.50"))
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
IMAGE_WIDTH = int(os.getenv("IMAGE_WIDTH", "640"))
IMAGE_HEIGHT = int(os.getenv("IMAGE_HEIGHT", "480"))
# 320 is a good CPU prototype trade-off. Use 416/640 when accuracy matters.
INFERENCE_SIZE = int(os.getenv("INFERENCE_SIZE", "320"))
PROCESS_EVERY_N_FRAMES = int(os.getenv("PROCESS_EVERY_N_FRAMES", "3"))
CPU_THREADS = int(os.getenv("CPU_THREADS", str(max(1, min(4, os.cpu_count() or 1)))) )
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "75"))

# Device configuration
try:
    import torch
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    if DEVICE == "cpu":
        torch.set_num_threads(CPU_THREADS)
except ImportError:
    DEVICE = "cpu"

# Model existence checks
FACE_MODEL_EXISTS = Path(FACE_MODEL_PATH).exists() if FACE_MODEL_PATH else False
OBJECT_MODEL_EXISTS = Path(OBJECT_MODEL_PATH).exists() if OBJECT_MODEL_PATH else False
PLATE_MODEL_EXISTS = Path(PLATE_MODEL_PATH).exists() if PLATE_MODEL_PATH else False


def get_config():
    """Get configuration dictionary."""
    return {
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "camera_index": CAMERA_INDEX,
        "resolution": f"{IMAGE_WIDTH}x{IMAGE_HEIGHT}",
        "device": DEVICE,
        "inference_size": INFERENCE_SIZE,
        "process_every_n_frames": PROCESS_EVERY_N_FRAMES,
        "cpu_threads": CPU_THREADS,
        "face_model_exists": FACE_MODEL_EXISTS,
        "object_model_exists": OBJECT_MODEL_EXISTS,
        "plate_model_exists": PLATE_MODEL_EXISTS,
    }
