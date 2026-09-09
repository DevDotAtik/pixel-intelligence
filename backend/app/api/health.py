"""Health check routes (kept separate from the analytics router)."""
from fastapi import APIRouter

import app.core.db as db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health endpoint — reports server + MongoDB reachability."""
    return {
        "status": "ok",
        "mongodb": db.is_connected(),
    }