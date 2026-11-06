"""One pending task card from a curator. Nothing is created until Apply.

This does not call Mistral and does not open an agent run. Apply uses the
same allowlist as every other card.
"""

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from organiser.agent.cards import summarise
from organiser.agent.runner import outside_home
from organiser.models import AgentProposal, Commitment, Task
from organiser.services.activity import record_line
from organiser.services.system import ensure_system_state

MAX_PENDING_PROPOSALS = 10
DEFAULT_REASON = "Noted for the house log."
DEFAULT_LABEL = "Noted"


class IngestRefused(Exception):
    def __init__(self, detail: str, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _one_line(text: str | None) -> str:
    return " ".join((text or "").split())


def ingest_proposal(
    session: Session,
    *,
    title: str,
    due_on: date | None,
    reason: str | None,
    source: str | None,
    now: datetime,
) -> AgentProposal:
    if ensure_system_state(session).paused:
        raise IngestRefused("The house is paused. Nothing was proposed.", 409)

    title = _one_line(title)
    if not title:
        raise IngestRefused("Give the proposal a title.", 422)

    reason_text = _one_line(reason) or DEFAULT_REASON
    source_text = _one_line(source)
    label = source_text or DEFAULT_LABEL
    if outside_home(" ".join(part for part in (title, reason_text, source_text) if part)):
        raise IngestRefused("Not for the house log.", 422)

    lowered = title.lower()
    open_task = session.scalars(
        select(Task).where(Task.status != "done", func.lower(Task.title) == lowered).limit(1)
    ).first()
    if open_task is not None:
        raise IngestRefused(
            f"An open task already has that title (id {open_task.id}). Propose an edit or a note instead.",
            409,
        )
    open_commitment = session.scalars(
        select(Commitment).where(Commitment.status == "open", func.lower(Commitment.title) == lowered).limit(1)
    ).first()
    if open_commitment is not None:
        raise IngestRefused(
            f"An open commitment already has that title (id {open_commitment.id}). Propose an edit or a note instead.",
            409,
        )
    waiting = session.scalars(
        select(AgentProposal)
        .where(
            AgentProposal.status == "pending",
            AgentProposal.action == "create_task",
            func.lower(AgentProposal.changes["title"].astext) == lowered,
        )
        .limit(1)
    ).first()
    if waiting is not None:
        raise IngestRefused("The same new task is already waiting as a proposal.", 409)

    pending = (
        session.scalar(select(func.count()).select_from(AgentProposal).where(AgentProposal.status == "pending")) or 0
    )
    if pending >= MAX_PENDING_PROPOSALS:
        raise IngestRefused("The proposal list is full. Apply or dismiss a card first.", 409)

    changes: dict = {"title": title}
    if due_on is not None:
        changes["due_on"] = due_on.isoformat()
    summary = summarise("create_task", changes, None)
    proposal = AgentProposal(
        run_id=None,
        origin="ingest",
        rule="feed",
        label=label,
        action="create_task",
        ref_type="task",
        ref_id=None,
        changes=changes,
        summary=summary,
        reason=reason_text,
        ref_updated_at=None,
        status="pending",
        created_at=now,
    )
    session.add(proposal)
    record_line(
        session,
        kind="note",
        title=f"Proposed: {summary}",
        body=(
            f"A card is waiting ({label}). Reason: {reason_text} "
            "Nothing was created. Apply makes the one change."
        ),
    )
    session.flush()
    return proposal
