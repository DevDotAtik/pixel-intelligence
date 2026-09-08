"""FastAPI main application module - includes all routers."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.api.health import router as health_router

app = FastAPI(
    title="AI Video Analytics API",
    description="Backend AI video analytics platform for border surveillance using existing CCTV infrastructure",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(api_router, prefix="/api", tags=["analytics"])


@app.get("/")
async def root():
    """Root endpoint returning API message."""
    from app.config import get_config
    return {
        "message": "AI Video Analytics API",
        "version": "1.0.0",
        "status": "operational",
        "configuration": get_config()
    }


@app.get("/health")
async def api_health_check():
    """API health check endpoint."""
    return {"status": "ok"}