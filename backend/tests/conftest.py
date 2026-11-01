import os

# Compose tests use hostname "db" and do not publish a port.
# A host-side run must set TEST_DATABASE_URL. Do not use Evolving Cook's 127.0.0.1:5432.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://organiser:organiser@db:5432/organiser_test",
)
os.environ["SEED_ON_START"] = "false"
os.environ["HOUSE_TIMEZONE"] = "Europe/London"

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine.url import make_url

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


@pytest.fixture
def client(database):
    with TestClient(app) as test_client:
        yield test_client
