"""The baseline revision matches the current models on an empty database."""

from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import make_url

from organiser.config import get_settings
from organiser.models import Base

ALEMBIC_DB = "organiser_alembic"


def _alembic_ini() -> Path:
    here = Path(__file__).resolve().parent
    for ancestor in list(here.parents)[:4]:
        for candidate in (ancestor / "alembic.ini", ancestor / "backend" / "alembic.ini"):
            if candidate.is_file():
                return candidate
    raise FileNotFoundError("alembic.ini")


def _admin_url():
    return make_url(get_settings().database_url).set(drivername="postgresql", database="postgres")


def _recreate() -> str:
    target = make_url(get_settings().database_url).set(database=ALEMBIC_DB)
    with psycopg.connect(_admin_url().render_as_string(hide_password=False), autocommit=True) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(ALEMBIC_DB))
        )
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(ALEMBIC_DB)))
    return target.render_as_string(hide_password=False)


def _drop() -> None:
    with psycopg.connect(_admin_url().render_as_string(hide_password=False), autocommit=True) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(ALEMBIC_DB))
        )


def test_baseline_upgrade_matches_models():
    url = _recreate()
    cfg = Config(str(_alembic_ini()))
    cfg.set_main_option("sqlalchemy.url", url)
    engine = create_engine(url)
    try:
        command.upgrade(cfg, "head")
        names = set(inspect(engine).get_table_names())
        assert set(Base.metadata.tables) <= names
        assert "alembic_version" in names
        inspector = inspect(engine)
        for name, table in Base.metadata.tables.items():
            db_cols = {column["name"] for column in inspector.get_columns(name)}
            assert db_cols == {column.name for column in table.columns}, name
        with engine.connect() as connection:
            origin = connection.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname = 'ck_agent_proposals_origin'"
                )
            ).scalar_one()
            effect = connection.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname = 'ck_action_requests_no_effect'"
                )
            ).scalar_one()
        assert "ingest" in origin
        assert "effect_applied" in effect
        with engine.connect() as connection:
            action = connection.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname = 'ck_agent_proposals_action'"
                )
            ).scalar_one()
            extension = connection.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar_one()
        assert "remember" in action
        assert "forget" in action
        assert extension == 1
        command.downgrade(cfg, "0003_sprint3")
        after = set(inspect(engine).get_table_names())
        assert "memory_items" not in after
        assert "tasks" in after
        with engine.connect() as connection:
            rolled = connection.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname = 'ck_agent_proposals_action'"
                )
            ).scalar_one()
        assert "remember" not in rolled
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        left = set(inspect(engine).get_table_names())
        assert "tasks" not in left
        assert left <= {"alembic_version"}
    finally:
        engine.dispose()
        _drop()
