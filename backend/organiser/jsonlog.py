"""One JSON object per log line.

The line is level, logger, and message. It is not a request body, a postcode,
a coordinate, or a secret. Tracebacks are omitted: an exception string can
carry a URL.
"""

import json
import logging
import re
from datetime import datetime, timezone

_SECRET = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|authorization)\b\s*[:=]\s*\S+"
)
# A UK postcode. Ordinary words do not match.
_POSTCODE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.IGNORECASE)
# A latitude or longitude with at least four decimal places. Not a clock fraction
# such as 08:00:00.123456, which is preceded by a colon.
_COORD = re.compile(r"(?<![:\d])-?\d{1,3}\.\d{4,}(?!\d)")

_EXTRAS = frozenset({"method", "path", "status_code", "duration_ms"})

_SKIP = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
    }
)

_configured = False


def scrub(text: str) -> str:
    """Replace secrets, postcodes, and coordinates. Leave the rest of the line."""
    text = _SECRET.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    text = _POSTCODE.sub("[redacted]", text)
    text = _COORD.sub("[redacted]", text)
    return text


class ScrubFilter(logging.Filter):
    """Scrub the formatted message before any handler, including tests, sees it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = scrub(record.getMessage())
        record.args = ()
        if record.exc_info:
            record.exc_info = None
            record.exc_text = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": scrub(record.getMessage()),
        }
        for key in _EXTRAS:
            value = record.__dict__.get(key)
            if isinstance(value, str):
                payload[key] = scrub(value)
            elif isinstance(value, (int, float, bool)):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Attach the JSON handler once. A second call does not drop other handlers."""
    global _configured
    if _configured:
        return
    _configured = True
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addFilter(ScrubFilter())
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").disabled = True
