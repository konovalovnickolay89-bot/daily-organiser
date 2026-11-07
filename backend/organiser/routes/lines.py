"""Line status, read on its own.

``GET /tfl/status`` uses the house ``TFL_APP_KEY``. It does not accept a key,
a place, or a shift from the client. A query string is ignored and is not
forwarded. A missing key does not call TfL. This does not call Mistral.

The body is a diagnostic read, always 200 while this process is up:

- ``configured`` — the house key is set. This is not the same as TfL answering.
- ``state`` — ``missing``, ``fresh``, ``stale``, or ``error``.
- ``stale`` — true only when ``state`` is ``stale``.
- ``fetched_at`` — when this process last parsed a body. Null if it never has.
- ``source_at`` — a timestamp TfL sent, or null. Not a live clock.
- ``failure`` — ``refused`` (403), ``limited`` (429), ``timeout``, ``malformed``,
  or ``upstream``. Null on a fresh read and when the key is missing.
- ``detail`` — a short house sentence, or null when the fresh read listed lines.
- ``lines`` — id, name, mode, severity, and a plain reason when it is not good service.

A fresh parse is shared for two minutes. One upstream call is in flight at a
time. A failed newer read keeps the last good parse for 30 minutes and marks
it stale. The upstream call waits at most five seconds. Nothing is scheduled.
"""

from fastapi import APIRouter

from organiser.config import get_settings
from organiser.schemas import ServiceStatusRead
from organiser.services.lines import service_status

router = APIRouter(prefix="/tfl", tags=["tfl"])


@router.get("/status", response_model=ServiceStatusRead)
def line_status() -> ServiceStatusRead:
    """Tube, Overground, Elizabeth line, and DLR. No shift and no location."""
    return ServiceStatusRead.model_validate(service_status(get_settings()))
