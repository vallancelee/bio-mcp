"""
Database migration management for Bio-MCP.
"""

import asyncio
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from ..config.logging_config import get_logger

logger = get_logger(__name__)


class MigrationManager:
    """Manages database migrations using Alembic."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.alembic_cfg = self._get_alembic_config()

    def _get_alembic_config(self) -> Config:
        """Get Alembic configuration."""
        # Find alembic.ini file in project root
        project_root = Path(__file__).parent.parent.parent.parent
        alembic_ini = project_root / "alembic.ini"
        
        if not alembic_ini.exists():
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")

        # Create Alembic config
        alembic_cfg = Config(str(alembic_ini))
        
        # Set the database URL
        # Convert asyncpg URLs to sync for Alembic
        sync_url = self.database_url
        if sync_url.startswith('postgresql+asyncpg://'):
            sync_url = sync_url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
        elif sync_url.startswith('postgresql://'):
            sync_url = sync_url.replace('postgresql://', 'postgresql+psycopg2://')
        
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        
        return alembic_cfg

    def current_revision(self) -> str | None:
        """Get the current database revision."""
        try:
            from alembic.runtime.migration import MigrationContext
            from sqlalchemy import create_engine
            
            # Create sync engine for Alembic operations
            sync_url = self.database_url
            if sync_url.startswith('postgresql+asyncpg://'):
                sync_url = sync_url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
            elif sync_url.startswith('postgresql://'):
                sync_url = sync_url.replace('postgresql://', 'postgresql+psycopg2://')
                
            engine = create_engine(sync_url)
            
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return context.get_current_revision()
                
        except Exception as e:
            logger.error(f"Failed to get current revision: {e}")
            return None

    def upgrade_to_latest(self) -> None:
        """Upgrade database to the latest revision."""
        try:
            logger.info("Running database migrations...")
            
            # Set environment variable for migration scripts
            os.environ['BIO_MCP_DATABASE_URL'] = self.database_url
            
            # Run migrations
            command.upgrade(self.alembic_cfg, "head")
            
            logger.info("Database migrations completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise

    def create_revision(self, message: str, autogenerate: bool = True) -> str:
        """Create a new migration revision."""
        try:
            logger.info(f"Creating new migration: {message}")
            
            # Set environment variable for migration scripts
            os.environ['BIO_MCP_DATABASE_URL'] = self.database_url
            
            # Create revision
            if autogenerate:
                revision = command.revision(
                    self.alembic_cfg, 
                    message=message, 
                    autogenerate=True
                )
            else:
                revision = command.revision(
                    self.alembic_cfg, 
                    message=message
                )
            
            logger.info(f"Created migration revision: {revision.revision}")
            return revision.revision
            
        except Exception as e:
            logger.error(f"Failed to create migration: {e}")
            raise

    def migration_history(self) -> list[dict]:
        """Get migration history."""
        try:
            from alembic.runtime.migration import MigrationContext
            from sqlalchemy import create_engine
            
            # Create sync engine for Alembic operations  
            sync_url = self.database_url
            if sync_url.startswith('postgresql+asyncpg://'):
                sync_url = sync_url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
            elif sync_url.startswith('postgresql://'):
                sync_url = sync_url.replace('postgresql://', 'postgresql+psycopg2://')
                
            engine = create_engine(sync_url)
            
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return [
                    {
                        "revision": rev.revision,
                        "down_revision": rev.down_revision,
                        "description": rev.doc
                    }
                    for rev in context.get_revisions()
                ]
                
        except Exception as e:
            logger.error(f"Failed to get migration history: {e}")
            return []

    def ensure_database_current(self) -> bool:
        """Ensure database is up to date with latest migrations."""
        try:
            current = self.current_revision()
            
            if current is None:
                logger.info("Database has no migration history, running initial migration...")
                self.upgrade_to_latest()
                return True
            
            # Check if we need to upgrade
            from alembic.script import ScriptDirectory
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            head_revision = script_dir.get_current_head()
            
            if current == head_revision:
                logger.info("Database is up to date")
                return True
            else:
                logger.info(f"Database needs upgrade from {current} to {head_revision}")
                self.upgrade_to_latest()
                return True
                
        except Exception as e:
            logger.error(f"Failed to ensure database is current: {e}")
            return False


async def run_migrations(database_url: str) -> bool:
    """
    Run database migrations asynchronously.
    
    Returns:
        bool: True if migrations completed successfully, False otherwise
    """
    try:
        # Run migrations in a thread pool since Alembic is synchronous
        loop = asyncio.get_event_loop()
        migration_manager = MigrationManager(database_url)
        
        # Run in thread pool to avoid blocking
        success = await loop.run_in_executor(
            None, 
            migration_manager.ensure_database_current
        )
        
        return success
        
    except Exception as e:
        logger.error(f"Async migration failed: {e}")
        return False


def init_migrations():
    """Initialize migration system - run this once to set up Alembic."""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        alembic_ini = project_root / "alembic.ini"
        
        if not alembic_ini.exists():
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")
            
        alembic_cfg = Config(str(alembic_ini))
        command.init(alembic_cfg, "migrations")
        
        logger.info("Migration system initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize migrations: {e}")
        raise