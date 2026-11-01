from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.db import get_db
from organiser.domain import ActionStatus
from organiser.models import ActionRequest
from organiser.schemas import ActionRequestList, ActionRequestRead, ApprovalDecision, EffectResult
from organiser.services.approvals import AlreadyDecided, ApprovalNotFound, decide

router = APIRouter(prefix="/approvals", tags=["approvals"])

_STATUSES = {item.value for item in ActionStatus} | {"all"}


@router.get("", response_model=ActionRequestList)
def list_approvals(
    session: Session = Depends(get_db),
    status: str = Query(default="pending", description="pending, approved, skipped, or all"),
    limit: int = Query(default=100, ge=1, le=200),
) -> ActionRequestList:
    if status not in _STATUSES:
        raise HTTPException(status_code=422, detail="Status must be pending, approved, skipped, or all.")
    statement = select(ActionRequest)
    if status != "all":
        statement = statement.where(ActionRequest.status == status)
    statement = statement.order_by(ActionRequest.created_at.asc(), ActionRequest.title.asc()).limit(limit)
    return ActionRequestList(items=list(session.scalars(statement).all()))


def _decide(session: Session, action_id: UUID, decision: str) -> ApprovalDecision:
    try:
        row, effect = decide(session, action_id, decision)
    except ApprovalNotFound:
        raise HTTPException(status_code=404, detail="No such approval.") from None
    except AlreadyDecided:
        raise HTTPException(status_code=409, detail="This has already been decided.") from None
    session.commit()
    session.refresh(row)
    recorded = ActionRequestRead.model_validate(row)
    return ApprovalDecision(**recorded.model_dump(), effect=EffectResult.model_validate(effect))


@router.post("/{action_id}/approve", response_model=ApprovalDecision)
def approve(action_id: UUID, session: Session = Depends(get_db)) -> ApprovalDecision:
    return _decide(session, action_id, "approve")


@router.post("/{action_id}/skip", response_model=ApprovalDecision)
def skip(action_id: UUID, session: Session = Depends(get_db)) -> ApprovalDecision:
    return _decide(session, action_id, "skip")
