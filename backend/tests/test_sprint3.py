"""Sprint 3: catch-up wording, past dates, the commute, shopping from the box, limits."""

import logging
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from agent_fakes import call, london, say
from organiser.agent.mistral import MistralUnavailable
from organiser.agent.wording import write_notes
from organiser.config import get_settings
from organiser.models import CommuteShift, ShoppingItem
from organiser.routes.catchup import get_note_client
from organiser.services.commute import ShiftRejected, tfl_clock, to_london

TOKEN = "banto-token-placeholder"
TFL = "tfl-key-placeholder"
LAT = "51.54321"
LON = "-0.27654"
POSTCODE = "POSTCODE-PLACEHOLDER"
UTC = timezone.utc


class NoteFake:
    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.messages = []

    def complete(self, *, model, messages, max_tokens=80):
        self.messages.append(messages)
        if self.error is not None:
            raise self.error
        return self.text

    def close(self):
        pass


def _look(client):
    response = client.post("/catch-up/look")
    assert response.status_code == 200, response.text
    return response.json()


def _at(house_clock, year, month, day, hour, minute=0):
    house_clock["now"] = london(year, month, day, hour, minute)


def _task(client, **fields):
    payload = {"title": "Put the bins out", "priority": "medium", "status": "todo"}
    payload.update(fields)
    response = client.post("/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _shift(client, **fields):
    payload = {
        "start": "2026-11-06T08:00:00+00:00",
        "end": "2026-11-06T16:00:00+00:00",
        "location_label": "Wembley",
    }
    payload.update(fields)
    return client.post("/commute/shift", json=payload, headers={"Authorization": f"Bearer {TOKEN}"})


def _use(monkeypatch, **env):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()


# --- catch-up wording -------------------------------------------------------


def test_catch_up_uses_mistral_wording_when_it_answers(client, db, house_clock, assistant_on, monkeypatch):
    from organiser.main import app

    _use(monkeypatch, HOUSE_POSTCODE=POSTCODE)
    fake = NoteFake("Bins are due today.")
    app.dependency_overrides[get_note_client] = lambda: fake
    try:
        _task(client, due_on="2026-11-02")
        _at(house_clock, 2026, 11, 2, 8, 0)
        _look(client)
        _at(house_clock, 2026, 11, 2, 16, 0)
        card = _look(client)["items"][0]
    finally:
        app.dependency_overrides.pop(get_note_client, None)
    assert card["fallback_used"] is False
    assert card["summary"] == "Note on Put the bins out: “Bins are due today.”"
    assert fake.messages
    prompt = fake.messages[0][0]["content"]
    assert "Put the bins out" in prompt
    assert POSTCODE not in prompt
    get_settings.cache_clear()
    before = len(fake.messages)
    assert client.get("/catch-up").status_code == 200
    assert len(fake.messages) == before
    assert db.scalar(select(func.count()).select_from(ShoppingItem)) == 0


def test_catch_up_falls_back_when_mistral_is_down(client, house_clock, assistant_on):
    from organiser.main import app

    fake = NoteFake(error=MistralUnavailable("Mistral could not be reached."))
    app.dependency_overrides[get_note_client] = lambda: fake
    try:
        _task(client, due_on="2026-11-02")
        _at(house_clock, 2026, 11, 2, 8, 0)
        _look(client)
        _at(house_clock, 2026, 11, 2, 16, 0)
        card = _look(client)["items"][0]
        state = client.get("/agent").json()
    finally:
        app.dependency_overrides.pop(get_note_client, None)
    assert card["fallback_used"] is True
    assert card["summary"] == "Note on Put the bins out: “Due today.”"
    assert state["reachable"] is False
    assert state["enabled"] is True


def test_quiet_hours_do_not_ask_mistral_for_wording(client, house_clock, assistant_on):
    from organiser.main import app

    fake = NoteFake(error=AssertionError("Mistral was asked during quiet hours."))
    app.dependency_overrides[get_note_client] = lambda: fake
    try:
        _task(client, due_on="2026-11-03")
        _at(house_clock, 2026, 11, 2, 14, 0)
        _look(client)
        _at(house_clock, 2026, 11, 2, 22, 0)
        body = _look(client)
    finally:
        app.dependency_overrides.pop(get_note_client, None)
    assert body["quiet"] is True
    assert body["items"] == []
    assert fake.messages == []


def test_a_bad_wording_reply_uses_the_template(client, house_clock, assistant_on):
    from organiser.main import app

    fake = NoteFake("Hello there\nextra line")
    app.dependency_overrides[get_note_client] = lambda: fake
    try:
        _task(client, due_on="2026-11-02")
        _at(house_clock, 2026, 11, 2, 8, 0)
        _look(client)
        _at(house_clock, 2026, 11, 2, 16, 0)
        card = _look(client)["items"][0]
    finally:
        app.dependency_overrides.pop(get_note_client, None)
    assert card["fallback_used"] is True
    assert "Due today." in card["summary"]


def test_write_notes_without_a_client_is_the_template():
    class _Draft:
        def __init__(self):
            self.title = "Bins"
            self.reason = "Due today"
            self.note = "Due today."

    assert write_notes(None, get_settings(), [_Draft()]) == [("Due today.", True)]


# --- past dates -------------------------------------------------------------


def test_a_past_date_stays_with_apply_and_not_now(client, house_clock):
    created = client.post(
        "/agent/proposals",
        json={"title": "Mend the stair rod", "due_on": "2026-11-01", "reason": "It was due."},
    )
    assert created.status_code == 201, created.text
    card = created.json()
    assert card["date_note"] == "This date has passed."
    assert card["status"] == "pending"

    _at(house_clock, 2026, 11, 4, 9, 0)
    waiting = client.get("/agent").json()["proposals"]
    assert [item["id"] for item in waiting] == [card["id"]]
    assert waiting[0]["status"] == "pending"
    assert waiting[0]["date_note"] == "This date has passed."

    applied = client.post(f"/agent/proposals/{card['id']}/apply")
    assert applied.status_code == 200, applied.text
    task = client.get("/tasks").json()["items"][0]
    assert task["title"] == "Mend the stair rod"
    assert task["due_on"] == "2026-11-01"


def test_not_now_still_dismisses_a_past_date(client, house_clock):
    card = client.post(
        "/agent/proposals",
        json={"title": "Oil the hinge", "due_on": "2026-10-30"},
    ).json()
    assert card["date_note"] == "This date has passed."
    dismissed = client.post(f"/agent/proposals/{card['id']}/dismiss")
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"
    assert client.get("/agent").json()["proposals"] == []
    assert client.get("/tasks").json()["items"] == []


def test_a_future_date_has_no_passed_note(client, house_clock):
    card = client.post(
        "/agent/proposals",
        json={"title": "Buy oat milk", "due_on": "2026-11-06"},
    ).json()
    assert card["date_note"] is None


def test_the_box_keeps_a_past_date_instead_of_refusing_it(client, house_clock, mistral):
    mistral(
        [
            call(
                "propose_change",
                {
                    "action": "create_task",
                    "changes": {"title": "Mend the stair rod", "due_on": "2026-11-01"},
                    "reason": "It was due.",
                },
            )
        ],
        [say("Added 1 proposal.")],
    )
    card = client.post("/agent/feed", json={"text": "the stair rod was due on Sunday"}).json()["proposals"][0]
    assert card["date_note"] == "This date has passed."
    assert card["status"] == "pending"


# --- shopping from the box --------------------------------------------------


def test_smart_add_can_propose_a_shopping_line(client, house_clock, mistral):
    mistral(
        [
            call(
                "propose_change",
                {"action": "create_shopping_item", "changes": {"name": "Oat milk"}, "reason": "For the week."},
            )
        ],
        [say("Added 1 proposal.")],
    )
    body = client.post("/agent/feed", json={"text": "buy oat milk"}).json()
    card = body["proposals"][0]
    assert card["summary"] == "Add to shopping: Oat milk"
    assert client.get("/shopping").json()["items"] == []
    applied = client.post(f"/agent/proposals/{card['id']}/apply")
    assert applied.status_code == 200, applied.text
    assert [item["name"] for item in client.get("/shopping").json()["items"]] == ["Oat milk"]


# --- rate limits ------------------------------------------------------------


def test_feed_burst_limit(client, house_clock, mistral, monkeypatch):
    monkeypatch.setenv("RATE_FEED_PER_MINUTE", "1")
    get_settings.cache_clear()
    fake = mistral([say("Nothing to add.")])
    assert client.post("/agent/feed", json={"text": "buy oat milk"}).status_code == 200
    limited = client.post("/agent/feed", json={"text": "buy oat milk again"})
    assert limited.status_code == 429
    assert limited.json()["detail"] == "Too many lines. Wait a moment. Nothing was sent."
    assert len(fake.calls) == 1
    get_settings.cache_clear()


def test_ingest_burst_limit(client, house_clock, monkeypatch):
    monkeypatch.setenv("RATE_INGEST_PER_MINUTE", "1")
    get_settings.cache_clear()
    assert client.post("/agent/proposals", json={"title": "Buy oat milk"}).status_code == 201
    limited = client.post("/agent/proposals", json={"title": "Buy bread"})
    assert limited.status_code == 429
    assert limited.json()["detail"] == "Too many proposals. Wait a moment."
    assert len(client.get("/agent").json()["proposals"]) == 1
    get_settings.cache_clear()


# --- commute ----------------------------------------------------------------


def test_london_wall_clock_across_the_clock_changes():
    assert tfl_clock(datetime(2026, 3, 29, 7, 0, tzinfo=UTC)) == ("20260329", "0800")
    assert tfl_clock(datetime(2026, 3, 29, 8, 0, tzinfo=london(2026, 3, 29, 8).tzinfo)) == ("20260329", "0800")
    assert tfl_clock(datetime(2026, 10, 25, 8, 0, tzinfo=UTC)) == ("20261025", "0800")
    assert tfl_clock(datetime.fromisoformat("2026-10-25T01:30:00+01:00")) == ("20261025", "0130")
    assert tfl_clock(datetime.fromisoformat("2026-10-25T01:30:00+00:00")) == ("20261025", "0130")
    assert (
        datetime.fromisoformat("2026-10-25T01:30:00+01:00").astimezone(UTC)
        != datetime.fromisoformat("2026-10-25T01:30:00+00:00").astimezone(UTC)
    )
    with pytest.raises(ShiftRejected, match="does not exist"):
        to_london(datetime(2026, 3, 29, 1, 30))
    with pytest.raises(ShiftRejected, match="happens twice"):
        to_london(datetime(2026, 10, 25, 1, 30))
    assert to_london(datetime(2026, 11, 6, 8, 0)).tzinfo is not None


def test_shift_push_stores_only_the_three_fields(client, db, monkeypatch, caplog):
    _use(monkeypatch, BANTO_COMMUTE_TOKEN=TOKEN, TFL_APP_KEY="", HOUSE_LAT="", HOUSE_LON="", HOUSE_POSTCODE="")
    missing = client.post(
        "/commute/shift",
        json={"start": "2026-11-06T08:00:00+00:00", "end": "2026-11-06T16:00:00+00:00", "location_label": "Wembley"},
    )
    assert missing.status_code == 401
    refused = client.post(
        "/commute/shift",
        json={"start": "2026-11-06T08:00:00+00:00", "end": "2026-11-06T16:00:00+00:00", "location_label": "Wembley"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert refused.status_code == 401
    assert TOKEN not in refused.text

    with caplog.at_level(logging.DEBUG):
        created = _shift(client)
    assert created.status_code == 201, created.text
    body = created.json()
    assert set(body) == {"id", "start", "end", "location_label"}
    assert body["location_label"] == "Wembley"
    again = _shift(client)
    assert again.status_code == 201
    assert again.json()["id"] == body["id"]
    assert db.scalar(select(func.count()).select_from(CommuteShift)) == 1
    assert {column.name for column in CommuteShift.__table__.columns} == {
        "id",
        "start_at",
        "end_at",
        "location_label",
    }
    activity = client.get("/agent/activity").json()["items"][0]
    assert activity["text"] == "Commute: Wembley 08:00–16:00"
    assert TOKEN not in caplog.text
    assert "Hilton" not in caplog.text
    get_settings.cache_clear()


def test_shift_push_refuses_anything_beyond_the_three_fields(client, db, monkeypatch):
    _use(monkeypatch, BANTO_COMMUTE_TOKEN=TOKEN)
    extra = _shift(client, guest="Ada")
    assert extra.status_code == 422
    hotel = _shift(client, location_label="Hilton")
    assert hotel.status_code == 422
    assert "house commute" in hotel.json()["detail"]
    park = _shift(client, location_label="Wembley Park")
    assert park.status_code == 422
    gap = _shift(client, start="2026-03-29T01:30:00", end="2026-03-29T09:00:00")
    assert gap.status_code == 422
    assert "does not exist" in gap.json()["detail"]
    ambiguous = _shift(client, start="2026-10-25T01:30:00", end="2026-10-25T09:00:00")
    assert ambiguous.status_code == 422
    assert "happens twice" in ambiguous.json()["detail"]
    assert db.scalar(select(func.count()).select_from(CommuteShift)) == 0
    get_settings.cache_clear()


def test_shift_push_without_a_token_stores_nothing(client, db, monkeypatch):
    _use(monkeypatch, BANTO_COMMUTE_TOKEN="")
    response = client.post(
        "/commute/shift",
        json={"start": "2026-11-06T08:00:00+00:00", "end": "2026-11-06T16:00:00+00:00", "location_label": "Wembley"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 503
    assert db.scalar(select(func.count()).select_from(CommuteShift)) == 0
    brief = client.get("/brief/morning").json()
    commute = next(section for section in brief["sections"] if section["key"] == "commute")
    assert commute["summary"] == "Commute is not connected."
    get_settings.cache_clear()


def test_the_two_october_half_hours_are_different_instants(client, db, monkeypatch):
    _use(monkeypatch, BANTO_COMMUTE_TOKEN=TOKEN)
    first = _shift(client, start="2026-10-25T01:30:00+01:00", end="2026-10-25T09:00:00+00:00")
    second = _shift(client, start="2026-10-25T01:30:00+00:00", end="2026-10-25T09:00:00+00:00")
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    starts = {row.start_at for row in db.scalars(select(CommuteShift))}
    assert len(starts) == 2
    assert {item.astimezone(UTC) for item in starts} == {
        datetime(2026, 10, 25, 0, 30, tzinfo=UTC),
        datetime(2026, 10, 25, 1, 30, tzinfo=UTC),
    }
    get_settings.cache_clear()


def test_commute_burst_limit(client, monkeypatch):
    _use(monkeypatch, BANTO_COMMUTE_TOKEN=TOKEN, RATE_COMMUTE_PER_HOUR="2")
    assert _shift(client, start="2026-11-06T08:00:00+00:00", end="2026-11-06T12:00:00+00:00").status_code == 201
    assert _shift(client, start="2026-11-06T13:00:00+00:00", end="2026-11-06T17:00:00+00:00").status_code == 201
    limited = _shift(client, start="2026-11-06T18:00:00+00:00", end="2026-11-06T20:00:00+00:00")
    assert limited.status_code == 429
    assert limited.json()["detail"] == "Too many shift updates. Nothing was stored."
    get_settings.cache_clear()


def _journey_body():
    return {
        "journeys": [
            {
                "duration": 34,
                "startDateTime": "2026-11-06T07:22:00",
                "legs": [
                    {"mode": {"id": "walking"}, "routeOptions": []},
                    {"mode": {"id": "tube"}, "routeOptions": [{"name": "Jubilee"}]},
                ],
            }
        ]
    }


def _status_body():
    return [
        {"name": "Jubilee", "lineStatuses": [{"statusSeverityDescription": "Minor Delays"}]},
        {"name": "Central", "lineStatuses": [{"statusSeverityDescription": "Severe Delays"}]},
    ]


def test_brief_reads_tfl_without_logging_the_origin_or_the_key(client, monkeypatch, caplog):
    _use(
        monkeypatch,
        BANTO_COMMUTE_TOKEN=TOKEN,
        TFL_APP_KEY=TFL,
        HOUSE_LAT=LAT,
        HOUSE_LON=LON,
        HOUSE_POSTCODE=POSTCODE,
    )
    monkeypatch.setattr("organiser.routes.brief.house_today", lambda tz: __import__("datetime").date(2026, 11, 6))
    calls = []

    def fake(method, url, **kwargs):
        calls.append((url, kwargs.get("params")))
        if "JourneyResults" in url:
            assert kwargs["params"]["date"] == "20261106"
            assert kwargs["params"]["time"] == "0800"
            assert kwargs["params"]["timeIs"] == "Arriving"
            assert kwargs["params"]["app_key"] == TFL
            assert "postcodes.io" not in url
            return _journey_body()
        if url.endswith("/Status"):
            return _status_body()
        raise AssertionError(url)

    monkeypatch.setattr("organiser.services.commute.request_json_any", fake)
    monkeypatch.setattr(
        "organiser.services.weather.request_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("postcode lookup")),
    )
    assert _shift(client).status_code == 201
    with caplog.at_level(logging.DEBUG):
        brief = client.get("/brief/morning")
    assert brief.status_code == 200
    commute = next(section for section in brief.json()["sections"] if section["key"] == "commute")
    assert "leave 07:22" in commute["summary"]
    assert "34 min" in commute["summary"]
    assert "Jubilee" in commute["summary"]
    assert "Minor Delays" in commute["summary"]
    assert "Central" not in commute["summary"]
    blob = brief.text + caplog.text
    for secret in (TOKEN, TFL, LAT, LON, POSTCODE):
        assert secret not in blob
    assert calls and "940GZZLUWYP" in calls[0][0]
    get_settings.cache_clear()


def test_brief_uses_a_postcode_without_storing_or_logging_it(client, monkeypatch, caplog):
    _use(
        monkeypatch,
        BANTO_COMMUTE_TOKEN=TOKEN,
        TFL_APP_KEY=TFL,
        HOUSE_LAT="",
        HOUSE_LON="",
        HOUSE_POSTCODE=POSTCODE,
    )
    monkeypatch.setattr("organiser.routes.brief.house_today", lambda tz: __import__("datetime").date(2026, 11, 6))

    def resolve(method, url, **kwargs):
        if "postcodes.io" in url:
            assert POSTCODE in url
            return {"result": {"latitude": 51.5, "longitude": -0.27}}
        if "open-meteo.com" in url:
            return {"current": {"temperature_2m": 8, "weather_code": 0}}
        raise AssertionError(url)

    def tfl(method, url, **kwargs):
        if "JourneyResults" in url:
            assert "51.50000" in url
            return _journey_body()
        return [{"name": "Jubilee", "lineStatuses": [{"statusSeverityDescription": "Good Service"}]}]

    monkeypatch.setattr("organiser.services.weather.request_json", resolve)
    monkeypatch.setattr("organiser.services.commute.request_json_any", tfl)
    assert _shift(client).status_code == 201
    with caplog.at_level(logging.DEBUG):
        brief = client.get("/brief/morning")
    commute = next(section for section in brief.json()["sections"] if section["key"] == "commute")
    assert "No line disruptions." in commute["summary"]
    assert POSTCODE not in brief.text + caplog.text
    assert TFL not in brief.text + caplog.text
    get_settings.cache_clear()


def test_tfl_spring_and_autumn_query_times(client, monkeypatch):
    _use(
        monkeypatch,
        BANTO_COMMUTE_TOKEN=TOKEN,
        TFL_APP_KEY=TFL,
        HOUSE_LAT=LAT,
        HOUSE_LON=LON,
        HOUSE_POSTCODE="",
    )
    seen = []

    def fake(method, url, **kwargs):
        if "JourneyResults" in url:
            seen.append((kwargs["params"]["date"], kwargs["params"]["time"]))
            return _journey_body()
        return _status_body()

    monkeypatch.setattr("organiser.services.commute.request_json_any", fake)
    assert _shift(client, start="2026-03-29T08:00:00+01:00", end="2026-03-29T16:00:00+01:00").status_code == 201
    monkeypatch.setattr("organiser.routes.brief.house_today", lambda tz: __import__("datetime").date(2026, 3, 29))
    assert client.get("/brief/morning").status_code == 200
    assert _shift(client, start="2026-10-25T08:00:00+00:00", end="2026-10-25T16:00:00+00:00").status_code == 201
    monkeypatch.setattr("organiser.routes.brief.house_today", lambda tz: __import__("datetime").date(2026, 10, 25))
    from organiser.services.commute import clear_cache

    clear_cache()
    assert client.get("/brief/morning").status_code == 200
    assert ("20260329", "0800") in seen
    assert ("20261025", "0800") in seen
    get_settings.cache_clear()


def test_journey_degrades_when_the_key_or_the_call_fails(client, monkeypatch, caplog):
    _use(monkeypatch, BANTO_COMMUTE_TOKEN=TOKEN, TFL_APP_KEY="", HOUSE_LAT=LAT, HOUSE_LON=LON)
    monkeypatch.setattr("organiser.routes.brief.house_today", lambda tz: __import__("datetime").date(2026, 11, 6))
    assert _shift(client).status_code == 201
    unkeyed = next(
        section for section in client.get("/brief/morning").json()["sections"] if section["key"] == "commute"
    )
    assert "Journey check is not connected." in unkeyed["summary"]
    assert "08:00–16:00" in unkeyed["summary"]

    _use(monkeypatch, BANTO_COMMUTE_TOKEN=TOKEN, TFL_APP_KEY=TFL, HOUSE_LAT="", HOUSE_LON="", HOUSE_POSTCODE="")
    unset = next(section for section in client.get("/brief/morning").json()["sections"] if section["key"] == "commute")
    assert "Home location is not set." in unset["summary"]

    _use(monkeypatch, BANTO_COMMUTE_TOKEN=TOKEN, TFL_APP_KEY=TFL, HOUSE_LAT=LAT, HOUSE_LON=LON)

    called = {"n": 0}

    def boom(method, url, **kwargs):
        called["n"] += 1
        raise RuntimeError(f"down {url} {LAT}")

    monkeypatch.setattr("organiser.services.commute.request_json_any", boom)
    with caplog.at_level(logging.DEBUG):
        failed = client.get("/brief/morning")
    line = next(section for section in failed.json()["sections"] if section["key"] == "commute")
    assert called["n"] >= 1
    assert "Journey check is unavailable." in line["summary"]
    assert LAT not in failed.text + caplog.text
    assert TFL not in caplog.text
    get_settings.cache_clear()


def test_no_shift_today_says_so_when_the_push_is_configured(client, monkeypatch):
    _use(monkeypatch, BANTO_COMMUTE_TOKEN=TOKEN)
    monkeypatch.setattr("organiser.routes.brief.house_today", lambda tz: __import__("datetime").date(2026, 11, 6))
    commute = next(section for section in client.get("/brief/morning").json()["sections"] if section["key"] == "commute")
    assert commute["summary"] == "No commute on the rota today."
    get_settings.cache_clear()
