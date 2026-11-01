"""Presence-bar headline.

The string is decided here, on the house clock (Europe/London by default).
A fresh arrival shows "Welcome home" until an hour has passed. The clock alone
never produces that line. From 22:00 to 04:59 the headline is the resident's
name: the presence bar already shows the house date beside Home.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from organiser.domain import DEFAULT_OWNER

ARRIVAL_DEBOUNCE = timedelta(hours=1)

WELCOME_HOME = "Welcome home"
GOOD_MORNING = "Good morning"
GOOD_AFTERNOON = "Good afternoon"
GOOD_EVENING = "Good evening"


def _in_zone(value: datetime, zone: ZoneInfo) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(zone)


def time_of_day_greeting(local: datetime, resident: str = DEFAULT_OWNER) -> str:
    """Headline for a house-local clock with no open arrival window."""
    hour = local.hour
    if 5 <= hour < 12:
        return GOOD_MORNING
    if 12 <= hour < 17:
        return GOOD_AFTERNOON
    if 17 <= hour < 22:
        return GOOD_EVENING
    return resident


def greeting_state(
    now: datetime,
    arrived_at: datetime | None,
    tz_name: str,
    resident: str = DEFAULT_OWNER,
) -> dict:
    """Greeting fields for one presence-bar read.

    The arrival window is half-open: ``[arrived_at, arrived_at + 1 hour)``.
    A later instant at exactly one hour uses the time of day again.
    ``arrived_at`` and ``debounce_until`` stay populated after the window
    closes so a repeat signal can be told from the first one.
    """
    zone = ZoneInfo(tz_name)
    local_now = _in_zone(now, zone)
    arrived = _in_zone(arrived_at, zone) if arrived_at is not None else None
    until = arrived + ARRIVAL_DEBOUNCE if arrived is not None else None
    window_open = arrived is not None and until is not None and arrived <= local_now < until
    if window_open:
        greeting = WELCOME_HOME
        reason = "arrival"
    else:
        greeting = time_of_day_greeting(local_now, resident)
        reason = "time_of_day"
    return {
        "greeting": greeting,
        "greeting_reason": reason,
        "arrived_at": arrived,
        "debounce_until": until,
        "house_date": local_now.date(),
    }


def arrival_window_open(now: datetime, arrived_at: datetime | None, tz_name: str) -> bool:
    return greeting_state(now, arrived_at, tz_name)["greeting_reason"] == "arrival"
