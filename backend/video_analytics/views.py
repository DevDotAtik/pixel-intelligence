import os
import logging
import time
from datetime import datetime
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock

import cv2
import numpy as np
import requests
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

FASTAPI_BASE_URL = os.getenv('FASTAPI_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
CAMERA_INDEX = int(os.getenv('CAMERA_INDEX', '0'))
STATE_LOCK = Lock()
MAX_RECENT_TRACKS = 20
STREAM_WIDTH = int(os.getenv('STREAM_WIDTH', '640'))
STREAM_HEIGHT = int(os.getenv('STREAM_HEIGHT', '480'))
FASTAPI_TIMEOUT_SECONDS = float(os.getenv('FASTAPI_TIMEOUT_SECONDS', '20'))
JPEG_QUALITY = int(os.getenv('JPEG_QUALITY', '75'))
PROCESS_EVERY_N_FRAMES = int(os.getenv('PROCESS_EVERY_N_FRAMES', '3'))
logger = logging.getLogger(__name__)
INFERENCE_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix='analytics')
inference_future: Future | None = None


class HomeView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'video_analytics/index.html')


def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def detect_faces_in_frame(frame_bytes):
    try:
        resp = requests.post(
            f'{FASTAPI_BASE_URL}/api/detect',
            files={'image_data': ('frame.jpg', frame_bytes, 'image/jpeg')},
            timeout=FASTAPI_TIMEOUT_SECONDS
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning('FastAPI detection failed (%s): %s', resp.status_code, resp.text[:500])
        return None
    except requests.RequestException as error:
        logger.warning('FastAPI is unavailable: %s', error)
        return None


class VideoCamera:
    def __init__(self):
        self.video = cv2.VideoCapture(CAMERA_INDEX)
        if self.video.isOpened():
            self.video.set(cv2.CAP_PROP_FRAME_WIDTH, STREAM_WIDTH)
            self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, STREAM_HEIGHT)

    def __del__(self):
        if self.video.isOpened():
            self.video.release()

    def get_frame(self):
        if not self.video.isOpened():
            return None
        ret, frame = self.video.read()
        if not ret or frame is None:
            return None
        # Some webcams ignore requested capture properties; normalise frames so
        # the CPU-only prototype has predictable inference cost.
        if frame.shape[1] != STREAM_WIDTH or frame.shape[0] != STREAM_HEIGHT:
            frame = cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT), interpolation=cv2.INTER_AREA)
        return frame


def draw_overlay(frame, detections=None):
    """Draw detection boxes and a compact, presentation-friendly overlay."""
    output = frame.copy()
    h, w = output.shape[:2]

    detection_count = 0
    if detections:
        detection_count = len(detections)
        for det in detections:
            bbox = det.get('bbox', [0, 0, 0, 0])
            cls = det.get('class', 'face')
            conf = det.get('confidence', 0)
            tid = det.get('tracking_id')

            x1, y1, x2, y2 = [int(v) for v in bbox]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            cv2.rectangle(output, (x1, y1), (x2, y2), (0, 255, 0), 2)

            label = f"ID:{tid} {cls} {conf:.2f}" if tid else f"{cls} {conf:.2f}"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            ly = max(y1 - 8, lh + 10)
            cv2.rectangle(output, (x1, ly - lh - 6), (x1 + lw + 4, ly + 2), (0, 255, 0), -1)
            cv2.putText(output, label, (x1 + 2, ly - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    ts = get_current_time()
    cv2.putText(output, ts, (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(output, f"Live detections: {detection_count}", (10, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    return output


camera = None
last_detections = []
last_analytics = {}
last_updated = None
recent_tracks = {}


def get_camera():
    global camera
    if camera is None or not camera.video.isOpened():
        camera = VideoCamera()
    return camera


def process_detection(frame_bytes):
    """Run slow API inference away from the MJPEG streaming loop."""
    result = detect_faces_in_frame(frame_bytes)
    detections = result.get('detections', []) if result else []
    analytics = result.get('analytics', {}) if result else {}
    update_dashboard_state(detections, analytics)


def queue_detection(frame_bytes):
    """Keep at most one inference in flight to avoid a request backlog."""
    global inference_future
    if inference_future is None or inference_future.done():
        inference_future = INFERENCE_EXECUTOR.submit(process_detection, frame_bytes)


def gen_frames():
    cam = get_camera()
    frame_number = 0
    while True:
        frame_number += 1
        frame = cam.get_frame()
        if frame is None:
            break

        if frame_number % max(1, PROCESS_EVERY_N_FRAMES) == 0:
            encoded_input, input_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if encoded_input:
                queue_detection(input_buffer.tobytes())

        # Never wait for inference here: the browser receives its first camera
        # frame immediately, then overlays update when the worker finishes.
        with STATE_LOCK:
            detections = last_detections.copy()
        output = draw_overlay(frame, detections)

        ret, buf = cv2.imencode('.jpg', output, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ret:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
        # Avoid burning a CPU core while still providing a smooth prototype feed.
        time.sleep(1 / 15)


class VideoStreamView(View):
    def get(self, request, *args, **kwargs):
        cam = get_camera()
        if not cam.video.isOpened():
            return JsonResponse({
                'error': f'Camera index {CAMERA_INDEX} is unavailable.',
                'hint': 'Close other apps using the webcam, check camera permission, or set CAMERA_INDEX.'
            }, status=503)
        return StreamingHttpResponse(
            gen_frames(),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )


@method_decorator(csrf_exempt, name='dispatch')
class DetectView(View):
    def post(self, request, *args, **kwargs):
        # If image uploaded, run detection on it
        if 'image' in request.FILES:
            image_bytes = request.FILES['image'].read()
            result = detect_faces_in_frame(image_bytes)

            if result:
                detections = result.get('detections', [])
                sidebar = build_sidebar_data(detections)
                return JsonResponse({
                    'success': True,
                    'face_count': len(detections),
                    'sidebar': sidebar,
                    'current_time': get_current_time()
                })

            return JsonResponse({'success': False, 'error': 'Detection failed'}, status=500)

        # No image - return current tracking state from the live stream
        global last_detections
        sidebar = build_sidebar_data(last_detections)
        return JsonResponse({
            'success': True,
            'face_count': len(last_detections),
            'sidebar': sidebar,
            'current_time': get_current_time()
        })


class SidebarDataView(View):
    def get(self, request, *args, **kwargs):
        with STATE_LOCK:
            sidebar = build_sidebar_data()
            detection_count = len(last_detections)
            analytics = last_analytics.copy()
            updated_at = last_updated
        return JsonResponse({
            'success': True,
            'detection_count': detection_count,
            'sidebar': sidebar,
            'analytics': analytics,
            'updated_at': updated_at,
            'current_time': get_current_time()
        })


def update_dashboard_state(detections, analytics):
    """Keep a small in-memory timeline for the dashboard, not identities."""
    global last_detections, last_analytics, last_updated
    now = get_current_time()
    with STATE_LOCK:
        last_detections = detections
        last_analytics = analytics
        last_updated = now
        for det in detections:
            tid = det.get('tracking_id')
            if tid is None:
                continue
            item = recent_tracks.setdefault(tid, {
                'id': f'Track {tid}',
                'tracking_id': tid,
                'class': det.get('class', 'object'),
                'confidence': det.get('confidence', 0),
                'first_seen': now,
                'last_seen': now,
                'total_detections': 0,
            })
            item['class'] = det.get('class', item['class'])
            item['confidence'] = det.get('confidence', item['confidence'])
            item['last_seen'] = now
            item['total_detections'] += 1

        if len(recent_tracks) > MAX_RECENT_TRACKS:
            oldest_ids = sorted(recent_tracks, key=lambda track_id: recent_tracks[track_id]['last_seen'])
            for track_id in oldest_ids[:-MAX_RECENT_TRACKS]:
                del recent_tracks[track_id]


def build_sidebar_data(detections=None):
    """Return recent anonymous tracks; never imply face recognition."""
    if detections is not None:
        # Retained for the image-upload endpoint while avoiding duplicate state.
        update_dashboard_state(detections, {})
    tracked = recent_tracks
    items = sorted((track.copy() for track in tracked.values()), key=lambda item: item['last_seen'], reverse=True)
    return {'tracks': items, 'total_tracks': len(items)}
