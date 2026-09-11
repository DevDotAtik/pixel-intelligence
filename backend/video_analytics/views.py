import os
import platform
import logging
import threading
import time
from datetime import datetime
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from urllib.parse import quote

import cv2
import numpy as np
import requests
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

FASTAPI_BASE_URL = os.getenv('FASTAPI_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
CAMERA_INDEX = int(os.getenv('CAMERA_INDEX', '0'))
# Optional network video source (MJPEG/RTSP served over HTTP/RTSP, e.g. an IP
# Webcam feed at http://192.168.1.50:8080/video). When set it wins over
# CAMERA_INDEX for CAM-01 and Django opens the URL directly instead of a
# local /dev/videoN device.
CAMERA_URL = os.getenv('CAMERA_URL', '').strip()
STATE_LOCK = Lock()
MAX_RECENT_TRACKS = 20
STREAM_WIDTH = int(os.getenv('STREAM_WIDTH', '640'))
STREAM_HEIGHT = int(os.getenv('STREAM_HEIGHT', '480'))
MIRROR_CAMERA = os.getenv('MIRROR_CAMERA', '1').lower() in {'1', 'true', 'yes'}
FASTAPI_TIMEOUT_SECONDS = float(os.getenv('FASTAPI_TIMEOUT_SECONDS', '20'))
JPEG_QUALITY = int(os.getenv('JPEG_QUALITY', '85'))
# Upper bound for the MJPEG streaming loop. For a local webcam this is the real
# server-side FPS; for an RTSP/MJPEG network camera it caps how fast the relay
# loop runs (the camera still delivers at its own rate).
STREAM_FPS = int(os.getenv('STREAM_FPS', '30'))
PROCESS_EVERY_N_FRAMES = int(os.getenv('PROCESS_EVERY_N_FRAMES', '3'))
DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'face')
CAMERA_CODE = os.getenv('CAMERA_CODE', 'CAM-01')
DEFAULT_CAMERA_CODE = CAMERA_CODE
# How long Django caches the FastAPI camera registry before re-fetching, so
# newly-registered RTSP/MJPEG cameras appear without a Django restart.
CAMERA_REGISTRY_TTL = float(os.getenv('CAMERA_REGISTRY_TTL_SECONDS', '15'))
CAMERA_REGISTRY: dict = {'at': 0.0, 'cameras': []}
CAMERA_REGISTRY_LOCK = Lock()
logger = logging.getLogger(__name__)
INFERENCE_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix='analytics')
inference_future: Future | None = None


class HomeView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'video_analytics/index.html')


def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def detect_faces_in_frame(frame_bytes, model=None, camera_code=None):
    """Proxy a frame to the FastAPI backend for inference.

    Args:
        frame_bytes: JPEG-encoded webcam frame.
        model: detector key (face/person/plate) — mirrors the console select box.
        camera_code: logical camera used for timeline attribution in Mongo.
    """
    try:
        data = {'model': model or DEFAULT_MODEL, 'camera_code': camera_code or CAMERA_CODE}
        resp = requests.post(
            f'{FASTAPI_BASE_URL}/api/detect',
            files={'image_data': ('frame.jpg', frame_bytes, 'image/jpeg')},
            data=data,
            timeout=FASTAPI_TIMEOUT_SECONDS
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning('FastAPI detection failed (%s): %s', resp.status_code, resp.text[:500])
        return None
    except requests.RequestException as error:
        logger.warning('FastAPI is unavailable: %s', error)
        return None


def _open_url_capture(url: str, open_timeout: float = 6.0) -> cv2.VideoCapture:
    """Open a network stream (RTSP / HTTP-MJPEG) robustly.

    FFmpeg's RTSP layer defaults to UDP transport, which silently fails or
    freezes on many Wi-Fi / NAT / phone setups. We force TCP transport via the
    ``OPENCV_FFMPEG_CAPTURE_OPTIONS`` env var and run the open inside a thread
    with a bounded timeout so a dead host returns an unopened capture quickly
    instead of blocking the MJPEG loop (or the TEST button) for minutes.
    """
    scheme = url.split('://', 1)[0].lower() if '://' in url else ''
    if scheme in {'rtsp', 'rtsps'}:
        os.environ.setdefault('OPENCV_FFMPEG_CAPTURE_OPTIONS', 'rtsp_transport;tcp')

    outcome: dict = {}

    def _open():
        try:
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(open_timeout * 1000))
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
                outcome['cap'] = cap
            else:
                cap.release()
                outcome['error'] = 'OpenCV could not open the stream (DESCRIBE/SETUP failed).'
        except Exception as error:  # bad URL, DNS failure, ...
            outcome['error'] = str(error)

    worker = threading.Thread(target=_open, daemon=True)
    worker.start()
    worker.join(timeout=open_timeout + 1)
    if worker.is_alive():
        logger.warning('Timed out opening network stream %r', url)
        return cv2.VideoCapture()
    cap = outcome.get('cap')
    if cap is not None:
        return cap
    logger.warning('Could not open network stream %r: %s', url, outcome.get('error'))
    return cv2.VideoCapture()


def _open_camera(source: str | int) -> cv2.VideoCapture:
    """Open the webcam, preferring the V4L2 backend on Linux.

    Some OpenCV builds (in particular `opencv-python-headless`) try the FFMPEG
    backend first for a windowless uvcvideo device and fail with
    "OpenCV should be configured with libavdevice to open a camera device".
    Forcing CAP_V4L2 skips that path; CAP_ANY is the fallback on other platforms.

    A network source (``CAMERA_URL``, an HTTP MJPEG/RTSP stream) is opened with
    the FFmpeg backend through ``_open_url_capture`` -- V4L2 cannot decode URLs.
    """
    if isinstance(source, str):
        return _open_url_capture(source)
    if platform.system() == 'Linux':
        cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
        if cap.isOpened():
            return cap
        cap.release()
    return cv2.VideoCapture(source)


def _fetch_camera_registry():
    """Camera registry (FastAPI/Mongo is the single source of truth).

    Cached with a short TTL so a camera registered in the console shows up in
    the stream within seconds — no Django restart required. The env-based
    CAMERA_URL/CAMERA_INDEX still act as the CAM-01 fallback.
    """
    now = time.monotonic()
    with CAMERA_REGISTRY_LOCK:
        if now - CAMERA_REGISTRY['at'] < CAMERA_REGISTRY_TTL:
            return CAMERA_REGISTRY['cameras']
        try:
            resp = requests.get(f'{FASTAPI_BASE_URL}/api/cameras', timeout=3)
            if resp.status_code == 200:
                cameras = resp.json().get('cameras', []) or []
                CAMERA_REGISTRY.update({'at': now, 'cameras': cameras})
                return cameras
        except requests.RequestException as error:
            logger.warning('Camera registry fetch failed: %s', error)
        return CAMERA_REGISTRY['cameras']


def _apply_credentials(stream_url, username='', password=''):
    """Inject rtsp://user:pass@host:port credentials when the registry row has
    them and the URL does not already embed any."""
    url = (stream_url or '').strip()
    if not url or not username:
        return url
    if url.startswith('http'):
        return url  # HTTP auth is not handled via the URL here
    if '://' not in url:
        return url
    scheme, _, rest = url.partition('://')
    host_part = rest.split('/', 1)[0]
    if '@' in host_part:
        return url  # already has credentials
    creds = f'{quote(username, safe="")}:{quote(password, safe="")}@'
    if '/' in rest:
        path = rest.split('/', 1)[1]
        return f'{scheme}://{creds}{host_part}/{path}'
    return f'{scheme}://{creds}{rest}'


def _camera_source(code):
    """Resolve a camera code to an OpenCV-openable source (URL string or index).

    A registered stream URL always wins; CAM-01 keeps its env fallbacks
    (CAMERA_URL, then the local CAMERA_INDEX device).
    """
    code = (code or DEFAULT_CAMERA_CODE).upper()
    for cam in _fetch_camera_registry():
        if str(cam.get('code', '')).upper() != code:
            continue
        if cam.get('enabled', True) is False:
            return None
        if cam.get('stream_url'):
            return _apply_credentials(
                cam['stream_url'], cam.get('username', ''), cam.get('password', '')
            )
        break  # registry row exists but has no URL — fall through to env
    # Env fallbacks for the reference webcam only.
    if code == DEFAULT_CAMERA_CODE:
        return CAMERA_URL or CAMERA_INDEX
    return None


class VideoCamera:
    def __init__(self, source=None):
        self.source = CAMERA_URL or CAMERA_INDEX if source is None else source
        # A string source is a network stream (RTSP/HTTP-MJPEG); an int is a
        # local /dev/videoN webcam. Mirror defaults differ between the two.
        self.network = isinstance(self.source, str)
        self.lock = Lock()
        self.video = _open_camera(self.source)
        if self.video.isOpened():
            self.video.set(cv2.CAP_PROP_FRAME_WIDTH, STREAM_WIDTH)
            self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, STREAM_HEIGHT)

    def release(self):
        if self.video and self.video.isOpened():
            self.video.release()

    def __del__(self):
        try:
            self.release()
        except Exception:
            pass

    def get_frame(self, mirror: bool | None = None):
        if not self.video.isOpened():
            return None
        # Concurrent /video readers share one capture; serialise reads so the
        # frame boundaries stay intact.
        with self.lock:
            ret, frame = self.video.read()
        if not ret or frame is None:
            return None
        # Some webcams ignore requested capture properties; normalise frames so
        # the CPU-only prototype has predictable inference cost.
        if frame.shape[1] != STREAM_WIDTH or frame.shape[0] != STREAM_HEIGHT:
            frame = cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT), interpolation=cv2.INTER_AREA)
        # Mirroring is decided by the stream generator: the plate tab always
        # uses the physical orientation, network cameras default to physical,
        # and the local webcam keeps the selfie-style mirror by default.
        if (MIRROR_CAMERA if mirror is None else mirror):
            frame = cv2.flip(frame, 1)
        return frame


# Per-class overlay colours (BGR).
CLASS_COLORS = {
    'face': (0, 255, 0),
    'person': (255, 165, 0),
    'plate': (0, 200, 255),
    'unknown': (200, 200, 200),
}


def _detection_label(det):
    """Build a compact single-line label for a detection."""
    cls = det.get('class', 'unknown')
    tid = det.get('tracking_id')
    conf = det.get('confidence', 0)
    attrs = det.get('attributes') or {}

    parts = []
    if tid is not None:
        parts.append(f'#{tid}')
    identity = attrs.get('identity') or det.get('identity')
    if identity:
        parts.append(identity)
    else:
        parts.append(cls)
    parts.append(f'{conf:.2f}')

    if attrs.get('plate_text'):
        parts.append(f"PLATE:{attrs['plate_text']}")
    elif cls == 'plate':
        parts.append('PLATE')
    vehicle_type = attrs.get('vehicle_type')
    vehicle_colour = attrs.get('vehicle_colour')
    if vehicle_type and vehicle_type != 'unknown':
        if vehicle_colour and vehicle_colour != 'unknown':
            parts.append(f"{vehicle_type} {vehicle_colour}")
        else:
            parts.append(vehicle_type)
    clothing = attrs.get('clothing') or {}
    ctype = clothing.get('type')
    ccol = clothing.get('colour')
    if (ctype and ctype != 'unknown' and ccol and ccol != 'unknown'
            and clothing.get('confidence', 0) >= 0.5):
        parts.append(f"{ctype} {ccol}")
    elif ctype and ctype != 'unknown' and clothing.get('confidence', 0) >= 0.5:
        parts.append(ctype)
    if attrs.get('direction') and attrs['direction'] not in ('UNKNOWN',):
        parts.append(attrs['direction'])
    return ' | '.join(p for p in parts if p)


def draw_overlay(frame, detections=None):
    """Draw detection boxes and a compact, presentation-friendly overlay.

    The frame is annotated in place — the streaming loop passes a fresh capture
    buffer each cycle, so no protective copy is needed (saves a full-frame
    copy every relayed frame).
    """
    output = frame
    h, w = output.shape[:2]

    detection_count = 0
    if detections:
        detection_count = len(detections)
        for det in detections:
            bbox = det.get('bbox', [0, 0, 0, 0])
            cls = det.get('class', 'unknown')
            color = CLASS_COLORS.get(cls, CLASS_COLORS['unknown'])

            x1, y1, x2, y2 = [int(v) for v in bbox]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)

            label = _detection_label(det)
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            ly = max(y1 - 8, lh + 10)
            cv2.rectangle(output, (x1, ly - lh - 6), (x1 + lw + 4, ly + 2), color, -1)
            cv2.putText(output, label, (x1 + 2, ly - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    ts = get_current_time()
    cv2.putText(output, ts, (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(output, f"Live detections: {detection_count}", (10, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    return output


last_detections = []
last_analytics = {}
last_updated = None
recent_tracks = {}
# Per-(camera, model) detection state so one camera's boxes never bleed into
# another camera's feed and a face stream never draws person/plate boxes.
# Key is (camera_code, model). ``last_detections``/``last_analytics`` keep the
# global snapshot used by the sidebar / detect endpoints (most recent inference
# wins there).
STATE_BY_MODEL: dict[tuple[str, str], dict] = {}

# Per-code capture cache — one VideoCamera per registered camera, keyed by its
# CAM-NN code, so concurrent viewers of the same camera share one source.
CAMERAS: dict[str, VideoCamera] = {}


def get_camera(code=None):
    code = (code or DEFAULT_CAMERA_CODE).upper()
    cam = CAMERAS.get(code)
    if cam is None or not cam.video.isOpened():
        if cam is not None:  # dead capture — drop and reopen
            cam.release()
        CAMERAS[code] = VideoCamera(_camera_source(code))
        cam = CAMERAS[code]
    return cam


def process_detection(frame_bytes, model=None, camera_code=None):
    """Run slow API inference away from the MJPEG streaming loop."""
    result = detect_faces_in_frame(frame_bytes, model=model, camera_code=camera_code)
    detections = result.get('detections', []) if result else []
    analytics = result.get('analytics', {}) if result else {}
    update_dashboard_state(detections, analytics,
                           model=model or DEFAULT_MODEL, camera_code=camera_code)


def queue_detection(frame_bytes, model=None, camera_code=None):
    """Keep at most one inference in flight to avoid a request backlog."""
    global inference_future
    if inference_future is None or inference_future.done():
        inference_future = INFERENCE_EXECUTOR.submit(
            process_detection, frame_bytes, model, camera_code
        )


def _parse_flag(value) -> Optional[bool]:
    """Coerce a query-string flag ('1'/'0'/'true'/'false'/...) into a bool."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in {'1', 'true', 'yes', 'on'}:
        return True
    if s in {'0', 'false', 'no', 'off'}:
        return False
    return None


def _registry_row(code):
    """Return the camera registry row for a code (or None)."""
    code = (code or DEFAULT_CAMERA_CODE).upper()
    for cam in _fetch_camera_registry():
        if str(cam.get('code', '')).upper() == code:
            return cam
    return None


def _resolve_mirror(model_key, mirror_q, cam, row=None) -> bool:
    """Decide frame orientation: plate always physical; then explicit query
    override; then the camera registry's ``mirror`` field; finally the
    source-nature default (local webcam selfie mirror, network streams none).
    """
    if model_key == 'plate':
        return False
    explicit = _parse_flag(mirror_q)
    if explicit is not None:
        return explicit
    row_mirror = row.get('mirror') if row else None
    if row_mirror is not None:
        return bool(row_mirror)
    return MIRROR_CAMERA if not cam.network else False


def gen_frames(model=None, camera_code=None, code=None, mirror=None):
    cam = get_camera(code)
    model_key = model or DEFAULT_MODEL
    state_code = (code or DEFAULT_CAMERA_CODE)
    frame_number = 0
    use_mirror = _resolve_mirror(model_key, mirror, cam, _registry_row(state_code))

    while True:
        loop_start = time.perf_counter()
        frame_number += 1
        frame = cam.get_frame(mirror=use_mirror)
        if frame is None:
            break

        # Sample a frame for inference only when the single-worker executor is
        # idle; an in-flight request would just get dropped anyway.
        if (frame_number % max(1, PROCESS_EVERY_N_FRAMES) == 0
                and (inference_future is None or inference_future.done())):
            encoded_input, input_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if encoded_input:
                queue_detection(input_buffer.tobytes(), model=model, camera_code=camera_code)

        # Never wait for inference here: the browser receives its first camera
        # frame immediately, then overlays update when the worker finishes.
        # Draw ONLY this (camera, model) pair's detections so boxes from another
        # camera (e.g. a concurrent webcam stream) never bleed into this feed.
        state_key = (state_code, model_key)
        with STATE_LOCK:
            detections = STATE_BY_MODEL.get(state_key, {}).get('detections', []).copy()
        output = draw_overlay(frame, detections)

        ret, buf = cv2.imencode('.jpg', output, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ret:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
        # Pace to the stream target, subtracting the work already done so the
        # loop holds ~ STREAM_FPS instead of silently drifting below it.
        wait = (1 / max(1, STREAM_FPS)) - (time.perf_counter() - loop_start)
        if wait > 0:
            time.sleep(wait)


class VideoStreamView(View):
    def get(self, request, *args, **kwargs):
        code = (request.GET.get('camera') or DEFAULT_CAMERA_CODE).upper()
        source = _camera_source(code)
        if source is None:
            return JsonResponse({
                'error': f"Camera {code} is not configured.",
                'hint': (f"Register an RTSP/MJPEG source for {code} in the "
                         f"console's Camera fleet, or check CAMERA_URL / CAMERA_INDEX "
                         f"for the reference webcam.")
            }, status=503)
        cam = get_camera(code)
        if not cam.video.isOpened():
            return JsonResponse({
                'error': f"Camera {code} is unavailable or the source failed to open.",
                'hint': 'Check the stream URL, credentials, network reachability, or camera permissions.'
            }, status=503)
        model = request.GET.get('model') or DEFAULT_MODEL
        camera_code = request.GET.get('camera_code') or code
        mirror = request.GET.get('mirror')
        return StreamingHttpResponse(
            gen_frames(model=model, camera_code=camera_code, code=code, mirror=mirror),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )


class CameraSnapshotView(View):
    """Return one raw JPEG from an already-open project camera.

    The registration page uses this when the browser cannot claim a local
    webcam because the Django live-console process already owns ``/dev/videoN``.
    It deliberately shares :func:`get_camera` rather than opening the device a
    second time, which makes webcam enrolment work alongside the console.
    """
    def get(self, request, *args, **kwargs):
        code = (request.GET.get('camera') or DEFAULT_CAMERA_CODE).upper()
        source = _camera_source(code)
        if source is None:
            return JsonResponse({'error': f'Camera {code} is not configured.'}, status=503)
        cam = get_camera(code)
        if not cam.video.isOpened():
            return JsonResponse({'error': f'Camera {code} is unavailable.'}, status=503)
        # Keep the actual capture orientation. The browser preview mirrors it
        # visually for the operator; the stored identity reference stays
        # physically oriented.
        frame = cam.get_frame(mirror=False)
        if frame is None:
            return JsonResponse({'error': f'Camera {code} produced no frame.'}, status=503)
        ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            return JsonResponse({'error': 'Could not encode camera frame.'}, status=500)
        response = HttpResponse(jpeg.tobytes(), content_type='image/jpeg')
        response['Cache-Control'] = 'no-store, max-age=0'
        return response


@method_decorator(csrf_exempt, name='dispatch')
class DetectView(View):
    def post(self, request, *args, **kwargs):
        model = request.POST.get('model') or request.GET.get('model') or DEFAULT_MODEL
        camera_code = request.POST.get('camera_code') or CAMERA_CODE

        # If image uploaded, run detection on it
        if 'image' in request.FILES:
            image_bytes = request.FILES['image'].read()
            result = detect_faces_in_frame(image_bytes, model=model, camera_code=camera_code)

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


def update_dashboard_state(detections, analytics, model=DEFAULT_MODEL, camera_code=None):
    """Keep a small in-memory timeline for the dashboard, not identities.

    Per-(camera, model) snapshot powers the MJPEG overlay so each camera only
    ever draws its own boxes; the global snapshot mirrors the most recent
    inference for the sidebar / detect endpoints.
    """
    global last_detections, last_analytics, last_updated
    now = get_current_time()
    state_key = (camera_code or DEFAULT_CAMERA_CODE, model or DEFAULT_MODEL)
    with STATE_LOCK:
        STATE_BY_MODEL.setdefault(state_key, {})
        STATE_BY_MODEL[state_key]['detections'] = detections
        STATE_BY_MODEL[state_key]['analytics'] = analytics
        STATE_BY_MODEL[state_key]['updated'] = now
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
