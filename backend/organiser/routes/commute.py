"""POST /commute/shift. The same check the Bantō webhook uses. Nothing is sent."""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from organiser.db import get_db
from organiser.services.commute import ShiftRefused, normalise_shift, record_shift

router = APIRouter(prefix="/commute", tags=["commute"])


@router.post("/shift")
def post_shift(payload: Any = Body(), session: Session = Depends(get_db)) -> dict:
    try:
        shift = normalise_shift(payload)
    except ShiftRefused as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    record_shift(session, shift)
    session.commit()
    return shift
