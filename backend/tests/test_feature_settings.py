"""Settings for each house feature. Persisted, audited, and free of secrets."""

import hashlib
import hmac
import json
from datetime import timedelta

from agent_fakes import london
from organiser.agent.context import build_context
from organiser.config import get_settings
from organiser.models import Event, MemoryItem
from organiser.services.settings import (
    PLAYLIST_UNAVAILABLE,
    VOICE_UNAVAILABLE,
    VOXTRAL_UNAVAILABLE,
    X_STAYS_OFF,
)
from organiser.x.store import brief_section, create_draft, remember_external
from test_sprint7 import XApi, _connect, _enable, _install

SECRET = "webhook-secret-not-real"
SENTINELS = (SECRET, "tfl-key-not-real", "SW1A 1AA", "51.5", "-0.1")


def _activity(client):
    return client.get("/agent/activity?limit=80").json()["items"]


def _titles(client):
    return [item["text"] for item in _activity(client)]


def test_playlist_toggle_shows_hearthis_and_is_audited(client, monkeypatch):
    hidden = client.get("/system/settings")
    assert hidden.status_code == 200
    assert hidden.json()["playlist"]["available"] is False
    assert hidden.json()["playlist"]["profile"] == ""
    refused = client.patch("/system/settings", json={"playlist_enabled": True})
    assert refused.status_code == 422
    assert refused.json()["detail"] == PLAYLIST_UNAVAILABLE

    monkeypatch.setenv("PLAYLIST_SOURCE", "hearthis")
    monkeypatch.setenv("HEARTHIS_PROFILE", "chlorophil")
    get_settings.cache_clear()
    try:
        shown = client.get("/system/settings").json()["playlist"]
        assert shown["source"] == "hearthis"
        assert shown["profile"] == "chlorophil"
        assert shown["enabled"] is True
        assert client.get("/system").json()["playlist"] is True

        off = client.patch("/system/settings", json={"playlist_enabled": False})
        assert off.status_code == 200
        assert off.json()["playlist"]["enabled"] is False
        assert client.get("/system").json()["playlist"] is False
        assert client.get("/playlist").json()["shown"] is False
        again = client.patch("/system/settings", json={"playlist_enabled": False})
        assert again.status_code == 200
        assert _titles(client).count("Settings: playlist off") == 1

        on = client.patch("/system/settings", json={"playlist_enabled": True})
        assert on.json()["playlist"]["enabled"] is True
        assert client.get("/playlist").json()["shown"] is True
        assert "Settings: playlist on" in _titles(client)
    finally:
        get_settings.cache_clear()


def test_alerts_and_webhooks_persist_without_echoing_a_secret(client, db, house_clock, monkeypatch, caplog):
    house_clock["now"] = london(2026, 11, 2, 9, 0)
    monkeypatch.setenv("WEBHOOK_SECRET_BANTO", SECRET)
    get_settings.cache_clear()
    try:
        body = client.get("/system/settings").json()
        assert body["alerts"]["enabled"] is True
        assert body["webhooks"]["enabled"] is True
        assert body["webhooks"]["banto"] == "configured"
        assert body["webhooks"]["banto_x"] == "not configured"
        assert SECRET not in client.get("/system/settings").text

        off = client.patch("/system/settings", json={"alerts_enabled": False, "webhooks_enabled": False})
        assert off.status_code == 200
        assert off.json()["alerts"]["enabled"] is False
        assert off.json()["webhooks"]["enabled"] is False
        from organiser.metrics import METRICS

        morning = london(2026, 11, 2, 9, 0)
        for minute in (0, 1, 2):
            METRICS.record_mistral(ok=False, seconds=0.1, at=morning + timedelta(minutes=minute))
        assert client.get("/alerts").json()["items"] == []

        raw = json.dumps(
            {
                "event": "commute",
                "start": "2026-11-06T07:00:00+00:00",
                "end": "2026-11-06T08:10:00+00:00",
                "location_label": "Wembley",
            }
        ).encode()
        stamp = int(morning.timestamp())
        signature = hmac.new(SECRET.encode(), f"{stamp}.".encode() + raw, hashlib.sha256).hexdigest()
        hooked = client.post(
            "/hooks/banto",
            content=raw,
            headers={
                "content-type": "application/json",
                "x-organiser-timestamp": str(stamp),
                "x-organiser-signature": signature,
            },
        )
        assert hooked.status_code == 503
        assert hooked.json()["detail"] == "Webhooks are off."
        assert SECRET not in hooked.text
        assert SECRET not in caplog.text
        assert db.query(Event).count() >= 1
        from organiser.models import CommuteShift

        assert db.query(CommuteShift).count() == 0

        client.patch("/system/settings", json={"alerts_enabled": True})
        assert [item["kind"] for item in client.get("/alerts").json()["items"]] == ["mistral_failing"]
        titles = _titles(client)
        assert "Settings: alerts off" in titles
        assert "Settings: webhooks off" in titles
        assert "Settings: alerts on" in titles
        assert all(item["type"] == "settings" for item in _activity(client) if item["text"].startswith("Settings:"))
    finally:
        get_settings.cache_clear()


def test_voice_reflects_the_environment_and_voxtral(client, monkeypatch):
    quiet = client.get("/system/settings").json()["voice"]
    assert quiet["mic"] == "off"
    assert quiet["env_enabled"] is False
    assert quiet["voxtral"] == "off"
    assert quiet["detail"] == VOICE_UNAVAILABLE
    refused = client.patch("/system/settings", json={"voice_enabled": True})
    assert refused.status_code == 422
    assert refused.json()["detail"] == VOICE_UNAVAILABLE
    assert client.post("/voice/transcribe", files={"file": ("line.webm", b"abc", "audio/webm")}).status_code == 404

    monkeypatch.setenv("VOICE_INPUT_ENABLED", "true")
    get_settings.cache_clear()
    try:
        allowed = client.get("/system/settings").json()["voice"]
        assert allowed["mic"] == "on"
        assert allowed["env_enabled"] is True
        assert allowed["voxtral"] == "unavailable"
        assert allowed["detail"] == VOXTRAL_UNAVAILABLE
        assert client.get("/system/facts").json()["voice_input"] == "on"

        off = client.patch("/system/settings", json={"voice_enabled": False})
        assert off.json()["voice"]["mic"] == "off"
        assert off.json()["voice"]["detail"] == "Voice input is allowed. The microphone is off."
        assert client.get("/system/facts").json()["voice_input"] == "off"
        assert client.post("/voice/transcribe", files={"file": ("line.webm", b"abc", "audio/webm")}).status_code == 404
        assert "Settings: voice off" in _titles(client)

        monkeypatch.setenv("MISTRAL_API_KEY", "test-key-not-real")
        get_settings.cache_clear()
        on = client.patch("/system/settings", json={"voice_enabled": True})
        assert on.json()["voice"]["mic"] == "on"
        assert on.json()["voice"]["voxtral"] == "ready"
        assert on.json()["voice"]["detail"] == "voxtral-mini"
        assert "test-key-not-real" not in on.text
    finally:
        get_settings.cache_clear()


def test_x_limits_persist_without_turning_x_on(client, db, house_clock, monkeypatch):
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    refused = client.patch("/system/settings", json={"x_enabled": True})
    assert refused.status_code == 422
    saved = client.patch(
        "/system/settings",
        json={"x_sync_minutes": 15, "x_daily_cap": 2, "x_from_max": 1, "x_draft_expiry_days": 2},
    )
    assert saved.status_code == 200
    body = saved.json()["x"]
    assert body["enabled"] is False
    assert body["sync_minutes"] == 15
    assert body["daily_cap"] == 2
    assert body["from_max"] == 1
    assert body["draft_expiry_days"] == 2
    assert body["detail"] == X_STAYS_OFF
    assert client.get("/x/status").json()["enabled"] is False
    titles = _titles(client)
    assert "Settings: X sync interval" in titles
    assert "Settings: X daily cap" in titles
    assert "Settings: From X maximum" in titles
    assert "Settings: X draft expiry" in titles

    db.expire_all()
    now = london(2026, 11, 6, 8, 0)
    draft = create_draft(db, "Put the bins out tonight", "The bins.", now, "assistant")
    assert draft.expires_at - now == timedelta(days=2)
    first = remember_external(
        db,
        kind="bookmark",
        external_id="501",
        text="Council collection moved to Friday",
        author="housebin",
        url=None,
        source="poll",
        now=now,
        strict=False,
    )
    second = remember_external(
        db,
        kind="bookmark",
        external_id="502",
        text="Spare bowls are in the cupboard",
        author="housebin",
        url=None,
        source="poll",
        now=now,
        strict=False,
    )
    assert first is not None
    assert second is None
    db.commit()
    section = brief_section(db, now)
    assert section is not None
    assert len(section["items"]) == 1

    _enable(monkeypatch)
    api = XApi()
    api.bookmarks = [{"id": "880", "text": "A later bin note", "author_id": "7"}]
    _install(api)
    try:
        _connect(client, db)
        assert client.post("/x/poll").json()["reason"] == "polled"
        house_clock["now"] = london(2026, 11, 6, 8, 10)
        assert client.post("/x/poll").json()["reason"] == "cached"
        house_clock["now"] = london(2026, 11, 6, 8, 16)
        assert client.post("/x/poll").json()["reason"] == "polled"
    finally:
        get_settings.cache_clear()


def test_agent_context_limits_the_log_and_the_memory_slot(client, db, house_clock):
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    now = london(2026, 11, 6, 8, 0)
    db.add(Event(kind="note", title="Recent bowls", body="In the cupboard", owner="Nick", recorded_at=now))
    db.add(
        Event(
            kind="note",
            title="Old bowls",
            body="Last week",
            owner="Nick",
            recorded_at=now - timedelta(days=3),
        )
    )
    db.add(
        MemoryItem(
            kind="fact",
            text="the spare bowls live in the cupboard",
            source="manual",
            created_at=now,
            pinned=False,
        )
    )
    db.add(
        MemoryItem(
            kind="fact",
            text="the oat milk stays in the door",
            source="manual",
            created_at=now,
            pinned=True,
        )
    )
    db.commit()
    saved = client.patch(
        "/system/settings",
        json={"context_memory_limit": 1, "context_smart_add_days": 1, "context_token_budget": 800, "context_catch_up_days": 2},
    )
    assert saved.status_code == 200
    assert saved.json()["agent_context"]["memory_limit"] == 1
    assert "Settings: context memory lines" in _titles(client)
    db.expire_all()
    context = build_context(db, purpose="smart_add", now=now, query="bowls milk")
    titles = [item.title for item in context.log]
    assert "Recent bowls" in titles
    assert "Old bowls" not in titles
    assert context.log_days == 1
    assert len(context.memory.items) == 1


def test_docs_status_follows_both_switches(client, monkeypatch):
    assert client.get("/system/settings").json()["docs"]["state"] == "off"
    monkeypatch.setenv("ENABLE_DOCS", "true")
    monkeypatch.setenv("DOCS_BEHIND_ACCESS", "false")
    get_settings.cache_clear()
    try:
        held = client.get("/system/settings").json()["docs"]
        assert held["state"] == "not published"
        assert "Cloudflare Access" in held["detail"]
        monkeypatch.setenv("DOCS_BEHIND_ACCESS", "true")
        get_settings.cache_clear()
        opened = client.get("/system/settings").json()["docs"]
        assert opened["state"] == "behind access"
        assert client.patch("/system/settings", json={"docs": "on"}).status_code == 422
    finally:
        get_settings.cache_clear()


def test_status_names_each_service_without_a_secret(client, monkeypatch):
    monkeypatch.setenv("TFL_APP_KEY", "tfl-key-not-real")
    monkeypatch.setenv("HOUSE_POSTCODE", "SW1A 1AA")
    monkeypatch.setenv("HOUSE_LAT", "51.5")
    monkeypatch.setenv("HOUSE_LON", "-0.1")
    get_settings.cache_clear()
    try:
        status = client.get("/system/status")
        assert status.status_code == 200
        names = [item["name"] for item in status.json()["services"]]
        assert names == ["mistral", "voxtral", "google", "tfl", "x", "hearthis"]
        by_name = {item["name"]: item for item in status.json()["services"]}
        assert by_name["mistral"]["state"] == "not configured"
        assert by_name["voxtral"]["state"] == "off"
        assert by_name["google"]["state"] == "not configured"
        assert by_name["tfl"]["state"] == "unknown"
        assert by_name["x"]["state"] == "off"
        assert by_name["hearthis"]["state"] == "off"
        for secret in SENTINELS:
            assert secret not in status.text
    finally:
        get_settings.cache_clear()
