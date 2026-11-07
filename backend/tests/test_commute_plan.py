"""Round trip planning. The provider is a fake. Nothing calls TfL, Mistral, or Google."""

import json
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from agent_fakes import london
from organiser.agent.mistral import MistralClient
from organiser.config import Settings, get_settings
from organiser.models import CommuteShift
from organiser.services.commute import clear_cache, move, tfl_clock
from organiser.services.commute_plan import (
    ADVISORY_FRESH_SECONDS,
    ADVISORY_STALE_SECONDS,
    classify,
    departure_deadline,
    destination_place,
    home_place,
    in_window,
    select_shift,
)

TOKEN = "banto-token-placeholder"
TFL = "tfl-key-placeholder"
LAT = "51.54321"
LON = "-0.27654"
POSTCODE = "POSTCODE-PLACEHOLDER"
UTC = timezone.utc
PRIVATE = (TOKEN, TFL, LAT, LON, POSTCODE, "940GZZLUWYP")


def _use(monkeypatch, **env):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()


def _freeze(monkeypatch, year, month, day, hour, minute=0):
    moment = london(year, month, day, hour, minute)
    monkeypatch.setattr("organiser.clock.current_time", lambda: moment)
    monkeypatch.setattr("organiser.routes.brief.house_today", lambda tz: moment.date())
    return moment


def _shift(client, **fields):
    payload = {
        "start": "2026-11-07T08:00:00+00:00",
        "end": "2026-11-07T16:00:00+00:00",
        "location_label": "Wembley",
    }
    payload.update(fields)
    return client.post("/commute/shift", json=payload, headers={"Authorization": f"Bearer {TOKEN}"})


def _journey(leave, minutes=34, line="Jubilee"):
    return {
        "journeys": [
            {
                "duration": minutes,
                "startDateTime": leave,
                "legs": [
                    {"mode": {"id": "walking"}, "routeOptions": []},
                    {"mode": {"id": "tube"}, "routeOptions": [{"name": line}]},
                ],
            }
        ]
    }


def _status():
    return [
        {"name": "Jubilee", "lineStatuses": [{"statusSeverityDescription": "Minor Delays"}]},
        {"name": "Central", "lineStatuses": [{"statusSeverityDescription": "Severe Delays"}]},
    ]


def _trap(monkeypatch, journeys=None, status=None, error=None):
    calls = []

    def fake(method, url, **kwargs):
        calls.append((method, url, kwargs.get("params"), kwargs.get("timeout")))
        if error is not None and "JourneyResults" in url:
            raise error
        if "JourneyResults" in url:
            params = kwargs["params"]
            if journeys is not None:
                return journeys(params)
            if params.get("timeIs") == "Departing":
                return _journey("2026-11-07T16:05:00", 36)
            return _journey("2026-11-07T07:22:00", 34)
        if url.endswith("/Status"):
            if isinstance(status, Exception):
                raise status
            return status if status is not None else _status()
        raise AssertionError(url)

    monkeypatch.setattr("organiser.services.commute.request_json_any", fake)
    monkeypatch.setattr("organiser.services.commute_plan.request_json_any", fake)
    monkeypatch.setattr(
        MistralClient,
        "_call",
        lambda self, *args, **kwargs: (_ for _ in ()).throw(AssertionError("mistral")),
    )
    monkeypatch.setattr(
        "organiser.services.weather.request_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("weather")),
    )
    return calls


def _row(start, end, ident="1"):
    return SimpleNamespace(id=ident, start_at=start, end_at=end, location_label="Wembley")


def _assert_private(text: str):
    for secret in PRIVATE:
        assert secret not in text
    assert "verified" not in text.replace("not_verified", "")


def test_buffer_arithmetic_crosses_the_london_clock_changes():
    # 02:10 BST minus 20 minutes is 00:50 GMT. Wall-clock subtraction would land
    # on 01:50, which does not exist on 29 March 2026.
    spring_start = datetime(2026, 3, 29, 2, 10, tzinfo=london(2026, 3, 29, 2).tzinfo)
    arrive = move(spring_start, -20)
    assert tfl_clock(arrive) == ("20260329", "0050")
    assert arrive.astimezone(UTC) == datetime(2026, 3, 29, 0, 50, tzinfo=UTC)

    first = datetime.fromisoformat("2026-10-25T01:30:00+01:00")
    later = move(first, 30)
    assert tfl_clock(later) == ("20261025", "0100")
    assert later.utcoffset() == timedelta(0)
    assert move(first, 90).astimezone(UTC) == datetime(2026, 10, 25, 2, 0, tzinfo=UTC)


def test_selection_keeps_a_future_shift_and_an_overnight_one():
    now = london(2026, 11, 7, 9, 0)
    finished = _row(london(2026, 11, 7, 8, 0), london(2026, 11, 7, 8, 30), "a")
    tomorrow = _row(london(2026, 11, 8, 22, 0), london(2026, 11, 9, 6, 0), "b")
    far = _row(now + timedelta(days=14, minutes=5), now + timedelta(days=14, hours=8), "c")
    chosen = select_shift([finished, far, tomorrow], now)
    assert chosen.id == "b"
    assert classify(chosen, now) == ("upcoming", True)
    assert select_shift([finished, far], now) is None

    running = _row(london(2026, 11, 6, 22, 0), london(2026, 11, 7, 6, 30), "night")
    later = _row(london(2026, 11, 7, 18, 0), london(2026, 11, 7, 23, 0), "eve")
    early = london(2026, 11, 7, 1, 0)
    assert select_shift([later, running], early).id == "night"
    assert classify(running, early) == ("overnight", True)


def test_home_and_destination_stay_unverified_when_only_nonempty():
    home = home_place(Settings(house_lat=SecretStr(LAT), house_lon=SecretStr(LON), house_postcode=SecretStr("")))
    assert home == {"state": "configured", "check": "not_verified", "kind": "coordinates", "label": "Home"}
    missing = home_place(Settings(house_lat=SecretStr(""), house_lon=SecretStr(""), house_postcode=SecretStr("")))
    assert missing["state"] == "missing"
    assert missing["check"] == "not_verified"
    broken = home_place(Settings(house_lat=SecretStr("nope"), house_lon=SecretStr("1"), house_postcode=SecretStr("")))
    assert broken["state"] == "unusable"
    assert broken["check"] == "not_verified"

    default = destination_place(Settings())
    assert default["label"] == "Wembley Park"
    assert default["check"] == "not_verified"
    assert default["override"] == "default"
    assert default["stop"] == "940GZZLUWYP"
    partial = destination_place(Settings(commute_destination_label="Somewhere", commute_destination_stop=""))
    assert partial["override"] == "ignored"
    assert partial["label"] == "Wembley Park"
    assert "Somewhere" not in json.dumps({key: partial[key] for key in partial if key != "note"})
    used = destination_place(
        Settings(commute_destination_label="North Greenwich", commute_destination_stop="940gzzlungw")
    )
    assert used["override"] == "used"
    assert used["label"] == "North Greenwich"
    assert used["check"] == "not_verified"


def test_quiet_window_does_not_include_the_hour_before_six():
    deadline = london(2026, 11, 7, 8, 0)
    assert in_window(london(2026, 11, 7, 7, 0), deadline, 90)
    assert not in_window(london(2026, 11, 7, 5, 0), deadline, 90)
    assert not in_window(deadline, deadline, 90)
    leave = departure_deadline(london(2026, 11, 7, 7, 50), "07:22")
    assert leave == london(2026, 11, 7, 7, 22)


def test_zero_shifts_do_not_call_a_provider(client, monkeypatch, caplog):
    _use(
        monkeypatch,
        BANTO_COMMUTE_TOKEN="",
        TFL_APP_KEY="",
        HOUSE_LAT="",
        HOUSE_LON="",
        HOUSE_POSTCODE="",
        COMMUTE_DISRUPTION_CHECKS="false",
    )
    _freeze(monkeypatch, 2026, 11, 7, 9, 0)
    calls = _trap(monkeypatch)
    with caplog.at_level(logging.DEBUG):
        plan = client.get("/commute/plan")
        brief = client.get("/brief/morning")
    assert plan.status_code == 200
    body = plan.json()
    assert body["summary"] == "Commute is not connected."
    assert body["shift"] is None
    assert body["advisory"] == {
        "active": False,
        "state": "inactive",
        "detail": "Pre-departure disruption checks are not active.",
    }
    assert body["home"]["state"] == "missing"
    assert body["home"]["check"] == "not_verified"
    assert body["destination"]["label"] == "Wembley Park"
    assert body["destination"]["check"] == "not_verified"
    assert calls == []
    commute = next(section for section in brief.json()["sections"] if section["key"] == "commute")
    assert commute["summary"] == "Commute is not connected."
    facts = client.get("/system/facts").json()
    assert facts["disruption_checks"] == "not active"
    _assert_private(plan.text + brief.text + caplog.text)
    get_settings.cache_clear()


def test_today_plans_both_legs_before_the_start_and_after_the_finish(client, monkeypatch, caplog):
    _use(
        monkeypatch,
        BANTO_COMMUTE_TOKEN=TOKEN,
        TFL_APP_KEY=TFL,
        HOUSE_LAT=LAT,
        HOUSE_LON=LON,
        HOUSE_POSTCODE=POSTCODE,
        COMMUTE_ARRIVAL_BUFFER_MINUTES="10",
        COMMUTE_RETURN_BUFFER_MINUTES="0",
        COMMUTE_DISRUPTION_CHECKS="false",
    )
    _freeze(monkeypatch, 2026, 11, 7, 7, 0)
    calls = _trap(monkeypatch)
    assert _shift(client).status_code == 201
    extra = _shift(client, arrive_by="07:40")
    assert extra.status_code == 422
    again = _shift(client)
    with caplog.at_level(logging.DEBUG):
        plan = client.get("/commute/plan")
    assert plan.status_code == 200
    body = plan.json()
    assert again.json()["id"] == body["shift"]["id"]
    assert body["shift"]["when"] == "today"
    assert body["shift"]["overnight"] is False
    assert body["arrival_buffer_minutes"] == 10
    assert body["outward"]["time_is"] == "Arriving"
    assert body["outward"]["clock"] == "07:22"
    assert body["outward"]["minutes"] == 34
    assert body["outward"]["lines"] == ["Jubilee"]
    assert body["back"]["time_is"] == "Departing"
    assert body["back"]["clock"] == "16:05"
    assert "leave 07:22" in body["summary"]
    assert "34 min" in body["summary"]
    assert "Minor Delays" in body["summary"]
    assert "Central" not in body["summary"]
    assert "Back departs 16:05." in body["summary"]
    assert body["home"]["check"] == "not_verified"
    assert body["advisory"]["state"] == "inactive"
    outward = next(item for item in calls if "JourneyResults" in item[1] and item[2]["timeIs"] == "Arriving")
    returning = next(item for item in calls if "JourneyResults" in item[1] and item[2]["timeIs"] == "Departing")
    assert outward[2]["date"] == "20261107"
    assert outward[2]["time"] == "0750"
    assert outward[1].endswith("/to/940GZZLUWYP")
    assert returning[2]["time"] == "1600"
    assert "/JourneyResults/940GZZLUWYP/to/" in returning[1]
    assert f"{LAT}" in outward[1]
    _assert_private(plan.text + caplog.text)
    assert "mistral" not in caplog.text
    get_settings.cache_clear()


def test_a_future_shift_is_not_hidden_by_an_empty_today(client, monkeypatch):
    _use(
        monkeypatch,
        BANTO_COMMUTE_TOKEN=TOKEN,
        TFL_APP_KEY="",
        HOUSE_LAT=LAT,
        HOUSE_LON=LON,
        COMMUTE_DISRUPTION_CHECKS="false",
    )
    _freeze(monkeypatch, 2026, 11, 7, 12, 0)
    calls = _trap(monkeypatch)
    assert _shift(
        client,
        start="2026-11-08T22:00:00+00:00",
        end="2026-11-09T06:30:00+00:00",
    ).status_code == 201
    body = client.get("/commute/plan").json()
    assert body["shift"]["when"] == "upcoming"
    assert body["shift"]["overnight"] is True
    assert "No commute on the rota today." not in body["summary"]
    assert "8 Nov · 22:00–06:30" in body["summary"]
    assert "Journey check is not connected." in body["summary"]
    assert body["outward"]["meta"] == "Arrive by 21:50"
    assert body["back"]["meta"] == "Departs at the finish 06:30"
    assert calls == []
    brief = next(section for section in client.get("/brief/morning").json()["sections"] if section["key"] == "commute")
    assert "22:00–06:30" in brief["summary"]
    assert brief["items"][0]["title"] == "Out"
    assert brief["items"][1]["title"] == "Back"
    assert brief["footnote"] == "Pre-departure disruption checks are not active."
    get_settings.cache_clear()


def test_overnight_and_dst_query_the_london_instants(client, monkeypatch):
    _use(
        monkeypatch,
        BANTO_COMMUTE_TOKEN=TOKEN,
        TFL_APP_KEY=TFL,
        HOUSE_LAT=LAT,
        HOUSE_LON=LON,
        HOUSE_POSTCODE="",
        COMMUTE_ARRIVAL_BUFFER_MINUTES="10",
        COMMUTE_RETURN_BUFFER_MINUTES="15",
        COMMUTE_DISRUPTION_CHECKS="false",
    )

    def journeys(params):
        if params["timeIs"] == "Arriving":
            return _journey("2026-03-28T21:40:00", 28)
        return _journey("2026-03-29T06:20:00", 31)

    calls = _trap(monkeypatch, journeys=journeys, status=[
        {"name": "Jubilee", "lineStatuses": [{"statusSeverityDescription": "Good Service"}]},
    ])
    created = _shift(client, start="2026-03-28T22:00:00+00:00", end="2026-03-29T06:00:00+01:00")
    assert created.status_code == 201
    _freeze(monkeypatch, 2026, 3, 28, 18, 0)
    body = client.get("/commute/plan").json()
    assert body["shift"]["overnight"] is True
    assert body["return_buffer_minutes"] == 15
    assert body["back"]["meta"] == "Departs 15 min after the finish"
    outward = next(item for item in calls if item[2] and item[2].get("timeIs") == "Arriving")
    returning = next(item for item in calls if item[2] and item[2].get("timeIs") == "Departing")
    assert (outward[2]["date"], outward[2]["time"]) == ("20260328", "2150")
    assert (returning[2]["date"], returning[2]["time"]) == ("20260329", "0615")
    assert "No line disruptions." in body["summary"]
    get_settings.cache_clear()


def test_stale_error_and_quiet_hours_do_not_send(client, monkeypatch, caplog):
    _use(
        monkeypatch,
        BANTO_COMMUTE_TOKEN=TOKEN,
        TFL_APP_KEY=TFL,
        HOUSE_LAT=LAT,
        HOUSE_LON=LON,
        COMMUTE_DISRUPTION_CHECKS="true",
        COMMUTE_PREDEPARTURE_MINUTES="90",
        COMMUTE_ARRIVAL_BUFFER_MINUTES="10",
        RATE_COMMUTE_DISRUPTION_PER_HOUR="6",
    )
    # Leave 22:50, so 21:40 is inside the window and 22:30 is still inside it, and quiet.
    _freeze(monkeypatch, 2026, 11, 7, 21, 40)
    state = {"now": 1_000.0}

    def mono():
        return state["now"]

    monkeypatch.setattr("organiser.services.commute_plan._mono", mono)

    def journeys(params):
        if params.get("timeIs") == "Departing":
            return _journey("2026-11-08T06:10:00", 36)
        return _journey("2026-11-07T22:50:00", 30)

    calls = _trap(monkeypatch, journeys=journeys)

    def advisory_calls():
        return [item for item in calls if item[3] == 5.0]

    assert _shift(client, start="2026-11-07T23:20:00+00:00", end="2026-11-08T06:00:00+00:00").status_code == 201
    with caplog.at_level(logging.DEBUG):
        fresh = client.get("/commute/plan").json()
    assert fresh["advisory"]["state"] == "fresh"
    assert fresh["advisory"]["active"] is True
    assert "Jubilee: Minor Delays" in fresh["advisory"]["detail"]
    assert "Central" not in fresh["advisory"]["detail"]
    assert len(advisory_calls()) == 1
    cached = client.get("/commute/plan").json()
    assert cached["advisory"]["state"] == "fresh"
    assert len(advisory_calls()) == 1

    state["now"] += ADVISORY_FRESH_SECONDS + 1

    def failing(method, url, **kwargs):
        calls.append((method, url, kwargs.get("params"), kwargs.get("timeout")))
        if kwargs.get("timeout") == 5.0:
            raise httpx.ReadTimeout("slow")
        if url.endswith("/Status"):
            return _status()
        if kwargs["params"].get("timeIs") == "Departing":
            return _journey("2026-11-08T06:10:00", 36)
        return _journey("2026-11-07T22:50:00", 30)

    monkeypatch.setattr("organiser.services.commute.request_json_any", failing)
    monkeypatch.setattr("organiser.services.commute_plan.request_json_any", failing)
    stale = client.get("/commute/plan").json()
    assert stale["advisory"]["state"] == "stale"
    assert "newer read failed" in stale["advisory"]["detail"]
    assert "live" not in stale["advisory"]["detail"].casefold()
    assert "Minor Delays" in stale["advisory"]["detail"]

    state["now"] += ADVISORY_STALE_SECONDS
    clear_cache()
    errored = client.get("/commute/plan").json()
    assert errored["advisory"]["state"] == "error"
    assert errored["advisory"]["detail"] == "Disruption check is unavailable."

    _freeze(monkeypatch, 2026, 11, 7, 22, 30)
    clear_cache()
    before = len(advisory_calls())
    held = client.get("/commute/plan").json()
    assert held["advisory"]["state"] == "held"
    assert held["advisory"]["detail"] == "Held for quiet hours. Nothing was sent."
    assert len(advisory_calls()) == before
    _assert_private(caplog.text + json.dumps(held))
    get_settings.cache_clear()


def test_a_paused_house_and_the_hourly_limit_skip_the_check(client, db, monkeypatch):
    _use(
        monkeypatch,
        BANTO_COMMUTE_TOKEN=TOKEN,
        TFL_APP_KEY=TFL,
        HOUSE_LAT=LAT,
        HOUSE_LON=LON,
        COMMUTE_DISRUPTION_CHECKS="true",
        RATE_COMMUTE_DISRUPTION_PER_HOUR="1",
    )
    _freeze(monkeypatch, 2026, 11, 7, 7, 0)
    calls = _trap(monkeypatch)
    assert _shift(client).status_code == 201
    assert client.post("/system/pause").status_code == 200
    paused = client.get("/commute/plan").json()
    assert paused["advisory"]["state"] == "paused"
    assert paused["advisory"]["detail"] == "The house is paused. Disruption checks are not running."
    assert [item for item in calls if item[3] == 5.0] == []
    assert client.post("/system/unpause").status_code == 200
    clear_cache()
    first = client.get("/commute/plan").json()
    assert first["advisory"]["state"] == "fresh"
    from organiser.services.commute_plan import clear_advisory_cache

    clear_advisory_cache()
    limited = client.get("/commute/plan").json()
    assert limited["advisory"]["state"] == "limited"
    assert db.get(CommuteShift, first["shift"]["id"]) is not None
    get_settings.cache_clear()


def test_line_status_is_separate_while_departure_checks_stay_off(client, monkeypatch):
    """Home can read lines. The pre-departure note does not call anyone while it is off."""
    _use(
        monkeypatch,
        BANTO_COMMUTE_TOKEN="",
        TFL_APP_KEY=TFL,
        HOUSE_LAT="",
        HOUSE_LON="",
        HOUSE_POSTCODE="",
        COMMUTE_DISRUPTION_CHECKS="false",
        MISTRAL_API_KEY="",
        MISTRAL_AGENT_ID="",
    )
    _freeze(monkeypatch, 2026, 11, 7, 9, 0)
    plan_calls = _trap(monkeypatch)
    line_calls = []

    def line_fake(method, url, **kwargs):
        line_calls.append((method, url, kwargs.get("params"), kwargs.get("timeout")))
        return [
            {
                "id": "jubilee",
                "name": "Jubilee",
                "modeName": "tube",
                "modified": "2026-11-07T09:00:00Z",
                "lineStatuses": [{"statusSeverityDescription": "Good Service"}],
            }
        ]

    monkeypatch.setattr("organiser.services.lines.request_json_any", line_fake)
    plan = client.get("/commute/plan")
    assert plan.status_code == 200
    body = plan.json()
    assert body["summary"] == "Commute is not connected."
    assert body["advisory"]["active"] is False
    assert body["advisory"]["state"] == "inactive"
    assert plan_calls == []
    status = client.get("/tfl/status")
    assert status.status_code == 200
    assert status.json()["configured"] is True
    assert status.json()["state"] == "fresh"
    assert status.json()["lines"][0]["name"] == "Jubilee"
    assert len(line_calls) == 1
    assert line_calls[0][3] == 5.0
    assert "Journey" not in line_calls[0][1]
    facts = client.get("/system/facts").json()
    assert facts["disruption_checks"] == "not active"
    assert facts["tfl"] == "configured"
    brief = next(section for section in client.get("/brief/morning").json()["sections"] if section["key"] == "commute")
    assert brief["summary"] == "Commute is not connected."
    assert plan_calls == []
    get_settings.cache_clear()


def test_a_failed_journey_stays_a_short_line(client, monkeypatch, caplog):
    _use(
        monkeypatch,
        BANTO_COMMUTE_TOKEN=TOKEN,
        TFL_APP_KEY=TFL,
        HOUSE_LAT=LAT,
        HOUSE_LON=LON,
        COMMUTE_DISRUPTION_CHECKS="false",
    )
    _freeze(monkeypatch, 2026, 11, 7, 7, 0)
    _trap(monkeypatch, error=RuntimeError(f"down {LAT} {TFL}"))
    assert _shift(client).status_code == 201
    with caplog.at_level(logging.DEBUG):
        body = client.get("/commute/plan").json()
    assert "Journey check is unavailable." in body["summary"]
    assert body["outward"]["state"] == "unavailable"
    assert LAT not in json.dumps(body)
    assert TFL not in caplog.text
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0", 0), ("10", 10), ("999", 180), ("-4", 0), ("nope", 10)],
)
def test_arrival_buffer_is_clamped(raw, expected, monkeypatch):
    _use(monkeypatch, COMMUTE_ARRIVAL_BUFFER_MINUTES=raw)
    assert get_settings().commute_arrival_buffer_minutes == expected
    get_settings.cache_clear()
