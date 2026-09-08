"""Image utility functions for FastAPI."""
import numpy as np
import cv2
from pathlib import Path


def load_image_from_bytes(image_bytes: bytes) -> np.ndarray:
    """Load an OpenCV image from raw bytes.
    
    Args:
        image_bytes: Raw image bytes (typically from HTTP POST body)
    
    Returns:
        numpy array representing the image, or None if invalid
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img


def encode_image_to_jpeg(img: np.ndarray, quality: int = 90) -> bytes:
    """Encode a numpy image array to JPEG bytes.
    
    Args:
        img: numpy array (OpenCV image format)
        quality: JPEG quality (1-100)
    
    Returns:
        JPEG-encoded bytes
    """
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    result, encimg = cv2.imencode('.jpg', img, encode_param)
    if result:
        return encimg.tobytes()
    return b""


def resize_image(img: np.ndarray, width: int, height: int) -> np.ndarray:
    """Resize an image to specified dimensions.
    
    Args:
        img: Input image array
        width: Target width
        height: Target height
    
    Returns:
        Resized image array
    """
    return cv2.resize(img, (width, height))


def get_image_info(img: np.ndarray) -> dict:
    """Get basic image information.
    
    Args:
        img: Image array
    
    Returns:
        Dictionary with image dimensions and properties
    """
    return {
        "height": img.shape[0],
        "width": img.shape[1],
        "channels": img.shape[2] if len(img.shape) > 2 else 1,
        "size_bytes": img.nbytes
    }