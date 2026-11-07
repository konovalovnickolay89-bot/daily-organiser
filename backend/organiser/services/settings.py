"""House choices on the Settings card. One row, one audit line per change.

Secrets stay in the environment. This module never logs a key, a postcode,
a coordinate, or a webhook secret. ``X_ENABLED`` is not stored here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from organiser.config import Settings, get_settings
from organiser.domain import DEFAULT_OWNER
from organiser.models import HouseSettings, IntegrationStatus, XItem
from organiser.services.events import record_event
from organiser.timeutil import utcnow

PLAYLIST_UNAVAILABLE = "The playlist stays hidden until the source is hearthis."
VOICE_UNAVAILABLE = "The microphone stays off until voice input is turned on."
VOXTRAL_UNAVAILABLE = "Voxtral is unavailable until the assistant key is set."
X_STAYS_OFF = "X stays off until X_ENABLED is set. These limits are saved for when it is on."
X_IN_USE = "These limits are in use. This screen does not turn X on or off."
DOCS_OFF = "Docs are off."
DOCS_BEHIND = "Docs are on, behind Cloudflare Access."
DOCS_NOT_PUBLISHED = "Docs stay off until they are behind Cloudflare Access."

_PROFILE = re.compile(r"[A-Za-z0-9_-]{1,40}")
_X_FIELDS = (
    ("x_sync_minutes", "Settings: X sync interval", "Sync interval is {value} minutes. Nothing was sent. X was not turned on."),
    ("x_daily_cap", "Settings: X daily cap", "The daily cap is {value}. Nothing was sent. X was not turned on."),
    ("x_from_max", "Settings: From X maximum", "From X shows at most {value}. Nothing was sent. X was not turned on."),
    ("x_draft_expiry_days", "Settings: X draft expiry", "A new draft expires after {value} days. Nothing was sent. X was not turned on."),
)
_CONTEXT_FIELDS = (
    ("context_token_budget", "Settings: context token budget", "The context budget is {value} tokens. Nothing was sent."),
    ("context_memory_limit", "Settings: context memory lines", "The context keeps {value} memories. Nothing was sent."),
    ("context_smart_add_days", "Settings: Smart Add days", "Smart Add reads {value} days. Nothing was sent."),
    ("context_catch_up_days", "Settings: catch-up days", "Catch-up reads {value} days. Nothing was sent."),
)


class SettingsRejected(Exception):
    def __init__(self, detail: str, status: int = 422) -> None:
        self.detail = detail
        self.status = status
        super().__init__(detail)


@dataclass(frozen=True)
class ContextLimits:
    token_budget: int
    memory_limit: int
    smart_add_days: int
    catch_up_days: int


def ensure_house_settings(session: Session) -> HouseSettings:
    """The singleton. The first row copies the poll interval from the environment."""
    row = session.get(HouseSettings, 1)
    if row is not None:
        return row
    settings = get_settings()
    minutes = min(1440, max(5, settings.x_poll_minutes))
    row = HouseSettings(
        id=1,
        playlist_enabled=None,
        alerts_enabled=True,
        webhooks_enabled=True,
        voice_enabled=None,
        x_sync_minutes=minutes,
        x_daily_cap=40,
        x_from_max=10,
        x_draft_expiry_days=7,
        context_token_budget=2000,
        context_memory_limit=10,
        context_smart_add_days=3,
        context_catch_up_days=7,
        updated_at=utcnow(),
    )
    session.add(row)
    session.flush()
    return row


def playlist_shown(session: Session) -> bool:
    """The quiet line. A null choice follows ``SHOW_PLAYLIST``. No source hides it."""
    settings = get_settings()
    if settings.playlist_source.strip().casefold() != "hearthis":
        return False
    row = ensure_house_settings(session)
    if row.playlist_enabled is None:
        return settings.playlist_on
    return bool(row.playlist_enabled)


def alerts_enabled(session: Session) -> bool:
    return ensure_house_settings(session).alerts_enabled


def webhooks_open(session: Session) -> bool:
    return ensure_house_settings(session).webhooks_enabled


def voice_mic_on(session: Session) -> bool:
    """The mic. ``VOICE_INPUT_ENABLED`` has to be on. A null choice follows it."""
    settings = get_settings()
    if not settings.voice_input_enabled:
        return False
    row = ensure_house_settings(session)
    if row.voice_enabled is None:
        return True
    return bool(row.voice_enabled)


def sync_minutes(session: Session) -> int:
    return ensure_house_settings(session).x_sync_minutes


def draft_expiry_days(session: Session) -> int:
    return ensure_house_settings(session).x_draft_expiry_days


def from_x_max(session: Session) -> int:
    return ensure_house_settings(session).x_from_max


def context_limits(session: Session) -> ContextLimits:
    row = ensure_house_settings(session)
    return ContextLimits(
        token_budget=row.context_token_budget,
        memory_limit=row.context_memory_limit,
        smart_add_days=row.context_smart_add_days,
        catch_up_days=row.context_catch_up_days,
    )


def daily_cap_reached(session: Session, now: datetime) -> bool:
    row = ensure_house_settings(session)
    start, end = _house_bounds(now)
    count = session.scalar(
        select(func.count()).select_from(XItem).where(XItem.created_at >= start, XItem.created_at < end)
    )
    return int(count or 0) >= row.x_daily_cap


def feature_settings_view(session: Session) -> dict:
    """The Settings card. Configured or not. Never a secret."""
    settings = get_settings()
    row = ensure_house_settings(session)
    return {
        "playlist": _playlist_view(settings, row),
        "alerts": {"enabled": row.alerts_enabled},
        "webhooks": {
            "enabled": row.webhooks_enabled,
            "banto": _configured(_set(settings.webhook_secret_banto.get_secret_value())),
            "banto_x": _configured(_set(settings.webhook_secret_banto_x.get_secret_value())),
        },
        "voice": _voice_view(settings, row),
        "x": {
            "enabled": settings.x_enabled,
            "sync_minutes": row.x_sync_minutes,
            "daily_cap": row.x_daily_cap,
            "from_max": row.x_from_max,
            "draft_expiry_days": row.x_draft_expiry_days,
            "detail": X_IN_USE if settings.x_enabled else X_STAYS_OFF,
        },
        "agent_context": {
            "token_budget": row.context_token_budget,
            "memory_limit": row.context_memory_limit,
            "smart_add_days": row.context_smart_add_days,
            "catch_up_days": row.context_catch_up_days,
        },
        "docs": _docs_view(settings),
    }


def apply_feature_settings(session: Session, payload) -> None:
    """Persist the fields that were sent. One log line for each change."""
    row = ensure_house_settings(session)
    data = payload.model_dump(exclude_unset=True)
    if "playlist_enabled" in data:
        _set_playlist(session, row, bool(data["playlist_enabled"]))
    if "alerts_enabled" in data:
        _set_flag(
            session,
            row,
            "alerts_enabled",
            bool(data["alerts_enabled"]),
            on="Settings: alerts on",
            off="Settings: alerts off",
            on_body="Alert cards were turned on in Settings. Nothing was sent.",
            off_body="Alert cards were turned off in Settings. Nothing was sent.",
        )
    if "webhooks_enabled" in data:
        _set_flag(
            session,
            row,
            "webhooks_enabled",
            bool(data["webhooks_enabled"]),
            on="Settings: webhooks on",
            off="Settings: webhooks off",
            on_body="Webhooks were turned on in Settings. A secret is still required. Nothing was sent.",
            off_body="Webhooks were turned off in Settings. Nothing was stored.",
        )
    if "voice_enabled" in data:
        _set_voice(session, row, bool(data["voice_enabled"]))
    _set_numbers(session, row, data, _X_FIELDS)
    _set_numbers(session, row, data, _CONTEXT_FIELDS)


def service_health(session: Session, now: datetime) -> list[dict]:
    """Names and a short state. This does not call out, and it has no secrets."""
    settings = get_settings()
    return [
        _mistral_health(settings, now),
        _voxtral_health(session, settings),
        _google_health(session, settings),
        _tfl_health(settings),
        _x_health(session, settings, now),
        _hearthis_health(session),
    ]


def _set(value: str) -> bool:
    return bool(value.strip())


def _configured(flag: bool) -> str:
    return "configured" if flag else "not configured"


def _public_profile(settings: Settings) -> str:
    if settings.playlist_source.strip().casefold() != "hearthis":
        return ""
    profile = (settings.hearthis_profile or "").strip() or "chlorophil"
    if not _PROFILE.fullmatch(profile):
        return ""
    return profile


def _playlist_view(settings: Settings, row: HouseSettings) -> dict:
    available = settings.playlist_source.strip().casefold() == "hearthis"
    if not available:
        enabled = False
    elif row.playlist_enabled is None:
        enabled = settings.playlist_on
    else:
        enabled = bool(row.playlist_enabled)
    if not available:
        detail = PLAYLIST_UNAVAILABLE
    elif enabled:
        detail = ""
    else:
        detail = "The playlist line is off."
    return {
        "enabled": enabled,
        "available": available,
        "source": "hearthis" if available else "",
        "profile": _public_profile(settings),
        "detail": detail,
    }


def _voice_view(settings: Settings, row: HouseSettings) -> dict:
    env_on = settings.voice_input_enabled
    mic = env_on and (True if row.voice_enabled is None else bool(row.voice_enabled))
    key = _set(settings.mistral_api_key.get_secret_value())
    model = settings.mistral_transcribe_model.strip() or "voxtral-mini"
    if not env_on:
        voxtral = "off"
        detail = VOICE_UNAVAILABLE
    elif not mic:
        voxtral = "unavailable" if not key else "off"
        detail = "Voice input is allowed. The microphone is off."
    elif not key:
        voxtral = "unavailable"
        detail = VOXTRAL_UNAVAILABLE
    else:
        voxtral = "ready"
        detail = model
    return {"mic": "on" if mic else "off", "env_enabled": env_on, "voxtral": voxtral, "detail": detail}


def _docs_view(settings: Settings) -> dict:
    if settings.enable_docs and settings.docs_behind_access:
        return {"state": "behind access", "detail": DOCS_BEHIND}
    if settings.enable_docs:
        return {"state": "not published", "detail": DOCS_NOT_PUBLISHED}
    return {"state": "off", "detail": DOCS_OFF}


def _audit(session: Session, title: str, body: str) -> None:
    record_event(session, kind="system", title=title, body=body, owner=DEFAULT_OWNER)


def _touch(row: HouseSettings) -> None:
    row.updated_at = utcnow()


def _set_playlist(session: Session, row: HouseSettings, enabled: bool) -> None:
    settings = get_settings()
    if enabled and settings.playlist_source.strip().casefold() != "hearthis":
        raise SettingsRejected(PLAYLIST_UNAVAILABLE)
    if row.playlist_enabled is enabled:
        return
    row.playlist_enabled = enabled
    _touch(row)
    if enabled:
        _audit(session, "Settings: playlist on", "The playlist line was turned on in Settings. Nothing was sent.")
    else:
        _audit(session, "Settings: playlist off", "The playlist line was turned off in Settings. Nothing was sent.")


def _set_voice(session: Session, row: HouseSettings, enabled: bool) -> None:
    if enabled and not get_settings().voice_input_enabled:
        raise SettingsRejected(VOICE_UNAVAILABLE)
    if row.voice_enabled is enabled:
        return
    row.voice_enabled = enabled
    _touch(row)
    if enabled:
        _audit(session, "Settings: voice on", "The microphone was turned on in Settings. Audio is not stored.")
    else:
        _audit(session, "Settings: voice off", "The microphone was turned off in Settings. Nothing was sent.")


def _set_flag(
    session: Session,
    row: HouseSettings,
    field: str,
    enabled: bool,
    *,
    on: str,
    off: str,
    on_body: str,
    off_body: str,
) -> None:
    if getattr(row, field) is enabled:
        return
    setattr(row, field, enabled)
    _touch(row)
    _audit(session, on if enabled else off, on_body if enabled else off_body)


def _set_numbers(session: Session, row: HouseSettings, data: dict, fields: tuple) -> None:
    changed = False
    for name, title, template in fields:
        if name not in data:
            continue
        value = int(data[name])
        if getattr(row, name) == value:
            continue
        setattr(row, name, value)
        _audit(session, title, template.format(value=value))
        changed = True
    if changed:
        _touch(row)


def _house_bounds(now: datetime) -> tuple[datetime, datetime]:
    zone = ZoneInfo(get_settings().house_timezone)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("UTC"))
    local = now.astimezone(zone)
    start = datetime.combine(local.date(), time.min, tzinfo=zone)
    return start, start + timedelta(days=1)


def _mistral_health(settings: Settings, now: datetime) -> dict:
    from organiser.metrics import METRICS

    if not _set(settings.mistral_api_key.get_secret_value()):
        return {"name": "mistral", "state": "not configured", "detail": "No assistant key."}
    if len(METRICS.failures_in_window(now)) >= 3:
        return {"name": "mistral", "state": "attention", "detail": "Failing in the last 15 minutes."}
    if METRICS.last_mistral_success is not None:
        return {"name": "mistral", "state": "ok", "detail": "A success is recorded."}
    return {"name": "mistral", "state": "unknown", "detail": "No success yet."}


def _voxtral_health(session: Session, settings: Settings) -> dict:
    view = _voice_view(settings, ensure_house_settings(session))
    state = view["voxtral"]
    if state == "ready":
        state = "ok"
    return {"name": "voxtral", "state": state, "detail": view["detail"]}


def _google_health(session: Session, settings: Settings) -> dict:
    if not settings.diary_configured:
        return {"name": "google", "state": "not configured", "detail": "Not configured."}
    row = session.get(IntegrationStatus, "diary")
    if row is not None and row.last_error_class:
        return {"name": "google", "state": "attention", "detail": row.last_error_class}
    if row is not None and row.last_ok_at is not None:
        return {"name": "google", "state": "ok", "detail": "A read succeeded."}
    return {"name": "google", "state": "unknown", "detail": "Not read yet."}


def _tfl_health(settings: Settings) -> dict:
    from organiser.services.commute import tfl_outcome

    if not settings.tfl_configured:
        return {"name": "tfl", "state": "not configured", "detail": "Not configured."}
    outcome = tfl_outcome()
    if outcome == "ok":
        return {"name": "tfl", "state": "ok", "detail": "A journey check succeeded."}
    if outcome == "attention":
        return {"name": "tfl", "state": "attention", "detail": "The last journey check failed."}
    return {"name": "tfl", "state": "unknown", "detail": "Not read yet."}


def _x_health(session: Session, settings: Settings, now: datetime) -> dict:
    from organiser.x.store import meter_view

    if not settings.x_enabled:
        return {"name": "x", "state": "off", "detail": "X is off."}
    if not _set(settings.x_client_id.get_secret_value()) or not _set(settings.x_token_key.get_secret_value()):
        return {"name": "x", "state": "not configured", "detail": "Not configured."}
    meter = meter_view(session, enabled=True, now=now)
    if meter.get("attention"):
        return {"name": "x", "state": "attention", "detail": str(meter["attention"])}
    if meter.get("connected"):
        return {"name": "x", "state": "ok", "detail": "Connected."}
    return {"name": "x", "state": "unknown", "detail": "Not connected."}


def _hearthis_health(session: Session) -> dict:
    from organiser.services.playlist import hearthis_outcome

    if not playlist_shown(session):
        return {"name": "hearthis", "state": "off", "detail": "Hidden."}
    outcome = hearthis_outcome()
    if outcome == "ok":
        return {"name": "hearthis", "state": "ok", "detail": "A track is cached."}
    if outcome == "attention":
        return {"name": "hearthis", "state": "attention", "detail": "The last read failed."}
    return {"name": "hearthis", "state": "unknown", "detail": "Not read yet."}
