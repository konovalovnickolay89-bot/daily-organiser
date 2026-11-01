from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from organiser.config import get_settings

_engine = None
_sessionmaker = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
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
