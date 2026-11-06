"""Household memory on the Settings screen.

List, search, pin, forget, and export. Forget writes one audit line.
Remember still arrives through the box and waits for Apply. Nothing here
calls Mistral, and the export has no embedding.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from organiser import clock
from organiser.agent.cards import clip
from organiser.agent.memory import MEMORY_TEXT_LIMIT, embed_query, forgotten_title, outside_memory
from organiser.db import get_db
from organiser.domain import DEFAULT_OWNER
from organiser.models import MemoryItem
from organiser.schemas import MemoryCreate, MemoryExport, MemoryList, MemoryPin, MemoryRead
from organiser.services.events import record_event

router = APIRouter(prefix="/memory", tags=["memory"])

NOT_HOUSE = "Not for the house log."


def _read(row: MemoryItem) -> MemoryRead:
    return MemoryRead.model_validate(row)


def _ordered():
    return select(MemoryItem).order_by(
        MemoryItem.pinned.desc(),
        MemoryItem.last_used_at.desc().nulls_last(),
        MemoryItem.created_at.desc(),
    )


@router.get("", response_model=MemoryList)
def list_memory(
    session: Session = Depends(get_db),
    q: str = Query(default="", max_length=200),
) -> MemoryList:
    """The memory list. A search is words in the text. This does not call Mistral."""
    statement = _ordered()
    term = " ".join(q.split())
    if term:
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(MemoryItem.text.ilike(f"%{escaped}%", escape="\\"))
    rows = session.scalars(statement.limit(200)).all()
    return MemoryList(items=[_read(row) for row in rows])


@router.get("/export", response_model=MemoryExport)
def export_memory(session: Session = Depends(get_db)) -> MemoryExport:
    """JSON of the memories. Embeddings stay in the database."""
    rows = session.scalars(_ordered()).all()
    return MemoryExport(exported_at=clock.current_time(), items=[_read(row) for row in rows])


@router.post("", response_model=MemoryRead, status_code=201)
def create_memory(payload: MemoryCreate, session: Session = Depends(get_db)) -> MemoryRead:
    """A manual line. The box's remember path does not use this."""
    text = " ".join(payload.text.split())
    if not text or len(text) > MEMORY_TEXT_LIMIT or outside_memory(text):
        raise HTTPException(status_code=422, detail=NOT_HOUSE if outside_memory(text) else "Keep a memory to a short line.")
    existing = session.scalar(select(MemoryItem.id).where(func.lower(MemoryItem.text) == text.lower()).limit(1))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already remembered.")
    now = clock.current_time()
    row = MemoryItem(
        kind=payload.kind,
        text=text,
        source="manual",
        created_at=now,
        pinned=False,
        embedding=embed_query(text),
    )
    session.add(row)
    session.commit()
    return _read(row)


@router.patch("/{item_id}", response_model=MemoryRead)
def pin_memory(item_id: UUID, payload: MemoryPin, session: Session = Depends(get_db)) -> MemoryRead:
    row = session.get(MemoryItem, item_id, with_for_update=True)
    if row is None:
        raise HTTPException(status_code=404, detail="No such memory.")
    row.pinned = payload.pinned
    session.commit()
    return _read(row)


@router.delete("/{item_id}", status_code=200)
def forget_memory(item_id: UUID, session: Session = Depends(get_db)) -> dict:
    """Forget one line after the screen has confirmed it. Writes one audit line."""
    row = session.get(MemoryItem, item_id, with_for_update=True)
    if row is None:
        raise HTTPException(status_code=404, detail="No such memory.")
    title, body = forgotten_title([row.text])
    session.delete(row)
    record_event(session, kind="note", title=clip(title, 200), body=body, owner=DEFAULT_OWNER)
    session.commit()
    return {"forgotten": True}
