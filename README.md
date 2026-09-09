# pixel-intelligence

A production-style **AI video-analytics platform** for a low-end, CPU-only laptop: it detects **faces**, **people + clothing + direction**, and **license plates** from live webcam frames, recognises **registered people by name**, and persists every reappearance as a deduplicated "subject sighting" with an identity timeline in MongoDB.

Built on the existing SIH-style prototype (phases 2–9), reorganised into three cooperating services:

| Port | Service | Job |
|------|---------|-----|
| `27017` | MongoDB | The single source of truth: registrations, sightings, subjects, cameras |
| `8000` | FastAPI | Model registry + REST API. Owns detection, registration & analytics |
| `8001` | Django | Webcam/MJPEG gateway. Streams the camera, forwards frames to FastAPI |
| `3000` | Next.js | Web UI (overview, live console, register, analytics, events, cameras) |

## Architecture

```
                        ┌──────────────────────────┐
                        │  Next.js UI :3000         │
                        │  (route handlers proxy)   │
                        └──┬──────────┬──────────┬──┘
                           │          │          │
                          GET/POST   GET        GET
                           │          │          │
                 ┌─────────▼──┐  ┌───▼───┐  ┌───▼───────┐
                 │ /api/*     │  │/detect│  │ /video    │
                 │ REST proxy │  └───┬───┘  └───┬───────┘
                 └─────┬──────┘      │          │
                       │          POST frame    │ (MJPEG stream)
                 ┌─────▼──────┐  ┌──▼─────────┐ │
                 │ FastAPI    │◇─│ Django     │◀┘
                 │  :8000     │  │  :8001     │──── webcam :0
                 └──┬─────┬───┘  └────────────┘
                    │     │
          ┌─────────▼─┐ ┌─▼──────────────┐
          │ MongoDB   │ │ Model registry │
          │  :27017   │ │ face / person  │
          └───────────┘ │ / plate        │
                        └────────────────┘
```

Frame flow on the console: Next `:3000` → Django `:8001/video/?model=…` (MJPEG) → Django forwards each **3rd** frame to FastAPI `:8000/api/detect` → detections are drawn on the stream, and every sighting is stored in Mongo → tightest path keeps the laptop at usable FPS.

## Model strategy (CPU-friendly, no GPU required)

Everything routes through a small model registry in `backend/app/config.py`
(`GET /api/models` returns it). Weights are **not committed** — see `backend/.env.example`.

| Model | Status | Notes |
|-------|--------|-------|
| **face** | ✅ bundles | `backend/model.pt` (or `backend/yolov8m-face.pt`). Boxes + 64-dim CPU embedding → matches registered people by cosine similarity (`FACE_MATCH_THRESHOLD`, default `0.72`). Body box inferred from the face for the timeline. |
| **person** | ⚠️ fallback | If you drop `yolov8n.pt` into `backend/`, real person boxes + COCO classes appear. Without it, runs in **FACE→BODY fallback**: face box scaled to a person box + clothing colour classifier + direction from tracked head movement. |
| **vehicle** | ⚠️ fallback | Same idea — requires `yolov8n.pt`. Without weights the model runs in optional mode (no output). |
| **plate** | ⚠️ OpenCV | No weights needed: morphology + contour candidate detection finds plate boxes. OCR (`tesseract` + `pytesseract`) is optional; without it `plate_text` is `null`. |

> On a CPU-only machine, keep `INFERENCE_SIZE=320`, `PROCESS_EVERY_N_FRAMES=3`
> and `CPU_THREADS=4` (all env-tunable) for a realtime stream.

## Run it

Prereqs: Python 3.11+, Node 20+, a running MongoDB at `127.0.0.1:27017`.

```bash
# 1) Python backend (port 8000)
cd backend
python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env              # optional: override thresholds/paths
# start MongoDB                            # e.g. mongod --dbpath ./mongodb-data
setsid -f venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2) Django webcam gateway (port 8001)
cd backend
venv/bin/python manage.py migrate
setsid -f venv/bin/python manage.py runserver 127.0.0.1:8001

# 3) Next.js UI (port 3000)
cd frontend
cp .env.example .env.local
npm install && npm run dev
```

Open `http://127.0.0.1:3000` → **LIVE CONSOLE** (pick a model, watch the stream) →
**REGISTER** a face-upload → the name appears on the live overlay and in the
**ANALYTICS** subject timeline and **EVENTS** log.

## Environment variables

**backend `.env`** (`backend/.env.example`):

```
MONGODB_URI=pixel_intelligence          # db name (or mongodb:// URL)
MONGODB_HOST=127.0.0.1 / MONGODB_PORT=27017
FACE_MODEL_PATH=model.pt                # relative to backend/
YOLO_MODEL_PATH=yolov8m-face.pt / PLATE_MODEL_PATH=plate_model.pt
INFERENCE_SIZE=320, CONFIDENCE_THRESHOLD=0.50, PROCESS_EVERY_N_FRAMES=3
JPEG_QUALITY=75, CPU_THREADS=4, FACE_MATCH_THRESHOLD=0.72
VANISH_SECONDS=5, MIN_SIGHTING_SECONDS=1
DEFAULT_MODEL=face / DEFAULT_CAMERA_CODE=CAM-01
```

**frontend `.env.local`** (`frontend/.env.example`):

```
NEXT_PUBLIC_FASTAPI_URL=http://127.0.0.1:8000
NEXT_PUBLIC_DJANGO_URL=http://127.0.0.1:8001
```

## Project layout

```
backend/
├─ app/                  # FastAPI
│  ├─ main.py            # app + lifespan (seeds mongo, closes stale sightings)
│  ├─ config.py          # model registry + runtime tuning (env-driven)
│  ├─ core/db.py         # MongoDB layer (dedup sightings, subjects, cameras)
│  ├─ api/routes.py      # /models /config /detect /events /stats /subjects
│  │                     #   /registrations /cameras /health
│  └─ detection/         # base, face, embedder, person, clothing, direction,
│                        #   plate, tracker (IoU), subject_service
├─ video_analytics/      # Django app: webcam stream, model-select, overlays
├─ detector/             # Django app: thin proxies to FastAPI
├─ face_backend/         # Django project package (settings, ROOT_URLCONF)
├─ model.pt / yolov8m-face.pt   # ⚠️ gitignored — download/model yourself
└─ legacy/               # original phase2–9 prototype scripts (kept for history)

frontend/
├─ src/app/              # overview, console, register, analytics, events,
│  │                     #   cameras, api-docs + route-handler proxies
├─ src/components/       # site-nav, shared UI, console (canvas feed, gauges),
│  │                     #   landing
└─ src/lib/              # backend-proxy (Next→FastAPI), sim.ts (constants)
```

## API (FastAPI :8000)

- `GET /models` — model registry (name, classes, availability, note)
- `GET /config` — live runtime tuning
- `POST /detect` — `multipart/form-data`: `image_data` (file), `model`, `camera_code` → detections with identity / attributes / timeline action
- `GET /events?limit=&offset=&camera=` — deduplicated subject sightings
- `GET /stats` — counts per class / camera + hourly + daily
- `GET /subjects` — identity aggregate per subject (registered, sightings, last seen)
- `POST /registrations` — `multipart`: `image_data`, `name`, `notes` → enrol a face
- `GET /cameras` · `PATCH /cameras/{code}` — camera status
- `GET /health` — service + MongoDB heartbeat

MongoDB `pixel_intelligence` collections: `registrations`, `sightings`, `subjects`, `cameras` (seeded `CAM-01…CAM-04`), `counters`.

## Legacy code

`backend/legacy/` keeps the original phase-by-phase prototype scripts
(`phase2_image_test` → `phase9_counting_fps`) and the old monolithic
`config.py`, along with `learn/` experiments — untouched, runnable from
`backend/` via `python -m legacy.phaseX_…`. The new platform supersedes them.

## Improvement ideas

- Drop real weights: `yolov8n.pt` (person/vehicle), `plate_model.pt` + `tesseract` (OCR) — zero code changes, registry picks them up automatically.
- Swap the 64-dim CPU embedding for `face_recognition`/InsightFace when a GPU is available.
- Move pagination/group filtering of events server-side (currently client-side per page).
- Webcam capture flow on the REGISTER page, and camera list UI against `/api/cameras`.