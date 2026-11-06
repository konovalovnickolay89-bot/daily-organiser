"""Signed inbound webhooks. One registry, not a plugin system.

POST /hooks/{source}. The signature is HMAC-SHA256 of ``{timestamp}.{raw body}``
with that source's secret. The timestamp header has to be within five minutes,
and a signature is accepted once in that window. A rejected body is not stored.
"""

import hashlib
import hmac
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from organiser import clock
from organiser.agent.runner import outside_home
from organiser.config import get_settings
from organiser.db import get_db
from organiser.limits import LIMITS
from organiser.services.commute import ShiftRejected, store_shift

router = APIRouter(prefix="/hooks", tags=["hooks"])

TIMESTAMP_HEADER = "x-organiser-timestamp"
SIGNATURE_HEADER = "x-organiser-signature"
WINDOW_SECONDS = 300

# Signature hexes accepted inside the window. The body is not kept.
_seen: dict[str, float] = {}


def clear_replay_cache() -> None:
    _seen.clear()


def _remember(signature: str, now_ts: float) -> bool:
    """True when this signature was already accepted inside the window."""
    cutoff = now_ts - WINDOW_SECONDS
    for key, seen_at in list(_seen.items()):
        if seen_at < cutoff:
            del _seen[key]
    if signature in _seen:
        return True
    _seen[signature] = now_ts
    return False


def _secret(source: str) -> str:
    settings = get_settings()
    if source == "banto":
        return settings.webhook_secret_banto.get_secret_value().strip()
    return ""


def _verify(secret: str, raw: bytes, timestamp: str, signature: str, now: datetime) -> None:
    try:
        stamp = int(timestamp)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="The webhook timestamp is not valid.") from None
    if stamp < 0 or str(stamp) != timestamp.strip():
        raise HTTPException(status_code=401, detail="The webhook timestamp is not valid.")
    now_ts = now.timestamp()
    if abs(now_ts - stamp) > WINDOW_SECONDS:
        raise HTTPException(status_code=401, detail="The webhook timestamp is outside the window.")
    digest = hmac.new(secret.encode(), f"{stamp}.".encode() + raw, hashlib.sha256).hexdigest()
    provided = signature.strip().lower()
    if not provided or not hmac.compare_digest(digest, provided):
        raise HTTPException(status_code=401, detail="The webhook signature does not match.")
    if _remember(provided, now_ts):
        raise HTTPException(status_code=409, detail="This webhook was already used.")


def _when(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ShiftRejected(f"Give the shift a {name}.")
    text = value.strip()
    if outside_home(text):
        raise ShiftRejected("Not for the house log.")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ShiftRejected(f"{name} is not a time.") from None


def _commute(session: Session, body: dict) -> dict:
    """The same shift check as POST /commute/shift. A bad body is not stored."""
    if set(body) != {"event", "start", "end", "location_label"}:
        raise ShiftRejected("The shift body is only start, end, and location_label.")
    label = body["location_label"]
    if not isinstance(label, str) or outside_home(label):
        raise ShiftRejected("Not for the house log.")
    if not LIMITS.allow("commute"):
        raise HTTPException(status_code=429, detail="Too many shift updates. Nothing was stored.")
    row = store_shift(session, _when(body["start"], "start"), _when(body["end"], "end"), label)
    session.commit()
    return {
        "id": str(row.id),
        "start": row.start_at.isoformat(),
        "end": row.end_at.isoformat(),
        "location_label": row.location_label,
    }


# source → event → handler. banto_x is not registered; its secret waits for later.
_EVENTS = {
    "banto": {
        "commute": _commute,
    },
}


@router.post("/{source}")
async def receive(source: str, request: Request, session: Session = Depends(get_db)) -> dict:
    name = source.casefold()
    events = _EVENTS.get(name)
    if events is None:
        raise HTTPException(status_code=404, detail="Unknown source.")
    secret = _secret(name)
    if not secret:
        raise HTTPException(status_code=503, detail="This source is not configured.")
    raw = await request.body()
    _verify(
        secret,
        raw,
        request.headers.get(TIMESTAMP_HEADER, ""),
        request.headers.get(SIGNATURE_HEADER, ""),
        clock.current_time(),
    )
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="The webhook body is not JSON.") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="The webhook body must be an object.")
    event = body.get("event")
    if not isinstance(event, str) or not event.strip():
        raise HTTPException(status_code=422, detail="Name the event.")
    handler = events.get(event.casefold())
    if handler is None:
        raise HTTPException(status_code=404, detail="Unknown event.")
    try:
        return handler(session, body)
    except ShiftRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
