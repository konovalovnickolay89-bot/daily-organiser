"""In-app shopping list. Names and ticks. Nothing is ordered."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from organiser.agent.runner import outside_home
from organiser.db import get_db
from organiser.models import ShoppingItem
from organiser.schemas import ShoppingCreate, ShoppingList, ShoppingRead
from organiser.timeutil import utcnow

router = APIRouter(prefix="/shopping", tags=["shopping"])


def _read(row: ShoppingItem) -> ShoppingRead:
    return ShoppingRead.model_validate(row)


@router.get("", response_model=ShoppingList)
def list_shopping(session: Session = Depends(get_db)) -> ShoppingList:
    rows = session.scalars(
        select(ShoppingItem).order_by(ShoppingItem.ticked.asc(), ShoppingItem.created_at.asc(), ShoppingItem.name.asc())
    ).all()
    return ShoppingList(items=[_read(row) for row in rows])


@router.post("", response_model=ShoppingRead, status_code=201)
def add_shopping(payload: ShoppingCreate, session: Session = Depends(get_db)) -> ShoppingRead:
    name = " ".join(payload.name.split())
    if not name:
        raise HTTPException(status_code=422, detail="Give the item a name.")
    if outside_home(name):
        raise HTTPException(status_code=422, detail="Not for the house log.")
    existing = session.scalars(
        select(ShoppingItem)
        .where(ShoppingItem.ticked.is_(False), func.lower(ShoppingItem.name) == name.casefold())
        .limit(1)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="That item is already on the list.")
    now = utcnow()
    row = ShoppingItem(name=name, ticked=False, created_at=now, updated_at=now)
    session.add(row)
    session.commit()
    return _read(row)


def _item(session: Session, item_id: UUID) -> ShoppingItem:
    row = session.get(ShoppingItem, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such item.")
    return row


@router.post("/{item_id}/tick", response_model=ShoppingRead)
def tick_shopping(item_id: UUID, session: Session = Depends(get_db)) -> ShoppingRead:
    row = _item(session, item_id)
    row.ticked = True
    row.updated_at = utcnow()
    session.commit()
    return _read(row)


@router.post("/{item_id}/untick", response_model=ShoppingRead)
def untick_shopping(item_id: UUID, session: Session = Depends(get_db)) -> ShoppingRead:
    row = _item(session, item_id)
    row.ticked = False
    row.updated_at = utcnow()
    session.commit()
    return _read(row)
