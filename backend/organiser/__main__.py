"""Run the API and, when frontend/dist exists, the built UI.

Bind address comes from HOST and PORT (see .env.example).
"""

import uvicorn

from organiser.config import ensure_secret, get_settings


def main() -> None:
    settings = get_settings()
    ensure_secret(settings)
    uvicorn.run(
        "organiser.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
    )


if __name__ == "__main__":
    main()
