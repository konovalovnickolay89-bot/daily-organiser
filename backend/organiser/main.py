from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from organiser import __version__
from organiser.config import get_settings
from organiser.db import get_engine, get_sessionmaker, wait_for_database
from organiser.models import Base
from organiser.routes import register
from organiser.seed import seed_if_empty
from organiser.services.system import ensure_system_state

UI_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    wait_for_database()
    Base.metadata.create_all(bind=get_engine())
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


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Daily Organiser",
        version=__version__,
        summary="Home operations log. Approvals record a decision and stop there.",
        lifespan=lifespan,
    )
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register(app)
    index = UI_DIST / "index.html"
    if index.is_file():
        app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
    else:

        @app.get("/", include_in_schema=False)
        def root() -> dict:
            return {
                "service": "daily-organiser",
                "health": "/health",
                "docs": "/docs",
                "ui": "The arrival screen is served when frontend/dist exists, or from the Vite dev server.",
            }

    return app


app = create_app()
