"""Open-Meteo for the house. Coordinates stay in memory. Nothing here is logged."""

import logging
import time
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from organiser.config import Settings
from organiser.models import IntegrationStatus
from organiser.services.outbound import request_json
from organiser.timeutil import utcnow

logger = logging.getLogger(__name__)

_CACHE: dict[str, tuple[float, dict]] = {}
_TTL_SECONDS = 20 * 60

# WMO codes, in short British phrases. https://open-meteo.com/en/docs
_CODES = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "cloudy",
    45: "fog",
    48: "fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "freezing drizzle",
    57: "freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "showers",
    82: "heavy showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "a thunderstorm",
    96: "a thunderstorm",
    99: "a thunderstorm",
}

ATTRIBUTION = "Weather data by Open-Meteo (CC BY 4.0)."


def clear_cache() -> None:
    _CACHE.clear()


def _clock(now: datetime) -> str:
    local = now.astimezone(ZoneInfo("Europe/London"))
    return local.strftime("%H:%M")


def _mark(session: Session, *, ok: bool, error_class: str | None) -> None:
    row = session.get(IntegrationStatus, "weather")
    if row is None:
        row = IntegrationStatus(name="weather", updated_at=utcnow())
        session.add(row)
    row.updated_at = utcnow()
    if ok:
        row.last_ok_at = row.updated_at
        row.last_error_class = None
    else:
        row.last_error_class = error_class
    session.commit()


def _coordinates(settings: Settings) -> tuple[float, float] | None:
    """Resolve the house point. The values are not logged and not returned."""
    kind = settings.home_location_kind
    if kind == "coordinates":
        try:
            lat = float(settings.house_lat.get_secret_value().strip())
            lon = float(settings.house_lon.get_secret_value().strip())
        except ValueError:
            return None
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return None
        return lat, lon
    if kind == "postcode":
        postcode = settings.house_postcode.get_secret_value().strip()
        try:
            body = request_json("GET", "https://api.postcodes.io/postcodes/" + quote(postcode))
        except Exception:
            return None
        result = body.get("result")
        if not isinstance(result, dict):
            return None
        try:
            lat = float(result["latitude"])
            lon = float(result["longitude"])
        except (KeyError, TypeError, ValueError):
            return None
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return None
        return lat, lon
    return None


def _phrase(code: int) -> str:
    return _CODES.get(code, "mixed conditions")


def _fetch(lat: float, lon: float) -> dict:
    body = request_json(
        "GET",
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": f"{lat:.5f}",
            "longitude": f"{lon:.5f}",
            "current": "temperature_2m,weather_code",
            "timezone": "Europe/London",
            "forecast_days": "1",
        },
    )
    current = body.get("current")
    if not isinstance(current, dict):
        raise ValueError("missing current")
    temperature = float(current["temperature_2m"])
    code = int(current["weather_code"])
    return {"temperature": round(temperature), "phrase": _phrase(code)}


def weather_section(session: Session, settings: Settings, now: datetime) -> dict:
    """A brief section. Unset and failures stay on this section."""
    if settings.home_location_kind is None:
        _mark(session, ok=False, error_class="unset")
        return {
            "key": "weather",
            "title": "Weather",
            "placeholder": False,
            "summary": "Weather location is not set.",
            "items": [],
        }

    cached = _CACHE.get("weather")
    fresh: dict | None = None
    try:
        point = _coordinates(settings)
        if point is None:
            raise ValueError("unresolved")
        if cached and time.monotonic() - cached[0] < _TTL_SECONDS:
            fresh = cached[1]
        else:
            fresh = _fetch(*point)
            _CACHE["weather"] = (time.monotonic(), fresh)
    except Exception:
        # Do not log the exception: the message can contain the request URL.
        logger.info("weather request failed")
        if cached is not None:
            fresh = cached[1]
        else:
            _mark(session, ok=False, error_class="unavailable")
            return {
                "key": "weather",
                "title": "Weather",
                "placeholder": False,
                "summary": f"Weather unavailable (as of {_clock(now)}).",
                "items": [],
            }

    _mark(session, ok=True, error_class=None)
    summary = f"{fresh['temperature']}°C, {fresh['phrase']}."
    return {
        "key": "weather",
        "title": "Weather",
        "placeholder": False,
        "summary": summary,
        "footnote": ATTRIBUTION,
        "items": [
            {
                "title": summary,
                "detail": ATTRIBUTION,
                "meta": f"As of {_clock(now)}",
            }
        ],
    }
