# T2: Enhanced Readiness Checks Plan

**Goal:** Replace stub readiness checks with comprehensive dependency validation for production cloud deployment.

## TDD Approach (Red-Green-Refactor)

1. **Write failing tests for individual dependency checks**
   - Test database connectivity with real connection attempts
   - Test Weaviate connectivity and required schema validation
   - Test schema/migration status verification
   - Test readiness check caching behavior (5s TTL)

2. **Write failing tests for health check aggregation**
   - Test `/readyz` endpoint returns 503 when any dependency fails
   - Test `/readyz` endpoint returns 200 when all dependencies ready
   - Test readiness check timeout handling
   - Test concurrent readiness check requests

3. **Write failing tests for configuration-driven checks**
   - Test optional dependency skipping based on configuration
   - Test custom timeout settings for different services
   - Test readiness check priority ordering

4. **Implement dependency checkers with clear interfaces**
   - Create abstract health check interface
   - Implement database readiness checker
   - Implement Weaviate readiness checker  
   - Implement schema validation checker

5. **Refactor: extract health check strategies and caching**
   - Extract health check result caching
   - Create health check orchestrator
   - Add health check metrics and monitoring

## Clean Code Principles

- **Interface Segregation:** Separate DB, Weaviate, Schema checkers with common interface
- **Open/Closed:** Extensible health check system for adding new dependencies
- **Command Query Separation:** Health checks are pure queries without side effects
- **Strategy Pattern:** Pluggable health check implementations
- **Single Responsibility:** Each checker handles one specific dependency

## File Structure
```
src/bio_mcp/http/
├── health/
│   ├── __init__.py
│   ├── interface.py        # Abstract health check interface
│   ├── database.py         # Database connectivity checker
│   ├── weaviate.py        # Weaviate connectivity + schema checker
│   ├── orchestrator.py    # Health check coordination
│   └── cache.py           # Result caching with TTL

tests/http/
├── test_health_database.py    # Database health check tests
├── test_health_weaviate.py    # Weaviate health check tests
├── test_health_orchestrator.py # Health check coordination tests
└── test_health_integration.py  # End-to-end readiness tests
```

## Implementation Steps

1. **Create health check module structure**
   ```bash
   mkdir -p src/bio_mcp/http/health
   touch src/bio_mcp/http/health/{__init__.py,interface.py,database.py,weaviate.py,orchestrator.py,cache.py}
   ```

2. **Create health check test files**
   ```bash
   touch tests/http/{test_health_database.py,test_health_weaviate.py,test_health_orchestrator.py,test_health_integration.py}
   ```

3. **Write tests first (TDD)**
   - Start with interface and abstract tests
   - Add database connectivity tests
   - Add Weaviate connectivity and schema tests
   - Add orchestrator and caching tests

4. **Implement health checkers**
   - Start with abstract interface
   - Implement database checker with connection pooling awareness
   - Implement Weaviate checker with schema validation
   - Wire everything through orchestrator with caching

## Key Components to Implement

### 1. Health Check Interface (`interface.py`)
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    healthy: bool
    message: str
    details: Optional[dict] = None
    check_duration_ms: float = 0.0

class HealthChecker(ABC):
    """Abstract base class for health checkers."""
    
    @abstractmethod
    async def check_health(self) -> HealthCheckResult:
        """Check if the dependency is healthy."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of this health checker."""
        pass
```

### 2. Database Health Checker (`database.py`)
```python
class DatabaseHealthChecker(HealthChecker):
    """Database connectivity and schema health checker."""
    
    async def check_health(self) -> HealthCheckResult:
        """Check database connectivity and migrations."""
        # 1. Test database connection
        # 2. Verify required tables exist
        # 3. Check Alembic migration status
        # 4. Validate connection pool health
        pass
```

### 3. Weaviate Health Checker (`weaviate.py`)
```python
class WeaviateHealthChecker(HealthChecker):
    """Weaviate connectivity and schema health checker."""
    
    async def check_health(self) -> HealthCheckResult:
        """Check Weaviate connectivity and schema."""
        # 1. Test Weaviate connectivity
        # 2. Verify required classes exist (Document, etc.)
        # 3. Check index health and statistics
        # 4. Validate authentication if configured
        pass
```

### 4. Health Check Orchestrator (`orchestrator.py`)
```python
class HealthOrchestrator:
    """Coordinates multiple health checks with caching."""
    
    def __init__(self, checkers: list[HealthChecker]):
        self.checkers = checkers
        self.cache = HealthCheckCache()
    
    async def check_all_health(self) -> dict[str, HealthCheckResult]:
        """Run all health checks with caching."""
        pass
    
    async def is_ready(self) -> bool:
        """Check if all dependencies are ready."""
        pass
```

### 5. Result Caching (`cache.py`)
```python
class HealthCheckCache:
    """Cache for health check results with TTL."""
    
    def __init__(self, ttl_seconds: int = 5):
        self.ttl_seconds = ttl_seconds
        self._cache = {}
        self._timestamps = {}
    
    async def get_or_check(
        self, 
        checker: HealthChecker
    ) -> HealthCheckResult:
        """Get cached result or perform fresh check."""
        pass
```

## Dependency-Specific Requirements

### Database Checks
- **Connection Test:** Execute `SELECT 1` with timeout
- **Schema Validation:** Verify required tables exist
- **Migration Status:** Check Alembic version matches expected
- **Pool Health:** Verify connection pool isn't exhausted

### Weaviate Checks  
- **Connectivity:** GET `/v1/.well-known/ready` endpoint
- **Authentication:** Verify API key if configured
- **Schema Validation:** Confirm required classes exist (Document, etc.)
- **Index Health:** Check if indexes are ready for queries

## Configuration Integration

Use existing environment variables:
- `BIO_MCP_DATABASE_URL` - Required for database checks
- `BIO_MCP_WEAVIATE_URL` - Required for Weaviate checks
- `BIO_MCP_HEALTH_CHECK_TIMEOUT` - Timeout for individual checks (default: 5s)
- `BIO_MCP_HEALTH_CACHE_TTL` - Cache TTL in seconds (default: 5s)

## Error Scenarios & Responses

### Database Failures
- **Connection timeout:** `DATABASE_TIMEOUT` with retry suggestion
- **Missing tables:** `DATABASE_SCHEMA_ERROR` with migration guidance
- **Migration mismatch:** `DATABASE_MIGRATION_REQUIRED` with version info

### Weaviate Failures
- **Connection timeout:** `WEAVIATE_TIMEOUT` with connectivity guidance
- **Authentication error:** `WEAVIATE_AUTH_ERROR` with key validation
- **Missing schema:** `WEAVIATE_SCHEMA_ERROR` with class creation guidance

## Integration with Existing App

Update `lifecycle.py` to use new orchestrator:
```python
from bio_mcp.http.health import create_health_orchestrator

# Global orchestrator instance
_health_orchestrator = None

async def check_readiness() -> bool:
    """Enhanced readiness check with real dependency validation."""
    global _health_orchestrator
    
    if _health_orchestrator is None:
        _health_orchestrator = create_health_orchestrator()
    
    return await _health_orchestrator.is_ready()
```

## Acceptance Criteria

- [ ] Database connectivity verified with real connection attempts
- [ ] Weaviate connectivity and schema validation working
- [ ] `/readyz` returns 503 when any dependency fails
- [ ] `/readyz` returns 200 only when all dependencies ready
- [ ] Health check results cached for 5s to reduce probe amplification
- [ ] Individual health checkers can be disabled via configuration
- [ ] Health check timeouts are configurable per service
- [ ] Structured logging includes health check results and timing
- [ ] Unit test coverage ≥ 90% for all health check modules
- [ ] Integration tests with real database/Weaviate connections
- [ ] All tests pass: `uv run pytest tests/http/`
- [ ] Code passes linting: `uv run ruff check`

## Testing Strategy

### Unit Tests
- Mock database/Weaviate clients for connectivity tests
- Test caching behavior with time manipulation
- Test error classification and response formatting
- Test configuration parsing and validation

### Integration Tests
- Use testcontainers for real database connections
- Test against running Weaviate instance (if available)
- Verify end-to-end readiness check behavior
- Test health check performance under load

### Error Injection Tests
- Simulate network timeouts and connection failures
- Test graceful degradation when dependencies unavailable
- Verify health check doesn't crash on malformed responses

## Performance Requirements

- **Individual checks:** Complete within 5s timeout
- **Cached responses:** Return within 10ms
- **Concurrent requests:** Handle 100+ concurrent readiness checks
- **Memory usage:** Health check cache bounded to reasonable size

## Notes

- Health checks should be non-blocking and fail gracefully
- Cache invalidation prevents probe storms in kubernetes/ALB scenarios  
- Each checker is independent and can be disabled for testing
- Health check results provide actionable information for debugging
- This prepares infrastructure for production deployment with proper monitoring