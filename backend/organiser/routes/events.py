from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.db import get_db
from organiser.domain import EventKind
from organiser.models import Event
from organiser.schemas import EventCreate, EventList, EventRead, EventUpdate, apply_changes
from organiser.scope import require_house_fields
from organiser.timeutil import utcnow

router = APIRouter(prefix="/events", tags=["events"])


def _get(session: Session, event_id: UUID) -> Event:
    row = session.get(Event, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such event.")
    return row


def _values(payload: EventCreate) -> dict:
    data = payload.model_dump()
    data["kind"] = data["kind"].value
    if data["recorded_at"] is None:
        data["recorded_at"] = utcnow()
    return data


@router.get("", response_model=EventList)
def list_events(
    session: Session = Depends(get_db),
    kind: EventKind | None = None,
    owner: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> EventList:
    statement = select(Event)
    if kind is not None:
        statement = statement.where(Event.kind == kind.value)
    if owner:
        statement = statement.where(Event.owner == owner)
    statement = statement.order_by(Event.recorded_at.desc(), Event.title.asc()).limit(limit)
    return EventList(items=list(session.scalars(statement).all()))


@router.post("", response_model=EventRead, status_code=201)
def create_event(payload: EventCreate, session: Session = Depends(get_db)) -> Event:
    require_house_fields(payload, "title", "body", "owner")
    row = Event(**_values(payload))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/{event_id}", response_model=EventRead)
def get_event(event_id: UUID, session: Session = Depends(get_db)) -> Event:
    return _get(session, event_id)


@router.patch("/{event_id}", response_model=EventRead)
def update_event(event_id: UUID, payload: EventUpdate, session: Session = Depends(get_db)) -> Event:
    require_house_fields(payload, "title", "body", "owner")
    row = _get(session, event_id)
    apply_changes(row, payload)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: UUID, session: Session = Depends(get_db)) -> None:
    row = _get(session, event_id)
    session.delete(row)
    session.commit()
