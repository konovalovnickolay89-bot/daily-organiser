from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from organiser import __version__
from organiser.config import get_settings
from organiser.db import (
    ensure_arrived_at_column,
    ensure_ingest_proposals,
    ensure_last_looked_at_column,
    ensure_sprint2,
    ensure_sprint3,
    get_engine,
    get_sessionmaker,
    wait_for_database,
)
from organiser.models import Base
from organiser.routes import register
from organiser.seed import seed_if_empty
from organiser.services.system import ensure_system_state

def _ui_dist() -> Path | None:
    """Built arrival screen, next to the package in the image or the repo."""
    package_dir = Path(__file__).resolve().parent
    for ancestor in list(package_dir.parents)[:3]:
        candidate = ancestor / "frontend" / "dist"
        if (candidate / "index.html").is_file():
            return candidate
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    wait_for_database()
    # create_all still boots an existing database. Alembic's baseline matches
    # these models; this process does not upgrade a live database.
    Base.metadata.create_all(bind=get_engine())
    ensure_arrived_at_column()
    ensure_last_looked_at_column()
    ensure_ingest_proposals()
    ensure_sprint2()
    ensure_sprint3()
    session = get_sessionmaker()()
    try:
        ensure_system_state(session)
        if settings.seed_on_start:
            seed_if_empty(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    yield


_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def create_app() -> FastAPI:
    settings = get_settings()
    # Both switches. ENABLE_DOCS alone does not publish /docs.
    # DOCS_BEHIND_ACCESS means this process is only reached through Cloudflare Access.
    docs_on = settings.enable_docs and settings.docs_behind_access
    app = FastAPI(
        title="Daily Organiser",
        version=__version__,
        summary="Home operations log. Approvals record a decision and stop there.",
        lifespan=lifespan,
        docs_url="/docs" if docs_on else None,
        redoc_url="/redoc" if docs_on else None,
        openapi_url="/openapi.json" if docs_on else None,
    )
    if not docs_on:

        def docs_disabled() -> None:
            raise HTTPException(status_code=404, detail="Not found.")

        for path in _DOCS_PATHS:
            app.add_api_route(path, docs_disabled, methods=["GET", "HEAD"], include_in_schema=False)
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register(app)
    ui_dist = _ui_dist()
    if ui_dist is not None:
        app.mount("/", StaticFiles(directory=ui_dist, html=True), name="ui")
    else:

        @app.get("/", include_in_schema=False)
        def root() -> dict:
            payload = {
                "service": "daily-organiser",
                "health": "/health",
                "ui": "The arrival screen is served when frontend/dist exists, or from the Vite dev server.",
            }
            if docs_on:
                payload["docs"] = "/docs"
            return payload

    return app


app = create_app()
