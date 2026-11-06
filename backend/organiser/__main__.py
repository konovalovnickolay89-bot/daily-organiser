import uvicorn

from organiser.config import get_settings
from organiser.jsonlog import configure_logging


def main() -> None:
    configure_logging()
    settings = get_settings()
    uvicorn.run(
        "organiser.main:app",
        host=settings.host,
        port=settings.port,
        factory=False,
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
