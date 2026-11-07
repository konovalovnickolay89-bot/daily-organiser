"""TfL line status, read on its own.

Tube, London Overground, the Elizabeth line, and the DLR. The house key is
``TFL_APP_KEY``. This does not read a shift, a home location, the diary, or
Bantō, and it does not call Mistral.

Bounds, all in this process:

- The upstream call waits at most ``TIMEOUT_SECONDS`` (5).
- A successful parse is fresh for ``FRESH_SECONDS`` (120). Further reads in
  that window do not call TfL.
- Readers that arrive during a call share that one call. They wait at most
  ``COALESCE_WAIT_SECONDS`` (8).
- If a newer read fails and the last good parse is younger than
  ``STALE_SECONDS`` (30 minutes), that parse is returned with ``state``
  ``stale``. It is not described as live or real-time.
- After that, a failed read returns ``error`` and no lines.
- There is no scheduler. A read happens only when this function is called.
- The key, the URL, and the upstream body are not logged. The key is not
  stored in the cache. Text from TfL is stripped and clipped before it is kept.

``fetched_at`` is this process's clock at the last good parse. ``source_at``
is the latest ``modified`` or status ``created`` value TfL sent that this
house could parse. A missing or ``/Date(...)`` value stays null. Nothing here
invents a source time.
"""

from __future__ import annotations

import hashlib
import html
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from organiser import clock
from organiser.config import Settings
from organiser.services.outbound import request_json_any

logger = logging.getLogger(__name__)

STATUS_URL = "https://api.tfl.gov.uk/Line/Mode/tube,overground,elizabeth-line,dlr/Status"
TIMEOUT_SECONDS = 5.0
FRESH_SECONDS = 120.0
STALE_SECONDS = 30 * 60.0
COALESCE_WAIT_SECONDS = 8.0
MAX_LINES = 40
_REASON_LIMIT = 240
_NAME_LIMIT = 80

MISSING = "TfL is not configured."
EMPTY = "No line status was listed."
STALE = "Showing the last line status. A newer read failed."
DETAILS = {
    "refused": "TfL refused the line status.",
    "limited": "TfL is limiting line status.",
    "timeout": "TfL did not answer in time.",
    "malformed": "TfL sent a line status this house could not read.",
    "upstream": "Line status is unavailable.",
}
_GOOD = {"good service"}
_MODES = {
    "tube": "Tube",
    "overground": "Overground",
    "elizabeth-line": "Elizabeth line",
    "dlr": "DLR",
}
_SCRIPT = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
_APP_KEY = re.compile(r"(?i)\b(?:app_key|app_id|api_key)\s*=\s*[^&\s]*")
_ID = re.compile(r"^[a-z0-9-]{1,64}$")
_SLUG = re.compile(r"[^a-z0-9]+")

_cond = threading.Condition()
_cache: dict[str, _Entry] = {}
_inflight = False
_flight = 0
_outcome: dict | None = None
_outcome_flight = -1


class _Bad(Exception):
    """The body was not a line-status list this house could read."""


@dataclass(frozen=True)
class _Entry:
    mono: float
    fetched_at: datetime
    source_at: datetime | None
    lines: tuple[dict, ...]


def _mono() -> float:
    return time.monotonic()


def clear_cache() -> None:
    """Drop the shared parse. The next read calls TfL when a key is set."""
    global _inflight, _outcome, _outcome_flight
    with _cond:
        _cache.clear()
        _outcome = None
        _outcome_flight = -1
        _inflight = False
        _cond.notify_all()


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _age(entry: _Entry) -> float:
    return _mono() - entry.mono


def _scrub(text: str, key: str) -> str:
    if key:
        text = text.replace(key, "")
    return _APP_KEY.sub("", text)


def _plain(value: object, limit: int, key: str) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = _SCRIPT.sub(" ", value)
    cleaned = _TAG.sub(" ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = _SCRIPT.sub(" ", cleaned)
    cleaned = _TAG.sub(" ", cleaned)
    cleaned = _CTRL.sub(" ", _scrub(cleaned, key))
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"
    return cleaned


def _stamp(value: object) -> datetime | None:
    """An ISO timestamp TfL sent. ``/Date(...)`` and other shapes stay unknown."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.startswith("/Date("):
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _slug(name: str) -> str:
    slug = _SLUG.sub("-", name.casefold()).strip("-")
    return slug[:64] or "line"


def _line(item: dict, key: str) -> tuple[dict, datetime | None] | None:
    name = _plain(item.get("name"), _NAME_LIMIT, key)
    if not name or not any(char.isalnum() for char in name):
        return None
    statuses = item.get("lineStatuses")
    if not isinstance(statuses, list):
        return None
    chosen = next((status for status in statuses if isinstance(status, dict)), None)
    if chosen is None:
        return None
    severity = _plain(chosen.get("statusSeverityDescription"), _NAME_LIMIT, key)
    if not severity:
        return None
    reason = None
    if severity.casefold() not in _GOOD:
        reason = _plain(chosen.get("reason"), _REASON_LIMIT, key) or None
    raw_id = item.get("id")
    if isinstance(raw_id, str) and _ID.fullmatch(raw_id.strip().casefold()):
        ident = raw_id.strip().casefold()
    else:
        ident = _slug(name)
    mode_name = item.get("modeName")
    mode = _MODES.get(mode_name.casefold(), "") if isinstance(mode_name, str) else ""
    if not mode:
        mode = "Line"
    source = _stamp(item.get("modified")) or _stamp(chosen.get("created"))
    return (
        {"id": ident, "name": name, "mode": mode, "severity": severity, "reason": reason},
        source,
    )


def _parse(body: object, key: str) -> tuple[tuple[dict, ...], datetime | None]:
    if not isinstance(body, list):
        raise _Bad()
    lines: list[dict] = []
    stamps: list[datetime] = []
    junk = 0
    for item in body:
        if not isinstance(item, dict):
            junk += 1
            continue
        parsed = _line(item, key)
        if parsed is None:
            junk += 1
            continue
        lines.append(parsed[0])
        if parsed[1] is not None:
            stamps.append(parsed[1])
        if len(lines) >= MAX_LINES:
            break
    if body and not lines and junk:
        raise _Bad()
    source = max(stamps) if stamps else None
    return tuple(lines), source


def _category(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 403:
            return "refused"
        if code == 429:
            return "limited"
        return "upstream"
    if isinstance(exc, (ValueError, TypeError, _Bad)):
        return "malformed"
    return "upstream"


def _public(
    entry: _Entry,
    *,
    state: str,
    failure: str | None,
    detail: str | None,
) -> dict:
    return {
        "configured": True,
        "state": state,
        "stale": state == "stale",
        "fetched_at": entry.fetched_at,
        "source_at": entry.source_at,
        "failure": failure,
        "detail": detail,
        "lines": [dict(line) for line in entry.lines],
    }


def _closed(*, configured: bool, state: str, failure: str | None = None, detail: str | None = None) -> dict:
    return {
        "configured": configured,
        "state": state,
        "stale": False,
        "fetched_at": None,
        "source_at": None,
        "failure": failure,
        "detail": detail,
        "lines": [],
    }


def _from_cache(digest: str, failure: str) -> dict:
    with _cond:
        entry = _cache.get(digest)
        age = None if entry is None else _age(entry)
    if entry is not None and age is not None and age < STALE_SECONDS:
        return _public(entry, state="stale", failure=failure, detail=f"{STALE} {DETAILS[failure]}")
    return _closed(configured=True, state="error", failure=failure, detail=DETAILS[failure])


def _fresh(digest: str) -> dict | None:
    """Lock held. A parse still inside the fresh window."""
    entry = _cache.get(digest)
    if entry is None or _age(entry) >= FRESH_SECONDS:
        return None
    detail = EMPTY if not entry.lines else None
    return _public(entry, state="fresh", failure=None, detail=detail)


def _read_upstream(key: str, digest: str, moment: datetime) -> dict:
    try:
        body = request_json_any(
            "GET",
            STATUS_URL,
            params={"app_key": key},
            timeout=TIMEOUT_SECONDS,
        )
        lines, source_at = _parse(body, key)
    except _Bad:
        logger.info("line status malformed")
        return _from_cache(digest, "malformed")
    except Exception as exc:
        failure = _category(exc)
        logger.info("line status %s", failure)
        return _from_cache(digest, failure)
    entry = _Entry(mono=_mono(), fetched_at=moment, source_at=source_at, lines=lines)
    with _cond:
        _cache[digest] = entry
    detail = EMPTY if not lines else None
    return _public(entry, state="fresh", failure=None, detail=detail)


def service_status(settings: Settings, now: datetime | None = None) -> dict:
    """One diagnostic read. Missing key does not call TfL."""
    moment = now if now is not None else clock.current_time()
    key = settings.tfl_app_key.get_secret_value().strip()
    if not key:
        return _closed(configured=False, state="missing", detail=MISSING)

    digest = _digest(key)
    global _inflight, _flight, _outcome, _outcome_flight
    with _cond:
        fresh = _fresh(digest)
        if fresh is not None:
            return fresh
        if _inflight:
            flight = _flight
            deadline = _mono() + COALESCE_WAIT_SECONDS
            while _inflight and _flight == flight:
                remaining = deadline - _mono()
                if remaining <= 0:
                    logger.info("line status wait")
                    return _from_cache(digest, "upstream")
                _cond.wait(remaining)
            if _outcome_flight == flight and _outcome is not None:
                return _outcome
            fresh = _fresh(digest)
            if fresh is not None:
                return fresh
        _inflight = True
        _flight += 1
        flight = _flight

    outcome = _closed(configured=True, state="error", failure="upstream", detail=DETAILS["upstream"])
    try:
        outcome = _read_upstream(key, digest, moment)
    finally:
        with _cond:
            _outcome = outcome
            _outcome_flight = flight
            _inflight = False
            _cond.notify_all()
    return outcome
