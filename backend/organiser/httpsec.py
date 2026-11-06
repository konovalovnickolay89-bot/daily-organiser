"""Response headers and an access line. Neither reads the body."""

import logging
import time

from starlette.datastructures import MutableHeaders

logger = logging.getLogger("organiser.access")

# Reviewed for a house app served on one origin. The theme boot script and the
# built CSS are files, so script-src and style-src stay 'self'. Docs stay off;
# Swagger would need a looser policy and is not served on the house.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "img-src 'self' data:; "
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
