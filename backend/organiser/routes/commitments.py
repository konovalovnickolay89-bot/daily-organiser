from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.db import get_db
from organiser.domain import CommitmentStatus
from organiser.models import Commitment
from organiser.schemas import (
    CommitmentCreate,
    CommitmentList,
    CommitmentRead,
    CommitmentUpdate,
    apply_changes,
)
from organiser.services.activity import record_line

router = APIRouter(prefix="/commitments", tags=["commitments"])


def _get(session: Session, commitment_id: UUID) -> Commitment:
    row = session.get(Commitment, commitment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such commitment.")
    return row


def _values(payload: CommitmentCreate) -> dict:
    data = payload.model_dump()
    data["status"] = data["status"].value
    return data


@router.get("", response_model=CommitmentList)
def list_commitments(
    session: Session = Depends(get_db),
    status: CommitmentStatus | None = None,
    owner: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> CommitmentList:
    statement = select(Commitment)
    if status is not None:
        statement = statement.where(Commitment.status == status.value)
    if owner:
        statement = statement.where(Commitment.owner == owner)
    statement = statement.order_by(
        Commitment.due_on.asc().nulls_last(),
        Commitment.title.asc(),
    ).limit(limit)
    return CommitmentList(items=list(session.scalars(statement).all()))


@router.post("", response_model=CommitmentRead, status_code=201)
def create_commitment(payload: CommitmentCreate, session: Session = Depends(get_db)) -> Commitment:
    row = Commitment(**_values(payload))
    session.add(row)
    record_line(
        session,
        kind="commitment",
        title=f"Added: {row.title}",
        body="Added in the house log. Nothing outside it was changed.",
    )
    session.commit()
    session.refresh(row)
    return row


@router.get("/{commitment_id}", response_model=CommitmentRead)
def get_commitment(commitment_id: UUID, session: Session = Depends(get_db)) -> Commitment:
    return _get(session, commitment_id)


@router.patch("/{commitment_id}", response_model=CommitmentRead)
def update_commitment(
    commitment_id: UUID,
    payload: CommitmentUpdate,
    session: Session = Depends(get_db),
) -> Commitment:
    row = _get(session, commitment_id)
    apply_changes(row, payload)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/{commitment_id}", status_code=204)
def delete_commitment(commitment_id: UUID, session: Session = Depends(get_db)) -> None:
    row = _get(session, commitment_id)
    session.delete(row)
    session.commit()
