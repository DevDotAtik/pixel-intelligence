"""Phase 2: OpenCV image handling (headless compatible)"""
import cv2
from pathlib import Path


def test_image_load():
    """Test loading an image and saving a copy."""
    image_path = Path("/home/atik-pathan/Desktop/project/pixel-intelligence/backend/test.jpeg")
    
    if not image_path.exists():
        print(f"[ERROR] Image not found: {image_path}")
        return False
    
    # Load image
    img = cv2.imread(str(image_path))
    if img is None:
        print("[ERROR] Failed to load image")
        return False
    
    print(f"[SUCCESS] Image loaded: {img.shape}")
    
    # Save a processed copy instead of displaying
    output_path = Path("/tmp/phase2_output.jpg")
    cv2.imwrite(str(output_path), img)
    print(f"[SUCCESS] Image saved to: {output_path}")
    
    return True


def test_invalid_image():
    """Test handling of invalid image paths."""
    img = cv2.imread("nonexistent_image.jpg")
    if img is None:
        print("[SUCCESS] Correctly handled invalid image path (returned None)")
    else:
        print("[WARNING] Should have returned None for invalid image")


if __name__ == "__main__":
    test_image_load()
    test_invalid_image()