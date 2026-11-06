from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from organiser.agent.rules import runs_today
from organiser.config import get_settings
from organiser.db import get_db
from organiser.schemas import HouseFacts, SystemRead
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


def _configured(flag: bool) -> str:
    return "configured" if flag else "not configured"


@router.get("", response_model=SystemRead)
def get_system(session: Session = Depends(get_db)) -> SystemRead:
    return _read(session)


@router.get("/facts", response_model=HouseFacts)
def house_facts(session: Session = Depends(get_db)) -> HouseFacts:
    """Timezone, assistant, and whether later connections have a value.

    The body is the words on the settings card. It does not include location,
    calendar ids, or tokens, and it does not call Mistral or any other service.
    """
    settings = get_settings()
    local_now = current_time()
    used = runs_today(session, local_now, settings.house_timezone)
    return HouseFacts(
        timezone=settings.house_timezone,
        assistant="on" if settings.assistant_enabled else "off",
        runs_left_today=max(0, settings.agent_runs_per_day - used),
        diary=_configured(settings.diary_configured),
        weather_location=_configured(settings.weather_location_configured),
        tfl=_configured(settings.tfl_configured),
        banto=_configured(settings.banto_configured),
    )


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
