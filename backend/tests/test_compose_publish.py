import re
from pathlib import Path

def _compose_text() -> str:
    here = Path(__file__).resolve().parent
    for ancestor in list(here.parents)[:4]:
        candidate = ancestor / "docker-compose.yml"
        if candidate.is_file():
            return candidate.read_text()
    raise FileNotFoundError("docker-compose.yml")


COMPOSE = _compose_text()


def test_compose_publishes_only_the_loopback_api():
    published = re.findall(r'^\s*-\s*"([^"]+)"\s*$', COMPOSE, re.MULTILINE)
    assert published == ["127.0.0.1:8080:8080"]


def test_compose_db_image_has_pgvector():
    db_section = COMPOSE.split("services:", 1)[1].split("api:", 1)[0]
    assert "pgvector/pgvector:pg16" in db_section
    assert "postgres:16-alpine" not in db_section


DOCUMENTED_TRANSCRIBE_MODEL = "voxtral-mini-transcribe-3"
_SHORT_DEFAULT = re.compile(
    r"MISTRAL_TRANSCRIBE_MODEL(?::\s*\$\{[^}:]*:-|=)\s*voxtral-mini(?!-)"
)


def _compose_root() -> Path:
    here = Path(__file__).resolve().parent
    for ancestor in list(here.parents)[:4]:
        if (ancestor / "docker-compose.yml").is_file():
            return ancestor
    raise FileNotFoundError("docker-compose.yml")


def _effective_model(shell_value: str | None, fallback: str) -> str:
    """Compose ``${VAR:-default}``: unset or empty uses the default. Any other value is passed through."""
    if shell_value is None or shell_value == "":
        return fallback
    return shell_value


def test_compose_transcribe_default_matches_the_app():
    from organiser.config import Settings

    app_default = Settings.model_fields["mistral_transcribe_model"].default
    found = re.findall(
        r"^ *MISTRAL_TRANSCRIBE_MODEL:\s*\$\{MISTRAL_TRANSCRIBE_MODEL:-([^}]+)\}\s*$",
        COMPOSE,
        re.MULTILINE,
    )
    assert found == [DOCUMENTED_TRANSCRIBE_MODEL]
    assert app_default == DOCUMENTED_TRANSCRIBE_MODEL
    fallback = found[0]
    assert _effective_model(None, fallback) == DOCUMENTED_TRANSCRIBE_MODEL
    assert _effective_model("", fallback) == DOCUMENTED_TRANSCRIBE_MODEL
    assert _effective_model("voxtral-small-transcribe-3", fallback) == "voxtral-small-transcribe-3"

    root = _compose_root()
    example = (root / ".env.example").read_text()
    assignments = [
        line.strip().lstrip("#").strip()
        for line in example.splitlines()
        if "MISTRAL_TRANSCRIBE_MODEL=" in line
    ]
    assert assignments == [f"MISTRAL_TRANSCRIBE_MODEL={DOCUMENTED_TRANSCRIBE_MODEL}"]
    for path in (root / "docker-compose.yml", root / ".env.example"):
        assert _SHORT_DEFAULT.search(path.read_text()) is None


def test_compose_does_not_publish_postgres():
    assert "5432:5432" not in COMPOSE
    assert "ports:" in COMPOSE
    db_section = COMPOSE.split("services:", 1)[1].split("api:", 1)[0]
    assert "ports:" not in db_section
