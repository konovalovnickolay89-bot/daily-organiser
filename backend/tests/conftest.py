import pytest
from fastapi.testclient import TestClient

from organiser.config import get_settings
from organiser.main import create_app
from tests.helpers import AUTH_SECRET, SESSION_SECRET


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    def _make():
        monkeypatch.setenv("AUTH_SECRET", AUTH_SECRET)
        monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET)
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "organiser.db"))
        get_settings.cache_clear()
        return TestClient(create_app())

    yield _make
    get_settings.cache_clear()


@pytest.fixture
def client(make_client):
    with make_client() as test_client:
        yield test_client


def login(client: TestClient, password: str = AUTH_SECRET):
    response = client.post("/api/auth/login", json={"password": password})
    assert response.status_code == 200, response.text
    return response
