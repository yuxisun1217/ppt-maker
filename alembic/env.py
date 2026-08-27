"""Alembic environment. Reads DATABASE_URL from .env (or the environment),
defaulting to the project's SQLite file. Postgres: set DATABASE_URL to a
postgresql+psycopg2:// URL and run `alembic upgrade head`."""
import os
import sys
from pathlib import Path
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / '.env')

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from database.models import Base  # noqa: E402  (target metadata for autogenerate)

target_metadata = Base.metadata


def _database_url() -> str:
    env_url = os.environ.get('DATABASE_URL')
    if env_url:
        return env_url
    return f'sqlite:///{(BASE_DIR / "app_data.db").as_posix()}'


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DB connection)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        {'sqlalchemy.url': _database_url()},
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite needs batch mode for ALTER TABLE in future migrations
            render_as_batch=connection.dialect.name == 'sqlite',
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
