"""Alert cards for the arrival screen. Dismiss hides one incident. Nothing is sent."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from organiser import clock
from organiser.db import get_db
from organiser.schemas import AlertList
from organiser.services.alerts import AlertNotActive, active_alerts, dismiss_alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertList)
def list_alerts(session: Session = Depends(get_db)) -> AlertList:
    """The cards showing now. One per kind. This does not call Mistral or send anything."""
    return AlertList(items=active_alerts(session, clock.current_time()))


@router.post("/{kind}/dismiss", response_model=AlertList)
def dismiss(kind: str, session: Session = Depends(get_db)) -> AlertList:
    """Hide the current incident of this kind. A new incident can show again."""
    try:
        items = dismiss_alert(session, kind, clock.current_time())
    except AlertNotActive:
        raise HTTPException(status_code=404, detail="That alert is not showing.") from None
    session.commit()
    return AlertList(items=items)
