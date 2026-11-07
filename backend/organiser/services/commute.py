"""A rota commute, and the journey from home to Wembley Park.

The push stores three fields: start, end, and the label ``Wembley``. That label
means Wembley Park station. The origin is the house point from the environment.
Coordinates, the postcode, and the TfL key are never logged and never stored.
A missing token or key leaves a short line on the brief and changes nothing else.
"""

import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.agent.cards import clip
from organiser.config import Settings, commute_point_for_label
from organiser.models import CommuteShift
from organiser.services.activity import record_line
from organiser.services.outbound import request_json_any
from organiser.services.weather import home_coordinates

logger = logging.getLogger(__name__)

LONDON = ZoneInfo("Europe/London")
UTC = timezone.utc
# Wembley Park Underground Station, on the TfL stop list.
WEMBLEY_STOP = "940GZZLUWYP"
STORED_LABEL = "Wembley"
_CACHE: dict[str, tuple[float, dict]] = {}
_TTL_SECONDS = 10 * 60
_tfl_outcome = "unknown"
_TAG = re.compile(r"<[^>]+>")
_GOOD = {"good service"}


class ShiftRejected(Exception):
    def __init__(self, detail: str, status_code: int = 422) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def clear_cache() -> None:
    global _tfl_outcome
    _CACHE.clear()
    _tfl_outcome = "unknown"


def tfl_outcome() -> str:
    """``ok``, ``attention``, or ``unknown``. No origin, postcode, or key."""
    return _tfl_outcome


def _note_tfl(state: str) -> None:
    global _tfl_outcome
    _tfl_outcome = state


def _back(aware: datetime) -> datetime:
    """Wall time after a trip through UTC. A gap does not come back as itself."""
    return aware.astimezone(UTC).astimezone(LONDON).replace(tzinfo=None)


def wall_exists(naive: datetime) -> bool:
    return _back(naive.replace(tzinfo=LONDON)) == naive


def is_ambiguous(naive: datetime) -> bool:
    first = naive.replace(tzinfo=LONDON, fold=0)
    second = naive.replace(tzinfo=LONDON, fold=1)
    if first.utcoffset() == second.utcoffset():
        return False
    return _back(first) == naive and _back(second) == naive


def to_london(value: datetime) -> datetime:
    """An aware instant, or a naive clock time that exists once in London."""
    if value.tzinfo is None:
        if not wall_exists(value):
            raise ShiftRejected("That time does not exist in Europe/London.")
        if is_ambiguous(value):
            raise ShiftRejected("That time happens twice in Europe/London. Send an offset.")
        return value.replace(tzinfo=LONDON)
    return value.astimezone(LONDON)


def tfl_clock(start: datetime) -> tuple[str, str]:
    """TfL date ``YYYYMMDD`` and time ``HHMM`` in the London wall clock."""
    local = start.astimezone(LONDON)
    return local.strftime("%Y%m%d"), local.strftime("%H%M")


def _hm(value: datetime) -> str:
    return value.astimezone(LONDON).strftime("%H:%M")


def accept_shift(start: datetime, end: datetime, label: str) -> tuple[datetime, datetime, str]:
    if commute_point_for_label(label) is None:
        raise ShiftRejected("Not a house commute.")
    start_at = to_london(start)
    end_at = to_london(end)
    if end_at <= start_at:
        raise ShiftRejected("The shift end is not after the start.")
    return start_at, end_at, STORED_LABEL


def store_shift(session: Session, start: datetime, end: datetime, label: str) -> CommuteShift:
    start_at, end_at, stored = accept_shift(start, end, label)
    existing = session.scalars(
        select(CommuteShift).where(
            CommuteShift.start_at == start_at,
            CommuteShift.end_at == end_at,
            CommuteShift.location_label == stored,
        )
    ).first()
    if existing is not None:
        return existing
    row = CommuteShift(start_at=start_at, end_at=end_at, location_label=stored)
    session.add(row)
    session.flush()
    record_line(
        session,
        kind="brief",
        title=f"Commute: {stored} {_hm(start_at)}–{_hm(end_at)}",
        body="A shift was noted. Only the start, the end, and the location were kept.",
    )
    return row


def pick_shift(rows: list[CommuteShift], today, now: datetime) -> CommuteShift | None:
    todays = [row for row in rows if row.start_at.astimezone(LONDON).date() == today]
    if not todays:
        return None
    local_now = now.astimezone(LONDON)
    if local_now.date() != today:
        return min(todays, key=lambda row: (row.start_at, str(row.id)))
    current = [row for row in todays if row.start_at <= local_now < row.end_at]
    if current:
        return min(current, key=lambda row: (row.start_at, str(row.id)))
    upcoming = [row for row in todays if row.start_at >= local_now]
    if upcoming:
        return min(upcoming, key=lambda row: (row.start_at, str(row.id)))
    return max(todays, key=lambda row: (row.start_at, str(row.id)))


def _plain(text: str) -> str:
    return " ".join(_TAG.sub(" ", text).split())


def _lines_from(journey: dict) -> list[str]:
    names: list[str] = []
    for leg in journey.get("legs") or []:
        if not isinstance(leg, dict):
            continue
        mode = leg.get("mode")
        mode_id = mode.get("id") if isinstance(mode, dict) else ""
        if str(mode_id).casefold() in {"walking", "walk"}:
            continue
        options = leg.get("routeOptions") or []
        if isinstance(options, list):
            for option in options:
                if isinstance(option, dict) and isinstance(option.get("name"), str):
                    name = option["name"].strip()
                    if name and name not in names:
                        names.append(name)
    return names


def _leave(journey: dict) -> str | None:
    raw = journey.get("startDateTime")
    if not isinstance(raw, str) or "T" not in raw:
        return None
    clock = raw.split("T", 1)[1]
    if len(clock) < 5 or clock[2] != ":":
        return None
    return clock[:5]


def _read_journey(body: dict) -> dict | None:
    journeys = body.get("journeys")
    if not isinstance(journeys, list) or not journeys or not isinstance(journeys[0], dict):
        return None
    journey = journeys[0]
    try:
        minutes = int(journey.get("duration"))
    except (TypeError, ValueError):
        return None
    leave = _leave(journey)
    if leave is None or minutes < 0:
        return None
    lines = _lines_from(journey)
    return {"leave": leave, "minutes": minutes, "lines": lines}


def _disruptions(body: object, used: list[str]) -> str:
    if not isinstance(body, list):
        return "Line disruptions unavailable."
    wanted = {name.casefold() for name in used}
    found: list[str] = []
    for line in body:
        if not isinstance(line, dict):
            continue
        name = line.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if wanted and name.casefold() not in wanted:
            continue
        for status in line.get("lineStatuses") or []:
            if not isinstance(status, dict):
                continue
            desc = _plain(str(status.get("statusSeverityDescription") or ""))
            if not desc or desc.casefold() in _GOOD:
                continue
            found.append(f"{name.strip()}: {desc}")
            break
    if not found:
        return "No line disruptions."
    return clip("; ".join(found), 180)


def _section(summary: str, *, meta: str | None = None, detail: str | None = None) -> dict:
    items = []
    if meta or detail:
        items.append({"title": "Wembley Park", "meta": meta, "detail": detail or summary})
    return {
        "key": "commute",
        "title": "Commute",
        "placeholder": False,
        "summary": summary,
        "items": items,
    }


def _fetch(settings: Settings, lat: float, lon: float, start: datetime, used_key: str) -> dict:
    cached = _CACHE.get(used_key)
    if cached and time.monotonic() - cached[0] < _TTL_SECONDS:
        return cached[1]
    day, clock = tfl_clock(start)
    origin = f"{lat:.5f},{lon:.5f}"
    key = settings.tfl_app_key.get_secret_value().strip()
    journey_url = (
        "https://api.tfl.gov.uk/Journey/JourneyResults/"
        + quote(origin, safe=",-.")
        + "/to/"
        + WEMBLEY_STOP
    )
    try:
        journey_body = request_json_any(
            "GET",
            journey_url,
            params={
                "app_key": key,
                "date": day,
                "time": clock,
                "timeIs": "Arriving",
                "mode": "tube,overground,elizabeth-line,dlr,bus",
                "journeyPreference": "leasttime",
            },
        )
    except Exception:
        logger.info("commute journey failed")
        raise
    if not isinstance(journey_body, dict):
        raise ValueError("journey")
    journey = _read_journey(journey_body)
    if journey is None:
        raise ValueError("journey")
    try:
        status_body = request_json_any(
            "GET",
            "https://api.tfl.gov.uk/Line/Mode/tube,overground,elizabeth-line,dlr/Status",
            params={"app_key": key},
        )
        disruptions = _disruptions(status_body, journey["lines"])
    except Exception:
        logger.info("commute disruptions failed")
        disruptions = "Line disruptions unavailable."
    via = f" · {', '.join(journey['lines'])}" if journey["lines"] else ""
    summary = f"Wembley Park · leave {journey['leave']} · {journey['minutes']} min{via}. {disruptions}"
    fresh = {"summary": summary, "disruptions": disruptions}
    _CACHE[used_key] = (time.monotonic(), fresh)
    _note_tfl("ok")
    return fresh


def commute_section(session: Session, settings: Settings, today, now: datetime) -> dict:
    rows = list(session.scalars(select(CommuteShift)))
    shift = pick_shift(rows, today, now)
    if shift is None:
        if settings.banto_configured:
            return _section("No commute on the rota today.")
        return _section("Commute is not connected.")

    span = f"{_hm(shift.start_at)}–{_hm(shift.end_at)}"
    if not settings.tfl_configured:
        return _section(f"Wembley Park · {span}. Journey check is not connected.", meta=span)
    if settings.home_location_kind is None:
        return _section(f"Wembley Park · {span}. Home location is not set.", meta=span)
    point = home_coordinates(settings)
    if point is None:
        return _section(f"Wembley Park · {span}. Journey check is unavailable.", meta=span)
    try:
        fresh = _fetch(settings, point[0], point[1], shift.start_at, str(shift.id))
    except Exception:
        _note_tfl("attention")
        return _section(f"Wembley Park · {span}. Journey check is unavailable.", meta=span)
    return _section(fresh["summary"], meta=span, detail=fresh["summary"])
