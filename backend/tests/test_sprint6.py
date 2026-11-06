"""Sprint 6: context contract, metrics, alerts, the hotel guard, and voice."""

import json
import logging
import tempfile
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from agent_fakes import london, say

from organiser import __version__
from organiser.agent.context import (
    SCHEMA_VERSION,
    TOKEN_BUDGET,
    TRIM_ORDER,
    ContextEntry,
    HouseContext,
    MemorySlot,
    build_context,
    token_count,
    trim_to_budget,
)
from organiser.agent.mistral import MistralClient
from organiser.agent.runner import outside_home
from organiser.agent.voice import voice_kind
from organiser.config import get_settings
from organiser.main import app
from organiser.metrics import METRICS
from organiser.models import AgentProposal, Commitment, Event, MemoryItem, Task
from organiser.routes.voice import get_transcriber

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "context"
MARKER = b"AUDIO-MARKER-9f3c-not-a-word"
NOT_IN_LOGS = "Lisbon-hotel-note-should-not-be-logged"


class FakeTranscriber:
    def __init__(self, text: str) -> None:
        self.text = text
        self.audio: list[bytes] = []

    def transcribe(self, audio: bytes, media_type: str) -> str:
        assert isinstance(audio, bytes)
        assert not isinstance(audio, str)
        self.audio.append(audio)
        return self.text


def _entry(kind: str, title: str) -> ContextEntry:
    return ContextEntry(kind=kind, id=title, title=title)  # type: ignore[arg-type]


def _project(context: HouseContext) -> dict:
    return {
        "schema_version": context.schema_version,
        "purpose": context.purpose,
        "theme": context.theme,
        "log_days": context.log_days,
        "trimmed": context.trimmed,
        "tasks": [item.title for item in context.tasks],
        "commitments": [item.title for item in context.commitments],
        "waiting": [item.title for item in context.waiting],
        "log": [item.title for item in context.log],
        "memory": [item.text for item in context.memory.items],
        "focus": context.focus.title if context.focus else None,
    }


def _seed(db, now):
    db.add(Task(title="Put the bins out", detail="Green bin.", status="todo", priority="high", owner="Nick"))
    db.add(Task(title="Book a hotel in Lisbon", status="todo", priority="low", owner="Nick"))
    db.add(Task(title="Call Hilton", status="todo", priority="low", owner="Nick"))
    db.add(Task(title="Payroll on Friday", detail="Work system.", status="todo", priority="low", owner="Nick"))
    db.add(Task(title="Water the plants", detail="for a guest", status="todo", priority="low", owner="Nick"))
    db.add(Task(title="Done already", status="done", priority="low", owner="Nick"))
    db.add(Commitment(title="Collect the dry cleaning", status="open", owner="Nick", source="manual"))
    db.add(Commitment(title="Meet a guest", status="open", owner="Nick", source="manual"))
    db.add(
        AgentProposal(
            origin="ingest",
            rule="feed",
            label="Noted",
            action="create_task",
            changes={"title": "Boiler filters"},
            summary="Waiting on the boiler filters",
            reason="Noted for the house log.",
            status="pending",
            created_at=now,
        )
    )
    db.add(
        AgentProposal(
            origin="ingest",
            rule="feed",
            label="Noted",
            action="create_task",
            changes={"title": "Towels"},
            summary="Guest towels",
            reason="A guest asked.",
            status="pending",
            created_at=now - timedelta(hours=1),
        )
    )
    db.add(Event(kind="note", title="Milk is low", body="Shopping.", owner="Nick", recorded_at=now - timedelta(hours=1)))
    db.add(Event(kind="note", title="Old note", body="Five days ago.", owner="Nick", recorded_at=now - timedelta(days=5)))
    db.add(Event(kind="note", title="Ancient", body="Ten days ago.", owner="Nick", recorded_at=now - timedelta(days=10)))
    db.add(
        Event(
            kind="note",
            title="Hilton breakfast",
            body="Not the house.",
            owner="Nick",
            recorded_at=now - timedelta(minutes=30),
        )
    )
    db.add(MemoryItem(kind="fact", text="the milk stays in the door", source="manual", created_at=now, pinned=False))
    db.add(
        MemoryItem(kind="routine", text="bins go out every Tuesday", source="manual", created_at=now, pinned=False)
    )
    db.flush()


def test_home_guard_allows_a_personal_hotel_and_refuses_work(client):
    allowed = "booked a hotel in Lisbon for May"
    assert outside_home(allowed) is False
    assert client.post("/tasks", json={"title": allowed}).status_code == 201
    remembered = client.post("/memory", json={"kind": "fact", "text": allowed})
    assert remembered.status_code == 201
    assert remembered.json()["text"] == allowed

    refused = [
        "Call Hilton",
        "Meet a guest",
        "Ask a colleague",
        "Email the employer",
        "Payroll is on the work email",
        "Leave it at work",
    ]
    for title in refused:
        response = client.post("/tasks", json={"title": title})
        assert response.status_code == 422, title
        assert response.json()["detail"] == "Not for the house log."
    stored = [item["title"] for item in client.get("/tasks").json()["items"]]
    assert stored == [allowed]


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("buy oat milk", "shopping"),
        ("remember the milk stays in the door", "remember"),
        ("forget the spare key", "forget"),
        ("put the bins out", "task"),
        ("booked a hotel in Lisbon for May", "task"),
        ("remember booked a hotel in Lisbon for May", "remember"),
        ("meet a guest", None),
        ("email my employer", None),
        ("what's for dinner?", None),
        ("Call Hilton", None),
        ("the workplace rota", None),
    ],
)
def test_voice_scope(text, kind):
    assert voice_kind(text) == kind


def test_context_contract_matches_the_golden_files(db, caplog):
    assert SCHEMA_VERSION == 1
    assert TOKEN_BUDGET == 2000
    assert TRIM_ORDER == ("log", "waiting", "commitments", "tasks", "memory")
    now = london(2026, 11, 6, 8, 0)
    _seed(db, now)
    db.add(Task(title=NOT_IN_LOGS, status="todo", priority="low", owner="Nick"))
    db.flush()
    focus = ContextEntry(kind="task", id="focus", title="Put the bins out", status="doing")
    with caplog.at_level(logging.INFO, logger="organiser.agent.context"):
        smart = build_context(db, purpose="smart_add", now=now, query="milk")
        catch = build_context(db, purpose="catch_up", now=now)
        follow = build_context(db, purpose="follow_up", now=now, query="Put the bins out", focus=focus)

    def without_probe(context: HouseContext) -> dict:
        projected = _project(context)
        projected["tasks"] = [title for title in projected["tasks"] if title != NOT_IN_LOGS]
        return projected

    assert NOT_IN_LOGS in [item.title for item in smart.tasks]
    assert without_probe(smart) == json.loads((FIXTURES / "smart_add.json").read_text())
    assert without_probe(catch) == json.loads((FIXTURES / "catch_up.json").read_text())
    assert without_probe(follow) == json.loads((FIXTURES / "follow_up.json").read_text())
    assert NOT_IN_LOGS not in caplog.text
    assert "Book a hotel in Lisbon" not in caplog.text
    assert "the milk stays in the door" not in caplog.text
    assert "context schema=1 purpose=smart_add" in caplog.text
    assert "tasks=" in caplog.text
    assert "memory=" in caplog.text


def test_token_budget_drops_the_oldest_log_line_first():
    context = HouseContext(
        schema_version=1,
        purpose="smart_add",
        time="2026-11-06T08:00",
        theme="morning",
        tasks=[_entry("task", "Put the bins out")],
        commitments=[],
        waiting=[_entry("waiting", "Boiler filters")],
        log=[_entry("log", "newest"), _entry("log", "oldest")],
        log_days=3,
        memory=MemorySlot(limit=10, items=[]),
    )
    trimmed = trim_to_budget(context, budget=token_count(context) - 1)
    assert [item.title for item in trimmed.log] == ["newest"]
    assert [item.title for item in trimmed.waiting] == ["Boiler filters"]
    assert [item.title for item in trimmed.tasks] == ["Put the bins out"]
    assert trimmed.trimmed is True
    assert trimmed.focus is None


def test_metrics_are_counts_without_house_text(client, house_clock, mistral):
    house_clock["now"] = london(2026, 11, 2, 8, 0)
    mistral([say("Nothing to add.")])
    assert client.post("/tasks", json={"title": "Put the bins out"}).status_code == 201
    assert client.post("/agent/feed", json={"text": "need oat milk"}).status_code == 200
    assert client.get("/agent/activity").status_code == 200
    body = client.get("/metrics").text
    assert body.endswith("\n")
    assert "Put the bins out" not in body
    assert "need oat milk" not in body
    assert 'organiser_http_requests_total{method="POST",route="/tasks",status="201"}' in body
    assert "organiser_http_request_duration_seconds_count" in body
    assert 'organiser_mistral_calls_total{result="ok"}' in body
    assert "organiser_mistral_duration_seconds_count" in body
    assert "organiser_activity_poll_age_seconds -1" not in body
    assert "organiser_activity_poll_age_seconds" in body
    assert "organiser_proposal_queue 0" in body
    status = client.get("/system/status").json()
    assert status["health"] == "ok"
    assert status["version"] == __version__ == "0.3.0"
    assert status["last_mistral_success"] is not None
    assert status["last_activity_poll"] is not None
    assert status["database_bytes"] > 0
    assert "Put the bins out" not in client.get("/system/status").text


def test_reads_for_status_do_not_call_mistral(client, mistral):
    fake = mistral([say("This must not run.")])
    assert client.get("/metrics").status_code == 200
    assert client.get("/system/status").status_code == 200
    assert client.get("/alerts").status_code == 200
    assert client.get("/health").status_code == 200
    assert fake.calls == []


def test_alerts_dedupe_dismiss_and_do_not_send(client, house_clock, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("an alert tried to send")

    monkeypatch.setattr("organiser.services.outbound.request_json_any", boom)
    morning = london(2026, 11, 2, 9, 0)
    house_clock["now"] = morning
    METRICS.started_at = morning
    METRICS.record_poll(morning)
    assert client.get("/alerts").json()["items"] == []

    for minute in (0, 1, 2):
        METRICS.record_mistral(ok=False, seconds=0.2, at=morning + timedelta(minutes=minute))
    METRICS.record_db_error(morning)
    kinds = [item["kind"] for item in client.get("/alerts").json()["items"]]
    assert kinds == ["mistral_failing", "database_error"]
    again = [item["kind"] for item in client.get("/alerts").json()["items"]]
    assert again == kinds

    dismissed = client.post("/alerts/mistral_failing/dismiss")
    assert dismissed.status_code == 200
    assert [item["kind"] for item in dismissed.json()["items"]] == ["database_error"]
    METRICS.record_mistral(ok=False, seconds=0.2, at=morning + timedelta(minutes=4))
    assert [item["kind"] for item in client.get("/alerts").json()["items"]] == ["database_error"]

    later = morning + timedelta(minutes=20)
    house_clock["now"] = later
    for minute in (0, 1, 2):
        METRICS.record_mistral(ok=False, seconds=0.1, at=later + timedelta(minutes=minute))
    assert "mistral_failing" in [item["kind"] for item in client.get("/alerts").json()["items"]]
    assert client.post("/alerts/no-such/dismiss").status_code == 404


def test_activity_poll_alert_is_the_weekday_window(client, house_clock):
    morning = london(2026, 11, 2, 9, 0)
    house_clock["now"] = morning
    METRICS.started_at = morning - timedelta(hours=3)
    METRICS.last_poll = None
    METRICS.last_db_error = None
    assert any(item["kind"] == "activity_poll" for item in client.get("/alerts").json()["items"])

    METRICS.record_poll(morning - timedelta(hours=1))
    assert all(item["kind"] != "activity_poll" for item in client.get("/alerts").json()["items"])

    house_clock["now"] = london(2026, 11, 7, 12, 0)
    METRICS.last_poll = london(2026, 11, 7, 7, 0)
    assert all(item["kind"] != "activity_poll" for item in client.get("/alerts").json()["items"])

    house_clock["now"] = london(2026, 11, 6, 23, 0)
    METRICS.last_poll = london(2026, 11, 6, 18, 0)
    assert all(item["kind"] != "activity_poll" for item in client.get("/alerts").json()["items"])

    shown = client.get("/alerts").json()["items"]
    assert all(item["kind"] != "activity_poll" for item in shown)


def test_voice_is_off_unless_enabled(client):
    response = client.post(
        "/voice/transcribe",
        files={"file": ("line.webm", b"abc", "audio/webm")},
    )
    assert response.status_code == 404
    assert client.get("/system/facts").json()["voice_input"] == "off"
    policy = client.get("/health").headers["permissions-policy"]
    assert "microphone=(self)" in policy
    assert "camera=()" in policy


def test_voice_returns_text_and_keeps_audio_in_memory(client, monkeypatch, caplog):
    monkeypatch.setenv("VOICE_INPUT_ENABLED", "true")
    get_settings.cache_clear()
    fake = FakeTranscriber("buy oat milk")
    app.dependency_overrides[get_transcriber] = lambda: fake

    def refuse_disk(*_args, **_kwargs):
        raise AssertionError("audio touched the disk")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", refuse_disk)
    monkeypatch.setattr(tempfile, "mkstemp", refuse_disk)
    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", lambda self: refuse_disk())
    try:
        with caplog.at_level(logging.DEBUG):
            response = client.post(
                "/voice/transcribe",
                files={"file": ("line.webm", MARKER, "audio/webm")},
            )
        assert response.status_code == 200, response.text
        assert response.json() == {"text": "buy oat milk"}
        assert fake.audio == [MARKER]
        assert MARKER.decode() not in caplog.text
        assert "buy oat milk" not in caplog.text
        assert client.get("/tasks").json()["items"] == []
        assert client.get("/events").json()["items"] == []
        assert client.get("/memory").json()["items"] == []
        assert client.get("/agent").json()["proposals"] == []
    finally:
        app.dependency_overrides.pop(get_transcriber, None)
        get_settings.cache_clear()


def test_voice_refuses_what_is_outside_its_scope(client, monkeypatch):
    monkeypatch.setenv("VOICE_INPUT_ENABLED", "true")
    get_settings.cache_clear()
    app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber("meet a guest at six")
    try:
        response = client.post(
            "/voice/transcribe",
            files={"file": ("line.webm", b"clip", "audio/webm")},
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "Not for the house log."
        assert "guest" not in response.json()["detail"].lower() or response.json()["detail"] == "Not for the house log."
        app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber("what is on today?")
        question = client.post(
            "/voice/transcribe",
            files={"file": ("line.webm", b"clip", "audio/webm")},
        )
        assert question.status_code == 422
        assert question.json()["detail"] == "Voice is for a task, a shop item, or remember and forget."
        assert client.get("/tasks").json()["items"] == []
    finally:
        app.dependency_overrides.pop(get_transcriber, None)
        get_settings.cache_clear()


def test_voxtral_posts_audio_from_memory(caplog):
    seen: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        seen["url"] = str(request.url).encode()
        return httpx.Response(200, json={"text": "put the bins out"})

    client = MistralClient("test-key", "https://api.mistral.ai", transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.DEBUG):
        text = client.transcribe(MARKER, model="voxtral-mini", media_type="audio/webm")
    client.close()
    assert text == "put the bins out"
    assert seen["url"].endswith(b"/v1/audio/transcriptions")
    assert MARKER in seen["body"]
    assert b"voxtral-mini" in seen["body"]
    assert b"test-key" not in seen["body"]
    assert MARKER.decode() not in caplog.text
