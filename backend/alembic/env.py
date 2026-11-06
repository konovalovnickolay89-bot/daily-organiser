"""Alembic environment.

The baseline matches the models already created by ``create_all``. On the house
database, stamp this revision after a backup. Do not upgrade it onto tables
that already exist. A fresh empty database can upgrade.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from organiser.config import get_settings
from organiser.models import Base

config = context.config

if config.config_file_name is not None:
    # Leave loggers that already exist enabled. The default turns them off,
    # which hides a later warning in the same process.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def database_url() -> str:
    configured = config.get_main_option("sqlalchemy.url") or ""
    if configured and not configured.startswith("driver://"):
        return configured
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {}) or {}
    section["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
