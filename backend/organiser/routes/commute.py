"""A shift push from the house rota.

Authenticated by the bearer in ``BANTO_COMMUTE_TOKEN``. The body is start, end,
and location_label. Anything else is refused. A missing token answers 503 and
stores nothing. The journey lookup is not done here.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from organiser.config import get_settings
from organiser.db import get_db
from organiser.limits import LIMITS
from organiser.schemas import ShiftPush, ShiftRead
from organiser.services.commute import ShiftRejected, store_shift

router = APIRouter(prefix="/commute", tags=["commute"])

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
