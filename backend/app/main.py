from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import (
    routes_capture,
    routes_health,
    routes_pairing,
    routes_sessions,
    routes_settings,
    routes_ws,
)
from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import entities as _entities  # noqa: F401
from app.database import Base
from app.middleware_pna import PrivateNetworkAccessMiddleware
from app.services.sessions import get_session_service
from app.services.video.pipeline import get_video_pipeline


def init_db() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        get_session_service().seed_procedure_types(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield
    get_video_pipeline().shutdown()


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=__version__,
    lifespan=lifespan,
)

# Cloudflare may host the static UI on a different origin. Clinical payloads
# still go browser → local service directly (never through Cloudflare).
# Credentials are not used; the desktop token is an explicit header.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
# Outer middleware so PNA headers are added to CORS preflight responses too.
app.add_middleware(PrivateNetworkAccessMiddleware)

app.include_router(routes_health.router)
app.include_router(routes_capture.router)
app.include_router(routes_sessions.router)
app.include_router(routes_pairing.router)
app.include_router(routes_settings.router)
app.include_router(routes_ws.router)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@app.get("/")
def root_index():
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "service": settings.app_name,
        "version": __version__,
        "docs": "/docs",
        "message": "Frontend not built yet. Run npm run build in frontend/, or use Vite dev server.",
    }


if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # Do not swallow API/ws
        if full_path.startswith("api/") or full_path.startswith("ws/") or full_path.startswith("docs"):
            return {"detail": "Not found"}
        candidate = FRONTEND_DIST / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
