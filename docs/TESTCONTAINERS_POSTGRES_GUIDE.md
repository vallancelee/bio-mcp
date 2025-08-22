# TestContainers PostgreSQL Testing Guide

## Overview

This guide provides instructions for using TestContainers with PostgreSQL to test database operations without mocking complexity. TestContainers provides real database instances in Docker containers, eliminating async mocking issues entirely.

## Installation

```bash
# Add TestContainers to your project
uv add --dev testcontainers[postgres]

# Ensure Docker is installed and running
docker --version  # Should show Docker version
docker ps  # Should list running containers (may be empty)
```

## Basic Setup

### 1. Create Test Configuration

```python
# tests/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer
from bio_mcp.shared.clients.database import DatabaseManager, DatabaseConfig

@pytest.fixture(scope="session")
def postgres_container():
    """Provide a PostgreSQL container for the test session."""
    with PostgresContainer("postgres:15-alpine") as postgres:
        postgres.start()
        yield postgres

@pytest.fixture(scope="function")
async def db_manager(postgres_container):
    """Provide a DatabaseManager connected to test PostgreSQL."""
    # Get connection URL from container
    connection_url = postgres_container.get_connection_url()
    
    # Convert to async URL (add +asyncpg)
    async_url = connection_url.replace("postgresql://", "postgresql+asyncpg://")
    
    # Create and initialize manager
    config = DatabaseConfig(url=async_url)
    manager = DatabaseManager(config)
    await manager.initialize()
    
    yield manager
    
    # Cleanup
    await manager.close()

@pytest.fixture(scope="function")
async def clean_db(db_manager):
    """Provide a clean database for each test."""
    # Clear all tables before test
    async with db_manager.get_session() as session:
        await session.execute(text("TRUNCATE TABLE pubmed_documents CASCADE"))
        await session.execute(text("TRUNCATE TABLE sync_watermarks CASCADE"))
        await session.execute(text("TRUNCATE TABLE corpus_checkpoints CASCADE"))
        await session.commit()
    
    yield db_manager
```

## Writing Tests with TestContainers

### Example 1: Simple CRUD Test

```python
# tests/integration/database/test_with_testcontainers.py
import pytest
from bio_mcp.shared.clients.database import PubMedDocument

class TestDatabaseWithRealPostgres:
    """Test database operations with real PostgreSQL container."""
    
    @pytest.mark.asyncio
    async def test_document_creation(self, clean_db):
        """Test creating a document in real database."""
        # No mocking needed - this is a real database!
        doc_data = {
            "pmid": "12345",
            "title": "Test Document",
            "abstract": "This is a test abstract"
        }
        
        # Create document
        created_doc = await clean_db.create_document(doc_data)
        
        # Verify it was created
        assert created_doc.pmid == "12345"
        assert created_doc.title == "Test Document"
        
        # Retrieve and verify
        retrieved_doc = await clean_db.get_document_by_pmid("12345")
        assert retrieved_doc is not None
        assert retrieved_doc.pmid == created_doc.pmid
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, clean_db):
        """Test transaction rollback on error."""
        from sqlalchemy.exc import IntegrityError
        
        # Create a document
        doc_data = {"pmid": "unique_123", "title": "Original"}
        await clean_db.create_document(doc_data)
        
        # Try to create duplicate - should fail
        with pytest.raises(IntegrityError):
            await clean_db.create_document(doc_data)
        
        # Verify only one document exists
        docs = await clean_db.list_documents()
        assert len(docs) == 1
```

### Example 2: Complex Integration Test

```python
@pytest.mark.asyncio
async def test_incremental_sync_workflow(clean_db):
    """Test complete incremental sync workflow."""
    # Create initial documents
    for i in range(10):
        await clean_db.create_document({
            "pmid": f"doc_{i}",
            "title": f"Document {i}"
        })
    
    # Create sync watermark
    await clean_db.create_or_update_sync_watermark(
        query_key="cancer_research",
        last_edat="2024/01/01",
        total_synced="10"
    )
    
    # Verify watermark
    watermark = await clean_db.get_sync_watermark("cancer_research")
    assert watermark.total_synced == "10"
    
    # Simulate next sync
    for i in range(10, 15):
        await clean_db.create_document({
            "pmid": f"doc_{i}",
            "title": f"Document {i}"
        })
    
    # Update watermark
    await clean_db.create_or_update_sync_watermark(
        query_key="cancer_research",
        last_edat="2024/01/02",
        total_synced="15",
        last_sync_count="5"
    )
    
    # Verify update
    watermark = await clean_db.get_sync_watermark("cancer_research")
    assert watermark.total_synced == "15"
    assert watermark.last_sync_count == "5"
```

## Advanced Configuration

### Custom Container Settings

```python
@pytest.fixture(scope="session")
def postgres_container():
    """PostgreSQL with custom configuration."""
    container = PostgresContainer(
        image="postgres:15-alpine",
        user="bio_mcp_test",
        password="test_password",
        dbname="bio_mcp_test_db",
        driver="asyncpg"  # Specify async driver
    )
    
    # Set resource limits
    container.with_env("POSTGRES_MAX_CONNECTIONS", "100")
    container.with_env("POSTGRES_SHARED_BUFFERS", "256MB")
    
    with container:
        yield container
```

### Parallel Test Execution

```python
@pytest.fixture(scope="function")
async def isolated_db_manager(postgres_container):
    """Provide isolated database schema for parallel tests."""
    import uuid
    
    # Create unique schema for this test
    schema_name = f"test_{uuid.uuid4().hex[:8]}"
    
    connection_url = postgres_container.get_connection_url()
    async_url = connection_url.replace("postgresql://", "postgresql+asyncpg://")
    
    # Create schema
    import asyncpg
    conn = await asyncpg.connect(async_url.replace("+asyncpg", ""))
    await conn.execute(f"CREATE SCHEMA {schema_name}")
    await conn.close()
    
    # Configure manager to use schema
    config = DatabaseConfig(url=f"{async_url}?options=-csearch_path={schema_name}")
    manager = DatabaseManager(config)
    await manager.initialize()
    
    yield manager
    
    # Cleanup
    await manager.close()
    conn = await asyncpg.connect(async_url.replace("+asyncpg", ""))
    await conn.execute(f"DROP SCHEMA {schema_name} CASCADE")
    await conn.close()
```

## Performance Optimization

### 1. Session-Scoped Container

```python
# Reuse container across all tests in session
@pytest.fixture(scope="session")
def postgres_container():
    """Single container for entire test session."""
    # Container starts once, used by all tests
    with PostgresContainer("postgres:15-alpine") as postgres:
        yield postgres
```

### 2. Connection Pooling

```python
@pytest.fixture(scope="session")
async def db_pool(postgres_container):
    """Shared connection pool for tests."""
    from sqlalchemy.ext.asyncio import create_async_engine
    
    url = postgres_container.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(
        async_url,
        pool_size=20,
        max_overflow=0,
        pool_pre_ping=True
    )
    
    yield engine
    
    await engine.dispose()
```

### 3. Data Fixtures

```python
@pytest.fixture
async def sample_documents(clean_db):
    """Provide sample documents for tests."""
    docs = []
    for i in range(100):
        doc = await clean_db.create_document({
            "pmid": f"sample_{i}",
            "title": f"Sample Document {i}",
            "abstract": f"Abstract for document {i}"
        })
        docs.append(doc)
    return docs
```

## Debugging TestContainers

### 1. Container Logs

```python
@pytest.fixture
def postgres_container():
    container = PostgresContainer("postgres:15-alpine")
    container.start()
    
    # Print connection details for debugging
    print(f"Container ID: {container.get_container_id()}")
    print(f"Connection URL: {container.get_connection_url()}")
    
    # Get logs if needed
    logs = container.get_logs()
    print(f"Container logs: {logs}")
    
    yield container
    container.stop()
```

### 2. Keep Container Running

```python
# For debugging, keep container alive after tests
@pytest.fixture
def persistent_postgres():
    container = PostgresContainer("postgres:15-alpine")
    container.start()
    
    print(f"PostgreSQL available at: {container.get_connection_url()}")
    print("Container will stay running after tests for inspection")
    
    yield container
    # Don't stop container - manual cleanup needed
```

### 3. Connect with psql

```bash
# Get container connection details from test output
docker ps  # Find the test container
docker exec -it <container_id> psql -U test -d test
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      docker:
        image: docker:dind
        options: --privileged
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --dev
      
      - name: Run tests with TestContainers
        run: |
          uv run pytest tests/integration/database/ -v
```

### GitLab CI

```yaml
# .gitlab-ci.yml
test:
  image: python:3.12
  services:
    - docker:dind
  variables:
    DOCKER_HOST: tcp://docker:2375
    DOCKER_DRIVER: overlay2
  script:
    - pip install uv
    - uv sync --dev
    - uv run pytest tests/integration/database/ -v
```

## Migration from Mock-Based Tests

### Step 1: Identify Tests to Migrate

```python
# Tests that should be migrated:
# - Complex transaction tests
# - Integration tests
# - Tests with many async mocks
# - Tests that frequently break due to mock issues

# Tests that can stay mocked:
# - Simple unit tests
# - Tests for error handling
# - Tests for business logic (not DB operations)
```

### Step 2: Create Parallel Test Structure

```
tests/
├── unit/
│   └── database/  # Keep simple mocked tests
└── integration/
    └── database/
        ├── conftest.py  # TestContainers fixtures
        └── test_*.py    # Real database tests
```

### Step 3: Gradual Migration

```python
# Mark tests during migration
@pytest.mark.skip(reason="Migrating to TestContainers")
async def test_old_mocked_version():
    pass

@pytest.mark.integration
async def test_new_testcontainers_version(clean_db):
    # New implementation with real database
    pass
```

## Best Practices

### 1. Test Isolation

```python
# Always use clean_db fixture for isolation
async def test_isolated(clean_db):
    # Each test gets a clean database state
    pass
```

### 2. Deterministic Tests

```python
# Use fixed IDs and timestamps for reproducibility
from datetime import datetime, UTC

async def test_deterministic(clean_db):
    fixed_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    doc = await clean_db.create_document({
        "pmid": "test_001",  # Fixed ID
        "title": "Test",
        "created_at": fixed_time  # Fixed timestamp
    })
```

### 3. Performance Testing

```python
@pytest.mark.performance
async def test_bulk_operations(clean_db):
    import time
    
    start = time.time()
    
    # Create 1000 documents
    docs = []
    for i in range(1000):
        docs.append({"pmid": f"perf_{i}", "title": f"Doc {i}"})
    
    await clean_db.bulk_create_documents(docs)
    
    elapsed = time.time() - start
    assert elapsed < 5.0  # Should complete within 5 seconds
```

## Troubleshooting

### Issue: Container fails to start
```python
# Check Docker is running
import docker
client = docker.from_env()
client.ping()  # Should return True

# Increase startup timeout
container = PostgresContainer("postgres:15-alpine")
container.with_startup_timeout(60)  # 60 seconds
```

### Issue: Connection refused
```python
# Ensure container is ready
@pytest.fixture
def postgres_container():
    container = PostgresContainer()
    container.start()
    
    # Wait for container to be ready
    import time
    time.sleep(2)
    
    # Or use wait strategy
    container.wait_for_logs("database system is ready to accept connections")
    
    yield container
```

### Issue: Slow tests
```python
# Use session-scoped container
# Use connection pooling
# Run tests in parallel with pytest-xdist
# Consider using in-memory PostgreSQL settings

@pytest.fixture(scope="session")
def fast_postgres():
    container = PostgresContainer("postgres:15-alpine")
    container.with_env("POSTGRES_FSYNC", "off")
    container.with_env("POSTGRES_SYNCHRONOUS_COMMIT", "off")
    container.with_env("POSTGRES_FULL_PAGE_WRITES", "off")
    yield container
```

## Summary

TestContainers eliminates async mocking complexity by providing real PostgreSQL instances. This approach:

✅ **Eliminates** async mocking issues completely  
✅ **Provides** realistic testing environment  
✅ **Catches** real database issues early  
✅ **Simplifies** test code significantly  
✅ **Supports** parallel test execution  
✅ **Works** in CI/CD pipelines  

For the bio-mcp project, migrate complex database tests to TestContainers while keeping simple unit tests mocked.