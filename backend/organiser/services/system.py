from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from organiser.config import get_settings
from organiser.domain import DEFAULT_OWNER
from organiser.models import SystemState
from organiser.services.events import record_event
from organiser.services.greeting import arrival_window_open, greeting_state
from organiser.timeutil import utcnow

QUIET_TEXT = "All quiet"
PAUSED_TEXT = "Paused"


class MissingState(Exception):
    pass


def ensure_system_state(session: Session) -> SystemState:
    row = session.get(SystemState, 1)
    if row is None:
        row = SystemState(id=1, paused=False, activity="quiet", status_text=QUIET_TEXT)
        session.add(row)
        session.flush()
    return row


def present_system(row: SystemState, now: datetime, tz_name: str) -> dict:
    greet = greeting_state(now, row.arrived_at, tz_name)
    return {
        "paused": row.paused,
        "activity": row.activity,
        "status_text": row.status_text,
        "house_date": greet["house_date"],
        "updated_at": row.updated_at,
        "greeting": greet["greeting"],
        "greeting_reason": greet["greeting_reason"],
        "arrived_at": greet["arrived_at"],
        "debounce_until": greet["debounce_until"],
        "playlist_stub": get_settings().show_playlist_stub,
    }


def record_arrival(session: Session, now: datetime, tz_name: str) -> SystemState:
    """Note an arrival for the presence bar.

    A second call inside the open hour leaves the first timestamp and does not
    write another log line. Nothing outside the house log is changed.
    """
    row = ensure_system_state(session)
    if arrival_window_open(now, row.arrived_at, tz_name):
        return row
    row.arrived_at = now.astimezone(ZoneInfo(tz_name))
    row.updated_at = utcnow()
    record_event(
        session,
        kind="system",
        title="Arrived home",
        body="Arrival noted on the presence bar for one hour. Nothing outside the house log was changed.",
        owner=DEFAULT_OWNER,
    )
    return row


def set_assistant_enabled(session: Session, enabled: bool) -> SystemState:
    """Persist the Settings switch and write one log line when it changes."""
    row = ensure_system_state(session)
    if row.assistant_enabled == enabled:
        return row
    row.assistant_enabled = enabled
    row.updated_at = utcnow()
    if enabled:
        record_event(
            session,
            kind="system",
            title="Assistant switched on",
            body="The assistant switch was turned on in Settings. Nothing was sent.",
            owner=DEFAULT_OWNER,
        )
    else:
        record_event(
            session,
            kind="system",
            title="Assistant switched off",
            body="The assistant switch was turned off in Settings. Nothing was sent.",
            owner=DEFAULT_OWNER,
        )
    return row


def assistant_effective(row: SystemState, keys_present: bool) -> bool:
    """Keys and the switch both have to be on. Pause is checked separately."""
    return bool(keys_present and row.assistant_enabled)


def set_paused(session: Session, paused: bool) -> SystemState:
    row = ensure_system_state(session)
    if row.paused == paused:
        return row
    row.paused = paused
    row.activity = "paused" if paused else "quiet"
    row.status_text = PAUSED_TEXT if paused else QUIET_TEXT
    row.updated_at = utcnow()
    if paused:
        record_event(
            session,
            kind="system",
            title="House paused",
            body="Pause set from the arrival screen. Nothing outside the house log was changed.",
            owner="Nick",
        )
    else:
        record_event(
            session,
            kind="system",
            title="House resumed",
            body="Pause cleared. The house log is quiet again. Nothing outside it was changed.",
            owner="Nick",
        )
    return row
