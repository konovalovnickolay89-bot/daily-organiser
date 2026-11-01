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


def test_compose_does_not_publish_postgres():
    assert "5432:5432" not in COMPOSE
    assert "ports:" in COMPOSE
    db_section = COMPOSE.split("services:", 1)[1].split("api:", 1)[0]
    assert "ports:" not in db_section
