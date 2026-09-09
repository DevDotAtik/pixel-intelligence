from pathlib import Path
import os

BASE_DIR = Path(__file__).parent

# Model paths - configurable, relative to backend directory
FACE_MODEL_PATH = BASE_DIR / "yolov8m-face.pt"
OBJECT_MODEL_PATH = BASE_DIR / "model.pt"
PLATE_MODEL_PATH = BASE_DIR / "plate_model.pt"

# Configuration
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.50"))
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
IMAGE_WIDTH = int(os.getenv("IMAGE_WIDTH", "1280"))
IMAGE_HEIGHT = int(os.getenv("IMAGE_HEIGHT", "720"))
PROCESS_EVERY_N_FRAMES = int(os.getenv("PROCESS_EVERY_N_FRAMES", "1"))

# Device configuration - auto-detect
try:
    import torch
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    DEVICE = "cpu"

# Vehicle classes - configurable, only count classes that exist in the loaded model
VEHICLE_CLASSES = ["car", "truck", "bus", "motorcycle"]

# Ensure paths are absolute for consistency
FACE_MODEL_PATH = str(FACE_MODEL_PATH)
OBJECT_MODEL_PATH = str(OBJECT_MODEL_PATH)
PLATE_MODEL_PATH = str(PLATE_MODEL_PATH)

# Model existence check
FACE_MODEL_EXISTS = FACE_MODEL_PATH and Path(FACE_MODEL_PATH).exists()
OBJECT_MODEL_EXISTS = OBJECT_MODEL_PATH and Path(OBJECT_MODEL_PATH).exists()
PLATE_MODEL_EXISTS = PLATE_MODEL_PATH and Path(PLATE_MODEL_PATH).exists()

print(f"[CONFIG] Face model exists: {FACE_MODEL_EXISTS} -> {FACE_MODEL_PATH}")
print(f"[CONFIG] Object model exists: {OBJECT_MODEL_EXISTS} -> {OBJECT_MODEL_PATH}")
print(f"[CONFIG] Plate model exists: {PLATE_MODEL_EXISTS} -> {PLATE_MODEL_PATH}")
print(f"[CONFIG] Confidence threshold: {CONFIDENCE_THRESHOLD}")
print(f"[CONFIG] Camera index: {CAMERA_INDEX}")
print(f"[CONFIG] Device: {DEVICE}")
print(f"[CONFIG] Resolution: {IMAGE_WIDTH}x{IMAGE_HEIGHT}")