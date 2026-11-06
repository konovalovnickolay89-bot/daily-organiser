"""X connect, the watch list, cards, and the one confirmed post."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from organiser import clock
from organiser.config import get_settings
from organiser.db import get_db
from organiser.schemas import (
    XCardList,
    XConnectRead,
    XDecisionRead,
    XPollRead,
    XPostWrite,
    XStatusRead,
    XWatchRead,
    XWatchWrite,
)
from organiser.x.oauth import (
    begin,
    disconnect,
    exchange_and_store,
    status_view,
    take_verifier,
)
from organiser.x.poll import poll, post_draft
from organiser.x.store import XRejected, add_watch, apply_item, card_body, cards, dismiss_item, remove_watch

router = APIRouter(prefix="/x", tags=["x"])


def _now():
    return clock.current_time()


def _rejected(exc: XRejected) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.detail)


def _guard_enabled() -> None:
    if not get_settings().x_enabled:
        raise HTTPException(status_code=404, detail="X is off.")


@router.get("/status", response_model=XStatusRead)
def x_status(session: Session = Depends(get_db)) -> XStatusRead:
    """Whether X is on, and the handle when it is connected. No token."""
    return XStatusRead.model_validate(status_view(session, get_settings()))


@router.post("/connect", response_model=XConnectRead)
def x_connect(session: Session = Depends(get_db)) -> XConnectRead:
    settings = get_settings()
    try:
        url = begin(session, settings, _now())
    except XRejected as exc:
        raise _rejected(exc) from None
    session.commit()
    return XConnectRead(authorize_url=url)


@router.get("/callback", include_in_schema=True)
def x_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_db),
):
    """Finish PKCE. The browser is sent back to the arrival screen. The code is not logged."""
    settings = get_settings()
    if not settings.x_enabled:
        return RedirectResponse("/?x=failed", status_code=303)
    if error:
        target = "/?x=denied" if error == "access_denied" else "/?x=failed"
        return RedirectResponse(target, status_code=303)
    if not code or not state:
        return RedirectResponse("/?x=failed", status_code=303)
    now = _now()
    try:
        verifier = take_verifier(session, settings, state, now)
        session.commit()
    except XRejected:
        session.rollback()
        return RedirectResponse("/?x=failed", status_code=303)
    try:
        exchange_and_store(session, settings, code, verifier, now)
        session.commit()
    except Exception:
        session.rollback()
        return RedirectResponse("/?x=failed", status_code=303)
    return RedirectResponse("/?x=connected", status_code=303)


@router.post("/disconnect", response_model=XStatusRead)
def x_disconnect(session: Session = Depends(get_db)) -> XStatusRead:
    settings = get_settings()
    try:
        disconnect(session, settings)
    except XRejected as exc:
        raise _rejected(exc) from None
    session.commit()
    return XStatusRead.model_validate(status_view(session, settings))


@router.post("/watches", response_model=XWatchRead)
def x_add_watch(payload: XWatchWrite, session: Session = Depends(get_db)) -> XWatchRead:
    _guard_enabled()
    try:
        row = add_watch(session, payload.kind, payload.value, _now())
    except XRejected as exc:
        raise _rejected(exc) from None
    session.commit()
    return XWatchRead(id=row.id, kind=row.kind, value=row.value)


@router.delete("/watches/{watch_id}", response_model=XStatusRead)
def x_remove_watch(watch_id: UUID, session: Session = Depends(get_db)) -> XStatusRead:
    _guard_enabled()
    settings = get_settings()
    try:
        remove_watch(session, watch_id)
    except XRejected as exc:
        raise _rejected(exc) from None
    session.commit()
    return XStatusRead.model_validate(status_view(session, settings))


@router.get("/items", response_model=XCardList)
def x_items(session: Session = Depends(get_db)) -> XCardList:
    settings = get_settings()
    if not settings.x_enabled:
        return XCardList(enabled=False, items=[])
    now = _now()
    rows = cards(session, now)
    session.commit()
    return XCardList(enabled=True, items=[card_body(row) for row in rows])


@router.post("/poll", response_model=XPollRead)
def x_poll(session: Session = Depends(get_db)) -> XPollRead:
    """Poll when the interval has elapsed. A quiet house or a backoff does not call X."""
    result = poll(session, get_settings(), _now())
    session.commit()
    return XPollRead.model_validate(result)


@router.post("/items/{item_id}/apply", response_model=XDecisionRead)
def x_apply(item_id: UUID, session: Session = Depends(get_db)) -> XDecisionRead:
    _guard_enabled()
    try:
        row = apply_item(session, item_id, _now())
    except XRejected as exc:
        raise _rejected(exc) from None
    session.commit()
    return XDecisionRead(id=row.id, status=row.status)


@router.post("/items/{item_id}/dismiss", response_model=XDecisionRead)
def x_dismiss(item_id: UUID, session: Session = Depends(get_db)) -> XDecisionRead:
    _guard_enabled()
    try:
        row = dismiss_item(session, item_id, _now())
    except XRejected as exc:
        raise _rejected(exc) from None
    session.commit()
    return XDecisionRead(id=row.id, status=row.status)


@router.post("/items/{item_id}/post", response_model=XDecisionRead)
def x_post(item_id: UUID, payload: XPostWrite, session: Session = Depends(get_db)) -> XDecisionRead:
    """Post one draft. confirm has to be true. Nothing is sent otherwise."""
    try:
        row = post_draft(session, get_settings(), item_id, _now(), confirm=payload.confirm)
    except XRejected as exc:
        if exc.persist:
            session.commit()
        raise _rejected(exc) from None
    session.commit()
    return XDecisionRead(id=row.id, status=row.status, tweet_id=row.posted_tweet_id)
