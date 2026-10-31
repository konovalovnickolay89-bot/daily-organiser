"""SQLite connection and schema. The database file lives under data/."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from organiser.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    due_date TEXT,
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high')),
    status TEXT NOT NULL DEFAULT 'todo'
        CHECK (status IN ('todo', 'doing', 'done')),
    recurring INTEGER NOT NULL DEFAULT 0 CHECK (recurring IN (0, 1)),
    assist_mode TEXT NOT NULL DEFAULT 'when_useful'
        CHECK (assist_mode IN ('off', 'when_useful')),
    context_hint TEXT,
    source TEXT NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'bot')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    body TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    task_id INTEGER,
    source TEXT NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'bot')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at);
"""


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column(conn: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    if name not in _column_names(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _migrate(conn: sqlite3.Connection) -> None:
    """Add assist hooks to a database created before those columns existed."""
    if "tasks" in _tables(conn):
        _add_column(conn, "tasks", "assist_mode", "TEXT NOT NULL DEFAULT 'when_useful'")
        _add_column(conn, "tasks", "context_hint", "TEXT")
        _add_column(conn, "tasks", "source", "TEXT NOT NULL DEFAULT 'manual'")
    if "notes" in _tables(conn):
        _add_column(conn, "notes", "source", "TEXT NOT NULL DEFAULT 'manual'")


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 3000")
    return conn


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    """Open, commit, and close on the calling thread.

    Do not wrap this in a FastAPI yield dependency. That framework can resume
    the generator on another thread, and sqlite refuses the hand-off.
    """
    conn = connect(get_settings().resolved_db_path())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Path) -> None:
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL").fetchone()
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()
