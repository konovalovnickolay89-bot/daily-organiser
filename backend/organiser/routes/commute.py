"""A shift push from the house rota, and a reading of the round trip.

``POST /shift`` is authenticated by the bearer in ``BANTO_COMMUTE_TOKEN``. The
body is start, end, and location_label. Anything else is refused. A missing
token answers 503 and stores nothing. The journey lookup is not done on that
post. ``GET /plan`` is the reading. It does not store a shift.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from organiser import clock
from organiser.config import get_settings
from organiser.db import get_db
from organiser.limits import LIMITS
from organiser.models import SystemState
from organiser.schemas import CommutePlanRead, ShiftPush, ShiftRead
from organiser.services.commute import ShiftRejected, store_shift
from organiser.services.commute_plan import build_plan

router = APIRouter(prefix="/commute", tags=["commute"])


@router.get("/plan", response_model=CommutePlanRead)
def read_plan(session: Session = Depends(get_db)) -> CommutePlanRead:
    """The next round trip. No body. Does not store a shift, send, or book.

    TfL is asked only when a key is set and a shift needs a journey. The
    pre-departure check runs only when ``COMMUTE_DISRUPTION_CHECKS`` is on,
    and only inside this read. There is no scheduler. This does not call Mistral.
    """
    row = session.get(SystemState, 1)
    paused = bool(row.paused) if row is not None else False
    plan = build_plan(session, get_settings(), clock.current_time(), paused)
    return CommutePlanRead.model_validate(plan)

NOT_CONFIGURED = "Commute push is not configured."
REFUSED = "Commute push was refused."
TOO_MANY = "Too many shift updates. Nothing was stored."


def _authorised(request: Request) -> None:
    settings = get_settings()
    expected = settings.banto_commute_token.get_secret_value().strip()
    if not expected:
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED)
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token or not secrets.compare_digest(token.strip().encode(), expected.encode()):
        raise HTTPException(status_code=401, detail=REFUSED)


@router.post("/shift", response_model=ShiftRead, status_code=201)
def push_shift(payload: ShiftPush, request: Request, session: Session = Depends(get_db)) -> ShiftRead:
    """Store one house commute. Only start, end, and the location label are kept."""
    _authorised(request)
    if not LIMITS.allow("commute"):
        raise HTTPException(status_code=429, detail=TOO_MANY)
    try:
        row = store_shift(session, payload.start, payload.end, payload.location_label)
    except ShiftRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    session.commit()
    return ShiftRead(
        id=row.id,
        start=row.start_at,
        end=row.end_at,
        location_label=row.location_label,
    )
