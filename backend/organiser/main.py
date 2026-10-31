"""FastAPI app. Serves the JSON API and, when built, the React UI."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

from organiser.config import ROOT, ensure_secret, get_settings
from organiser.db import init_db
from organiser.routes import api_router, auth_router, health_router
from organiser.spa import looks_like_file, path_escapes, resolve_dist_file

logger = logging.getLogger("uvicorn.error")

FRONTEND_DIST = ROOT / "frontend" / "dist"


def create_app() -> FastAPI:
    settings = get_settings()
    ensure_secret(settings)
    db_path = settings.resolved_db_path()
    init_db(db_path)
    logger.info("Using SQLite database %s", db_path)

    app = FastAPI(
        title="Daily Organiser",
        version="0.1.0",
        description="Personal home tasks and notes for Nick.",
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.signing_secret(),
        session_cookie=settings.session_cookie_name,
        max_age=settings.session_max_age,
        same_site="lax",
        https_only=settings.session_https_only,
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        content_type = response.headers.get("content-type", "")
        if request.url.path.startswith("/api") or content_type.startswith("text/html"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    def frontend_index():
        return _frontend("")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_path(full_path: str):
        return _frontend(full_path)

    return app


def _frontend(full_path: str):
    dist = FRONTEND_DIST
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    if not dist.is_dir():
        raise HTTPException(status_code=404, detail="Not found")
    if path_escapes(dist, full_path):
        raise HTTPException(status_code=404, detail="Not found")
    served = resolve_dist_file(dist, full_path)
    if served is not None:
        return FileResponse(served)
    if full_path and looks_like_file(full_path):
        raise HTTPException(status_code=404, detail="Not found")
    index = dist / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not found")


def dist_dir() -> Path:
    return FRONTEND_DIST
