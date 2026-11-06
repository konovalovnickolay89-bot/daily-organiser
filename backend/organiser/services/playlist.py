"""The latest track on a public hearthis.at profile. The app does not stream it."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import httpx

from organiser.config import Settings

CACHE = timedelta(hours=1)
PROFILE = re.compile(r"[A-Za-z0-9_-]{1,40}")
_cache: dict[str, tuple[datetime, dict]] = {}
_transport: httpx.BaseTransport | None = None


class PlaylistError(Exception):
    pass


def clear_cache() -> None:
    _cache.clear()


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


def _empty(*, shown: bool, offline: bool = False) -> dict:
    return {
        "shown": shown,
        "offline": offline,
        "title": None,
        "genre": None,
        "artwork_url": None,
        "permalink_url": None,
    }


def _private(value: object) -> bool:
    """hearthis sends private as the string \"0\" or \"1\"."""
    if value is True or value == 1:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def _track(item: dict) -> dict | None:
    if _private(item.get("private")):
        return None
    title = item.get("title")
    link = item.get("permalink_url")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(link, str) or not link.startswith("https://hearthis.at/"):
        return None
    genre = item.get("genre") if isinstance(item.get("genre"), str) else ""
    art = item.get("thumb") if isinstance(item.get("thumb"), str) else None
    if not isinstance(art, str) or not art.startswith("https://img.hearthis.at/"):
        art = None
    return {
        "title": " ".join(title.split())[:200],
        "genre": " ".join(genre.split())[:80] or None,
        "artwork_url": art,
        "permalink_url": link,
    }


def _fetch(profile: str) -> dict:
    url = f"https://api-v2.hearthis.at/{profile}/"
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True, transport=_transport) as client:
            response = client.get(url, params={"type": "tracks", "page": "1", "count": "10"})
    except httpx.HTTPError:
        raise PlaylistError() from None
    host = response.url.host
    if host != "api-v2.hearthis.at" or response.status_code >= 400:
        raise PlaylistError()
    try:
        body = response.json()
    except ValueError:
        raise PlaylistError() from None
    if not isinstance(body, list):
        raise PlaylistError()
    for item in body:
        if isinstance(item, dict):
            track = _track(item)
            if track is not None:
                return track
    raise PlaylistError()


def current(settings: Settings, now: datetime) -> dict:
    if not settings.playlist_on:
        return _empty(shown=False)
    profile = (settings.hearthis_profile or "").strip() or "chlorophil"
    if not PROFILE.fullmatch(profile):
        return _empty(shown=True, offline=True)
    cached = _cache.get(profile)
    if cached is not None and now - cached[0] < CACHE:
        return {**cached[1], "shown": True, "offline": False}
    try:
        track = _fetch(profile)
    except PlaylistError:
        if cached is not None:
            return {**cached[1], "shown": True, "offline": True}
        return _empty(shown=True, offline=True)
    _cache[profile] = (now, track)
    return {**track, "shown": True, "offline": False}
