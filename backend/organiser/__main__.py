import uvicorn

from organiser.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "organiser.main:app",
        host=settings.host,
        port=settings.port,
        factory=False,
    )


if __name__ == "__main__":
    main()
