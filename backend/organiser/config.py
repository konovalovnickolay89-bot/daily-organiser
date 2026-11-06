from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _secret_set(value: SecretStr) -> bool:
    return bool(value.get_secret_value().strip())


def calendar_id_list(raw: str) -> tuple[str, ...]:
    """Comma-separated diary ids. A blank value means the primary calendar only.

    The diary is read-only. This does not call Google.
    """
    parts = tuple(part.strip() for part in raw.split(",") if part.strip())
    return parts or ("primary",)


# The label "Wembley" means this TfL point. The journey origin is home
# (coordinates or postcode), not a station name. The lookup lives in
# services/commute.py and does not log the origin or the key.
WEMBLEY_POINT = "Wembley Park"
COMMUTE_ORIGIN = "home"


def commute_point_for_label(label: str) -> str | None:
    """Map the one commute label this house accepts. Any other label is ignored."""
    if label.strip().casefold() == "wembley":
        return WEMBLEY_POINT
    return None


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

    # Public /docs, /redoc, and /openapi.json stay off unless BOTH are true.
    # Turn them on later only when Cloudflare Access already covers those paths.
    # This process does not check Access and will not serve docs for a public URL.
    enable_docs: bool = False
    docs_behind_access: bool = False

    # Mistral assistant. With the key or the agent id empty, the assistant is off
    # and nothing is sent. Never commit either value. discovery-system keeps it in
    # the house environment file. See docs/mistral-agent.md.
    mistral_api_key: SecretStr = SecretStr("")
    mistral_agent_id: str = ""
    mistral_model: str = "mistral-medium-latest"
    # Embeddings for memory. Empty key skips the call and retrieval uses words.
    mistral_embed_model: str = "mistral-embed"
    # Voice on Smart Add. Off until the house sets this. The model is Voxtral.
    voice_input_enabled: bool = False
    mistral_transcribe_model: str = "voxtral-mini"
    mistral_base_url: str = "https://api.mistral.ai"
    # One Mistral call. Together with the run deadline this stays inside the
    # proxy's ~100s limit. See RUN_DEADLINE_SECONDS in agent/runner.py.
    mistral_timeout_seconds: float = 25.0
    # "high" by default. Empty leaves the model's own default.
    mistral_reasoning_effort: str = "high"
    # Cost guard across every trigger, and the cap on proposals Nick did not ask for.
    agent_runs_per_day: int = 12
    agent_proactive_per_day: int = 3
    # Burst limits for this process. They reset on restart. See organiser/limits.py.
    rate_feed_per_minute: int = 6
    rate_ingest_per_minute: int = 30
    rate_commute_per_hour: int = 12

    # Home location for a later weather line and commute origin.
    # Set both coordinates, or a postcode, in the house file only.
    # Coordinates win when both are set. Never log the values, and never commit them.
    house_lat: SecretStr = SecretStr("")
    house_lon: SecretStr = SecretStr("")
    house_postcode: SecretStr = SecretStr("")

    # Diary, later, read-only. Empty stays "not configured" on Settings.
    # A future client may request only calendar.events.readonly and
    # calendar.calendarlist.readonly. It must not request a write scope.
    google_oauth_client_id: SecretStr = SecretStr("")
    google_oauth_client_secret: SecretStr = SecretStr("")
    google_oauth_refresh_token: SecretStr = SecretStr("")
    # Blank means primary. The ids are not shown on Settings and are not logged.
    google_calendar_ids: SecretStr = SecretStr("")

    # Commute. A label of Wembley means Wembley Park. Origin is home.
    # Empty leaves the brief line and the push unwired. Never log either value.
    tfl_app_key: SecretStr = SecretStr("")
    banto_commute_token: SecretStr = SecretStr("")

    # Signed inbound webhooks. Empty means that source answers 503.
    # WEBHOOK_SECRET_BANTO_X signs POST /hooks/banto_x. Those x.* events join the
    # same pipeline as the poll. Nothing is accepted while X_ENABLED is off.
    webhook_secret_banto: SecretStr = SecretStr("")
    webhook_secret_banto_x: SecretStr = SecretStr("")

    # X, Nick's own developer app. Off until X_ENABLED is set. Tokens are sealed
    # with X_TOKEN_KEY and are never logged. The redirect must match the app.
    x_enabled: bool = False
    x_client_id: SecretStr = SecretStr("")
    x_client_secret: SecretStr = SecretStr("")
    x_redirect_uri: str = "https://organiser.apidiscoverysolution.uk/x/callback"
    x_token_key: SecretStr = SecretStr("")
    x_poll_minutes: int = 30

    # hearthis.at profile. Empty source keeps the line hidden. SHOW_PLAYLIST
    # defaults to on once a source is set. The line links out. It does not play.
    playlist_source: str = ""
    hearthis_profile: str = "chlorophil"
    show_playlist: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @property
    def assistant_enabled(self) -> bool:
        return bool(self.mistral_api_key.get_secret_value().strip() and self.mistral_agent_id.strip())

    @property
    def home_location_kind(self) -> str | None:
        """``coordinates`` when both are set, else ``postcode``, else nothing.

        The return value is the kind, never the location itself.
        """
        if _secret_set(self.house_lat) and _secret_set(self.house_lon):
            return "coordinates"
        if _secret_set(self.house_postcode):
            return "postcode"
        return None

    @property
    def weather_location_configured(self) -> bool:
        return self.home_location_kind is not None

    @property
    def diary_configured(self) -> bool:
        return (
            _secret_set(self.google_oauth_client_id)
            and _secret_set(self.google_oauth_client_secret)
            and _secret_set(self.google_oauth_refresh_token)
        )

    @property
    def calendar_ids(self) -> tuple[str, ...]:
        return calendar_id_list(self.google_calendar_ids.get_secret_value())

    @property
    def tfl_configured(self) -> bool:
        return _secret_set(self.tfl_app_key)

    @property
    def banto_configured(self) -> bool:
        return _secret_set(self.banto_commute_token)

    @property
    def playlist_on(self) -> bool:
        """True when a source is set and the line has not been turned off.

        An empty SHOW_PLAYLIST means on, once PLAYLIST_SOURCE is hearthis.
        """
        if self.playlist_source.strip().casefold() != "hearthis":
            return False
        flag = self.show_playlist.strip().casefold()
        return flag not in {"0", "false", "no", "off"}

    @property
    def poll_interval_minutes(self) -> int:
        return min(24 * 60, max(1, self.x_poll_minutes))


@lru_cache
def get_settings() -> Settings:
    return Settings()
