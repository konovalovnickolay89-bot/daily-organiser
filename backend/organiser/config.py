from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Hostname "db" is the compose network. Do not default to 127.0.0.1:5432:
    # Evolving Cook already owns that port on the house box.
    database_url: str = "postgresql+psycopg://organiser:organiser@db:5432/organiser"
    seed_on_start: bool = True
    house_timezone: str = "Europe/London"
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080"
    )
    host: str = "127.0.0.1"
    port: int = 8080

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
