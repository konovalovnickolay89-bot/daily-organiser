import os

# Compose tests use hostname "db" and do not publish a port.
# A host-side run must set TEST_DATABASE_URL. Do not use Evolving Cook's 127.0.0.1:5432.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://organiser:organiser@db:5432/organiser_test",
)
os.environ["SEED_ON_START"] = "false"
os.environ["HOUSE_TIMEZONE"] = "Europe/London"
# The assistant is off in tests unless a test turns it on with a fake. Environment
# values beat a developer's .env, and the base URL cannot resolve, so no test can
# spend a real key or send house data to Mistral.
os.environ["MISTRAL_API_KEY"] = ""
os.environ["MISTRAL_AGENT_ID"] = ""
os.environ["MISTRAL_BASE_URL"] = "http://mistral.invalid"

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine.url import make_url

from agent_fakes import ScriptedMistral, london

from organiser.config import get_settings
from organiser.db import get_engine, get_sessionmaker
from organiser.main import app
from organiser.models import Base


def ensure_test_database(url: str) -> None:
    target = make_url(url)
    admin = target.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (target.database,),
        ).fetchone()
        if exists is None:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target.database)))


ensure_test_database(get_settings().database_url)


@pytest.fixture
def database():
    from organiser.db import ensure_vector_extension

    ensure_vector_extension()
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(database):
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _reset_process_guards():
    from organiser.agent.reach import reset as reset_reach
    from organiser.limits import LIMITS
    from organiser.metrics import METRICS
    from organiser.services.commute import clear_cache
    from organiser.services.lines import clear_cache as clear_line_status
    from organiser.services.playlist import clear_cache as clear_playlist
    from organiser.services.playlist import set_transport as set_playlist_transport
    from organiser.x.client import set_transport as set_x_transport

    LIMITS.reset()
    reset_reach()
    clear_cache()
    clear_line_status()
    clear_playlist()
    set_playlist_transport(None)
    set_x_transport(None)
    METRICS.reset()
    yield
    LIMITS.reset()
    reset_reach()
    clear_cache()
    clear_line_status()
    clear_playlist()
    set_playlist_transport(None)
    set_x_transport(None)
    METRICS.reset()


@pytest.fixture
def client(database):
    with TestClient(app) as test_client:
        yield test_client


# --- Mistral assistant -------------------------------------------------------


@pytest.fixture
def house_clock(monkeypatch):
    """Freeze organiser.clock. Monday 2 November 2026, 08:00 in London, unless a test moves it."""
    state = {"now": london(2026, 11, 2, 8, 0)}
    monkeypatch.setattr("organiser.clock.current_time", lambda: state["now"])
    return state


@pytest.fixture
def assistant_on(monkeypatch):
    """A key and an agent id, so the assistant counts as set up. Nothing reaches Mistral."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key-not-real")
    monkeypatch.setenv("MISTRAL_AGENT_ID", "ag_test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def reminder_ai(assistant_on):
    """A scripted completion for reminder assessment. The real client is not used."""
    from agent_fakes import ReminderAssessor

    from organiser.main import app
    from organiser.routes.agent import get_mistral

    def install(answer) -> ReminderAssessor:
        fake = ReminderAssessor(answer)
        app.dependency_overrides[get_mistral] = lambda: fake
        return fake

    yield install
    app.dependency_overrides.pop(get_mistral, None)


@pytest.fixture
def mistral(assistant_on):
    """Install a scripted Mistral for the API: ``fake = mistral([call(...)], [say(...)])``."""
    from organiser.routes.agent import get_mistral

    def install(*script) -> ScriptedMistral:
        fake = ScriptedMistral(*script)
        app.dependency_overrides[get_mistral] = lambda: fake
        return fake

    yield install
    app.dependency_overrides.pop(get_mistral, None)
