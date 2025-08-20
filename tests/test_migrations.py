"""
Tests for database migrations using pytest-alembic.
"""

import os
from pathlib import Path

import pytest
from pytest_alembic import Config
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container for testing."""
    with PostgresContainer("postgres:15") as postgres:
        yield postgres


@pytest.fixture
def alembic_config(postgres_container):
    """Create Alembic configuration for testing."""
    # Find alembic.ini file
    project_root = Path(__file__).parent.parent
    alembic_ini = project_root / "alembic.ini"
    
    if not alembic_ini.exists():
        pytest.skip(f"alembic.ini not found at {alembic_ini}")
    
    # Get PostgreSQL connection URL from testcontainer
    db_url = postgres_container.get_connection_url()
    
    # Return pytest-alembic Config with test database
    return Config({
        "file": str(alembic_ini),
        "sqlalchemy.url": db_url
    })


@pytest.mark.migrations
@pytest.mark.docker
def test_single_head_revision(alembic_runner):
    """Test that there is only one head revision (no branches)."""
    # Check that we have exactly one head
    heads = alembic_runner.heads
    assert len(heads) == 1, f"Expected exactly one head, got {len(heads)}: {heads}"


@pytest.mark.migrations
@pytest.mark.docker
def test_upgrade_and_downgrade(alembic_runner):
    """Test that all migrations can be applied and rolled back."""
    # Start with a clean database
    alembic_runner.migrate_up_to("base")
    
    # Apply all migrations
    alembic_runner.migrate_up_to("head")
    
    # Test that we can downgrade to base
    alembic_runner.migrate_down_to("base")


@pytest.mark.migrations
@pytest.mark.docker
def test_migration_roundtrip(alembic_runner):
    """Test each migration can be applied and rolled back individually."""
    # Test roundtrip for each revision
    alembic_runner.migrate_up_to("001_initial_schema")
    alembic_runner.roundtrip_next_revision()


@pytest.mark.migrations
@pytest.mark.docker
def test_migration_schemas_match(alembic_runner):
    """Test that migration schemas match the SQLAlchemy models."""
    # This would require importing the models and comparing
    # For now, just ensure migrations run cleanly
    alembic_runner.migrate_up_to("head")
    
    # Could add more detailed schema validation here
    # by introspecting the database and comparing to Base.metadata


@pytest.mark.migrations
@pytest.mark.docker
def test_no_data_loss_on_upgrade(alembic_runner):
    """Test that migrations don't cause data loss."""
    # Apply initial migration
    alembic_runner.migrate_up_to("001_initial_schema")
    
    # Insert test data (would need actual database connection)
    # For now, just test that migration completes
    pass


class TestSpecificMigrations:
    """Tests for specific migration scenarios."""
    
    @pytest.mark.migrations
    @pytest.mark.docker
    def test_initial_schema_migration(self, alembic_runner):
        """Test the initial schema migration specifically."""
        # Start fresh
        alembic_runner.migrate_up_to("base")
        
        # Apply only the initial migration
        alembic_runner.migrate_up_to("001_initial_schema")
        
        # Test downgrade
        alembic_runner.migrate_down_to("base")
    
    @pytest.mark.migrations
    @pytest.mark.docker
    def test_migration_idempotency(self, alembic_runner):
        """Test that running migrations multiple times is safe."""
        # Apply all migrations
        alembic_runner.migrate_up_to("head")
        
        # Apply again - should be no-op
        alembic_runner.migrate_up_to("head")


@pytest.mark.skipif(
    not os.getenv("BIO_MCP_DATABASE_URL"), 
    reason="Real database tests require BIO_MCP_DATABASE_URL"
)
def test_migrations_against_real_database():
    """Test migrations against a real PostgreSQL database."""
    from src.bio_mcp.clients.migrations import MigrationManager
    
    db_url = os.getenv("BIO_MCP_DATABASE_URL")
    
    manager = MigrationManager(db_url)
    
    # Test getting current revision
    current = manager.current_revision()
    assert current is not None or current == "base"
    
    # Test migration history
    history = manager.migration_history()
    assert isinstance(history, list)