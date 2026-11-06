"""Catch-up on the arrival screen.

GET only reads and never calls Mistral. POST /catch-up/look records a look and
may open one pass. When the assistant is on, that pass asks Mistral for the
note wording. If it is off or does not answer, the template is used and the
card is marked. Apply and Not now are the two taps. Neither sends, buys, or books.
"""

from collections.abc import Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from organiser import clock
from organiser.agent.mistral import MistralClient
from organiser.agent.wording import write_notes
from organiser.config import get_settings
from organiser.db import get_db, get_sessionmaker
from organiser.schemas import AppliedChange, CatchUpApplyResult, CatchUpItemRead, CatchUpRead
from organiser.services.catchup import (
    CatchUpClosed,
    CatchUpNotFound,
    CatchUpPaused,
    CatchUpStale,
    apply_item,
    dismiss_item,
    read_catchup,
    record_look,
)
from organiser.services.system import ensure_system_state

router = APIRouter(prefix="/catch-up", tags=["catch-up"])

PAUSED = "The house is paused. Nothing was changed."
STALE = "The item changed since this was prepared. Nothing was applied."


def get_note_client() -> Iterator[MistralClient | None]:
    """A client for catch-up wording, or None when the assistant is off."""
    settings = get_settings()
    if not settings.assistant_enabled:
        yield None
        return
    session = get_sessionmaker()()
    try:
        enabled = ensure_system_state(session).assistant_enabled
        session.commit()
    finally:
        session.close()
    if not enabled:
        yield None
        return
    client = MistralClient(
        settings.mistral_api_key.get_secret_value(),
        settings.mistral_base_url,
        settings.mistral_timeout_seconds,
    )
    try:
        yield client
    finally:
        client.close()


def _writer(client: MistralClient | None):
    if client is None:
        return None

    def write(drafts):
        return write_notes(client, get_settings(), drafts)

    return write


def _read(payload: dict) -> CatchUpRead:
    return CatchUpRead(
        paused=payload["paused"],
        quiet=payload["quiet"],
        as_of=payload["as_of"],
        house_date=payload["house_date"],
        items=[CatchUpItemRead.model_validate(item) for item in payload["items"]],
    )


@router.get("", response_model=CatchUpRead)
def get_catchup(session: Session = Depends(get_db)) -> CatchUpRead:
    """Pending cards, when the rules say to show them. Does not record a look."""
    payload = read_catchup(session, clock.current_time())
    session.commit()
    return _read(payload)


@router.post("/look", response_model=CatchUpRead)
def look(
    session: Session = Depends(get_db),
    client: MistralClient | None = Depends(get_note_client),
) -> CatchUpRead:
    """Record a look. After a gap, prepare one catch-up. Two tabs share it."""
    payload = record_look(session, clock.current_time(), _writer(client))
    session.commit()
    return _read(payload)


@router.post("/items/{item_id}/apply", response_model=CatchUpApplyResult)
def apply(item_id: UUID, session: Session = Depends(get_db)) -> CatchUpApplyResult:
    """Add the note on this card to one task or commitment."""
    now = clock.current_time()
    try:
        item, applied = apply_item(session, item_id, now)
    except CatchUpPaused:
        raise HTTPException(status_code=409, detail=PAUSED) from None
    except CatchUpNotFound:
        raise HTTPException(status_code=404, detail="No such catch-up.") from None
    except CatchUpClosed:
        raise HTTPException(status_code=409, detail="This has already been decided.") from None
    except CatchUpStale:
        session.commit()
        raise HTTPException(status_code=409, detail=STALE) from None
    session.commit()
    return CatchUpApplyResult(item=CatchUpItemRead.model_validate(item), applied=AppliedChange(**applied))


@router.post("/items/{item_id}/dismiss", response_model=CatchUpItemRead)
def dismiss(item_id: UUID, session: Session = Depends(get_db)) -> CatchUpItemRead:
    """Not now. The item rests for 72 hours."""
    try:
        item = dismiss_item(session, item_id, clock.current_time())
    except CatchUpPaused:
        raise HTTPException(status_code=409, detail=PAUSED) from None
    except CatchUpNotFound:
        raise HTTPException(status_code=404, detail="No such catch-up.") from None
    except CatchUpClosed:
        raise HTTPException(status_code=409, detail="This has already been decided.") from None
    session.commit()
    return CatchUpItemRead.model_validate(item)
