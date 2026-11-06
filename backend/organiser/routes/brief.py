from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from organiser.config import get_settings
from organiser.db import get_db
from organiser.schemas import MorningBrief
from organiser.services.brief import morning_brief
from organiser.services.system import ensure_system_state
from organiser.timeutil import house_today

router = APIRouter(prefix="/brief", tags=["brief"])


@router.get("/morning", response_model=MorningBrief)
def get_morning_brief(session: Session = Depends(get_db)) -> MorningBrief:
    state = ensure_system_state(session)
    settings = get_settings()
    if settings.x_enabled:
        from organiser import clock
        from organiser.x.store import expire_drafts

        expire_drafts(session, clock.current_time())
    session.commit()
    today = house_today(settings.house_timezone)
    return MorningBrief.model_validate(morning_brief(session, today, state.paused))
