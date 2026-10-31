import asyncio
import sqlite3
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
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
    assert task["assist_mode"] == "when_useful"
    assert task["context_hint"] is None
    assert task["source"] == "manual"

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
    assert saved["source"] == "manual"

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


def test_title_only_task_stays_plain_and_assist_hook_round_trips(client):
    login(client)
    plain = client.post("/api/tasks", json={"title": "Fold towels"})
    assert plain.status_code == 201, plain.text
    body = plain.json()
    assert body["assist_mode"] == "when_useful"
    assert body["context_hint"] is None
    assert body["source"] == "manual"

    hinted = client.post(
        "/api/tasks",
        json={
            "title": "Check the evening train",
            "assist_mode": "when_useful",
            "context_hint": "  public transport  ",
            "source": "manual",
        },
    )
    assert hinted.status_code == 201, hinted.text
    assert hinted.json()["context_hint"] == "public transport"

    quiet = client.patch(
        f"/api/tasks/{body['id']}",
        json={"assist_mode": "off"},
    )
    assert quiet.status_code == 200
    assert quiet.json()["assist_mode"] == "off"
    assert quiet.json()["title"] == "Fold towels"

    bot_note = client.post(
        "/api/notes",
        json={"body": "Leave ten minutes earlier", "source": "bot", "task_id": hinted.json()["id"]},
    )
    assert bot_note.status_code == 201, bot_note.text
    assert bot_note.json()["source"] == "bot"


def test_existing_database_gains_assist_columns(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due_date TEXT,
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'todo',
            recurring INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            body TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '',
            task_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO tasks (title, priority, status, recurring, created_at, updated_at)
        VALUES ('Old task', 'medium', 'todo', 0, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("AUTH_SECRET", AUTH_SECRET)
    monkeypatch.setenv("SESSION_SECRET", SESSION_SECRET)
    monkeypatch.setenv("DATABASE_PATH", str(path))
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            login(client)
            listed = client.get("/api/tasks")
            assert listed.status_code == 200, listed.text
            task = listed.json()[0]
            assert task["title"] == "Old task"
            assert task["assist_mode"] == "when_useful"
            assert task["source"] == "manual"
            assert task["context_hint"] is None
    finally:
        get_settings.cache_clear()


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