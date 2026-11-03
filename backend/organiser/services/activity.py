"""House activity, read from the operational log.

Pause, arrival, Apply, and catch-up already write events. Add (the box, and a
task or commitment created on its own) writes one line here too.
``GET /agent/activity`` turns those lines into a short poll. It never calls Mistral.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.agent.cards import clip
from organiser.config import get_settings
from organiser.domain import DEFAULT_OWNER
from organiser.models import Event
from organiser.services.events import record_event


def activity_type(kind: str, title: str) -> str:
    """A short verb for a curator. The log kind stays what the row is about."""
    if title == "House paused":
        return "pause"
    if title == "House resumed":
        return "resume"
    if title == "Arrived home":
        return "arrival"
    if title.startswith("Catch-up:"):
        return "catchup"
    if title.startswith("Applied:"):
        return "apply"
    if title.startswith("Added:"):
        return "add"
    if title.startswith("Proposed:"):
        return "proposal"
    if kind == "approval":
        return "approval"
    return kind


def record_line(session: Session, *, kind: str, title: str, body: str) -> Event:
    return record_event(
        session,
        kind=kind,
        title=clip(title, 200),
        body=body,
        owner=DEFAULT_OWNER,
    )


def list_activity(session: Session, *, limit: int, since: datetime | None) -> list[dict]:
    statement = select(Event)
    if since is not None:
        statement = statement.where(Event.recorded_at > since)
    statement = statement.order_by(Event.recorded_at.desc(), Event.id.desc()).limit(limit)
    zone = ZoneInfo(get_settings().house_timezone)
    items = []
    for event in session.scalars(statement):
        recorded = event.recorded_at
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=ZoneInfo("UTC"))
        items.append(
            {
                "id": event.id,
                "at": recorded.astimezone(zone),
                "text": event.title,
                "type": activity_type(event.kind, event.title),
            }
        )
    return items
