from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from organiser.config import get_settings
from organiser.db import get_db
from organiser.schemas import SystemRead
from organiser.services.system import ensure_system_state, set_paused
from organiser.timeutil import house_today

router = APIRouter(prefix="/system", tags=["system"])


def _read(session: Session) -> SystemRead:
    row = ensure_system_state(session)
    session.commit()
    return SystemRead(
        paused=row.paused,
        activity=row.activity,
        status_text=row.status_text,
        house_date=house_today(get_settings().house_timezone),
        updated_at=row.updated_at,
    )


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
