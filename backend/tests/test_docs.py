from fastapi.testclient import TestClient

from organiser.config import get_settings
from organiser.main import create_app

PATHS = (
    "/tasks",
    "/commitments",
    "/events",
    "/action-requests",
    "/brief/morning",
    "/approvals",
    "/system/pause",
    "/system/unpause",
    "/system/facts",
    "/agent/activity",
    "/agent/proposals",
    "/shopping",
    "/memory",
    "/memory/export",
    "/commute/shift",
    "/system/assistant",
    "/system/calendars",
    "/commute/shift",
    "/commute/plan",
    "/hooks/{source}",
    "/metrics",
    "/system/status",
    "/alerts",
    "/alerts/{kind}/dismiss",
    "/voice/transcribe",
    "/x/status",
    "/x/connect",
    "/x/callback",
    "/x/disconnect",
    "/x/watches",
    "/x/watches/{watch_id}",
    "/x/items",
    "/x/poll",
    "/x/items/{item_id}/apply",
    "/x/items/{item_id}/dismiss",
    "/x/items/{item_id}/post",
    "/playlist",
)


def test_docs_are_off_unless_enabled(client):
    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_docs_stay_off_without_the_access_flag(database, monkeypatch):
    monkeypatch.setenv("ENABLE_DOCS", "true")
    monkeypatch.setenv("DOCS_BEHIND_ACCESS", "false")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as docs_client:
            assert docs_client.get("/docs").status_code == 404
            assert docs_client.get("/openapi.json").status_code == 404
    finally:
        get_settings.cache_clear()


def test_docs_list_the_house_routes_when_enabled(database, monkeypatch):
    monkeypatch.setenv("ENABLE_DOCS", "true")
    monkeypatch.setenv("DOCS_BEHIND_ACCESS", "true")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as docs_client:
            assert docs_client.get("/docs").status_code == 200
            assert docs_client.get("/redoc").status_code == 200
            spec = docs_client.get("/openapi.json")
            assert spec.status_code == 200
            paths = spec.json()["paths"]
            for path in PATHS:
                assert path in paths
            assert "/system/facts" in paths
    finally:
        get_settings.cache_clear()
