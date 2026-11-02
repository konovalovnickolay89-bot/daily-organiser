from functools import lru_cache

from pydantic import SecretStr
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

    # Mistral assistant. With the key or the agent id empty, the assistant is off
    # and nothing is sent. Never commit either value: on the house box they live
    # in /etc/daily-organiser.env. See docs/mistral-agent.md.
    mistral_api_key: SecretStr = SecretStr("")
    mistral_agent_id: str = ""
    mistral_model: str = "mistral-medium-latest"
    mistral_base_url: str = "https://api.mistral.ai"
    mistral_timeout_seconds: float = 60.0
    # "high" by default. Empty leaves the model's own default.
    mistral_reasoning_effort: str = "high"
    # Cost guard across every trigger, and the cap on proposals Nick did not ask for.
    agent_runs_per_day: int = 12
    agent_proactive_per_day: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @property
    def assistant_enabled(self) -> bool:
        return bool(self.mistral_api_key.get_secret_value().strip() and self.mistral_agent_id.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
