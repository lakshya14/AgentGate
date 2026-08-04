from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# --- Project-specific imports ---
from config import settings
from database import Base
import models  # registers GithubEvent, AuditLog on Base.metadata

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Override sqlalchemy.url with the value from our .env (via pydantic-settings)
# This avoids hardcoding credentials in alembic.ini
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate — Alembic diffs this against the live DB
target_metadata = Base.metadata

# Tables created and managed by LangGraph's AsyncPostgresSaver checkpointer.
# They exist in the DB but have no SQLAlchemy model — Alembic must NOT touch these.
_UNMANAGED_TABLES = {
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
}

def include_object(object, name, type_, reflected, compare_to):
    """Filter function that tells Alembic autogenerate which DB objects to manage.

    Only tables declared in Base.metadata (our SQLAlchemy models) are managed.
    All other tables (LangGraph, pgvector, etc.) are silently ignored.
    """
    if type_ == "table" and name in _UNMANAGED_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without connecting).

    Useful for reviewing what SQL would be executed before applying it.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connects and applies migrations directly)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
