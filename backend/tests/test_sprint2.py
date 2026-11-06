"""Sprint 2: shopping, weather, the read-only diary, and the assistant switch."""

import logging
from pathlib import Path

import pytest
from sqlalchemy import inspect

from organiser.config import get_settings
from organiser.services.diary import clear_cache as clear_diary_cache
from organiser.services.weather import clear_cache as clear_weather_cache

LAT = "10.50000"
LON = "20.50000"
POSTCODE = "POSTCODE-PLACEHOLDER"
CLIENT = "oauth-client-sentinel"
SECRET = "oauth-secret-sentinel"
REFRESH = "oauth-refresh-sentinel"
CALENDAR_ID = "cal-id-sentinel"
OTHER_ID = "other-id-sentinel"
TOKEN = "access-token-sentinel"


@pytest.fixture
def reload_settings(monkeypatch):
    yield monkeypatch
    get_settings.cache_clear()
    clear_weather_cache()
    clear_diary_cache()


def test_shopping_table_has_no_allergen_column(db):
    columns = {column["name"] for column in inspect(db.get_bind()).get_columns("shopping_items")}
    assert {"id", "name", "ticked"} <= columns
    assert "allergen" not in columns
    assert "allergens" not in columns


def test_shopping_is_names_and_ticks(client):
    created = client.post("/shopping", json={"name": "  Oat milk  "})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Oat milk"
    assert body["ticked"] is False
    assert "allergen" not in body

    refused = client.post("/shopping", json={"name": "Bread", "allergen": "gluten"})
    assert refused.status_code == 422
    outside = client.post("/shopping", json={"name": "Hilton towels"})
    assert outside.status_code == 422
    assert "Hilton" not in outside.text

    duplicate = client.post("/shopping", json={"name": "oat milk"})
    assert duplicate.status_code == 409

    ticked = client.post(f"/shopping/{body['id']}/tick")
    assert ticked.status_code == 200
    assert ticked.json()["ticked"] is True

    shopping = next(section for section in client.get("/brief/morning").json()["sections"] if section["key"] == "shopping")
    assert shopping["summary"] == "All ticked off."
    assert shopping["items"][0]["title"] == "Oat milk"
    assert shopping["items"][0]["ticked"] is True

    cleared = client.post(f"/shopping/{body['id']}/untick")
    assert cleared.json()["ticked"] is False
    shopping = next(section for section in client.get("/brief/morning").json()["sections"] if section["key"] == "shopping")
    assert shopping["summary"] == "1 to get"


def test_assistant_switch_persists_and_is_audited(client, reload_settings):
    reload_settings.setenv("MISTRAL_API_KEY", "key-sentinel")
    reload_settings.setenv("MISTRAL_AGENT_ID", "agent-sentinel")
    get_settings.cache_clear()

    turned_off = client.post("/system/assistant", json={"enabled": False})
    assert turned_off.status_code == 200
    assert turned_off.json()["assistant_switch"] == "off"
    assert turned_off.json()["assistant"] == "off"
    assert "key-sentinel" not in turned_off.text

    extra = client.post("/system/assistant", json={"enabled": True, "token": "no"})
    assert extra.status_code == 422

    again = client.post("/system/assistant", json={"enabled": False})
    assert again.status_code == 200
    activity = client.get("/agent/activity?limit=20").json()["items"]
    switched = [item for item in activity if item["text"] == "Assistant switched off"]
    assert len(switched) == 1
    assert switched[0]["type"] == "assistant"

    feed = client.post("/agent/feed", json={"text": "Buy oat milk"})
    assert feed.status_code == 503

    turned_on = client.post("/system/assistant", json={"enabled": True}).json()
    assert turned_on["assistant_switch"] == "on"
    assert turned_on["assistant"] == "on"
    assert client.get("/system/facts").json()["assistant_switch"] == "on"


def test_weather_uses_coordinates_without_logging_them(client, reload_settings, caplog):
    reload_settings.setenv("HOUSE_LAT", LAT)
    reload_settings.setenv("HOUSE_LON", LON)
    reload_settings.setenv("HOUSE_POSTCODE", POSTCODE)
    get_settings.cache_clear()
    clear_weather_cache()
    calls = []

    def fake(method, url, **kwargs):
        calls.append((method, url))
        assert "open-meteo.com" in url
        assert method == "GET"
        return {"current": {"temperature_2m": 11.4, "weather_code": 3}}

    reload_settings.setattr("organiser.services.weather.request_json", fake)
    with caplog.at_level(logging.DEBUG):
        brief = client.get("/brief/morning")
    assert brief.status_code == 200
    weather = next(section for section in brief.json()["sections"] if section["key"] == "weather")
    assert weather["summary"] == "11°C, cloudy."
    assert "Open-Meteo" in weather["footnote"]
    blob = brief.text + caplog.text
    for secret in (LAT, LON, POSTCODE):
        assert secret not in blob
    assert calls and all("open-meteo.com" in url for _, url in calls)
    assert "postcodes.io" not in "".join(url for _, url in calls)


def test_weather_postcode_is_resolved_and_not_logged(client, reload_settings, caplog):
    reload_settings.setenv("HOUSE_LAT", "")
    reload_settings.setenv("HOUSE_LON", "")
    reload_settings.setenv("HOUSE_POSTCODE", POSTCODE)
    get_settings.cache_clear()
    clear_weather_cache()

    def fake(method, url, **kwargs):
        if "postcodes.io" in url:
            assert POSTCODE in url
            return {"result": {"latitude": 10.5, "longitude": 20.5}}
        return {"current": {"temperature_2m": 8, "weather_code": 61}}

    reload_settings.setattr("organiser.services.weather.request_json", fake)
    with caplog.at_level(logging.DEBUG):
        brief = client.get("/brief/morning")
    weather = next(section for section in brief.json()["sections"] if section["key"] == "weather")
    assert weather["summary"] == "8°C, light rain."
    assert POSTCODE not in brief.text + caplog.text


def test_weather_failure_stays_on_its_section(client, reload_settings, caplog):
    reload_settings.setenv("HOUSE_LAT", LAT)
    reload_settings.setenv("HOUSE_LON", LON)
    get_settings.cache_clear()
    clear_weather_cache()

    def fake(method, url, **kwargs):
        raise RuntimeError(f"down {url}")

    reload_settings.setattr("organiser.services.weather.request_json", fake)
    with caplog.at_level(logging.DEBUG):
        brief = client.get("/brief/morning")
    assert brief.status_code == 200
    tasks = brief.json()["sections"][0]
    assert tasks["key"] == "tasks"
    weather = next(section for section in brief.json()["sections"] if section["key"] == "weather")
    assert weather["summary"].startswith("Weather unavailable (as of ")
    assert LAT not in brief.text + caplog.text
    assert LON not in caplog.text


def _diary_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", CLIENT)
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", SECRET)
    monkeypatch.setenv("GOOGLE_OAUTH_REFRESH_TOKEN", REFRESH)
    monkeypatch.setenv("GOOGLE_CALENDAR_IDS", "")
    get_settings.cache_clear()
    clear_diary_cache()


def test_diary_is_read_only_deduped_and_hides_outside_home(client, reload_settings, caplog):
    _diary_env(reload_settings)
    calls = []

    def fake(method, url, **kwargs):
        calls.append((method, url, kwargs.get("data"), kwargs.get("params")))
        if url.endswith("/token"):
            assert kwargs["data"]["grant_type"] == "refresh_token"
            assert "scope" not in kwargs["data"]
            return {"access_token": TOKEN, "expires_in": 3600}
        if url.endswith("/events"):
            assert method == "GET"
            return {
                "items": [
                    {
                        "id": "event-1",
                        "summary": "Put the bins out",
                        "status": "confirmed",
                        "start": {"dateTime": "2026-11-06T09:30:00Z"},
                    },
                    {
                        "id": "event-1",
                        "summary": "Put the bins out",
                        "start": {"dateTime": "2026-11-06T09:30:00Z"},
                    },
                    {
                        "id": "event-2",
                        "summary": "Hilton breakfast",
                        "start": {"dateTime": "2026-11-06T08:00:00Z"},
                    },
                    {
                        "id": "event-3",
                        "summary": "Boiler service",
                        "start": {"date": "2026-11-06"},
                    },
                ]
            }
        raise AssertionError(method + " " + url)

    reload_settings.setattr("organiser.services.diary.request_json", fake)
    with caplog.at_level(logging.DEBUG):
        brief = client.get("/brief/morning")
    appointments = next(section for section in brief.json()["sections"] if section["key"] == "appointments")
    titles = [item["title"] for item in appointments["items"]]
    assert titles.count("Put the bins out") == 1
    assert "Boiler service" in titles
    assert all("Hilton" not in title for title in titles)
    assert appointments["footnote"] == "Read only. This is not a calendar."
    blob = brief.text + caplog.text
    for secret in (CLIENT, SECRET, REFRESH, CALENDAR_ID, TOKEN, "Hilton"):
        assert secret not in blob
    assert all(method in {"GET", "POST"} for method, *_ in calls)
    assert any(url.endswith("/token") for _, url, *_ in calls)
    assert any(url.endswith("/events") for _, url, *_ in calls)
    assert not any("insert" in url or "import" in url or method == "PATCH" or method == "DELETE" for method, url, *_ in calls)

    listed = client.get("/system/calendars")
    assert listed.status_code == 200
    assert listed.json()["configured"] is True
    assert listed.json()["using_primary"] is True
    assert CALENDAR_ID not in listed.text


def test_settings_can_add_and_remove_a_calendar_by_name(client, reload_settings):
    _diary_env(reload_settings)

    def fake(method, url, **kwargs):
        if url.endswith("/token"):
            return {"access_token": TOKEN, "expires_in": 3600}
        if "calendarList" in url:
            assert method == "GET"
            return {
                "items": [
                    {"id": CALENDAR_ID, "summary": "Home", "primary": True},
                    {"id": OTHER_ID, "summary": "Family", "primary": False},
                ]
            }
        if url.endswith("/events"):
            return {"items": []}
        raise AssertionError(url)

    reload_settings.setattr("organiser.services.diary.request_json", fake)
    missing = client.post("/system/calendars", json={"name": "Work rota"})
    assert missing.status_code == 404
    outside = client.post("/system/calendars", json={"name": "Guest list"})
    assert outside.status_code == 422
    added = client.post("/system/calendars", json={"name": "Family"})
    assert added.status_code == 200
    body = added.json()
    names = [item["name"] for item in body["items"]]
    assert "Family" in names
    assert "Home" in names
    assert CALENDAR_ID not in added.text
    assert OTHER_ID not in added.text
    family = next(item for item in body["items"] if item["name"] == "Family")
    removed = client.delete(f"/system/calendars/{family['id']}")
    assert removed.status_code == 200
    assert "Family" not in [item["name"] for item in removed.json()["items"]]


def test_diary_failure_leaves_the_rest_of_the_brief(client, reload_settings, caplog):
    _diary_env(reload_settings)

    def fake(method, url, **kwargs):
        raise RuntimeError("token down")

    reload_settings.setattr("organiser.services.diary.request_json", fake)
    with caplog.at_level(logging.DEBUG):
        brief = client.get("/brief/morning")
    assert brief.status_code == 200
    appointments = next(section for section in brief.json()["sections"] if section["key"] == "appointments")
    assert appointments["summary"] == "Diary not connected — reconnect in Settings."
    assert brief.json()["sections"][0]["key"] == "tasks"
    assert TOKEN not in caplog.text


def test_diary_client_names_only_readonly_scopes():
    source = (Path(__file__).resolve().parents[1] / "organiser" / "services" / "diary.py").read_text()
    assert "https://www.googleapis.com/auth/calendar.events.readonly" in source
    assert "https://www.googleapis.com/auth/calendar.calendarlist.readonly" in source
    assert "events.insert" not in source
    assert "calendars.insert" not in source
    assert "/auth/calendar\"" not in source
