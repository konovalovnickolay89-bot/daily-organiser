"""Line status on its own. The provider is a fake. Nothing calls TfL or Mistral."""

import json
import logging
import threading
from datetime import datetime, timezone

import httpx
from pydantic import SecretStr

from organiser.agent.mistral import MistralClient
from organiser.config import Settings, get_settings
from organiser.services.lines import (
    FRESH_SECONDS,
    STALE_SECONDS,
    STATUS_URL,
    clear_cache,
    service_status,
)

TFL = "tfl-key-placeholder"
OTHER = "tfl-other-placeholder"
POSTCODE = "ZZ99 9ZZ"
LAT = "51.54321"
LON = "-0.27654"
UTC = timezone.utc
NOW = datetime(2026, 11, 7, 14, 6, tzinfo=UTC)
PRIVATE = (TFL, OTHER, POSTCODE, LAT, LON, "940GZZLUWYP", "Wembley")


def _use(monkeypatch, **env):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()


def _settings(key: str = TFL) -> Settings:
    return Settings(
        tfl_app_key=SecretStr(key),
        banto_commute_token=SecretStr(""),
        house_lat=SecretStr(""),
        house_lon=SecretStr(""),
        house_postcode=SecretStr(""),
        google_oauth_client_id=SecretStr(""),
        google_oauth_client_secret=SecretStr(""),
        google_oauth_refresh_token=SecretStr(""),
        mistral_api_key=SecretStr(""),
    )


def _good():
    return [
        {
            "id": "jubilee",
            "name": "Jubilee",
            "modeName": "tube",
            "modified": "2026-11-07T14:05:00Z",
            "lineStatuses": [
                {
                    "statusSeverityDescription": "Minor Delays",
                    "reason": (
                        "<script>alert(1)</script><b>Minor delays</b> due to a signal failure "
                        f"at Baker Street. app_key={TFL}"
                    ),
                    "created": "2026-11-07T14:04:00Z",
                }
            ],
        },
        {
            "id": "central",
            "name": "Central",
            "modeName": "tube",
            "modified": "2026-11-07T13:00:00Z",
            "lineStatuses": [
                {"statusSeverityDescription": "Good Service", "reason": f"Ignore {TFL}"},
            ],
        },
        {
            "id": "london-overground",
            "name": "London Overground",
            "modeName": "overground",
            "lineStatuses": [{"statusSeverityDescription": "Good Service"}],
        },
        {
            "id": "elizabeth",
            "name": "Elizabeth line",
            "modeName": "elizabeth-line",
            "modified": "/Date(1487088000000)/",
            "lineStatuses": [{"statusSeverityDescription": "Part Suspended", "reason": "  "}],
        },
        {
            "id": "dlr",
            "name": "DLR",
            "modeName": "dlr",
            "lineStatuses": [{"statusSeverityDescription": "Good Service"}],
        },
    ]


def _status(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", f"{STATUS_URL}?app_key={TFL}")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError("upstream", request=request, response=response)


class _Return:
    def __init__(self, body):
        self.body = body


def _trap(monkeypatch, body=None, error=None):
    calls = []

    def fake(method, url, **kwargs):
        calls.append((method, url, kwargs.get("params"), kwargs.get("timeout")))
        if isinstance(error, _Return):
            return error.body
        if error is not None:
            raise error
        return body if body is not None else _good()

    monkeypatch.setattr("organiser.services.lines.request_json_any", fake)
    monkeypatch.setattr(
        MistralClient,
        "_call",
        lambda self, *args, **kwargs: (_ for _ in ()).throw(AssertionError("mistral")),
    )
    monkeypatch.setattr(
        "organiser.services.commute.request_json_any",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("commute")),
    )
    monkeypatch.setattr(
        "organiser.services.weather.request_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("weather")),
    )
    return calls


def _clock(monkeypatch):
    state = {"now": 1_000.0}

    def mono():
        return state["now"]

    monkeypatch.setattr("organiser.services.lines._mono", mono)
    return state


def _assert_private(text: str):
    for secret in PRIVATE:
        assert secret not in text


def test_missing_key_does_not_call_tfl(monkeypatch):
    calls = _trap(monkeypatch)
    body = service_status(_settings(""))
    assert calls == []
    assert body["configured"] is False
    assert body["state"] == "missing"
    assert body["stale"] is False
    assert body["lines"] == []
    assert body["failure"] is None
    assert body["detail"] == "TfL is not configured."
    assert body["fetched_at"] is None
    assert body["source_at"] is None


def test_fresh_read_keeps_disruption_and_drops_good_service_reason(monkeypatch):
    calls = _trap(monkeypatch)
    body = service_status(_settings(), NOW)
    assert len(calls) == 1
    method, url, params, timeout = calls[0]
    assert method == "GET"
    assert url == STATUS_URL
    assert params == {"app_key": TFL}
    assert timeout == 5.0
    assert "Journey" not in url
    assert set(body) == {
        "configured",
        "state",
        "stale",
        "fetched_at",
        "source_at",
        "failure",
        "detail",
        "lines",
    }
    assert body["configured"] is True
    assert body["state"] == "fresh"
    assert body["stale"] is False
    assert body["failure"] is None
    assert body["detail"] is None
    assert body["fetched_at"] == NOW
    assert body["source_at"] == datetime(2026, 11, 7, 14, 5, tzinfo=UTC)
    jubilee = body["lines"][0]
    assert jubilee == {
        "id": "jubilee",
        "name": "Jubilee",
        "mode": "Tube",
        "severity": "Minor Delays",
        "reason": "Minor delays due to a signal failure at Baker Street.",
    }
    central = next(line for line in body["lines"] if line["id"] == "central")
    assert central["severity"] == "Good Service"
    assert central["reason"] is None
    assert [line["mode"] for line in body["lines"]] == [
        "Tube",
        "Tube",
        "Overground",
        "Elizabeth line",
        "DLR",
    ]
    elizabeth = next(line for line in body["lines"] if line["id"] == "elizabeth")
    assert elizabeth["severity"] == "Part Suspended"
    assert elizabeth["reason"] is None
    rendered = json.dumps(body, default=str)
    assert TFL not in rendered
    assert "<" not in rendered


def test_second_read_uses_the_cache_until_it_is_cleared(monkeypatch):
    calls = _trap(monkeypatch)
    clock = _clock(monkeypatch)
    first = service_status(_settings(), NOW)
    second = service_status(_settings(), NOW)
    assert len(calls) == 1
    assert second["fetched_at"] == first["fetched_at"]
    clock["now"] += FRESH_SECONDS + 1
    service_status(_settings(), NOW)
    assert len(calls) == 2
    clear_cache()
    service_status(_settings(), NOW)
    assert len(calls) == 3


def test_a_different_key_does_not_reuse_the_parse(monkeypatch):
    calls = _trap(monkeypatch)
    service_status(_settings(TFL), NOW)
    service_status(_settings(OTHER), NOW)
    assert len(calls) == 2
    assert calls[0][2]["app_key"] == TFL
    assert calls[1][2]["app_key"] == OTHER


def test_failed_refresh_is_stale_then_recovers(monkeypatch):
    clock = _clock(monkeypatch)
    calls = _trap(monkeypatch)
    fresh = service_status(_settings(), NOW)
    clock["now"] += FRESH_SECONDS + 1
    calls.clear()
    _trap(monkeypatch, error=httpx.ReadTimeout("timed out"))
    stale = service_status(_settings(), NOW)
    assert stale["state"] == "stale"
    assert stale["stale"] is True
    assert stale["configured"] is True
    assert stale["failure"] == "timeout"
    assert stale["fetched_at"] == fresh["fetched_at"]
    assert stale["source_at"] == fresh["source_at"]
    assert stale["lines"][0]["name"] == "Jubilee"
    assert "newer read failed" in stale["detail"]
    assert "did not answer" in stale["detail"]
    assert "live" not in stale["detail"].casefold()
    assert "real-time" not in stale["detail"].casefold()
    assert "realtime" not in stale["detail"].casefold()
    _trap(monkeypatch)
    recovered = service_status(_settings(), NOW)
    assert recovered["state"] == "fresh"
    assert recovered["failure"] is None
    assert recovered["stale"] is False


def test_a_failed_read_with_nothing_fresh_enough_is_an_error(monkeypatch):
    clock = _clock(monkeypatch)
    _trap(monkeypatch)
    service_status(_settings(), NOW)
    clock["now"] += STALE_SECONDS + 1
    _trap(monkeypatch, error=_status(429))
    body = service_status(_settings(), NOW)
    assert body["configured"] is True
    assert body["state"] == "error"
    assert body["stale"] is False
    assert body["lines"] == []
    assert body["failure"] == "limited"
    assert body["fetched_at"] is None
    assert body["detail"] == "TfL is limiting line status."


def test_upstream_failures_stay_honest_and_unlogged(monkeypatch, caplog):
    unreadable = "TfL sent a line status this house could not read."
    cases = (
        (_status(403), "refused", "TfL refused the line status."),
        (_status(429), "limited", "TfL is limiting line status."),
        (httpx.ReadTimeout(f"slow {TFL}"), "timeout", "TfL did not answer in time."),
        (ValueError(f"not json {STATUS_URL}?app_key={TFL}"), "malformed", unreadable),
        (_status(500), "upstream", "Line status is unavailable."),
        (_Return({"unexpected": TFL}), "malformed", unreadable),
        (_Return(["nope", 3]), "malformed", unreadable),
    )
    for error, failure, detail in cases:
        clear_cache()
        caplog.clear()
        _trap(monkeypatch, error=error)
        with caplog.at_level(logging.DEBUG):
            body = service_status(_settings(), NOW)
        text = json.dumps(body) + caplog.text
        assert body["configured"] is True
        assert body["state"] == "error"
        assert body["failure"] == failure
        assert body["detail"] == detail
        assert body["lines"] == []
        _assert_private(text)
        assert "api.tfl.gov.uk" not in text


def test_concurrent_readers_share_one_call_and_the_cache_has_no_private_payload(monkeypatch):
    release = threading.Event()
    entered = threading.Event()
    calls = {"n": 0}
    lock = threading.Lock()

    def fake(method, url, **kwargs):
        with lock:
            calls["n"] += 1
        assert kwargs["params"] == {"app_key": TFL}
        assert url == STATUS_URL
        entered.set()
        assert release.wait(2)
        return _good()

    monkeypatch.setattr("organiser.services.lines.request_json_any", fake)
    waits = {"n": 0}
    original = __import__("organiser.services.lines", fromlist=["_cond"])._cond.wait

    def counting_wait(timeout=None):
        with lock:
            waits["n"] += 1
        return original(timeout)

    import organiser.services.lines as lines

    monkeypatch.setattr(lines._cond, "wait", counting_wait)
    results = []
    errors = []

    def run():
        try:
            results.append(service_status(_settings(), NOW))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(8)]
    try:
        for thread in threads:
            thread.start()
        assert entered.wait(2)
        pause = threading.Event()
        for _ in range(200):
            with lock:
                if waits["n"] >= 7 and calls["n"] == 1:
                    break
            pause.wait(0.01)
        with lock:
            assert calls["n"] == 1
            assert waits["n"] >= 7
    finally:
        release.set()
    for thread in threads:
        thread.join(3)
        assert not thread.is_alive()
    assert errors == []
    assert len(results) == 8
    assert {item["state"] for item in results} == {"fresh"}
    cached = json.dumps(list(lines._cache.values()), default=_dump)
    _assert_private(cached)
    assert "app_key" not in cached
    clear_cache()
    assert lines._cache == {}
    service_status(_settings(), NOW)
    with lock:
        assert calls["n"] == 2


def _dump(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return {key: getattr(value, key) for key in value.__dataclass_fields__}
    raise TypeError(type(value))


def test_route_reads_lines_with_no_shift_banto_calendar_or_location(client, monkeypatch, caplog):
    _use(
        monkeypatch,
        TFL_APP_KEY=TFL,
        BANTO_COMMUTE_TOKEN="",
        HOUSE_LAT="",
        HOUSE_LON="",
        HOUSE_POSTCODE="",
        GOOGLE_OAUTH_CLIENT_ID="",
        GOOGLE_OAUTH_CLIENT_SECRET="",
        GOOGLE_OAUTH_REFRESH_TOKEN="",
        MISTRAL_API_KEY="",
        MISTRAL_AGENT_ID="",
    )
    calls = _trap(monkeypatch)
    with caplog.at_level(logging.DEBUG):
        response = client.get(
            "/tfl/status",
            params={"app_key": "client-supplied-secret", "postcode": POSTCODE, "lat": LAT},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["state"] == "fresh"
    assert body["lines"][0]["name"] == "Jubilee"
    assert body["lines"][0]["reason"].startswith("Minor delays")
    assert len(calls) == 1
    assert calls[0][2] == {"app_key": TFL}
    assert "client-supplied-secret" not in calls[0][1]
    brief = client.get("/brief/morning")
    assert brief.status_code == 200
    commute = next(section for section in brief.json()["sections"] if section["key"] == "commute")
    assert commute["summary"] == "Commute is not connected."
    assert commute["items"] == []
    text = response.text + brief.text + caplog.text
    _assert_private(text)
    assert "client-supplied-secret" not in text
    assert POSTCODE not in text
    assert "api.tfl.gov.uk" not in caplog.text
    facts = client.get("/system/facts")
    assert facts.json()["tfl"] == "configured"
    assert facts.json()["banto"] == "not configured"
    assert facts.json()["diary"] == "not configured"
    get_settings.cache_clear()


def test_route_reports_a_missing_key_without_a_call(client, monkeypatch):
    _use(monkeypatch, TFL_APP_KEY="", BANTO_COMMUTE_TOKEN="")
    calls = _trap(monkeypatch)
    response = client.get("/tfl/status")
    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["state"] == "missing"
    assert response.json()["detail"] == "TfL is not configured."
    assert calls == []
    get_settings.cache_clear()
