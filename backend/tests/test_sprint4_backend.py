"""Sprint 4: logs, headers, home scope, the playlist flag, webhooks, and context."""

import hashlib
import hmac
import json
import logging
from datetime import timedelta

from sqlalchemy import func, select

from agent_fakes import london, say
from organiser import clock
from organiser.agent.context import MEMORY_LIMIT, build_context
from organiser.agent.runner import feed_packet
from organiser.config import get_settings
from organiser.httpsec import SECURITY_HEADERS
from organiser.jsonlog import JsonFormatter, scrub
from organiser.limits import LIMITS
from organiser.models import Commitment, Event, Task
from organiser.routes.hooks import clear_replay_cache
from organiser.timeutil import utcnow

SECRET = "webhook-secret-not-real"
SENTINEL = "BODY-SENTINEL-9f3"


def _count_events(db) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(Event))


def _sign(raw: bytes, stamp: int, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), f"{stamp}.".encode() + raw, hashlib.sha256).hexdigest()


def _stamp() -> int:
    return int(clock.current_time().timestamp())


def _post_hook(client, raw: bytes, *, source="banto", stamp=None, signature=None, secret=SECRET):
    stamp = _stamp() if stamp is None else stamp
    signature = _sign(raw, stamp, secret) if signature is None else signature
    return client.post(
        f"/hooks/{source}",
        content=raw,
        headers={
            "content-type": "application/json",
            "x-organiser-timestamp": str(stamp),
            "x-organiser-signature": signature,
        },
    )


def test_health_carries_security_headers(client):
    response = client.get("/health")
    for key, value in SECURITY_HEADERS.items():
        assert response.headers[key.lower()] == value


def test_logs_are_json_and_drop_secrets_places_and_bodies(client, caplog):
    assert scrub("api_key=abc SW1A 1AA at 51.5074,-0.1278") == "api_key=[redacted] [redacted] at [redacted],[redacted]"
    record = logging.LogRecord("organiser.test", logging.INFO, __file__, 1, "token=sekret near 51.5010", (), None)
    line = json.loads(JsonFormatter().format(record))
    assert line["message"] == "token=[redacted] near [redacted]"
    assert "logger" in line and "level" in line and "time" in line
    assert "exc_info" not in line

    with caplog.at_level(logging.INFO):
        created = client.post(
            "/tasks",
            json={"title": "Put the bins out", "detail": f"{SENTINEL} SW1A 1AA 51.5074"},
        )
    assert created.status_code == 201
    blob = caplog.text
    assert SENTINEL not in blob
    assert "SW1A 1AA" not in blob
    assert "51.5074" not in blob
    assert "\n{" not in blob or blob.strip().startswith("{") or "request" in blob


def test_inbound_routes_refuse_outside_the_house(client, db):
    samples = [
        ("/tasks", {"title": "Book a Hilton room"}),
        ("/commitments", {"title": "Meet a colleague"}),
        ("/events", {"kind": "note", "title": "Guest list"}),
        ("/action-requests", {"title": "Email the employer", "mode": "observe"}),
    ]
    before = _count_events(db)
    for path, payload in samples:
        response = client.post(path, json=payload)
        assert response.status_code == 422, path
        assert response.json()["detail"] == "Not for the house log."
    assert client.get("/tasks").json()["items"] == []
    assert client.get("/commitments").json()["items"] == []
    assert _count_events(db) == before


def test_playlist_stub_is_off_unless_configured(client, monkeypatch):
    assert client.get("/system").json()["playlist_stub"] is False
    monkeypatch.setenv("SHOW_PLAYLIST_STUB", "true")
    get_settings.cache_clear()
    try:
        assert client.get("/system").json()["playlist_stub"] is True
    finally:
        get_settings.cache_clear()


def test_commute_shift_and_signed_webhook_share_one_check(client, db, house_clock, monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_BANTO", SECRET)
    monkeypatch.setenv("WEBHOOK_SECRET_BANTO_X", "later-secret")
    monkeypatch.setenv("BANTO_COMMUTE_TOKEN", "banto-push-token")
    get_settings.cache_clear()
    clear_replay_cache()
    LIMITS.reset()
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    shift = {
        "start": "2026-11-06T07:00:00+00:00",
        "end": "2026-11-06T08:10:00+00:00",
        "location_label": "Wembley",
    }
    try:
        direct = client.post("/commute/shift", json=shift, headers={"Authorization": "Bearer banto-push-token"})
        assert direct.status_code == 201
        assert direct.json()["location_label"] == "Wembley"
        assert "staff" not in direct.text
        assert "Wembley Park" not in direct.text

        raw = json.dumps({"event": "commute", **shift}).encode()
        hooked = _post_hook(client, raw)
        assert hooked.status_code == 200, hooked.text
        assert hooked.json()["location_label"] == "Wembley"
        assert hooked.json()["id"] == direct.json()["id"]

        again = _post_hook(client, raw)
        assert again.status_code == 409
        titles = [item["title"] for item in client.get("/events?kind=brief").json()["items"]]
        assert titles.count("Commute: Wembley 07:00–08:10") == 1
        assert SECRET not in hooked.text
        assert "later-secret" not in repr(get_settings())
    finally:
        get_settings.cache_clear()
        clear_replay_cache()
        LIMITS.reset()


def test_webhook_rejects_bad_signatures_unknowns_and_stores_nothing(client, db, house_clock, monkeypatch, caplog):
    monkeypatch.setenv("WEBHOOK_SECRET_BANTO", SECRET)
    monkeypatch.setenv("WEBHOOK_SECRET_BANTO_X", "later-secret")
    monkeypatch.setenv("BANTO_COMMUTE_TOKEN", "banto-push-token")
    get_settings.cache_clear()
    clear_replay_cache()
    LIMITS.reset()
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    before = _count_events(db)
    raw = json.dumps(
        {
            "event": "commute",
            "start": "2026-11-06T07:00:00+00:00",
            "end": "2026-11-06T08:10:00+00:00",
            "location_label": "Wembley",
            "staff_id": "staff-99",
        }
    ).encode()
    try:
        with caplog.at_level(logging.DEBUG):
            bad_sig = _post_hook(client, raw, signature="0" * 64)
            old = _post_hook(client, raw, stamp=_stamp() - 600)
            unknown_source = _post_hook(client, raw, source="banto_x")
            unknown_event = _post_hook(
                client,
                json.dumps(
                    {
                        "event": "ping",
                        "start": "2026-11-06T07:00:00+00:00",
                        "end": "2026-11-06T08:10:00+00:00",
                        "location_label": "Wembley",
                    }
                ).encode(),
            )
            outside = client.post(
                "/commute/shift",
                json={
                    "start": "2026-11-06T07:00:00+00:00",
                    "end": "2026-11-06T08:10:00+00:00",
                    "location_label": "hotel",
                },
                headers={"Authorization": "Bearer banto-push-token"},
            )
            extra = _post_hook(client, raw)
            missing = client.post("/hooks/banto", json={"event": "commute"})
        assert bad_sig.status_code == 401
        assert old.status_code == 401
        assert unknown_source.status_code == 404
        assert unknown_event.status_code == 404
        assert outside.status_code == 422
        assert extra.status_code == 422
        assert missing.status_code == 401
        assert _count_events(db) == before
        assert "staff-99" not in caplog.text
        assert SECRET not in caplog.text
    finally:
        get_settings.cache_clear()
        clear_replay_cache()
        LIMITS.reset()


def test_unconfigured_webhook_stays_closed(client, monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_BANTO", "")
    get_settings.cache_clear()
    try:
        response = client.post("/hooks/banto", json={"event": "commute"})
        assert response.status_code == 503
    finally:
        get_settings.cache_clear()


def test_context_shape_window_and_home_filter(db):
    now = london(2026, 11, 6, 8, 0)
    db.add(Task(title="Put the bins out", detail="Green bin.", status="todo", priority="high", owner="Nick"))
    db.add(Task(title="Book a hotel room", status="todo", priority="low", owner="Nick"))
    db.add(Task(title="Call Hilton", status="todo", priority="low", owner="Nick"))
    db.add(Task(title="Done already", status="done", priority="low", owner="Nick"))
    db.add(Commitment(title="Collect the dry cleaning", status="open", owner="Nick", source="manual"))
    db.add(Commitment(title="Meet a guest", status="open", owner="Nick", source="manual"))
    db.add(
        Event(
            kind="note",
            title="Milk is low",
            body="Noted for the shopping list.",
            owner="Nick",
            recorded_at=utcnow(),
        )
    )
    db.add(
        Event(
            kind="note",
            title="Old note",
            body="Five days ago.",
            owner="Nick",
            recorded_at=now - timedelta(days=5),
        )
    )
    db.add(
        Event(
            kind="note",
            title="Hilton breakfast",
            body="Not the house.",
            owner="Nick",
            recorded_at=utcnow(),
        )
    )
    db.flush()

    morning = build_context(db, purpose="smart_add", now=now)
    dumped = morning.model_dump()
    assert set(dumped) == {
        "schema_version",
        "purpose",
        "time",
        "theme",
        "tasks",
        "commitments",
        "waiting",
        "log",
        "log_days",
        "memory",
        "focus",
        "trimmed",
    }
    assert morning.schema_version == 1
    assert morning.trimmed is False
    assert morning.focus is None
    assert set(dumped["tasks"][0]) == {"kind", "id", "title", "status", "due_on", "at"}
    assert morning.purpose == "smart_add"
    assert morning.theme == "morning"
    assert morning.time.startswith("2026-11-06T08:00")
    assert morning.log_days == 3
    assert morning.memory.limit == MEMORY_LIMIT == 10
    assert morning.memory.items == []
    assert [item.title for item in morning.tasks] == ["Book a hotel room", "Put the bins out"]
    assert [item.title for item in morning.commitments] == ["Collect the dry cleaning"]
    assert [item.title for item in morning.log] == ["Milk is low"]
    assert morning.waiting == []

    evening = build_context(db, purpose="catch_up", now=london(2026, 11, 6, 18, 0))
    assert evening.theme == "evening"
    assert evening.log_days == 7
    assert {item.title for item in evening.log} == {"Milk is low", "Old note"}
    assert evening.memory.items == []


def test_smart_add_receives_context_without_rewriting_the_packet(client, house_clock, mistral):
    house_clock["now"] = london(2026, 11, 2, 8, 0)
    plain = feed_packet(london(2026, 11, 2, 8, 0), "Europe/London", 3, "need filters for the boiler before Friday")
    fake = mistral([say("Nothing to add.")])
    response = client.post("/agent/feed", json={"text": "need filters for the boiler before Friday"})
    assert response.status_code == 200
    packet = fake.calls[0][2]
    assert packet.startswith(plain)
    assert "\n\nContext:\n" in packet
    context = json.loads(packet.split("\n\nContext:\n", 1)[1])
    assert context["purpose"] == "smart_add"
    assert context["log_days"] == 3
    assert context["memory"]["limit"] == 10
    assert context["memory"]["items"] == []


def test_catch_up_builds_context_and_still_chooses_in_code(client, db, house_clock, monkeypatch):
    seen = []
    real = build_context

    def spy(session, *, purpose, now):
        ctx = real(session, purpose=purpose, now=now)
        seen.append((ctx.purpose, ctx.log_days, len(ctx.memory.items)))
        return ctx

    monkeypatch.setattr("organiser.services.catchup.build_context", spy)
    house_clock["now"] = london(2026, 11, 2, 8, 0)
    client.post("/tasks", json={"title": "Put the bins out", "due_on": "2026-11-02", "priority": "high"})
    first = client.post("/catch-up/look")
    assert first.status_code == 200
    assert first.json()["items"] == []
    assert seen == [("catch_up", 7, 0)]
    house_clock["now"] = london(2026, 11, 2, 16, 0)
    opened = client.post("/catch-up/look")
    assert opened.status_code == 200
    assert opened.json()["items"][0]["rule"] == "due_today"
    assert seen[-1][0] == "catch_up"
