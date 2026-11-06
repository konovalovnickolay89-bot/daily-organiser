from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from organiser.config import get_settings

_engine = None
_sessionmaker = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_settings().database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 3},
        )
    return _engine


def get_sessionmaker():
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _sessionmaker


def reset_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _sessionmaker = None


def get_db() -> Generator[Session, None, None]:
    session = get_sessionmaker()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_last_looked_at_column() -> None:
    """Add the last-look timestamp on databases created before catch-up existed.

    ``create_all`` does not alter an existing ``system_state`` table.
    The Alembic baseline already includes this column. These patches stay so a
    database created before the baseline still boots. Stamp that baseline after
    a backup; do not upgrade it onto tables that already exist.
    """
    with get_engine().begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE system_state "
                "ADD COLUMN IF NOT EXISTS last_looked_at TIMESTAMP WITH TIME ZONE"
            )
        )


def ensure_arrived_at_column() -> None:
    """Add the arrival timestamp on databases created before that column existed.

    ``create_all`` does not alter an existing ``system_state`` table.
    """
    with get_engine().begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE system_state "
                "ADD COLUMN IF NOT EXISTS arrived_at TIMESTAMP WITH TIME ZONE"
            )
        )


def ensure_ingest_proposals() -> None:
    """Let a proposal exist without a Mistral run.

    ``create_all`` does not alter an existing ``agent_proposals`` table.
    Ingest cards use ``origin = 'ingest'`` and a null ``run_id``.
    """
    with get_engine().begin() as connection:
        connection.execute(text("ALTER TABLE agent_proposals ALTER COLUMN run_id DROP NOT NULL"))
        connection.execute(text("ALTER TABLE agent_proposals DROP CONSTRAINT IF EXISTS ck_agent_proposals_origin"))
        connection.execute(
            text(
                "ALTER TABLE agent_proposals ADD CONSTRAINT ck_agent_proposals_origin "
                "CHECK (origin in ('feed', 'proactive', 'ingest'))"
            )
        )


def ensure_sprint3() -> None:
    """Commute rows and the catch-up fallback flag on a database from 0002.

    ``create_all`` creates a missing table and does not add a column. These
    statements match Alembic ``0003_sprint3`` and can run twice.
    """
    from organiser.patches import SPRINT3_UPGRADE

    with get_engine().begin() as connection:
        for statement in SPRINT3_UPGRADE:
            connection.execute(text(statement))


def ensure_sprint2() -> None:
    """Shopping, diary rows, and the assistant switch on a database from 0001.

    ``create_all`` creates missing tables and does not add a column or widen a
    check. These statements match Alembic ``0002_sprint2`` and can run twice.
    """
    from organiser.patches import SPRINT2_UPGRADE

    with get_engine().begin() as connection:
        for statement in SPRINT2_UPGRADE:
            connection.execute(text(statement))


def wait_for_database(attempts: int = 30, delay_seconds: float = 1.0) -> None:
    import time

    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:  # connection refused while Postgres is still starting
            last_error = exc
            time.sleep(delay_seconds)
    raise RuntimeError("PostgreSQL did not become ready.") from last_error
