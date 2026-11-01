from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.db import get_db
from organiser.domain import ActionMode, ActionStatus
from organiser.models import ActionRequest
from organiser.schemas import (
    ActionRequestCreate,
    ActionRequestList,
    ActionRequestRead,
    ActionRequestUpdate,
    apply_changes,
)
from organiser.timeutil import utcnow

router = APIRouter(prefix="/action-requests", tags=["action requests"])


def _get(session: Session, request_id: UUID) -> ActionRequest:
    row = session.get(ActionRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such action request.")
    return row


def _values(payload: ActionRequestCreate) -> dict:
    data = payload.model_dump()
    data["mode"] = data["mode"].value
    data["status"] = data["status"].value
    data["effect_applied"] = False
    if data["status"] != "pending":
        data["decided_at"] = utcnow()
    return data


@router.get("", response_model=ActionRequestList)
def list_action_requests(
    session: Session = Depends(get_db),
    status: ActionStatus | None = None,
    mode: ActionMode | None = None,
    owner: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> ActionRequestList:
    statement = select(ActionRequest)
    if status is not None:
        statement = statement.where(ActionRequest.status == status.value)
    if mode is not None:
        statement = statement.where(ActionRequest.mode == mode.value)
    if owner:
        statement = statement.where(ActionRequest.owner == owner)
    statement = statement.order_by(ActionRequest.created_at.asc(), ActionRequest.title.asc()).limit(limit)
    return ActionRequestList(items=list(session.scalars(statement).all()))


@router.post("", response_model=ActionRequestRead, status_code=201)
def create_action_request(payload: ActionRequestCreate, session: Session = Depends(get_db)) -> ActionRequest:
    row = ActionRequest(**_values(payload))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/{request_id}", response_model=ActionRequestRead)
def get_action_request(request_id: UUID, session: Session = Depends(get_db)) -> ActionRequest:
    return _get(session, request_id)


@router.patch("/{request_id}", response_model=ActionRequestRead)
def update_action_request(
    request_id: UUID,
    payload: ActionRequestUpdate,
    session: Session = Depends(get_db),
) -> ActionRequest:
    row = _get(session, request_id)
    previous = row.status
    apply_changes(row, payload)
    if row.status != previous and row.status != "pending" and row.decided_at is None:
        row.decided_at = utcnow()
    if row.status == "pending":
        row.decided_at = None
        row.resolution = None
    row.effect_applied = False
    session.commit()
    session.refresh(row)
    return row


@router.delete("/{request_id}", status_code=204)
def delete_action_request(request_id: UUID, session: Session = Depends(get_db)) -> None:
    row = _get(session, request_id)
    session.delete(row)
    session.commit()
