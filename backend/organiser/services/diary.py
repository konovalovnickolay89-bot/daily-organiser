"""Read-only Google Calendar. No create, edit, or write scope is requested."""

import hashlib
import logging
import time
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.agent.runner import outside_home
from organiser.config import Settings
from organiser.models import CalendarSubscription, IntegrationStatus
from organiser.services.outbound import request_json
from organiser.timeutil import utcnow

logger = logging.getLogger(__name__)

# Consent must be these two scopes only. The refresh call does not send a scope,
# so this process cannot widen what was granted.
SCOPES = (
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
)

_TOKEN: dict[str, float | str] = {}


class DiaryError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail


def clear_cache() -> None:
    _TOKEN.clear()


def _mark(session: Session, *, ok: bool, error_class: str | None) -> None:
    row = session.get(IntegrationStatus, "diary")
    if row is None:
        row = IntegrationStatus(name="diary", updated_at=utcnow())
        session.add(row)
    row.updated_at = utcnow()
    if ok:
        row.last_ok_at = row.updated_at
        row.last_error_class = None
    else:
        row.last_error_class = error_class
    session.commit()


def _token(settings: Settings) -> str:
    expiry = float(_TOKEN.get("exp") or 0)
    cached = _TOKEN.get("token")
    if isinstance(cached, str) and expiry > time.time() + 30:
        return cached
    body = request_json(
        "POST",
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "refresh_token",
            "client_id": settings.google_oauth_client_id.get_secret_value(),
            "client_secret": settings.google_oauth_client_secret.get_secret_value(),
            "refresh_token": settings.google_oauth_refresh_token.get_secret_value(),
        },
    )
    token = body.get("access_token")
    if not isinstance(token, str) or not token:
        raise DiaryError(503, "Diary not connected — reconnect in Settings.")
    expires = int(body.get("expires_in") or 3600)
    _TOKEN["token"] = token
    _TOKEN["exp"] = time.time() + expires
    return token


def _calendar_list(settings: Settings) -> list[dict]:
    body = request_json(
        "GET",
        "https://www.googleapis.com/calendar/v3/users/me/calendarList",
        params={"maxResults": "100"},
        headers={"Authorization": f"Bearer {_token(settings)}"},
    )
    items = body.get("items")
    if not isinstance(items, list):
        return []
    found = []
    for item in items:
        if not isinstance(item, dict):
            continue
        calendar_id = item.get("id")
        name = item.get("summary")
        if isinstance(calendar_id, str) and isinstance(name, str) and name.strip():
            found.append({"id": calendar_id, "name": name.strip(), "primary": bool(item.get("primary"))})
    return found


def _events(settings: Settings, calendar_id: str, start: datetime, end: datetime) -> list[dict]:
    body = request_json(
        "GET",
        "https://www.googleapis.com/calendar/v3/calendars/" + quote(calendar_id, safe="") + "/events",
        params={
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": "50",
        },
        headers={"Authorization": f"Bearer {_token(settings)}"},
    )
    items = body.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _when(start: dict, zone: ZoneInfo) -> tuple[str, str]:
    if start.get("date") and not start.get("dateTime"):
        return str(start["date"]), "All day"
    raw = start.get("dateTime")
    if not isinstance(raw, str):
        return "", ""
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(zone)
    except ValueError:
        return raw, ""
    return moment.isoformat(), moment.strftime("%H:%M")


def _active_ids(session: Session, settings: Settings) -> list[str]:
    rows = list(
        session.scalars(
            select(CalendarSubscription)
            .where(CalendarSubscription.enabled.is_(True))
            .order_by(CalendarSubscription.display_name.asc())
        )
    )
    if rows:
        return [row.calendar_id for row in rows]
    return list(settings.calendar_ids)


def appointments_section(session: Session, settings: Settings, now: datetime) -> dict:
    """Today's appointments. A failure stays in this section."""
    disconnected = {
        "key": "appointments",
        "title": "Appointments",
        "placeholder": False,
        "summary": "Diary not connected — reconnect in Settings.",
        "footnote": "Read only. This is not a calendar.",
        "items": [],
    }
    if not settings.diary_configured:
        _mark(session, ok=False, error_class="unconfigured")
        return disconnected

    zone = ZoneInfo(settings.house_timezone)
    local = now.astimezone(zone)
    start = datetime.combine(local.date(), datetime.min.time(), tzinfo=zone)
    end = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), tzinfo=zone)

    try:
        collected: list[tuple[str, dict]] = []
        seen: set[str] = set()
        for calendar_id in _active_ids(session, settings):
            for item in _events(settings, calendar_id, start, end):
                event_id = item.get("id")
                if not isinstance(event_id, str) or event_id in seen:
                    continue
                if item.get("status") == "cancelled":
                    continue
                title = item.get("summary")
                title = title.strip() if isinstance(title, str) else ""
                if not title:
                    title = "Busy"
                if outside_home(title):
                    continue
                seen.add(event_id)
                stamp, label = _when(item.get("start") if isinstance(item.get("start"), dict) else {}, zone)
                collected.append(
                    (
                        stamp,
                        {
                            "title": title,
                            "meta": label or None,
                            "ref": hashlib.sha256(event_id.encode()).hexdigest()[:12],
                        },
                    )
                )
    except Exception:
        logger.info("diary request failed")
        _mark(session, ok=False, error_class="unavailable")
        return disconnected

    collected.sort(key=lambda pair: (pair[0], pair[1]["title"].lower()))
    _mark(session, ok=True, error_class=None)
    summary = "Nothing on the diary today." if not collected else (
        "1 appointment" if len(collected) == 1 else f"{len(collected)} appointments"
    )
    return {
        "key": "appointments",
        "title": "Appointments",
        "placeholder": False,
        "summary": summary,
        "footnote": "Read only. This is not a calendar.",
        "items": [item for _, item in collected],
    }


def calendar_view(session: Session, settings: Settings) -> dict:
    """Names only. Provider ids stay in the table."""
    if not settings.diary_configured:
        return {"configured": False, "using_primary": False, "items": []}
    rows = list(session.scalars(select(CalendarSubscription).order_by(CalendarSubscription.display_name.asc())))
    if not rows:
        return {
            "configured": True,
            "using_primary": settings.calendar_ids == ("primary",),
            "items": [],
        }
    return {
        "configured": True,
        "using_primary": False,
        "items": [
            {"id": row.id, "name": row.display_name, "enabled": row.enabled}
            for row in rows
            if row.enabled
        ],
    }


def _seed_current(session: Session, settings: Settings, listing: list[dict], now: datetime) -> None:
    for calendar_id in settings.calendar_ids:
        match = None
        for item in listing:
            if calendar_id == "primary" and item.get("primary"):
                match = item
                break
            if item["id"] == calendar_id:
                match = item
                break
        stored = match["id"] if match else calendar_id
        display = match["name"] if match else ("Primary" if calendar_id == "primary" else "Calendar")
        if outside_home(display):
            continue
        session.add(
            CalendarSubscription(
                provider="google",
                calendar_id=stored,
                display_name=display,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )


def add_calendar(session: Session, settings: Settings, name: str) -> dict:
    if not settings.diary_configured:
        raise DiaryError(409, "Diary not connected.")
    cleaned = " ".join(name.split())
    if not cleaned:
        raise DiaryError(422, "Give the calendar a name.")
    if outside_home(cleaned):
        raise DiaryError(422, "Not for the house log.")
    try:
        listing = _calendar_list(settings)
    except DiaryError:
        raise
    except Exception:
        logger.info("diary list failed")
        raise DiaryError(503, "Diary not connected — reconnect in Settings.") from None
    matches = [item for item in listing if item["name"].casefold() == cleaned.casefold()]
    if not matches:
        raise DiaryError(404, "No calendar has that name.")
    if len(matches) > 1:
        raise DiaryError(409, "More than one calendar has that name.")
    chosen = matches[0]
    now = utcnow()
    existing_rows = list(session.scalars(select(CalendarSubscription).limit(1)))
    if not existing_rows:
        _seed_current(session, settings, listing, now)
        session.flush()
    current = session.scalars(
        select(CalendarSubscription).where(
            CalendarSubscription.provider == "google",
            CalendarSubscription.calendar_id == chosen["id"],
        )
    ).first()
    if current is None:
        session.add(
            CalendarSubscription(
                provider="google",
                calendar_id=chosen["id"],
                display_name=chosen["name"],
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
    else:
        current.enabled = True
        current.display_name = chosen["name"]
        current.updated_at = now
    session.commit()
    return calendar_view(session, settings)


def remove_calendar(session: Session, settings: Settings, subscription_id) -> dict:
    row = session.get(CalendarSubscription, subscription_id)
    if row is None:
        raise DiaryError(404, "That calendar is not on the list.")
    session.delete(row)
    session.commit()
    return calendar_view(session, settings)
