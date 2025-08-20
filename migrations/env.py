"""
Alembic environment configuration for Bio-MCP database migrations.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Import your models here
from src.bio_mcp.clients.database import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_database_url():
    """Get database URL from environment variables or config."""
    # First try to get URL from alembic config (for tests)
    url = config.get_main_option("sqlalchemy.url")
    
    # Fall back to environment variable
    if not url:
        url = os.getenv('BIO_MCP_DATABASE_URL')
    
    if not url:
        raise ValueError("Database URL must be provided via alembic config or BIO_MCP_DATABASE_URL environment variable")
    
    # Convert URLs for sync migrations (Alembic standard)
    if url.startswith('postgresql+asyncpg://'):
        # Convert asyncpg to psycopg2 for sync operations
        url = url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
    elif url.startswith('postgresql://') and not url.startswith('postgresql+'):
        # Ensure we use psycopg2 for synchronous operations
        url = url.replace('postgresql://', 'postgresql+psycopg2://')
    
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_sync() -> None:
    """Run migrations in 'online' mode with sync engine."""
    from sqlalchemy import create_engine
    
    connectable = create_engine(
        get_database_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = create_async_engine(
        get_database_url(),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Always use sync engine for migrations - Alembic works better with sync
    run_migrations_sync()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()