"""The quiet playlist line. A link out. The track is not streamed."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from organiser import clock
from organiser.config import get_settings
from organiser.db import get_db
from organiser.schemas import PlaylistRead
from organiser.services.playlist import current
from organiser.services.settings import playlist_shown

router = APIRouter(tags=["playlist"])


@router.get("/playlist", response_model=PlaylistRead)
def playlist(session: Session = Depends(get_db)) -> PlaylistRead:
    shown = playlist_shown(session)
    session.commit()
    return PlaylistRead.model_validate(current(get_settings(), clock.current_time(), shown=shown))
