"""Presence-bar greeting: London time of day, and arrival for one hour."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from organiser.services.greeting import greeting_state

LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

# (hour, minute, headline) on a Europe/London clock, with no arrival.
BUCKETS = [
    (0, 0, "Good night"),
    (4, 59, "Good night"),
    (5, 0, "Good morning"),
    (11, 59, "Good morning"),
    (12, 0, "Good afternoon"),
    (16, 59, "Good afternoon"),
    (17, 0, "Good evening"),
    (21, 59, "Good evening"),
    (22, 0, "Good night"),
    (23, 30, "Good night"),
]


def _london(hour: int, minute: int, *, year: int = 2026, month: int = 11, day: int = 1) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=LONDON)


@pytest.mark.parametrize(("hour", "minute", "expected"), BUCKETS)
def test_time_of_day_buckets(hour, minute, expected):
    state = greeting_state(_london(hour, minute), None, "Europe/London")
    assert state["greeting"] == expected
    assert state["greeting_reason"] == "time_of_day"
    assert state["arrived_at"] is None
    assert state["debounce_until"] is None
    assert state["greeting"] != "Welcome home"


def test_buckets_use_london_civil_time_during_british_summer_time():
    # 04:00 UTC on 15 July 2026 is 05:00 in London. The UTC hour is still night.
    morning = greeting_state(datetime(2026, 7, 15, 4, 0, tzinfo=UTC), None, "Europe/London")
    assert morning["greeting"] == "Good morning"
    assert morning["house_date"].isoformat() == "2026-07-15"

    # 03:59 UTC is 04:59 BST, still the quiet hour.
    quiet = greeting_state(datetime(2026, 7, 15, 3, 59, tzinfo=UTC), None, "Europe/London")
    assert quiet["greeting"] == "Good night"
    assert quiet["greeting_reason"] == "time_of_day"


def test_arrival_overrides_time_of_day_until_the_hour_ends():
    arrived = _london(11, 30)
    opened = greeting_state(arrived, arrived, "Europe/London")
    assert opened["greeting"] == "Welcome home"
    assert opened["greeting_reason"] == "arrival"
    assert opened["debounce_until"] == arrived + timedelta(hours=1)

    # Afternoon has started, and the arrival hour is still open.
    during = greeting_state(_london(12, 29), arrived, "Europe/London")
    assert during["greeting"] == "Welcome home"
    assert during["greeting_reason"] == "arrival"
    assert during["arrived_at"] == arrived

    ended = greeting_state(_london(12, 30), arrived, "Europe/London")
    assert ended["greeting"] == "Good afternoon"
    assert ended["greeting_reason"] == "time_of_day"
    assert ended["arrived_at"] == arrived
    assert ended["debounce_until"] == arrived + timedelta(hours=1)


def test_arrival_overrides_good_night():
    arrived = _london(22, 30)
    during = greeting_state(_london(23, 29), arrived, "Europe/London")
    assert during["greeting"] == "Welcome home"
    assert during["greeting_reason"] == "arrival"

    ended = greeting_state(_london(23, 30), arrived, "Europe/London")
    assert ended["greeting"] == "Good night"
    assert ended["greeting_reason"] == "time_of_day"


def test_an_arrival_in_the_future_does_not_count():
    now = _london(9, 0)
    state = greeting_state(now, _london(12, 0), "Europe/London")
    assert state["greeting"] == "Good morning"
    assert state["greeting_reason"] == "time_of_day"


@pytest.fixture
def clock(monkeypatch):
    state = {"now": _london(9, 0)}

    def current_time() -> datetime:
        return state["now"]

    monkeypatch.setattr("organiser.routes.system.current_time", current_time)
    return state


def _titles(client) -> list[str]:
    return [item["title"] for item in client.get("/events?kind=system").json()["items"]]


def test_api_time_of_day_buckets(client, clock):
    for hour, minute, expected in BUCKETS:
        clock["now"] = _london(hour, minute)
        body = client.get("/system").json()
        assert body["greeting"] == expected
        assert body["greeting_reason"] == "time_of_day"
        assert body["arrived_at"] is None
        assert body["debounce_until"] is None
        assert body["house_date"] == "2026-11-01"

    # Same rule in summer: the API converts to Europe/London before choosing.
    clock["now"] = datetime(2026, 7, 15, 4, 0, tzinfo=UTC)
    summer = client.get("/system").json()
    assert summer["greeting"] == "Good morning"
    assert summer["house_date"] == "2026-07-15"

    clock["now"] = datetime(2026, 7, 15, 3, 59, tzinfo=UTC)
    assert client.get("/system").json()["greeting"] == "Good night"


def test_api_arrival_precedence_and_debounce(client, clock):
    clock["now"] = _london(11, 30)
    opened = client.post("/system/arrive")
    assert opened.status_code == 200
    body = opened.json()
    assert body["greeting"] == "Welcome home"
    assert body["greeting_reason"] == "arrival"
    assert body["status_text"] == "All quiet"
    arrived = datetime.fromisoformat(body["arrived_at"])
    until = datetime.fromisoformat(body["debounce_until"])
    assert arrived == _london(11, 30)
    assert until == _london(12, 30)

    # A repeat inside the hour does not move the window or write a second line.
    # Afternoon would otherwise have replaced the morning line.
    clock["now"] = _london(12, 15)
    repeat = client.post("/system/arrive").json()
    assert repeat["greeting"] == "Welcome home"
    assert repeat["greeting_reason"] == "arrival"
    assert datetime.fromisoformat(repeat["arrived_at"]) == arrived
    assert datetime.fromisoformat(repeat["debounce_until"]) == until
    assert datetime.fromisoformat(repeat["updated_at"]) == datetime.fromisoformat(body["updated_at"])
    assert _titles(client).count("Arrived home") == 1

    clock["now"] = _london(12, 30)
    closed = client.get("/system").json()
    assert closed["greeting"] == "Good afternoon"
    assert closed["greeting_reason"] == "time_of_day"
    assert datetime.fromisoformat(closed["arrived_at"]) == arrived

    fresh = client.post("/system/arrive").json()
    assert fresh["greeting"] == "Welcome home"
    assert datetime.fromisoformat(fresh["arrived_at"]) == _london(12, 30)
    assert _titles(client).count("Arrived home") == 2


def test_api_quiet_hours_arrival_then_back_to_good_night(client, clock):
    clock["now"] = _london(23, 10)
    assert client.get("/system").json()["greeting"] == "Good night"

    arrived = client.post("/system/arrive").json()
    assert arrived["greeting"] == "Welcome home"
    assert arrived["greeting_reason"] == "arrival"

    clock["now"] = _london(23, 40)
    assert client.get("/system").json()["greeting"] == "Welcome home"

    clock["now"] = datetime(2026, 11, 2, 0, 10, tzinfo=LONDON)
    later = client.get("/system").json()
    assert later["greeting"] == "Good night"
    assert later["greeting_reason"] == "time_of_day"
    assert later["house_date"] == "2026-11-02"
    assert _titles(client).count("Arrived home") == 1


def test_pause_does_not_clear_an_open_arrival(client, clock):
    clock["now"] = _london(15, 0)
    client.post("/system/arrive")
    paused = client.post("/system/pause").json()
    assert paused["paused"] is True
    assert paused["status_text"] == "Paused"
    assert paused["greeting"] == "Welcome home"
    assert paused["greeting_reason"] == "arrival"


def test_arrival_leaves_the_morning_brief_unchanged(client, clock):
    clock["now"] = _london(8, 0)
    before = client.get("/brief/morning").json()
    client.post("/system/arrive")
    after = client.get("/brief/morning").json()
    assert after["title"] == before["title"] == "Morning brief"
    assert after["house_date"] == before["house_date"]
    assert after["sections"] == before["sections"]
    assert client.get("/system").json()["greeting"] == "Welcome home"
