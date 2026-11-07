from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from organiser import __version__
from organiser import clock as house_clock
from organiser.agent.rules import runs_today
from organiser.config import get_settings
from organiser.db import get_db
from organiser.metrics import METRICS
from organiser.schemas import (
    AssistantSwitch,
    CalendarListRead,
    CalendarName,
    HouseFacts,
    LocalReminderWrite,
    StatusRead,
    SystemRead,
)
from organiser.services.diary import DiaryError, add_calendar, calendar_view, remove_calendar
from organiser.services.system import (
    assistant_effective,
    ensure_system_state,
    present_system,
    record_arrival,
    set_assistant_enabled,
    set_paused,
)
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


def _reminder_words(session: Session) -> dict:
    from organiser.agent.local_reminders import reminder_flags

    return reminder_flags(session).as_words()


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
    row = ensure_system_state(session)
    used = runs_today(session, local_now, settings.house_timezone)
    switch = "on" if row.assistant_enabled else "off"
    return HouseFacts(
        timezone=settings.house_timezone,
        assistant="on" if assistant_effective(row, settings.assistant_enabled) else "off",
        assistant_switch=switch,
        runs_left_today=max(0, settings.agent_runs_per_day - used),
        diary=_configured(settings.diary_configured),
        weather_location=_configured(settings.weather_location_configured),
        tfl=_configured(settings.tfl_configured),
        banto=_configured(settings.banto_configured),
        voice_input="on" if settings.voice_input_enabled else "off",
        disruption_checks="active" if settings.commute_disruption_checks else "not active",
        **_reminder_words(session),
    )


@router.get("/status", response_model=StatusRead)
def status(session: Session = Depends(get_db)) -> StatusRead:
    """Health, version, the last Mistral success, the last activity poll, and the database size.

    This does not call Mistral. A failed size read is a database error and leaves the size empty.
    """
    now = house_clock.current_time()
    size: int | None
    try:
        raw = session.execute(text("SELECT pg_database_size(current_database())")).scalar_one()
        size = int(raw)
    except SQLAlchemyError:
        session.rollback()
        METRICS.record_db_error(now)
        size = None
    health = "degraded" if size is None else METRICS.health(now)
    from organiser.x.store import meter_view

    return StatusRead(
        health=health,
        version=__version__,
        last_mistral_success=METRICS.last_mistral_success,
        last_activity_poll=METRICS.last_poll,
        database_bytes=size,
        x=meter_view(session, enabled=get_settings().x_enabled, now=now),
    )


@router.post("/local-reminders", response_model=HouseFacts)
def set_local_reminders(payload: LocalReminderWrite, session: Session = Depends(get_db)) -> HouseFacts:
    """Save the master switch and any type switches that were sent.

    Master off prepares nothing. A type that is omitted is not changed, so an
    older client cannot turn a type on by saving the master switch.
    """
    from organiser.agent.local_reminders import TypesUnavailable, set_reminder_flags

    if not payload.any_set():
        raise HTTPException(status_code=422, detail="Name a switch. Nothing was saved.")
    try:
        set_reminder_flags(
            session,
            house_clock.current_time(),
            enabled=payload.enabled,
            overdue=payload.overdue,
            stalled=payload.stalled,
            upcoming=payload.upcoming,
        )
    except TypesUnavailable:
        session.rollback()
        raise HTTPException(
            status_code=503,
            detail="The reminder types are not in this database yet. Nothing was turned on.",
        ) from None
    session.commit()
    return house_facts(session)


@router.post("/assistant", response_model=HouseFacts)
def set_assistant(payload: AssistantSwitch, session: Session = Depends(get_db)) -> HouseFacts:
    """Turn the assistant on or off without removing its keys. One log line."""
    set_assistant_enabled(session, payload.enabled)
    session.commit()
    return house_facts(session)


@router.get("/calendars", response_model=CalendarListRead)
def list_calendars(session: Session = Depends(get_db)) -> CalendarListRead:
    """Diary names for Settings. No provider id, token, or secret."""
    return CalendarListRead.model_validate(calendar_view(session, get_settings()))


@router.post("/calendars", response_model=CalendarListRead)
def attach_calendar(payload: CalendarName, session: Session = Depends(get_db)) -> CalendarListRead:
    try:
        body = add_calendar(session, get_settings(), payload.name)
    except DiaryError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from None
    return CalendarListRead.model_validate(body)


@router.delete("/calendars/{subscription_id}", response_model=CalendarListRead)
def detach_calendar(subscription_id: UUID, session: Session = Depends(get_db)) -> CalendarListRead:
    try:
        body = remove_calendar(session, get_settings(), subscription_id)
    except DiaryError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from None
    return CalendarListRead.model_validate(body)


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
