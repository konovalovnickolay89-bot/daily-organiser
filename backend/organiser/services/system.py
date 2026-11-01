from sqlalchemy.orm import Session

from organiser.models import SystemState
from organiser.services.events import record_event
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
