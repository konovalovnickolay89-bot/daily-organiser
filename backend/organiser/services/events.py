from sqlalchemy.orm import Session

from organiser.models import Event
from organiser.timeutil import utcnow


def record_event(
    session: Session,
    *,
    kind: str,
    title: str,
    body: str | None,
    owner: str | None,
) -> Event:
    event = Event(
        kind=kind,
        title=title,
        body=body,
        owner=owner,
        recorded_at=utcnow(),
    )
    session.add(event)
    return event
