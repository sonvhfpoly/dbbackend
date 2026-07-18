import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# app/ itself (not app/app) is the import root for this codebase (see
# pyproject.toml's pythonpath=["app"] comment) — alembic is invoked with cwd=app/,
# but env.py is loaded from app/alembic/, so app/ must be added to sys.path
# explicitly for `from core... / from domains...` imports below to resolve.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import settings  # noqa: E402
from core.database import Base  # noqa: E402

# Import every domain's models so their tables are registered on Base.metadata
# before autogenerate diffs it — mirrors the same import list main.py keeps
# for Base.metadata.create_all (now retired in favor of these migrations).
from domains.market import models as market_models  # noqa: F401,E402
from domains.student import models as student_models  # noqa: F401,E402
from domains.guidance import models as guidance_models  # noqa: F401,E402
from domains.task import models as task_models  # noqa: F401,E402
from domains.task_builder import models as task_builder_models  # noqa: F401,E402
from domains.evidence import models as evidence_models  # noqa: F401,E402
from domains.eportfolio import models as eportfolio_models  # noqa: F401,E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Real DB URL comes from app settings (.env / real env vars), never from
# alembic.ini — keeps one source of truth and avoids committing a connection
# string. See core/config.py for the env-var precedence.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
