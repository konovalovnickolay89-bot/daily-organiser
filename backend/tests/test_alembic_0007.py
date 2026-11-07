"""Alembic 0007 adds the memory search column and can come back down."""

from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import make_url

from organiser.config import get_settings

ALEMBIC_DB = "organiser_alembic_0007"


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
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(ALEMBIC_DB)))
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(ALEMBIC_DB)))
    return target.render_as_string(hide_password=False)


def _drop() -> None:
    with psycopg.connect(_admin_url().render_as_string(hide_password=False), autocommit=True) as connection:
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(ALEMBIC_DB)))


def test_0007_upgrade_and_downgrade():
    url = _recreate()
    cfg = Config(str(_alembic_ini()))
    cfg.set_main_option("sqlalchemy.url", url)
    engine = create_engine(url)
    try:
        command.upgrade(cfg, "0006_sprint7")
        assert "search_vector" not in {column["name"] for column in inspect(engine).get_columns("memory_items")}
        assert "house_settings" not in inspect(engine).get_table_names()

        command.upgrade(cfg, "0007_settings_search")
        columns = {column["name"] for column in inspect(engine).get_columns("memory_items")}
        assert "search_vector" in columns
        settings_columns = {column["name"] for column in inspect(engine).get_columns("house_settings")}
        assert "x_sync_minutes" in settings_columns
        assert "playlist_enabled" in settings_columns
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO memory_items (id, kind, text, source, created_at, pinned) "
                    "VALUES (gen_random_uuid(), 'fact', 'oat milk stays in the door', 'manual', now(), true)"
                )
            )
            matched = connection.execute(
                text(
                    "SELECT count(*) FROM memory_items "
                    "WHERE search_vector @@ plainto_tsquery('english', 'milk')"
                )
            ).scalar_one()
            index = connection.execute(
                text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_memory_items_search'")
            ).scalar_one()
            trigger = connection.execute(
                text("SELECT 1 FROM pg_trigger WHERE tgname = 'trg_memory_items_search'")
            ).scalar_one()
        assert matched == 1
        assert "gin" in index.lower()
        assert trigger == 1

        command.downgrade(cfg, "0006_sprint7")
        after = inspect(engine)
        assert "search_vector" not in {column["name"] for column in after.get_columns("memory_items")}
        assert "house_settings" not in after.get_table_names()
        assert "memory_items" in after.get_table_names()

        command.upgrade(cfg, "head")
        assert "search_vector" in {column["name"] for column in inspect(engine).get_columns("memory_items")}
        command.downgrade(cfg, "0006_sprint7")
        assert "house_settings" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
        _drop()
