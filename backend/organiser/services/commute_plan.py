"""Round trip for the next house shift.

Outward is home to the configured destination, arriving before the shift by
the arrival buffer. The return leaves the destination after the shift finishes.
Both clocks are Europe/London. A shift that runs past midnight keeps the
return on the finish instant, not on the start date.

Nothing here is scheduled. ``GET /commute/plan`` and the morning brief are the
only callers. Pre-departure disruption checks stay off until
``COMMUTE_DISRUPTION_CHECKS`` is set. While they are off, this module does not
call TfL for that check. It does not send, book, or call Mistral.

A nonempty home or destination is ``configured`` and ``not_verified``. This
module does not ask a provider to confirm either one, so it never reports
them as verified.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.config import WEMBLEY_POINT, Settings
from organiser.limits import LIMITS
from organiser.models import CommuteShift
from organiser.services.catchup import is_quiet
from organiser.services.commute import (
    LONDON,
    WEMBLEY_STOP,
    disruption_note,
    fetch_leg,
    is_ambiguous,
    move,
    tfl_clock,
    wall_exists,
)
from organiser.services.outbound import request_json_any
from organiser.services.weather import home_coordinates

logger = logging.getLogger(__name__)

HORIZON = timedelta(days=14)
STATUS_URL = "https://api.tfl.gov.uk/Line/Mode/tube,overground,elizabeth-line,dlr/Status"
ADVISORY_FRESH_SECONDS = 120.0
ADVISORY_STALE_SECONDS = 30 * 60.0
_ADVISORY_LIMIT = 4
_STOP = re.compile(r"^940[A-Z0-9]{5,16}$")
_LABEL = re.compile(r"^[A-Za-z][A-Za-z .'-]{0,39}$")

INACTIVE = "Pre-departure disruption checks are not active."
HELD = "Held for quiet hours. Nothing was sent."
PAUSED = "The house is paused. Disruption checks are not running."
WAITING = "Not in the pre-departure window."
LIMITED = "Disruption checks are waiting. The hourly limit was reached."
UNCONFIGURED = "TfL is not configured."
UNAVAILABLE = "Disruption check is unavailable."
STALE = "Showing the last disruption check. A newer read failed."
NO_ROTA = "No commute on the rota today."
NOT_CONNECTED = "Commute is not connected."

_lock = threading.Lock()
_advisory: dict[str, tuple[float, str]] = {}


def _mono() -> float:
    return time.monotonic()


def clear_advisory_cache() -> None:
    with _lock:
        _advisory.clear()


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _hm(value: datetime) -> str:
    return value.astimezone(LONDON).strftime("%H:%M")


def _day(value: datetime) -> str:
    local = value.astimezone(LONDON)
    return f"{local.strftime('%a')} {local.day} {local.strftime('%b')}"


def select_shift(rows: list[CommuteShift], now: datetime) -> CommuteShift | None:
    """The earliest shift that has not finished, inside the next 14 days.

    A shift that started yesterday and is still running is included. A shift
    that has already finished is not, so a later one can show. Anything that
    starts after the horizon stays off this reading.
    """
    local = now.astimezone(LONDON)
    horizon = local + HORIZON
    chosen: CommuteShift | None = None
    for row in rows:
        start = row.start_at.astimezone(LONDON)
        end = row.end_at.astimezone(LONDON)
        if end <= local or start > horizon:
            continue
        rank = (row.start_at, str(row.id))
        if chosen is None or rank < (chosen.start_at, str(chosen.id)):
            chosen = row
    return chosen


def classify(shift: CommuteShift, now: datetime) -> tuple[str, bool]:
    start = shift.start_at.astimezone(LONDON)
    end = shift.end_at.astimezone(LONDON)
    today = now.astimezone(LONDON).date()
    overnight = end.date() > start.date()
    if start.date() > today:
        when = "upcoming"
    elif overnight or start.date() < today:
        when = "overnight"
    else:
        when = "today"
    return when, overnight


def home_place(settings: Settings) -> dict:
    """Whether home is set. Nonempty is configured, never provider-verified.

    Coordinates are checked as numbers only. A postcode is not sent anywhere
    from this function.
    """
    kind = settings.home_location_kind
    state = "missing" if kind is None else "configured"
    if kind == "coordinates":
        lat = settings.house_lat.get_secret_value().strip()
        lon = settings.house_lon.get_secret_value().strip()
        try:
            point = (float(lat), float(lon))
        except ValueError:
            point = None
        if point is None or not (-90.0 <= point[0] <= 90.0 and -180.0 <= point[1] <= 180.0):
            state = "unusable"
    return {"state": state, "check": "not_verified", "kind": kind, "label": "Home"}


def destination_place(settings: Settings) -> dict:
    """Wembley Park unless both a station label and a stop id are set.

    A half-set override is ignored and is not echoed. The stop id stays in
    this process. The public place is the label, configured, not verified.
    """
    label = " ".join(settings.commute_destination_label.split())
    stop = settings.commute_destination_stop.strip().upper()
    if label or stop:
        if _LABEL.fullmatch(label) and _STOP.fullmatch(stop):
            return {
                "label": label,
                "stop": stop,
                "state": "configured",
                "check": "not_verified",
                "override": "used",
                "note": None,
            }
        return {
            "label": WEMBLEY_POINT,
            "stop": WEMBLEY_STOP,
            "state": "configured",
            "check": "not_verified",
            "override": "ignored",
            "note": "A partial destination override was ignored.",
        }
    return {
        "label": WEMBLEY_POINT,
        "stop": WEMBLEY_STOP,
        "state": "configured",
        "check": "not_verified",
        "override": "default",
        "note": None,
    }


def departure_deadline(target: datetime, leave_hhmm: str | None) -> datetime:
    """London instant to leave. An unknown or impossible clock uses ``target``."""
    if not leave_hhmm or len(leave_hhmm) < 5 or leave_hhmm[2] != ":":
        return target
    try:
        hour, minute = int(leave_hhmm[:2]), int(leave_hhmm[3:5])
    except ValueError:
        return target
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return target
    local = target.astimezone(LONDON)
    naive = local.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=None)
    if not wall_exists(naive):
        return target
    if is_ambiguous(naive):
        earlier = naive.replace(tzinfo=LONDON, fold=0)
        later = naive.replace(tzinfo=LONDON, fold=1)
        picked = earlier if earlier <= target else later
    else:
        picked = naive.replace(tzinfo=LONDON)
    if picked > target:
        picked = move(picked, -24 * 60)
    return picked


def in_window(now: datetime, deadline: datetime | None, minutes: int) -> bool:
    if deadline is None:
        return False
    start = deadline - timedelta(minutes=minutes)
    moment = now.astimezone(deadline.tzinfo)
    return start <= moment < deadline


def _public_place(place: dict) -> dict:
    return {
        "state": place["state"],
        "check": place["check"],
        "kind": place.get("kind"),
        "label": place["label"],
        "override": place.get("override"),
        "note": place.get("note"),
    }


def _shell(role: str, time_is: str, target: datetime, state: str, detail: str, meta: str) -> dict:
    return {
        "role": role,
        "time_is": time_is,
        "target": target,
        "clock": None,
        "minutes": None,
        "lines": [],
        "detail": detail,
        "meta": meta,
        "state": state,
    }


def _planned(role: str, time_is: str, target: datetime, raw: dict, meta: str) -> dict:
    via = f" · {', '.join(raw['lines'])}" if raw["lines"] else ""
    detail = f"{raw['minutes']} min{via}. {raw['disruptions']}"
    return {
        "role": role,
        "time_is": time_is,
        "target": target,
        "clock": raw["leave"],
        "minutes": raw["minutes"],
        "lines": list(raw["lines"]),
        "detail": detail,
        "meta": meta,
        "state": "planned",
        "disruptions": raw["disruptions"],
    }


def _advisory_view(state: str, detail: str, *, active: bool) -> dict:
    return {"active": active, "state": state, "detail": detail}


def _cached(digest: str, *, fresh: bool) -> dict | None:
    with _lock:
        entry = _advisory.get(digest)
        if entry is None:
            return None
        age = _mono() - entry[0]
    if fresh and age < ADVISORY_FRESH_SECONDS:
        return _advisory_view("fresh", entry[1], active=True)
    if not fresh and age < ADVISORY_STALE_SECONDS:
        return _advisory_view("stale", f"{STALE} {entry[1]}", active=True)
    return None


def _store(digest: str, note: str) -> None:
    with _lock:
        _advisory[digest] = (_mono(), note)
        if len(_advisory) <= _ADVISORY_LIMIT:
            return
        oldest = min(_advisory, key=lambda item: _advisory[item][0])
        _advisory.pop(oldest, None)


def predeparture_advisory(
    settings: Settings,
    now: datetime,
    *,
    paused: bool,
    deadline: datetime | None,
    lines: list[str],
) -> dict:
    """In-app note for the window before leaving. No call unless the checks are on.

    Quiet hours and a paused house skip the call. A fresh note is reused for
    two minutes. A failed newer read can keep the last note for 30 minutes and
    says so. The hourly limit is this process only. Nothing is sent.
    """
    if not settings.commute_disruption_checks:
        return _advisory_view("inactive", INACTIVE, active=False)
    if paused:
        return _advisory_view("paused", PAUSED, active=True)
    if not in_window(now, deadline, settings.commute_predeparture_minutes):
        return _advisory_view("waiting", WAITING, active=True)
    if is_quiet(now.astimezone(LONDON)):
        return _advisory_view("held", HELD, active=True)
    key = settings.tfl_app_key.get_secret_value().strip()
    if not key:
        return _advisory_view("unconfigured", UNCONFIGURED, active=True)
    digest = _digest(key)
    fresh = _cached(digest, fresh=True)
    if fresh is not None:
        return fresh
    if not LIMITS.allow("commute_disruption"):
        stale = _cached(digest, fresh=False)
        if stale is not None:
            return stale
        return _advisory_view("limited", LIMITED, active=True)
    try:
        body = request_json_any("GET", STATUS_URL, params={"app_key": key}, timeout=5.0)
        note = disruption_note(body, lines).replace(key, "")
    except Exception:
        logger.info("commute disruption check failed")
        stale = _cached(digest, fresh=False)
        if stale is not None:
            return stale
        return _advisory_view("error", UNAVAILABLE, active=True)
    _store(digest, note)
    return _advisory_view("fresh", note, active=True)


def _span(shift: CommuteShift, when: str) -> str:
    times = f"{_hm(shift.start_at)}–{_hm(shift.end_at)}"
    if when == "upcoming":
        return f"{_day(shift.start_at)} · {times}"
    return times


def _summary(label: str, span: str, outward: dict | None, back: dict | None, *, empty: str | None) -> str:
    if empty is not None:
        return empty
    assert outward is not None
    if outward["state"] == "unconnected":
        return f"{label} · {span}. Journey check is not connected."
    if outward["state"] == "no_home":
        return f"{label} · {span}. Home location is not set."
    if outward["state"] != "planned":
        return f"{label} · {span}. Journey check is unavailable."
    via = f" · {', '.join(outward['lines'])}" if outward["lines"] else ""
    disruption = outward.get("disruptions") or "Line disruptions unavailable."
    text = f"{label} · leave {outward['clock']} · {outward['minutes']} min{via}. {disruption}"
    if back is None:
        return text
    if back["state"] == "planned" and back["clock"]:
        return f"{text} Back departs {back['clock']}."
    if back["state"] == "unavailable":
        return f"{text} Return check is unavailable."
    return text


def _load_leg(settings: Settings, origin: str, destination: str, when: datetime, time_is: str, cache_key: str, meta: str, role: str):
    try:
        raw = fetch_leg(settings, origin, destination, when, time_is, cache_key)
    except Exception:
        return _shell(role, time_is, when, "unavailable", "Journey check is unavailable.", meta)
    return _planned(role, time_is, when, raw, meta)


def build_plan(session: Session, settings: Settings, now: datetime, paused: bool) -> dict:
    rows = list(session.scalars(select(CommuteShift)))
    shift = select_shift(rows, now)
    home = home_place(settings)
    destination = destination_place(settings)
    arrive_buffer = settings.commute_arrival_buffer_minutes
    return_buffer = settings.commute_return_buffer_minutes
    base = {
        "home": _public_place(home),
        "destination": _public_place(destination),
        "arrival_buffer_minutes": arrive_buffer,
        "return_buffer_minutes": return_buffer,
    }
    if shift is None:
        empty = NO_ROTA if settings.banto_configured else NOT_CONNECTED
        advisory = predeparture_advisory(settings, now, paused=paused, deadline=None, lines=[])
        return {
            **base,
            "summary": empty,
            "shift": None,
            "outward": None,
            "back": None,
            "advisory": advisory,
        }

    when, overnight = classify(shift, now)
    arrive_by = move(shift.start_at, -arrive_buffer)
    depart_at = move(shift.end_at, return_buffer)
    span = _span(shift, when)
    out_meta = f"Arrive by {_hm(arrive_by)}"
    if return_buffer == 0:
        back_meta = f"Departs at the finish {_hm(depart_at)}"
    else:
        back_meta = f"Departs {return_buffer} min after the finish"
    label = destination["label"]

    if not settings.tfl_configured:
        outward = _shell("outward", "Arriving", arrive_by, "unconnected", "Journey check is not connected.", out_meta)
        back = _shell("return", "Departing", depart_at, "unconnected", "Journey check is not connected.", back_meta)
    elif home["state"] == "missing":
        outward = _shell("outward", "Arriving", arrive_by, "no_home", "Home location is not set.", out_meta)
        back = _shell("return", "Departing", depart_at, "no_home", "Home location is not set.", back_meta)
    else:
        point = home_coordinates(settings)
        if point is None:
            home["state"] = "unusable"
            base["home"] = _public_place(home)
            outward = _shell("outward", "Arriving", arrive_by, "unavailable", "Journey check is unavailable.", out_meta)
            back = _shell("return", "Departing", depart_at, "unavailable", "Journey check is unavailable.", back_meta)
        else:
            origin = f"{point[0]:.5f},{point[1]:.5f}"
            stop = destination["stop"]
            out_day, out_clock = tfl_clock(arrive_by)
            back_day, back_clock = tfl_clock(depart_at)
            outward = _load_leg(
                settings,
                origin,
                stop,
                arrive_by,
                "Arriving",
                f"{shift.id}:out:{out_day}{out_clock}",
                out_meta,
                "outward",
            )
            back = _load_leg(
                settings,
                stop,
                origin,
                depart_at,
                "Departing",
                f"{shift.id}:back:{back_day}{back_clock}",
                back_meta,
                "return",
            )

    deadline = None
    lines: list[str] = []
    if outward is not None and outward["state"] == "planned":
        deadline = departure_deadline(arrive_by, outward["clock"])
        lines = list(outward["lines"])
    elif outward is not None:
        deadline = arrive_by
    advisory = predeparture_advisory(settings, now, paused=paused, deadline=deadline, lines=lines)
    summary = _summary(label, span, outward, back, empty=None)
    return {
        **base,
        "summary": summary,
        "shift": {
            "id": shift.id,
            "start": shift.start_at,
            "end": shift.end_at,
            "location_label": shift.location_label,
            "when": when,
            "overnight": overnight,
        },
        "outward": outward,
        "back": back,
        "advisory": advisory,
    }


def section_for_brief(session: Session, settings: Settings, today, now: datetime, paused: bool = False) -> dict:
    """Brief section. ``today`` is the house date the brief already chose."""
    del today
    plan = build_plan(session, settings, now, paused)
    items = []
    for leg in (plan["outward"], plan["back"]):
        if leg is None:
            continue
        title = "Out" if leg["role"] == "outward" else "Back"
        items.append({"title": title, "meta": leg["meta"], "detail": leg["detail"]})
    footnote = None
    if plan["shift"] is not None:
        footnote = plan["advisory"]["detail"]
    return {
        "key": "commute",
        "title": "Commute",
        "placeholder": False,
        "summary": plan["summary"],
        "items": items,
        "footnote": footnote,
    }
