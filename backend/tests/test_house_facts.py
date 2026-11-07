"""Settings facts. The body names what is set. It never contains the value."""

import logging

import pytest

from organiser.config import get_settings

LOCATION = "HOUSE-LOCATION-PLACEHOLDER"
OTHER_LOCATION = "HOUSE-OTHER-PLACEHOLDER"
POSTCODE = "POSTCODE-PLACEHOLDER"
CLIENT_ID = "oauth-client-placeholder"
CLIENT_SECRET = "oauth-secret-placeholder"
REFRESH = "oauth-refresh-placeholder"
CALENDARS = "primary,house-calendar"
TFL = "tfl-key-placeholder"
BANTO = "banto-token-placeholder"

SECRET_TEXT = (LOCATION, OTHER_LOCATION, POSTCODE, CLIENT_ID, CLIENT_SECRET, REFRESH, CALENDARS, TFL, BANTO)

FACT_KEYS = {
    "timezone",
    "assistant",
    "assistant_switch",
    "runs_left_today",
    "diary",
    "weather_location",
    "tfl",
    "banto",
    "voice_input",
    "disruption_checks",
    "local_reminders",
}


@pytest.fixture
def reload_settings(monkeypatch):
    yield monkeypatch
    get_settings.cache_clear()


def _clear():
    get_settings.cache_clear()


def test_house_facts_when_nothing_is_configured(client, reload_settings):
    for name in (
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GOOGLE_OAUTH_REFRESH_TOKEN",
        "GOOGLE_CALENDAR_IDS",
        "HOUSE_LAT",
        "HOUSE_LON",
        "HOUSE_POSTCODE",
        "TFL_APP_KEY",
        "BANTO_COMMUTE_TOKEN",
        "MISTRAL_API_KEY",
        "MISTRAL_AGENT_ID",
    ):
        reload_settings.setenv(name, "")
    _clear()

    response = client.get("/system/facts")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == FACT_KEYS
    assert body["timezone"] == "Europe/London"
    assert body["assistant"] == "off"
    assert body["assistant_switch"] == "on"
    assert body["runs_left_today"] == 12
    assert body["diary"] == "not configured"
    assert body["weather_location"] == "not configured"
    assert body["tfl"] == "not configured"
    assert body["banto"] == "not configured"
    assert body["voice_input"] == "off"
    assert body["disruption_checks"] == "not active"
    assert body["local_reminders"] == "off"


def test_house_facts_do_not_echo_or_log_secrets(client, reload_settings, caplog):
    reload_settings.setenv("HOUSE_LAT", LOCATION)
    reload_settings.setenv("HOUSE_LON", OTHER_LOCATION)
    reload_settings.setenv("HOUSE_POSTCODE", POSTCODE)
    reload_settings.setenv("GOOGLE_OAUTH_CLIENT_ID", CLIENT_ID)
    reload_settings.setenv("GOOGLE_OAUTH_CLIENT_SECRET", CLIENT_SECRET)
    reload_settings.setenv("GOOGLE_OAUTH_REFRESH_TOKEN", REFRESH)
    reload_settings.setenv("GOOGLE_CALENDAR_IDS", CALENDARS)
    reload_settings.setenv("TFL_APP_KEY", TFL)
    reload_settings.setenv("BANTO_COMMUTE_TOKEN", BANTO)
    reload_settings.setenv("MISTRAL_API_KEY", "")
    reload_settings.setenv("MISTRAL_AGENT_ID", "")
    _clear()

    with caplog.at_level(logging.DEBUG):
        response = client.get("/system/facts")

    assert response.status_code == 200
    body = response.json()
    assert body["diary"] == "configured"
    assert body["weather_location"] == "configured"
    assert body["tfl"] == "configured"
    assert body["banto"] == "configured"
    assert body["assistant"] == "off"
    blob = response.text + caplog.text + repr(get_settings())
    for secret in SECRET_TEXT:
        assert secret not in blob
    assert "primary" not in response.text


def test_partial_location_and_diary_stay_unconfigured(client, reload_settings):
    reload_settings.setenv("HOUSE_LAT", LOCATION)
    reload_settings.setenv("HOUSE_LON", "")
    reload_settings.setenv("HOUSE_POSTCODE", "")
    reload_settings.setenv("GOOGLE_OAUTH_CLIENT_ID", CLIENT_ID)
    reload_settings.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    reload_settings.setenv("GOOGLE_OAUTH_REFRESH_TOKEN", "")
    reload_settings.setenv("GOOGLE_CALENDAR_IDS", "primary")
    _clear()

    body = client.get("/system/facts").json()
    assert body["weather_location"] == "not configured"
    assert body["diary"] == "not configured"
    assert LOCATION not in client.get("/system/facts").text
