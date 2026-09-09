"""FastAPI application entrypoint.

Binds every router under ``/api`` and, on startup, primes MongoDB indexes and
seeds the default camera fleet. Run with:

    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.api.health import router as health_router
from app.config import get_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed the database / indexes at startup (safe when Mongo is off)."""
    try:
        from app.core import db as database

        database.ensure_indexes()
        database.seed_cameras()
        database.close_stale_sightings()
        print("[DB] MongoDB ready; indexes + camera fleet seeded.")
    except Exception as error:
        print(f"[DB] MongoDB unavailable at startup: {error}")
    yield


app = FastAPI(
    title="Pixel Intelligence — AI Video Analytics API",
    description=(
        "Backend AI video analytics platform for realtime camera monitoring: "
        "face (with registration-based recognition), person (clothing + "
        "movement direction) and license plate detection. Storage: MongoDB."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: the Next.js console runs on a different origin during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(api_router, prefix="/api", tags=["analytics"])


@app.get("/")
async def root() -> dict:
    """Root landing — JSON flavour of the app."""
    return {
        "message": "Pixel Intelligence — AI Video Analytics API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "configuration": get_config(),
    }