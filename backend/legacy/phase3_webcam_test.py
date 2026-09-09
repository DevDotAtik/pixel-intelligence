"""Phase 3: OpenCV Webcam access (headless compatible)"""
import cv2
from pathlib import Path


def test_webcam_access():
    """Test opening webcam and reading frames."""
    camera_index = 0
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print(f"[ERROR] Cannot open webcam with index {camera_index}")
        return False
    
    print(f"[SUCCESS] Webcam opened with index {camera_index}")
    
    # Get camera properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"[INFO] Resolution: {width}x{height}")
    print(f"[INFO] FPS (reported): {fps}")
    
    # Read a frame
    ret, frame = cap.read()
    if not ret or frame is None:
        print("[ERROR] Failed to read frame from webcam")
        cap.release()
        return False
    
    print(f"[SUCCESS] Frame captured: {frame.shape}")
    
    # Save the frame instead of displaying (headless)
    output_path = Path("/tmp/phase3_frame.jpg")
    cv2.imwrite(str(output_path), frame)
    print(f"[SUCCESS] Frame saved to: {output_path}")
    
    # Release resource
    cap.release()
    return True


def test_camera_failure():
    """Test handling of invalid camera index."""
    cap = cv2.VideoCapture(9999)
    if not cap.isOpened():
        print("[SUCCESS] Correctly handled invalid camera index")
    else:
        print("[WARNING] Should have failed for invalid camera index")
    cap.release()


if __name__ == "__main__":
    test_webcam_access()
    test_camera_failure()