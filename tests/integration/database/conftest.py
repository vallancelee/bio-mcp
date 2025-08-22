"""
TestContainers configuration for database integration tests.

This file provides fixtures for using real PostgreSQL containers in tests,
eliminating async mocking complexity. Integrates with global test configuration.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer

from bio_mcp.shared.clients.database import (
    DatabaseConfig,
    DatabaseManager,
)

# Mark all tests in this module as requiring Docker
pytestmark = [pytest.mark.docker, pytest.mark.integration]


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container():
    """
    Provide a PostgreSQL container for the entire test session.

    This container is shared across all tests for performance.
    Each test should clean up its data or use isolated schemas.
    """
    container = PostgresContainer(
        image="postgres:15-alpine",
        username="bio_mcp_test",
        password="test_password",
        dbname="bio_mcp_test",
    )

    # Start container
    container.start()

    # Log connection details for debugging
    print("\nPostgreSQL Test Container Started")
    print(f"Connection URL: {container.get_connection_url()}")
    print(
        f"Container: {container._container.name if hasattr(container, '_container') else 'N/A'}"
    )

    yield container

    # Cleanup
    container.stop()


@pytest_asyncio.fixture(scope="function")
async def db_manager(postgres_container) -> AsyncGenerator[DatabaseManager, None]:
    """
    Provide a DatabaseManager connected to the test PostgreSQL container.

    Each test function gets its own DatabaseManager instance.
    """
    # Get connection URL and convert to async
    connection_url = postgres_container.get_connection_url()
    # Replace both possible sync drivers with asyncpg
    async_url = connection_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )
    async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")

    # Create and initialize manager
    config = DatabaseConfig(
        url=async_url,
        pool_size=5,
        max_overflow=10,
        echo=False,  # Set to True for SQL debugging
    )

    manager = DatabaseManager(config)
    await manager.initialize()

    yield manager

    # Cleanup connections
    await manager.close()


@pytest_asyncio.fixture(scope="function")
async def clean_db(
    db_manager: DatabaseManager,
) -> AsyncGenerator[DatabaseManager, None]:
    """
    Provide a clean database state for each test.

    This fixture ensures each test starts with empty tables.
    """
    # Clear all data from tables
    async with db_manager.get_session() as session:
        # Delete in correct order to respect foreign keys
        await session.execute(text("DELETE FROM corpus_checkpoints"))
        await session.execute(text("DELETE FROM sync_watermarks"))
        await session.execute(text("DELETE FROM pubmed_documents"))
        await session.commit()

    yield db_manager

    # Optional: Clean up after test
    async with db_manager.get_session() as session:
        await session.execute(text("DELETE FROM corpus_checkpoints"))
        await session.execute(text("DELETE FROM sync_watermarks"))
        await session.execute(text("DELETE FROM pubmed_documents"))
        await session.commit()


@pytest_asyncio.fixture(scope="function")
async def db_with_sample_data(
    clean_db: DatabaseManager,
) -> tuple[DatabaseManager, dict]:
    """
    Provide a database with sample data for testing.

    Returns a tuple of (DatabaseManager, sample_data_dict).
    """
    sample_data = {"documents": [], "watermarks": [], "checkpoints": []}

    # Create sample documents
    for i in range(10):
        doc = await clean_db.create_document(
            {
                "pmid": f"SAMPLE_{i:04d}",
                "title": f"Sample Document {i}",
                "abstract": f"This is the abstract for sample document {i}.",
                "authors": [f"Author {i}A", f"Author {i}B"],
                "journal": "Test Journal",
                "keywords": ["sample", "test", f"category_{i % 3}"],
            }
        )
        sample_data["documents"].append(doc)

    # Create sample watermarks
    watermark1 = await clean_db.create_or_update_sync_watermark(
        query_key="test_query_1",
        last_edat="2024/01/01",
        total_synced="5",
        last_sync_count="5",
    )
    sample_data["watermarks"].append(watermark1)

    watermark2 = await clean_db.create_or_update_sync_watermark(
        query_key="test_query_2",
        last_edat="2024/01/02",
        total_synced="5",
        last_sync_count="5",
    )
    sample_data["watermarks"].append(watermark2)

    # Create sample checkpoint
    checkpoint = await clean_db.create_corpus_checkpoint(
        checkpoint_id="test_checkpoint_001",
        name="Test Checkpoint",
        description="Sample checkpoint for testing",
        primary_queries=["test_query_1", "test_query_2"],
    )
    sample_data["checkpoints"].append(checkpoint)

    return clean_db, sample_data


@pytest_asyncio.fixture(scope="function")
async def isolated_db_manager(
    postgres_container,
) -> AsyncGenerator[DatabaseManager, None]:
    """
    Provide a DatabaseManager with an isolated schema for parallel test execution.

    Each test gets its own PostgreSQL schema, allowing safe parallel execution.
    """
    import uuid

    import asyncpg

    # Generate unique schema name
    schema_name = f"test_{uuid.uuid4().hex[:8]}"

    # Get base connection URL
    connection_url = postgres_container.get_connection_url()

    # Create schema using asyncpg directly (remove driver spec for asyncpg)
    asyncpg_url = connection_url.replace("postgresql+psycopg2://", "postgresql://")
    conn = await asyncpg.connect(asyncpg_url)
    try:
        await conn.execute(f"CREATE SCHEMA {schema_name}")
    finally:
        await conn.close()

    # Create manager with schema-specific search path
    # Replace both possible sync drivers with asyncpg
    async_url = connection_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )
    async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")
    config = DatabaseConfig(
        url=f"{async_url}?options=-csearch_path={schema_name}", pool_size=5, echo=False
    )

    manager = DatabaseManager(config)
    await manager.initialize()

    yield manager

    # Cleanup
    await manager.close()

    # Drop schema
    conn = await asyncpg.connect(asyncpg_url)
    try:
        await conn.execute(f"DROP SCHEMA {schema_name} CASCADE")
    finally:
        await conn.close()


@pytest.fixture
def assert_database_empty():
    """
    Provide an assertion helper to verify database is empty.
    """

    async def _assert_empty(db_manager: DatabaseManager):
        async with db_manager.get_session() as session:
            # Check documents
            result = await session.execute(
                text("SELECT COUNT(*) FROM pubmed_documents")
            )
            doc_count = result.scalar()
            assert doc_count == 0, f"Expected 0 documents, found {doc_count}"

            # Check watermarks
            result = await session.execute(text("SELECT COUNT(*) FROM sync_watermarks"))
            watermark_count = result.scalar()
            assert watermark_count == 0, (
                f"Expected 0 watermarks, found {watermark_count}"
            )

            # Check checkpoints
            result = await session.execute(
                text("SELECT COUNT(*) FROM corpus_checkpoints")
            )
            checkpoint_count = result.scalar()
            assert checkpoint_count == 0, (
                f"Expected 0 checkpoints, found {checkpoint_count}"
            )

    return _assert_empty


@pytest.fixture
def assert_document_exists():
    """
    Provide an assertion helper to verify a document exists in the database.
    """

    async def _assert_exists(db_manager: DatabaseManager, pmid: str):
        doc = await db_manager.get_document_by_pmid(pmid)
        assert doc is not None, f"Document with PMID {pmid} not found"
        return doc

    return _assert_exists


# Performance testing fixtures


@pytest.fixture(scope="session")
def fast_postgres_container():
    """
    PostgreSQL container optimized for test performance.

    WARNING: Uses unsafe settings - only for testing!
    """
    container = PostgresContainer(
        image="postgres:15-alpine",
        username="bio_mcp_test",
        password="test_password",
        dbname="bio_mcp_test",
    )

    # Optimize for speed (unsafe for production!)
    container.with_env("POSTGRES_FSYNC", "off")
    container.with_env("POSTGRES_SYNCHRONOUS_COMMIT", "off")
    container.with_env("POSTGRES_FULL_PAGE_WRITES", "off")
    container.with_env("POSTGRES_CHECKPOINT_SEGMENTS", "32")
    container.with_env("POSTGRES_CHECKPOINT_COMPLETION_TARGET", "0.9")
    container.with_env("POSTGRES_WAL_BUFFERS", "16MB")
    container.with_env("POSTGRES_SHARED_BUFFERS", "256MB")

    container.start()
    yield container
    container.stop()


# Debugging fixtures


@pytest.fixture
def debug_postgres_container():
    """
    PostgreSQL container that stays running after tests for debugging.

    Container must be manually stopped:
    docker ps
    docker stop <container_id>
    """
    container = PostgresContainer("postgres:15-alpine")
    container.start()

    print("\n" + "=" * 60)
    print("DEBUG CONTAINER STARTED")
    print(f"Connection URL: {container.get_connection_url()}")
    print(
        f"Container: {container._container.name if hasattr(container, '_container') else 'N/A'}"
    )
    print(
        "Connect with: docker exec -it <container_name> psql -U bio_mcp_test -d bio_mcp_test"
    )
    print("Container will remain running after tests!")
    print("=" * 60 + "\n")

    yield container
    # Don't stop - leave running for debugging
