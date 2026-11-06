"""In-app alert cards. They are computed, deduped, and dismissible.

Nothing here sends, buys, books, or emails. A dismissal is one row in this database.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.config import get_settings
from organiser.metrics import FAILURE_WINDOW, METRICS, POLL_STALE
from organiser.models import AlertDismissal

KINDS = ("mistral_failing", "activity_poll", "database_error")

# Monday–Friday, 06:00–21:59 in the house timezone. The same hours as a
# proactive review. Nights and weekends do not raise the poll card.
WEEKDAY_HOURS = (6, 22)

_COPY = {
    "mistral_failing": (
        "Assistant failing",
        "Mistral failed 3 or more times in 15 minutes. Nothing was sent.",
    ),
    "activity_poll": (
        "Activity poll is quiet",
        "No activity poll for over 2 hours. Nothing was sent.",
    ),
    "database_error": (
        "Database error",
        "The house database reported an error. Nothing was sent.",
    ),
}


def _signature(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo("UTC"))
    return moment.isoformat(timespec="seconds")


def in_weekday_window(now: datetime) -> bool:
    settings = get_settings()
    local = now.astimezone(ZoneInfo(settings.house_timezone))
    return local.weekday() < 5 and WEEKDAY_HOURS[0] <= local.hour < WEEKDAY_HOURS[1]


def _candidates(now: datetime) -> list[dict]:
    found: list[dict] = []
    failures = METRICS.failures_in_window(now)
    if len(failures) >= 3:
        found.append(_card("mistral_failing", _signature(min(failures))))
    mark = METRICS.last_poll or METRICS.started_at
    if in_weekday_window(now) and now - mark > POLL_STALE:
        found.append(_card("activity_poll", _signature(mark)))
    error = METRICS.last_db_error
    if error is not None and now - error <= FAILURE_WINDOW:
        found.append(_card("database_error", _signature(error)))
    return found


def _card(kind: str, signature: str) -> dict:
    title, detail = _COPY[kind]
    return {"kind": kind, "title": title, "detail": detail, "signature": signature}


def _dismissed(session: Session) -> dict[str, str]:
    rows = session.scalars(select(AlertDismissal)).all()
    return {row.kind: row.signature for row in rows}


def active_alerts(session: Session, now: datetime) -> list[dict]:
    """One card per kind. A dismissed signature stays hidden until the incident changes."""
    from organiser.services.settings import alerts_enabled

    if not alerts_enabled(session):
        return []
    hidden = _dismissed(session)
    shown = []
    for card in _candidates(now):
        if hidden.get(card["kind"]) == card["signature"]:
            continue
        shown.append({"kind": card["kind"], "title": card["title"], "detail": card["detail"]})
    return shown


class AlertNotActive(Exception):
    """That card is not showing. Nothing was dismissed."""


def dismiss_alert(session: Session, kind: str, now: datetime) -> list[dict]:
    if kind not in KINDS:
        raise AlertNotActive()
    current = next((card for card in _candidates(now) if card["kind"] == kind), None)
    if current is None:
        raise AlertNotActive()
    row = session.get(AlertDismissal, kind)
    if row is None:
        session.add(AlertDismissal(kind=kind, signature=current["signature"], dismissed_at=now))
    else:
        row.signature = current["signature"]
        row.dismissed_at = now
    session.flush()
    return active_alerts(session, now)
