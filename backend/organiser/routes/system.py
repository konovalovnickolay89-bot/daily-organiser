from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from organiser.config import get_settings
from organiser.db import get_db
from organiser.schemas import SystemRead
from organiser.services.system import ensure_system_state, present_system, record_arrival, set_paused
from organiser.timeutil import house_now

router = APIRouter(prefix="/system", tags=["system"])


def current_time() -> datetime:
    return house_now(get_settings().house_timezone)


def _read(session: Session) -> SystemRead:
    row = ensure_system_state(session)
    session.commit()
    payload = present_system(row, current_time(), get_settings().house_timezone)
    return SystemRead.model_validate(payload)


@router.get("", response_model=SystemRead)
def get_system(session: Session = Depends(get_db)) -> SystemRead:
    return _read(session)


@router.post("/pause", response_model=SystemRead)
def pause(session: Session = Depends(get_db)) -> SystemRead:
    set_paused(session, True)
    session.commit()
    return _read(session)


@router.post("/unpause", response_model=SystemRead)
def unpause(session: Session = Depends(get_db)) -> SystemRead:
    set_paused(session, False)
    session.commit()
    return _read(session)


@router.post("/arrive", response_model=SystemRead)
def arrive(session: Session = Depends(get_db)) -> SystemRead:
    """House arrival stub.

    Records one arrival and opens the "Welcome home" hour. A repeat inside
    that hour is ignored. This does not call out of the house.
    """
    record_arrival(session, current_time(), get_settings().house_timezone)
    session.commit()
    return _read(session)
