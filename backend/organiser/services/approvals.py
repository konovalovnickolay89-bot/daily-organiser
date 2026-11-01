from uuid import UUID

from sqlalchemy.orm import Session

from organiser.domain import DECISION_SUMMARIES, SKIP_SUMMARY
from organiser.models import ActionRequest
from organiser.services.events import record_event
from organiser.timeutil import utcnow


class ApprovalNotFound(Exception):
    pass


class AlreadyDecided(Exception):
    pass


def decide(session: Session, action_id: UUID, decision: str) -> tuple[ActionRequest, dict]:
    row = session.get(ActionRequest, action_id)
    if row is None:
        raise ApprovalNotFound(str(action_id))
    if row.status != "pending":
        raise AlreadyDecided(row.status)

    if decision == "approve":
        row.status = "approved"
        summary = DECISION_SUMMARIES[row.mode]
        verb = "Approved"
    elif decision == "skip":
        row.status = "skipped"
        summary = SKIP_SUMMARY
        verb = "Skipped"
    else:
        raise ValueError(f"Unknown decision {decision}")

    row.resolution = summary
    row.decided_at = utcnow()
    row.updated_at = row.decided_at
    # effect_applied stays false. There is no dispatcher and no outside call.
    record_event(
        session,
        kind="approval",
        title=f"{verb}: {row.title}",
        body=f"{row.mode}. {summary}",
        owner=row.owner,
    )
    return row, {"applied": False, "summary": summary}
