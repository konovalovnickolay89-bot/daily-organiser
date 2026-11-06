"""Response headers and an access line. Neither reads the body."""

import logging
import re
import time

from starlette.datastructures import MutableHeaders

from organiser.metrics import METRICS

logger = logging.getLogger("organiser.access")

_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

# Reviewed for a house app served on one origin. The theme boot script and the
# built CSS are files, so script-src and style-src stay 'self'. Docs stay off;
# Swagger would need a looser policy and is not served on the house.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    # The mic is allowed on this origin so Smart Add can ask when voice is on.
    # Camera, location, and payment stay closed. The button itself stays hidden
    # until VOICE_INPUT_ENABLED.
    "Permissions-Policy": "camera=(), microphone=(self), geolocation=(), payment=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "img-src 'self' data: https://img.hearthis.at; "
        "style-src 'self'; "
        "font-src 'self'; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
}


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in SECURITY_HEADERS.items():
                    headers.setdefault(key, value)
            await send(message)

        await self.app(scope, receive, send_wrapper)


def route_label(scope: dict) -> str:
    """The route template when Starlette has one, otherwise the path with ids folded."""
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    raw = scope.get("path") or "/"
    return _UUID.sub("{id}", raw.split("?", 1)[0])


class AccessLogMiddleware:
    """Method, path, and status. No query string, no body, no headers."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                duration_ms = round((time.perf_counter() - started) * 1000, 1)
                METRICS.record_request(
                    scope.get("method", ""),
                    route_label(scope),
                    status,
                    duration_ms / 1000,
                )
                logger.info(
                    "request",
                    extra={
                        "method": scope.get("method", ""),
                        "path": scope.get("path", ""),
                        "status_code": status,
                        "duration_ms": duration_ms,
                    },
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)
