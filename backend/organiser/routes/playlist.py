"""The quiet playlist line. A link out. The track is not streamed."""

from fastapi import APIRouter

from organiser import clock
from organiser.config import get_settings
from organiser.schemas import PlaylistRead
from organiser.services.playlist import current

router = APIRouter(tags=["playlist"])


@router.get("/playlist", response_model=PlaylistRead)
def playlist() -> PlaylistRead:
    return PlaylistRead.model_validate(current(get_settings(), clock.current_time()))
