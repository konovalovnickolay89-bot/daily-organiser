"""Environment settings. Secrets stay in the process environment or .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

_PLACEHOLDERS = {
    "change-me",
    "change-me-to-a-long-random-string",
    "replace-me",
    "secret",
    "password",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    auth_secret: str
    session_secret: str = ""
    session_cookie_name: str = "organiser_session"
    session_max_age: int = 1_209_600
    session_https_only: bool = False
    database_path: str = "data/organiser.db"
    host: str = "127.0.0.1"
    port: int = 8000

    def signing_secret(self) -> str:
        return self.session_secret or self.auth_secret

    def resolved_db_path(self) -> Path:
        path = Path(self.database_path)
        if not path.is_absolute():
            path = ROOT / path
        return path


def check_secret(name: str, value: str) -> None:
    stripped = value.strip()
    if (
        stripped != value
        or len(stripped) < 16
        or stripped.lower() in _PLACEHOLDERS
    ):
        raise RuntimeError(
            f"{name} must be a random string of at least 16 characters. "
            "Copy .env.example to .env and replace the placeholder. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )


def ensure_secret(settings: Settings) -> None:
    check_secret("AUTH_SECRET", settings.auth_secret)
    if settings.session_secret:
        check_secret("SESSION_SECRET", settings.session_secret)


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        if any(tuple(err.get("loc", ())) == ("auth_secret",) for err in exc.errors()):
            raise RuntimeError(
                "AUTH_SECRET is not set. Copy .env.example to .env and set AUTH_SECRET "
                "to a long random string."
            ) from exc
        raise
