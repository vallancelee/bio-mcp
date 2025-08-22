"""
Analysis and Solutions for Async Mocking Issues in Database Tests

PROBLEM DIAGNOSIS:
==================
The core issue is that Python's mock library has challenges with async context managers.
When we mock `engine.begin()`, it returns a coroutine object by default, but SQLAlchemy
expects an async context manager (object with __aenter__ and __aexit__ methods).

ROOT CAUSE:
-----------
1. AsyncMock() when called returns a coroutine, not an async context manager
2. Setting __aenter__ and __aexit__ on AsyncMock doesn't work as expected
3. The pattern `async with self.get_session() as session` also expects async context manager

FAILED APPROACHES:
------------------
1. mock_engine.begin.return_value = mock_begin_context  # Returns coroutine, not context manager
2. mock_begin_context.__aenter__ = AsyncMock(return_value=mock_conn)  # Doesn't work properly
3. mock_engine.begin.return_value.__aenter__.return_value = mock_conn  # AttributeError on coroutine

SOLUTIONS:
==========
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


class AsyncContextManagerMock:
    """Helper class to properly mock async context managers."""

    def __init__(self, return_value=None):
        self.return_value = return_value
        self.aenter_called = False
        self.aexit_called = False

    async def __aenter__(self):
        self.aenter_called = True
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.aexit_called = True
        return None


class TestAsyncMockingSolutions:
    """Demonstrates solutions for async mocking issues."""

    @pytest.mark.asyncio
    async def test_solution_1_custom_async_context_manager(self):
        """Solution 1: Use custom async context manager class."""
        from bio_mcp.shared.clients.database import DatabaseConfig, DatabaseManager

        config = DatabaseConfig(url="postgresql://test/db")
        manager = DatabaseManager(config)

        with (
            patch(
                "bio_mcp.shared.clients.database.create_database_engine"
            ) as mock_create_engine,
            patch(
                "bio_mcp.shared.clients.database.async_sessionmaker"
            ) as mock_sessionmaker,
        ):
            # Create proper mock engine
            mock_engine = AsyncMock(spec=AsyncEngine)
            mock_create_engine.return_value = mock_engine

            # Use custom async context manager for begin()
            mock_conn = AsyncMock()
            mock_begin_context = AsyncContextManagerMock(return_value=mock_conn)
            mock_engine.begin.return_value = mock_begin_context

            # Mock session factory
            mock_sessionmaker.return_value = MagicMock()

            # This should work now
            await manager.initialize()

            assert manager.engine == mock_engine
            assert mock_begin_context.aenter_called
            assert mock_begin_context.aexit_called

    @pytest.mark.asyncio
    async def test_solution_2_asynccontextmanager_decorator(self):
        """Solution 2: Use asynccontextmanager from contextlib."""
        from bio_mcp.shared.clients.database import DatabaseConfig, DatabaseManager

        config = DatabaseConfig(url="postgresql://test/db")
        manager = DatabaseManager(config)

        with (
            patch(
                "bio_mcp.shared.clients.database.create_database_engine"
            ) as mock_create_engine,
            patch(
                "bio_mcp.shared.clients.database.async_sessionmaker"
            ) as mock_sessionmaker,
        ):
            mock_engine = AsyncMock(spec=AsyncEngine)
            mock_create_engine.return_value = mock_engine

            # Use asynccontextmanager to create proper context
            mock_conn = AsyncMock()

            @asynccontextmanager
            async def mock_begin():
                yield mock_conn

            mock_engine.begin = mock_begin
            mock_sessionmaker.return_value = MagicMock()

            await manager.initialize()

            assert manager.engine == mock_engine
            mock_conn.run_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_solution_3_magicmock_with_spec(self):
        """Solution 3: Use MagicMock with proper spec_set."""
        from bio_mcp.shared.clients.database import DatabaseConfig, DatabaseManager

        config = DatabaseConfig(url="postgresql://test/db")
        manager = DatabaseManager(config)

        with (
            patch(
                "bio_mcp.shared.clients.database.create_database_engine"
            ) as mock_create_engine,
            patch(
                "bio_mcp.shared.clients.database.async_sessionmaker"
            ) as mock_sessionmaker,
        ):
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_create_engine.return_value = mock_engine

            # Create a MagicMock that behaves like async context manager
            mock_conn = AsyncMock()
            mock_begin_result = MagicMock()
            mock_begin_result.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_result.__aexit__ = AsyncMock(return_value=None)

            # Make begin() return our mock context manager
            mock_engine.begin = MagicMock(return_value=mock_begin_result)
            mock_sessionmaker.return_value = MagicMock()

            await manager.initialize()

            assert manager.engine == mock_engine
            mock_conn.run_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_mocking_issue(self):
        """Demonstrate the session mocking issue."""
        from bio_mcp.shared.clients.database import DatabaseConfig, DatabaseManager

        config = DatabaseConfig(url="postgresql://test/db")
        manager = DatabaseManager(config)

        # Mock session factory to return proper async context manager
        mock_session = AsyncMock(spec=AsyncSession)

        # Solution for session context manager
        class AsyncSessionMock:
            def __init__(self, session):
                self.session = session

            async def __aenter__(self):
                return self.session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

            def __call__(self):
                return self

        mock_session_factory = AsyncSessionMock(mock_session)
        manager.session_factory = mock_session_factory

        # Now this pattern works
        async with manager.get_session() as session:
            assert session == mock_session


class TestRecommendedApproach:
    """Recommended approach for database testing."""

    @pytest.mark.asyncio
    async def test_recommended_pattern_for_database_manager(self):
        """Recommended pattern using helper functions."""
        from bio_mcp.shared.clients.database import DatabaseConfig, DatabaseManager

        def create_mock_engine():
            """Helper to create properly mocked engine."""
            mock_engine = MagicMock(spec=AsyncEngine)

            # Mock the begin() context manager
            mock_conn = AsyncMock()
            mock_begin = MagicMock()
            mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin.__aexit__ = AsyncMock(return_value=None)
            mock_engine.begin = MagicMock(return_value=mock_begin)

            # Mock dispose
            mock_engine.dispose = AsyncMock()

            return mock_engine, mock_conn

        def create_mock_session_factory():
            """Helper to create properly mocked session factory."""
            mock_session = AsyncMock(spec=AsyncSession)

            class SessionFactoryMock:
                def __call__(self):
                    return mock_session

                async def __aenter__(self):
                    return mock_session

                async def __aexit__(self, *args):
                    return None

            # Make the session itself work as async context manager
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            return SessionFactoryMock(), mock_session

        config = DatabaseConfig(url="postgresql://test/db")
        manager = DatabaseManager(config)

        with (
            patch(
                "bio_mcp.shared.clients.database.create_database_engine"
            ) as mock_create_engine,
            patch(
                "bio_mcp.shared.clients.database.async_sessionmaker"
            ) as mock_sessionmaker,
        ):
            mock_engine, mock_conn = create_mock_engine()
            mock_create_engine.return_value = mock_engine

            mock_session_factory, mock_session = create_mock_session_factory()
            mock_sessionmaker.return_value = mock_session_factory

            # Initialize works
            await manager.initialize()
            assert manager.engine == mock_engine

            # Session operations work
            session = manager.get_session()
            async with session as s:
                assert s == mock_session


"""
BEST PRACTICES FOR FUTURE TESTS:
=================================

1. **Use Helper Classes for Async Context Managers:**
   Create reusable helper classes like AsyncContextManagerMock that properly 
   implement __aenter__ and __aexit__ methods.

2. **Prefer MagicMock over AsyncMock for Context Managers:**
   MagicMock allows setting __aenter__ and __aexit__ directly, while AsyncMock 
   has issues with this pattern.

3. **Create Test Fixtures:**
   Create pytest fixtures that provide properly mocked database components:
   - @pytest.fixture for mock_engine
   - @pytest.fixture for mock_session_factory
   - @pytest.fixture for mock_session

4. **Use Integration Tests for Complex Async Flows:**
   For complex async database operations, consider using test databases
   (e.g., with testcontainers) instead of mocking everything.

5. **Mock at Higher Levels:**
   Instead of mocking low-level SQLAlchemy components, mock at the 
   DatabaseManager method level for simpler tests.

6. **Document Mock Patterns:**
   Keep a library of working mock patterns for common scenarios like:
   - Async context managers
   - Database sessions
   - Transaction handling

ALTERNATIVE TESTING STRATEGIES:
================================

1. **In-Memory SQLite:**
   Use SQLite in-memory database for testing instead of mocking:
   ```python
   config = DatabaseConfig(url="sqlite+aiosqlite:///:memory:")
   ```

2. **TestContainers:**
   Use testcontainers-python to spin up real PostgreSQL for tests:
   ```python
   from testcontainers.postgres import PostgresContainer
   ```

3. **Repository Pattern:**
   Refactor to use repository pattern, making it easier to mock:
   - Create AbstractRepository interface
   - Implement DatabaseRepository
   - Mock at repository level, not database level

4. **Dependency Injection:**
   Use dependency injection to make testing easier:
   - Pass session factory as parameter
   - Use protocols for type hints
   - Mock protocol implementations
"""
