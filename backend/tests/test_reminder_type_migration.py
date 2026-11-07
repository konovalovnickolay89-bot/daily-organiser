"""Disposable upgrade and downgrade for the reminder type columns.

Uses a new database and drops it. Does not touch the house database, and does
not use the organiser or organiser_test databases.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

from organiser.config import get_settings
from organiser.models import Base

BACKEND = Path(__file__).resolve().parents[1]
DATABASE = "reminder_types_mig"
TASK_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
MEMORY_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


def _admin(url):
    return url.set(drivername="postgresql", database="postgres")


def _connect(url):
    return psycopg.connect(_admin(url).render_as_string(hide_password=False), autocommit=True)


def _recreate(url):
    with _connect(url) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(DATABASE))
        )
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))


def _drop(url):
    with _connect(url) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(DATABASE))
        )


def _alembic(url, *args):
    env = os.environ.copy()
    env["DATABASE_URL"] = url.set(database=DATABASE).render_as_string(hide_password=False)
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(f"alembic {args} failed\n{completed.stdout}\n{completed.stderr}")
    return completed.stdout


def _columns(engine):
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'reminder_control' ORDER BY column_name"
            )
        ).scalars()
        return set(rows)


def _plant(engine):
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tasks (id, title) VALUES (:id, :title)"),
            {"id": TASK_ID, "title": "Water the plants"},
        )
        connection.execute(
            text(
                "INSERT INTO memory_items (id, kind, text, source, created_at) "
                "VALUES (:id, 'fact', :text, 'manual', now())"
            ),
            {"id": MEMORY_ID, "text": "The spare key is in the hall drawer"},
        )


def _survives(engine):
    with engine.connect() as connection:
        task = connection.execute(text("SELECT title FROM tasks WHERE id = :id"), {"id": TASK_ID}).scalar()
        memory = connection.execute(text("SELECT text FROM memory_items WHERE id = :id"), {"id": MEMORY_ID}).scalar()
    assert task == "Water the plants"
    assert memory == "The spare key is in the hall drawer"


def test_type_columns_from_0006_and_from_the_three_column_table():
    base = make_url(get_settings().database_url)
    if base.database == DATABASE:
        pytest.skip("The test database is the throwaway name.")
    engine = None
    _recreate(base)
    try:
        target = base.set(database=DATABASE)
        engine = create_engine(target.render_as_string(hide_password=False))
        heads = _alembic(base, "heads")
        assert "reminder_types_off" in heads
        assert heads.count("(head)") == 1

        _alembic(base, "upgrade", "0006_sprint7")
        _plant(engine)

        _alembic(base, "upgrade", "reminder_switch_off")
        assert _columns(engine) == {"id", "enabled", "updated_at"}
        Base.metadata.create_all(engine)
        assert _columns(engine) == {"id", "enabled", "updated_at"}
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO reminder_control (id, enabled) VALUES (1, true)"))

        from organiser.agent.local_reminders import TypesUnavailable, reminder_flags, set_reminder_flags
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime(2026, 11, 7, 18, 0, tzinfo=ZoneInfo("Europe/London"))
        with Session(engine) as session:
            flags = reminder_flags(session)
            assert flags.master is True
            assert flags.types_ready is False
            assert flags.overdue is False
            with pytest.raises(TypesUnavailable):
                set_reminder_flags(session, now, overdue=True)
            session.rollback()
            kept = set_reminder_flags(session, now, enabled=True)
            session.commit()
        assert kept.master is True
        assert kept.types_ready is False
        assert _columns(engine) == {"id", "enabled", "updated_at"}

        _alembic(base, "upgrade", "head")
        assert _columns(engine) == {"id", "enabled", "overdue", "stalled", "upcoming", "updated_at"}
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT enabled, overdue, stalled, upcoming FROM reminder_control WHERE id = 1")
            ).one()
        assert row == (True, False, False, False)
        with engine.begin() as connection:
            connection.execute(text("UPDATE reminder_control SET overdue = true, stalled = true WHERE id = 1"))

        _alembic(base, "downgrade", "reminder_switch_off")
        assert _columns(engine) == {"id", "enabled", "updated_at"}
        with engine.connect() as connection:
            enabled = connection.execute(text("SELECT enabled FROM reminder_control WHERE id = 1")).scalar()
        assert enabled is True
        _survives(engine)

        _alembic(base, "downgrade", "0006_sprint7")
        assert _columns(engine) == set()
        _survives(engine)

        _alembic(base, "upgrade", "head")
        assert _columns(engine) == {"id", "enabled", "overdue", "stalled", "upcoming", "updated_at"}
        with engine.connect() as connection:
            present = connection.execute(text("SELECT count(*) FROM reminder_control")).scalar()
        assert present == 0
        _survives(engine)
    finally:
        if engine is not None:
            engine.dispose()
        _drop(base)
