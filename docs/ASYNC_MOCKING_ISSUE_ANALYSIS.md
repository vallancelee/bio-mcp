# Async Mocking Issue Analysis and Solutions

## Problem Summary

The persistent async mocking issue in the database tests stems from a fundamental incompatibility between Python's `unittest.mock` library and SQLAlchemy's async context managers.

## Root Cause Analysis

### The Core Issue
When mocking `engine.begin()` in SQLAlchemy async operations:
1. `AsyncMock()` returns a **coroutine** when called
2. SQLAlchemy expects an **async context manager** (object with `__aenter__` and `__aexit__` methods)
3. The error `TypeError: 'coroutine' object does not support the asynchronous context manager protocol` occurs

### Why It Happens
```python
# What AsyncMock does:
mock_engine.begin()  # Returns: <coroutine object>

# What SQLAlchemy expects:
async with engine.begin() as conn:  # Needs: object with __aenter__/__aexit__
    await conn.run_sync(...)
```

### The Session Problem
Similar issue occurs with sessions:
```python
async with self.get_session() as session:  # session_factory() must return async context manager
    # ... database operations
```

## Failed Approaches

These common approaches **don't work**:

1. **Direct AsyncMock assignment**:
```python
mock_begin_context = AsyncMock()
mock_begin_context.__aenter__ = AsyncMock(return_value=mock_conn)  # Doesn't work!
```

2. **Chained attribute access**:
```python
mock_engine.begin.return_value.__aenter__.return_value = mock_conn  # AttributeError!
```

3. **Simple return value**:
```python
mock_engine.begin.return_value = mock_context  # Returns coroutine, not context manager!
```

## Working Solutions

### Solution 1: Custom Async Context Manager Class
```python
class AsyncContextManagerMock:
    def __init__(self, return_value=None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

# Usage:
mock_conn = AsyncMock()
mock_begin_context = AsyncContextManagerMock(return_value=mock_conn)
mock_engine.begin.return_value = mock_begin_context
```

### Solution 2: MagicMock with Proper Setup
```python
mock_conn = AsyncMock()
mock_begin_result = MagicMock()
mock_begin_result.__aenter__ = AsyncMock(return_value=mock_conn)
mock_begin_result.__aexit__ = AsyncMock(return_value=None)
mock_engine.begin = MagicMock(return_value=mock_begin_result)
```

### Solution 3: Using contextlib.asynccontextmanager
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def mock_begin():
    yield mock_conn

mock_engine.begin = mock_begin
```

## Best Practices for Future Tests

### 1. Create Reusable Test Fixtures
```python
@pytest.fixture
def mock_engine():
    """Provides properly mocked async engine."""
    engine = MagicMock(spec=AsyncEngine)
    conn = AsyncMock()
    
    # Setup async context manager
    begin_ctx = MagicMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=conn)
    begin_ctx.__aexit__ = AsyncMock(return_value=None)
    engine.begin = MagicMock(return_value=begin_ctx)
    
    return engine, conn
```

### 2. Mock at Higher Levels
Instead of mocking SQLAlchemy internals, mock DatabaseManager methods:
```python
with patch.object(manager, 'create_document') as mock_create:
    mock_create.return_value = expected_document
    # Test business logic, not database internals
```

### 3. Use Alternative Testing Strategies

#### Option A: In-Memory Database
```python
# Use SQLite for unit tests
config = DatabaseConfig(url="sqlite+aiosqlite:///:memory:")
```

#### Option B: TestContainers
```python
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15") as postgres:
        yield postgres.get_connection_url()
```

#### Option C: Repository Pattern
Refactor to use repository pattern for easier mocking:
```python
class DocumentRepository(Protocol):
    async def create(self, data: dict) -> Document: ...
    async def get_by_id(self, id: str) -> Document: ...

# Mock the repository, not the database
```

## Lifecycle and Fixture Considerations

The issue is **not primarily** about pytest fixture lifecycle, but about:
1. **Type mismatch**: AsyncMock produces coroutines, not context managers
2. **Mock configuration**: Need specific setup for async context manager protocol
3. **SQLAlchemy expectations**: Strict requirements for async context managers

### Fixture Best Practices
```python
# Scope fixtures appropriately
@pytest.fixture(scope="function")  # New mock for each test
async def db_session():
    # Setup
    session = create_mock_session()
    yield session
    # Cleanup
    await session.close()

# Use autouse for common setup
@pytest.fixture(autouse=True)
def reset_mocks():
    # Reset any module-level mocks between tests
    yield
    # Cleanup
```

## Recommended Approach for This Project

Given the current architecture:

1. **For unit tests**: Use the custom `AsyncContextManagerMock` helper class
2. **For integration tests**: Use TestContainers with real PostgreSQL
3. **For new code**: Consider repository pattern to improve testability
4. **Document patterns**: Keep working mock patterns in test utilities

## Migration Path

To fix existing failing tests:

1. **Immediate fix**: Apply Solution 2 (MagicMock approach) to failing tests
2. **Refactor**: Create shared test utilities module with helper functions
3. **Long-term**: Consider architectural changes for better testability

## Example Fix for Current Tests

```python
# In test_database_client.py, replace:
mock_begin_context = AsyncMock()
mock_begin_context.__aenter__ = AsyncMock(return_value=mock_conn)
mock_begin_context.__aexit__ = AsyncMock(return_value=None)
mock_engine.begin.return_value = mock_begin_context

# With:
mock_begin_context = MagicMock()
mock_begin_context.__aenter__ = AsyncMock(return_value=mock_conn)
mock_begin_context.__aexit__ = AsyncMock(return_value=None)
mock_engine.begin = MagicMock(return_value=mock_begin_context)
```

## Key Takeaways

1. **AsyncMock limitations**: Not suitable for mocking async context managers directly
2. **MagicMock flexibility**: Better for setting special methods like `__aenter__`
3. **Test at right level**: Mock business logic, not framework internals when possible
4. **Document patterns**: Keep working examples for team reference
5. **Consider alternatives**: Real databases or in-memory databases for complex async flows