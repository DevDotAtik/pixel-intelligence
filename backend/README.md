# AI-Based Intelligent Video Analytics Platform
## Smart India Hackathon Problem Statement 187 / SIH26187

---

## Project Overview

This prototype demonstrates how existing CCTV camera infrastructure can be enhanced with AI-based video analytics for border surveillance. It currently provides real-time face detection, tracking, and counting. The configured object model exposes only a `FACE` class, so person and vehicle detection are unavailable until a compatible multi-class model is intentionally configured.

**Important:** This is a **prototype for learning and SIH demonstration only**. It is not production-ready for actual border surveillance.

---

## SIH Problem Statement

**Problem:** Existing CCTV cameras continuously generate video, but manually monitoring all feeds is difficult, especially for border surveillance where multiple streams need constant attention.

**Solution:** An AI video analytics layer that processes camera streams automatically, detecting and tracking objects, providing counting and analytics, and connecting to a Django dashboard for visualization.

---

## Architecture

```text
Camera (Webcam/RTSP) 
    ↓ OpenCV
    ↓ YOLO (Face + Object Detection)
    ↓ Tracking
    ↓ Counting & Analytics
    ↓ FastAPI
    ↓ JSON Response
    ↓ Django Dashboard
```

### Core Components

1. **Face Detection** - Compact YOLO face model (`model.pt`) by default; set `FACE_MODEL_PATH` to `yolov8m-face.pt` for higher accuracy when hardware allows
2. **Object Detection** - Optional general YOLO model (`model.pt`); inspect its class list before enabling object or vehicle claims
3. **Tracking** - Object tracking using tracking IDs
4. **Counting** - Current count vs. event count separation
5. **Event Logging** - JSON-based event persistence
6. **FastAPI Backend** - RESTful API services
7. **Django Frontend** - Dashboard and user interface

---

## Technologies

- **Language:** Python 3.x
- **Computer Vision:** OpenCV, YOLO (Ultralytics)
- **Backend:** FastAPI
- **Frontend:** Django
- **Model Format:** PyTorch .pt files
- **Environment:** CPU-compatible (GPU optional)

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/face-analytics.git
cd face-analytics
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

### 3. Install Dependencies

```bash
pip install opencv-python ultralytics fastapi uvicorn django djangorestframework
```

### 4. Verify Model Files

Ensure the following model files exist in the `backend/` directory:

- `yolov8m-face.pt` - Face detection model (class: 'face')
- `model.pt` - General object detection model (class: 'FACE')

### 5. Environment Configuration

Create a `.env` file in the `backend/` directory:

```ini
CONFIDENCE_THRESHOLD=0.50
CAMERA_INDEX=0
IMAGE_WIDTH=1280
IMAGE_HEIGHT=720
PROCESS_EVERY_N_FRAMES=1
```

---

## Environment Setup

### Python Version

```bash
python3 --version  # Should output Python 3.x
```

### OpenCV Installation

```bash
python3 -c "import cv2; print(cv2.__version__)"
```

### Ultralytics Installation

```bash
python3 -c "from ultralytics import YOLO; print(ultralytics.__version__)"
```

### CUDA/GPU (Optional)

The application works on CPU by default. If NVIDIA GPU is available:

```bash
python3 -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

If CUDA is available, the YOLO models will automatically use GPU acceleration. Otherwise, CPU is used.

---

## Model Setup

### Available Models

| Model | Path | Classes | Task |
|-------|------|---------|------|
| Face Model | `backend/model.pt` by default | `FACE` | Compact face detection |
| Object Model | `backend/model.pt` | `FACE` | Face detection only (not a general object model) |
| Plate Model | `backend/plate_model.pt` | N/A | Not available (optional) |

### Model Configuration

Model paths are configured in `backend/config.py`:

```python
FACE_MODEL_PATH = BASE_DIR / "yolov8m-face.pt"
OBJECT_MODEL_PATH = BASE_DIR / "model.pt"
PLATE_MODEL_PATH = BASE_DIR / "plate_model.pt"
```

If a model file doesn't exist, the corresponding detection module is automatically disabled.

---

## Running the Webcam Demo

### Arena/Next.js frontend integration

The Arena console uses `CAM-01` for the real Django MJPEG stream. `CAM-01` is
the UI camera label; the Linux device index is configured separately. On the
development laptop used for this prototype, `/dev/video0` is the usable stream
and `/dev/video1` is not a readable camera feed.

Start the services in separate terminals:

```bash
# FastAPI / YOLO
venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Django camera gateway (uses the webcam and serves /video/)
CAMERA_INDEX=0 venv/bin/python manage.py runserver 127.0.0.1:8001

# Arena frontend
cd ../frontend
npm install
npm run dev
```

Open `http://127.0.0.1:3000/console`. The feed is delivered by Django while
YOLO inference runs in a background worker, so slow CPU inference does not hide
the camera image. Set `NEXT_PUBLIC_DJANGO_URL` in the frontend environment if
the Django host or port differs.

### Start the FastAPI Backend

```bash
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Run the Live Face Detection Demo

```bash
python3 phase5_live_face.py
```

Or run the comprehensive counting+FPS demo:

```bash
python3 phase9_counting_fps.py
```

### Expected Output

The demo processes webcam frames and displays:
- Face count in real-time
- FPS (Frames Per Second)
- Inference time per frame
- Tracking IDs for detected objects

Press 'Q' or Ctrl+C to stop the demo.

---

## FastAPI Endpoints

### GET /

```json
{
    "message": "AI Video Analytics API",
    "version": "1.0.0",
    "status": "operational",
    "configuration": {
        "confidence_threshold": 0.5,
        "camera_index": 0,
        "resolution": "1280x720",
        "device": "cpu",
        "face_model_exists": true,
        "object_model_exists": true,
        "plate_model_exists": false
    }
}
```

### GET /health

```json
{
    "status": "ok"
}
```

### GET /models

```json
{
    "face_model": {
        "exists": true,
        "path": "/path/to/yolov8m-face.pt"
    },
    "object_model": {
        "exists": true,
        "path": "/path/to/model.pt"
    },
    "plate_model": {
        "exists": false,
        "path": "/path/to/plate_model.pt"
    }
}
```

### POST /detect

Accepts an image and returns detection results:

```json
{
    "detections": [
        {
            "class": "face",
            "confidence": 0.94,
            "bbox": [100, 80, 250, 300]
        }
    ],
    "analytics": {
        "face_count": 1,
        "object_count": 1
    }
}
```

### GET /events

Returns recent detection events:

```json
{
    "events": [
        {
            "timestamp": "2026-09-06T17:42:31",
            "event_type": "VEHICLE_DETECTED",
            "class_name": "car",
            "confidence": 0.91,
            "tracking_id": 4
        }
    ],
    "count": 1
}
```

### GET /event-counts

```json
{
    "counts": {
        "FACE_DETECTED": 2,
        "PERSON_DETECTED": 1,
        "VEHICLE_DETECTED": 1
    }
}
```

---

## Django Integration

### Django Frontend Integration

The Django frontend calls the FastAPI backend through HTTP requests. The Django project should NOT contain YOLO logic - all detection processing is done by the FastAPI backend.

### API Communication Flow

```text
Django Frontend
    ↓ HTTP Request
    ↓ FastAPI Backend
    ↓ OpenCV + YOLO
    ↓ Detection + Tracking
    ↓ JSON Response
    ↓ Django Dashboard
```

### Django Settings

Add the FastAPI base URL to Django settings:

```python
FASTAPI_BASE_URL = os.environ.get('FASTAPI_BASE_URL', 'http://localhost:8000')
```

### Django Views (Example)

```python
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class FastAPIHealthView(APIView):
    def get(self, request):
        try:
            resp = requests.get(f"{FASTAPI_BASE_URL}/api/health", timeout=5)
            return Response(resp.json())
        except requests.ConnectionError:
            return Response(
                {"status": "offline"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
```

### Django URL Example

```python
from django.urls import path
from .fastapi_views import HealthCheckView

urlpatterns = [
    path('health/', FastAPIHealthView.as_view(), name='health'),
]
```

---

## Detection & Counting Explanation

### Current Count vs. Event Count

**Important Distinction:**

| Concept | Description |
|---------|-------------|
| **Current Count** | Number of objects currently visible in the frame |
| **Event Count** | Number of unique detection events that occurred |

**Example:**

If one person appears for 300 frames:

- ❌ **BAD:** Total detections = 300 (counts every frame)
- ✅ **CORRECT:** Person ID 1, frames 1-300 (one tracked person)
- ✅ **CURRENT COUNT:** Current persons visible = 1
- ✅ **EVENT COUNT:** Total unique person events = 1

### Tracking IDs

Each detected object is assigned a unique tracking ID that persists across frames. When an object leaves the frame and re-enters, it may receive a new ID. The system maintains a set of active tracking IDs and counts unique events based on these IDs.

---

## Performance

### FPS Calculation

FPS (Frames Per Second) is calculated based on the processing time per frame:

```text
FPS = number_of_frames / elapsed_time
```

### Factors Affecting FPS

- **Camera Resolution:** Higher resolution = lower FPS
- **YOLO Model Size:** Larger models (yolov8m, yolov8x) = slower inference
- **CPU/GPU:** GPU acceleration significantly improves FPS
- **Number of Detections:** More objects = longer inference time
- **Frame Processing Frequency:** Processing every Nth frame improves FPS

### Typical Performance (CPU)

- **Face Model (yolov8m-face):** ~25-30 FPS on 1280x720 resolution
- **Object Model:** ~10-15 FPS depending on model size
- **Inference Time:** ~30-50 ms per frame (CPU)

### Performance Optimizations

If performance is poor, try:

1. **Lower inference resolution** - Set `IMAGE_WIDTH` and `IMAGE_HEIGHT` in config
2. **Process every Nth frame** - Set `PROCESS_EVERY_N_FRAMES` in config
3. **Use smaller YOLO model** - Switch to `yolov8n-face.pt` or `yolov8n.pt`
4. **Use GPU** - Ensure CUDA is available and PyTorch is built with GPU support

---

## Limitations

### Current Limitations

1. **No GPU acceleration by default** - Works on CPU; GPU requires CUDA setup
2. **Single camera support** - Multi-camera support not implemented
3. **No RTSP/CCTV stream integration** - Webcam only for prototype
4. **No number plate OCR** - Plate detection model not included
5. **Fixed confidence threshold** - Could be made configurable per-class
6. **Simple tracking algorithm** - May lose tracking IDs after occlusions

### Known Issues

- Face model `model.pt` has class name 'FACE' (uppercase) vs 'face' (lowercase) in `yolov8m-face.pt`
- Vehicle class filtering depends on model classes matching configured VEHICLE_CLASSES
- Event counting accumulates across all frames (reset required for long-running sessions)

---

## Privacy Considerations

### Important Privacy Notes

1. **Only process authorized camera feeds** - Do not monitor unauthorized streams
2. **Do not store raw webcam frames by default** - Only store event metadata
3. **Make event logging configurable** - Enable/disable via configuration
4. **Do not implement identity recognition** - This project uses face detection only, not recognition
5. **Clearly distinguish face detection from face recognition** - This system detects faces, not specific individuals
6. **Do not expose camera streams publicly during development**
7. **Validate uploaded files** - Ensure only valid images are processed
8. **Add basic API security considerations** - Use HTTPS in production, limit CORS origins

### Data Handling

- **Frames:** Not stored by default (processed in memory only)
- **Events:** Stored in `backend/events/events.json` (metadata only: timestamp, class, confidence, tracking_id)
- **Images:** No webcam images stored by default

---

## Future Scope

### Planned Extensions (Roadmap)

1. **RTSP CCTV Integration** - Replace webcam with CCTV/RTSP streams
2. **Multi-Camera Support** - Process multiple camera feeds simultaneously
3. **Edge Deployment** - Optimize for edge devices (Raspberry Jetson, etc.)
4. **GPU Acceleration** - Full CUDA support for improved FPS
5. **Number Plate OCR** - Add Tesseract OCR for plate text extraction
6. **Object Intrusion Detection** - Detect unauthorized border crossings
7. **Restricted-Zone Detection** - Define and monitor restricted areas
8. **Line Crossing** - Detect when objects cross virtual lines
9. **Loitering Detection** - Identify objects staying in one area too long
10. **Motion Detection** - Detect movement in the frame
11. **Alert System** - Email/SMS alerts for specific events
12. **Database Integration** - Persistent event storage (PostgreSQL, MongoDB)
13. **Docker Deployment** - Containerized deployment
14. **Cloud/Edge Architecture** - distributed processing setup
15. **Role-Based Dashboard** - Different views for different users
16. **Camera Health Monitoring** - Monitor CCTV camera status and connectivity

---

## SIH Demo - 5 Minutes

### Demo Sequence

**STEP 1:** Start the backend
```bash
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**STEP 2:** Start webcam_demo.py
```bash
python3 phase5_live_face.py
```

**STEP 3:** Show one face
- System displays: `Faces: 1`

**STEP 4:** Add another person
- System displays: `Faces: 2`

**STEP 5:** Move one person out of the frame
- Current count decreases
- Event count remains historically recorded

**STEP 6:** Show an object/vehicle (if available)
- System detects: `car`, `person`, etc.

**STEP 7:** Show FPS
- Display: `FPS: 28.4`

**STEP 8:** Open FastAPI Swagger documentation
- Visit: `http://localhost:8000/docs`

**STEP 9:** Send a test image to POST /detect
- Use the test image or webcam capture

**STEP 10:** Show the JSON response
- Verify detection results and analytics

**STEP 11:** Show Django dashboard architecture
- Explain how Django calls FastAPI endpoints

**STEP 12:** Explain the architecture
> "The webcam is only our prototype camera source. The backend architecture is designed so that an authorized CCTV/RTSP stream can later replace the webcam input."

---

## Repository Structure

```text
face-analytics/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI main application
│   │   ├── config.py        # Configuration module
│   │   ├── api/
│   │   │   ├── routes.py    # API routes
│   │   │   └── health.py    # Health check
│   │   ├── detection/
│   │   │   ├── face_detector.py  # Face detection
│   │   │   ├── object_detector.py  # Object detection
│   │   │   └── tracker.py  # Object tracking
│   │   ├── analytics/
│   │   │   ├── counter.py   # Counting system
│   │   │   └── event_logger.py  # Event logging
│   │   └── utils/
│   │       └── image.py     # Image utilities
│   ├── events/              # Event log files
│   │   └── events.json      # Detection events
│   ├── config.py            # Global configuration
│   ├── phase1_image_test.py   # Phase 1 test
│   ├── phase2_image_test.py   # Phase 2 test
│   ├── phase3_webcam_test.py  # Phase 3 test
│   ├── phase4_face_detection.py  # Phase 4 test
│   ├── phase5_live_face.py      # Live face detection
│   ├── phase6_object_detection.py   # Object detection
│   ├── phase7_vehicle_detection.py  # Vehicle detection
│   ├── phase8_tracking.py       # Tracking test
│   ├── phase9_counting_fps.py   # Counting + FPS demo
│   ├── requirements.txt     # Python dependencies
│   └── README.md            # This file
├── frontend/                # Django frontend (teammate's area)
│   ├── manage.py
│   ├── face_backend/
│   └── detector/
└── .gitignore
```

---

## Git / Team Workflow

### Repository Structure

```text
face-analytics/
├── frontend/           # My teammate's area
│   └── Django frontend
└── backend/            # My area
    └── AI video analytics
```

### Recommended Branches

- `main` - Stable version
- `feature/backend-ai` - Backend AI development
- `feature/django-dashboard` - Django frontend development

### Workflow

1. Work mainly inside `backend/`
2. My teammate works mainly inside `frontend/`
3. Keep frontend and backend loosely coupled
4. Do not modify frontend files unless necessary for integration
5. Use API contracts between FastAPI and Django

---

## Presentation-Friendly UI

### OpenCV Demo Layout

```text
================================================
          AI VIDEO ANALYTICS
================================================

LIVE CAMERA

[                CAMERA                ]

FACE DETECTION
Current Faces: 2
Face Events: 8

OBJECT DETECTION
Persons: 3
Cars: 1
Vehicles: 1
Other Objects: 2

SYSTEM
FPS: 28.4
Inference: 31 ms
Resolution: 1280x720

RECENT EVENTS
17:42:31 FACE_DETECTED
17:42:32 PERSON_DETECTED
17:42:35 VEHICLE_DETECTED
================================================
```

### Readable Overays

- Confidence scores displayed with bounding boxes
- Class names shown above each detection
- FPS and inference time shown in corner
- Event log shown in sidebar

---

## Security and Privacy

### Checklist

- [ ] Only process authorized camera feeds
- [ ] Do not implement covert monitoring
- [ ] Do not store raw webcam frames by default
- [ ] Make event logging configurable
- [ ] Do not implement identity recognition
- [ ] Clearly distinguish face detection from face recognition
- [ ] Do not expose camera streams publicly during development
- [ ] Do not hardcode secrets (use environment variables)
- [ ] Validate uploaded files
- [ ] Add basic API security considerations to README

---

## Acknowledgments

- **Ultralytics** for YOLO models and framework
- **OpenCV** computer vision library
- **FastAPI** for modern API development
- **Django** for frontend framework
- **Smart India Hackathon** for the problem statement and opportunity

---

## Contact

- **Backend Developer:** [Your Name]
- **Frontend Developer:** [Teammate's Name]
- **Repository:** [GitHub Repository URL]
