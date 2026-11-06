"""Apply and Not now.

Apply makes exactly the stored change to one household row, in this database,
and writes one log line. Nothing is sent, bought or booked. Action requests and
approvals are untouched: they still only record a decision.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from organiser.agent.cards import DETAIL_LIMIT, clip, note_line, with_note
from organiser.domain import DEFAULT_OWNER
from organiser.models import AgentProposal, Commitment, ShoppingItem, Task
from organiser.schemas import (
    CommitmentCreate,
    CommitmentUpdate,
    ShoppingCreate,
    TaskCreate,
    TaskUpdate,
    apply_changes,
)
from organiser.services.events import record_event
from organiser.services.system import ensure_system_state

ASSISTANT_SOURCE = "assistant"


class ProposalNotFound(Exception):
    pass


class ProposalClosed(Exception):
    pass


class ProposalStale(Exception):
    """The row changed or went away since the proposal. The proposal is marked stale."""


class HousePaused(Exception):
    pass


class ProposalRefused(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail


def _values(payload) -> dict:
    data = payload.model_dump()
    for key, value in data.items():
        if hasattr(value, "value"):
            data[key] = value.value
    return data


def _stale(proposal: AgentProposal, now: datetime) -> ProposalStale:
    proposal.status = "stale"
    proposal.decided_at = now
    return ProposalStale(str(proposal.id))


def apply_proposal(session: Session, proposal_id: UUID, now: datetime) -> tuple[AgentProposal, dict]:
    if ensure_system_state(session).paused:
        raise HousePaused()
    proposal = session.get(AgentProposal, proposal_id, with_for_update=True)
    if proposal is None:
        raise ProposalNotFound(str(proposal_id))
    if proposal.status != "pending":
        raise ProposalClosed(proposal.status)

    changes = dict(proposal.changes)
    row: Task | Commitment | ShoppingItem
    event_kind = proposal.ref_type or "task"
    applied_type = proposal.ref_type or "task"
    if proposal.action == "create_shopping_item":
        from organiser.agent.runner import outside_home

        payload = ShoppingCreate.model_validate(changes)
        if outside_home(payload.name):
            proposal.status = "dismissed"
            proposal.decided_at = now
            raise ProposalRefused("Not for the house log. Nothing was added.")
        row = ShoppingItem(name=payload.name, ticked=False, created_at=now, updated_at=now)
        session.add(row)
        event_kind = "brief"
        applied_type = "shopping"
    elif proposal.action == "create_task":
        row = Task(**_values(TaskCreate.model_validate(changes)), created_at=now, updated_at=now)
        session.add(row)
    elif proposal.action == "create_commitment":
        payload = CommitmentCreate.model_validate({**changes, "source": ASSISTANT_SOURCE})
        row = Commitment(**_values(payload), created_at=now, updated_at=now)
        session.add(row)
    else:
        model = Task if proposal.ref_type == "task" else Commitment
        found = session.get(model, proposal.ref_id, with_for_update=True) if proposal.ref_id else None
        if found is None or found.updated_at != proposal.ref_updated_at:
            raise _stale(proposal, now)
        row = found
        if proposal.action == "add_note":
            detail = with_note(row.detail, note_line(date.fromisoformat(changes["dated"]), changes["note"]))
            if len(detail) > DETAIL_LIMIT:
                raise _stale(proposal, now)
            row.detail = detail
        elif proposal.action == "update_task":
            apply_changes(row, TaskUpdate.model_validate(changes))
        elif proposal.action == "update_commitment":
            apply_changes(row, CommitmentUpdate.model_validate(changes))
        else:
            raise ValueError(f"Unknown action {proposal.action}")
        row.updated_at = now
    session.flush()

    proposal.status = "applied"
    proposal.decided_at = now
    proposal.applied_ref_id = row.id
    record_event(
        session,
        kind=event_kind,
        title=clip(f"Applied: {proposal.summary}", 200),
        body=(
            f"Proposed by the assistant ({proposal.label}). Reason: {proposal.reason} "
            "Nothing outside the house log was changed."
        ),
        owner=DEFAULT_OWNER,
    )
    return proposal, {"ref_type": applied_type, "ref_id": row.id, "summary": proposal.summary}


def dismiss_proposal(session: Session, proposal_id: UUID, now: datetime) -> AgentProposal:
    proposal = session.get(AgentProposal, proposal_id, with_for_update=True)
    if proposal is None:
        raise ProposalNotFound(str(proposal_id))
    if proposal.status != "pending":
        raise ProposalClosed(proposal.status)
    proposal.status = "dismissed"
    proposal.decided_at = now
    return proposal
