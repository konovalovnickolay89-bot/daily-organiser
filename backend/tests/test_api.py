import asyncio
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from organiser.config import get_settings
from organiser.main import create_app
from tests.helpers import AUTH_SECRET, SESSION_SECRET, login


def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_rejects_placeholder_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "change-me-to-a-long-random-string")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "organiser.db"))
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        create_app()
    get_settings.cache_clear()


def test_login_failure_does_not_open_a_session(client):
    bad = client.post("/api/auth/login", json={"password": "not-the-real-secret"})
    assert bad.status_code == 401
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/today").status_code == 401


def test_login_sets_httponly_cookie(client):
    response = login(client)
    cookie = response.headers["set-cookie"].lower()
    assert "organiser_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"authenticated": True}


def test_task_note_and_today_after_login(client):
    login(client)
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    created = client.post(
        "/api/tasks",
        json={
            "title": "Buy oat milk",
            "due_date": today,
            "priority": "high",
            "status": "todo",
            "recurring": True,
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["title"] == "Buy oat milk"
    assert task["due_date"] == today
    assert task["priority"] == "high"
    assert task["status"] == "todo"
    assert task["recurring"] is True

    later = client.post(
        "/api/tasks",
        json={"title": "Mend the gate", "due_date": tomorrow, "priority": "low"},
    )
    assert later.status_code == 201, later.text

    note = client.post(
        "/api/notes",
        json={
            "body": "Hardware shop closes at 4",
            "tags": ["Home", "errands"],
            "task_id": task["id"],
        },
    )
    assert note.status_code == 201, note.text
    saved = note.json()
    assert saved["tags"] == ["home", "errands"]
    assert saved["task_id"] == task["id"]
    assert saved["task_title"] == "Buy oat milk"

    page = client.get("/api/today")
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["date"] == today
    titles = [item["title"] for item in body["tasks"]]
    assert titles == ["Buy oat milk"]
    assert any(item["body"] == "Hardware shop closes at 4" for item in body["notes"])

    found = client.get("/api/notes", params={"q": "hardware", "tag": "Home"})
    assert found.status_code == 200
    assert len(found.json()) == 1

    missed = client.get("/api/notes", params={"tag": "garden"})
    assert missed.json() == []

    doing = client.patch(f"/api/tasks/{task['id']}", json={"status": "doing"})
    assert doing.status_code == 200
    assert doing.json()["status"] == "doing"

    listed = client.get("/api/tasks", params={"status": "doing", "q": "oat"})
    assert [item["id"] for item in listed.json()] == [task["id"]]


def test_percent_in_title_is_searchable(client):
    login(client)
    created = client.post("/api/tasks", json={"title": "100% cocoa"})
    assert created.status_code == 201
    tasks = client.get("/api/tasks", params={"q": "100%"})
    assert [item["title"] for item in tasks.json()] == ["100% cocoa"]


def test_delete_task_unlinks_note(client):
    login(client)
    task = client.post("/api/tasks", json={"title": "Sort the shed"}).json()
    note = client.post(
        "/api/notes",
        json={"body": "Keep the good screws", "task_id": task["id"]},
    ).json()
    deleted = client.delete(f"/api/tasks/{task['id']}")
    assert deleted.status_code == 204
    fetched = client.get(f"/api/notes/{note['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["task_id"] is None
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_missing_task_link_is_rejected(client):
    login(client)
    response = client.post("/api/notes", json={"body": "Orphan", "task_id": 999})
    assert response.status_code == 400


def test_logout_closes_the_session(client):
    login(client)
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/notes", json={"body": "nope"}).status_code == 401


def test_routes_require_login(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/api/notes").status_code == 401
    assert client.get("/api/today").status_code == 401


def test_configured_test_secret_is_not_a_placeholder():
    assert len(AUTH_SECRET) >= 16
    assert "change-me" not in AUTH_SECRET


def test_parallel_reads_on_the_async_server(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", AUTH_SECRET)
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "organiser.db"))
    get_settings.cache_clear()
    app = create_app()

    async def scenario():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login_response = await client.post(
                "/api/auth/login",
                json={"password": AUTH_SECRET},
            )
            assert login_response.status_code == 200
            created = await client.post("/api/tasks", json={"title": "Parallel task"})
            assert created.status_code == 201
            noted = await client.post("/api/notes", json={"body": "parallel note"})
            assert noted.status_code == 201
            for _ in range(15):
                notes, tasks = await asyncio.gather(
                    client.get("/api/notes"),
                    client.get("/api/tasks"),
                )
                assert notes.status_code == 200, notes.text
                assert tasks.status_code == 200, tasks.text

    asyncio.run(scenario())
    get_settings.cache_clear()