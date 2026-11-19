"""FastAPI application entrypoint serving /api/* and the built React SPA in production."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.routers.api import router as api_router
from app.services.snapshot_service import SnapshotService


def _resolve_static_dir(settings: Settings) -> Path | None:
    if settings.static_dir:
        candidate = Path(settings.static_dir).resolve()
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate

    # Default locations: repo layout (../../frontend/dist) or container layout (/app/static)
    candidates = [
        Path(__file__).resolve().parents[2] / "frontend" / "dist",
        Path("/app/static"),
    ]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return None


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the TowerMap FastAPI application."""
    active_settings = settings or get_settings()

    application = FastAPI(
        title="TowerMap",
        description=(
            "Read-only homelab dashboard mapping Docker stacks, host ports, "
            "Gluetun VPN topology, and domain routes."
        ),
        version="0.1.0",
    )
    application.state.settings = active_settings
    application.state.snapshot_service = SnapshotService(active_settings)
    application.include_router(api_router)

    static_dir = _resolve_static_dir(active_settings)
    if static_dir is not None:
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            application.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="assets",
            )

        index_file = static_dir / "index.html"

        @application.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API endpoint not found")
            if full_path:
                requested = (static_dir / full_path).resolve()
                if requested.is_file() and requested.is_relative_to(static_dir):
                    return FileResponse(requested)
            return FileResponse(index_file)

    return application


app = create_app()
