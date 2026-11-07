"""A rota commute, and the journey from home to Wembley Park.

The push stores three fields: start, end, and the label ``Wembley``. That label
means Wembley Park station. The origin is the house point from the environment.
Coordinates, the postcode, and the TfL key are never logged and never stored.
A missing token or key leaves a short line on the brief and changes nothing else.
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.agent.cards import clip
from organiser.config import Settings, commute_point_for_label
from organiser.models import CommuteShift
from organiser.services.activity import record_line
from organiser.services.outbound import request_json_any

logger = logging.getLogger(__name__)

LONDON = ZoneInfo("Europe/London")
UTC = timezone.utc
# Wembley Park Underground Station, on the TfL stop list.
WEMBLEY_STOP = "940GZZLUWYP"
STORED_LABEL = "Wembley"
_CACHE: dict[str, tuple[float, dict]] = {}
_TTL_SECONDS = 10 * 60
_CACHE_LIMIT = 32
_TAG = re.compile(r"<[^>]+>")
_GOOD = {"good service"}


class ShiftRejected(Exception):
    def __init__(self, detail: str, status_code: int = 422) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def clear_cache() -> None:
    _CACHE.clear()
    from organiser.services.commute_plan import clear_advisory_cache

    clear_advisory_cache()


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


def move(moment: datetime, minutes: int) -> datetime:
    """Move an aware instant by minutes.

    The sum is done in UTC and then shown in London, so a clock change is not
    applied twice and a gap is not invented by subtracting wall-clock minutes.
    """
    base = moment if moment.tzinfo is not None else to_london(moment)
    return (base.astimezone(UTC) + timedelta(minutes=minutes)).astimezone(LONDON)


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


def disruption_note(body: object, used: list[str]) -> str:
    """Plain disruption line for the lines in one journey. No key and no place."""
    return _disruptions(body, used)


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


def _segment(value: str) -> str:
    return quote(value, safe=",-.")


def _remember(key: str, value: dict) -> None:
    _CACHE[key] = (time.monotonic(), value)
    if len(_CACHE) <= _CACHE_LIMIT:
        return
    oldest = min(_CACHE, key=lambda item: _CACHE[item][0])
    _CACHE.pop(oldest, None)


def fetch_leg(
    settings: Settings,
    origin: str,
    destination: str,
    when: datetime,
    time_is: str,
    cache_key: str,
) -> dict:
    """One journey. The cache keeps the parsed times and line names, not the origin.

    ``time_is`` is ``Arriving`` for the way out and ``Departing`` for the way back.
    The origin and the key are not logged.
    """
    cached = _CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < _TTL_SECONDS:
        return cached[1]
    day, clock = tfl_clock(when)
    key = settings.tfl_app_key.get_secret_value().strip()
    journey_url = (
        "https://api.tfl.gov.uk/Journey/JourneyResults/"
        + _segment(origin)
        + "/to/"
        + _segment(destination)
    )
    try:
        journey_body = request_json_any(
            "GET",
            journey_url,
            params={
                "app_key": key,
                "date": day,
                "time": clock,
                "timeIs": time_is,
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
        disruptions = _disruptions(status_body, journey["lines"]).replace(key, "")
    except Exception:
        logger.info("commute disruptions failed")
        disruptions = "Line disruptions unavailable."
    fresh = {
        "leave": journey["leave"],
        "minutes": journey["minutes"],
        "lines": journey["lines"],
        "disruptions": disruptions,
    }
    _remember(cache_key, fresh)
    return fresh


def commute_section(session: Session, settings: Settings, today, now: datetime, paused: bool = False) -> dict:
    """The brief's commute block. The plan is shared with ``GET /commute/plan``."""
    from organiser.services.commute_plan import section_for_brief

    return section_for_brief(session, settings, today, now, paused)
