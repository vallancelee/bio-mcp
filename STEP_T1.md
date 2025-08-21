# T1: Async-Safe Invocation & Error Envelope Plan

**Goal:** Enhance the HTTP adapter with async-safe tool invocation, standardized error envelopes, and comprehensive trace handling.

## TDD Approach (Red-Green-Refactor)

1. **Write failing tests for sync/async tool detection**
   - Test that adapter can detect coroutine vs regular functions
   - Test that sync functions are wrapped with `anyio.to_thread.run_sync`
   - Test that async functions are awaited directly
   - Test mixed sync/async tool execution scenarios

2. **Write failing tests for standard error envelope format**
   - Test consistent error structure across all failure modes
   - Test error code standardization (WEAVIATE_TIMEOUT, PUBMED_RATE_LIMIT, etc.)
   - Test error message formatting and sanitization
   - Test error context preservation (tool name, params, timing)

3. **Write failing tests for trace_id generation and propagation**
   - Test trace_id uniqueness across concurrent requests
   - Test trace_id format (UUID4 standard)
   - Test trace_id propagation through error paths
   - Test structured logging with trace_id correlation

4. **Implement async wrapper with proper error handling**
   - Create tool execution adapter that handles sync/async transparently
   - Implement standardized error envelope generation
   - Add comprehensive exception mapping and classification

5. **Refactor: extract error helpers and consolidate trace handling**
   - Extract error envelope builders for reusability
   - Create trace context manager for request lifecycle
   - Implement structured logging with trace correlation

## Clean Code Principles

- **Don't Repeat Yourself:** Single error envelope factory with consistent structure
- **Fail Fast:** Validate inputs early, explicit error types for different failure modes
- **Composition over Inheritance:** Error envelope builder pattern for flexibility
- **Single Responsibility:** Separate concerns - async handling, error mapping, logging
- **Dependency Injection:** Configurable error handlers and logging adapters

## File Structure
```
src/bio_mcp/http/
├── adapters.py         # Enhanced with async/sync detection
├── errors.py           # Error envelope builders and error codes
├── tracing.py          # Trace context and correlation
└── middleware.py       # Request tracing and logging middleware

tests/http/
├── test_adapters.py    # Async/sync tool execution tests
├── test_errors.py      # Error envelope and classification tests
├── test_tracing.py     # Trace ID and context tests
└── test_integration.py # End-to-end async execution tests
```

## Implementation Steps

1. **Create async adapter module**
   ```bash
   touch src/bio_mcp/http/adapters.py
   touch src/bio_mcp/http/errors.py
   touch src/bio_mcp/http/tracing.py
   touch src/bio_mcp/http/middleware.py
   ```

2. **Add async dependencies**
   ```bash
   # anyio already added in T0, verify availability
   uv list | grep anyio
   ```

3. **Write adapter tests first (TDD)**
   ```bash
   touch tests/http/test_adapters.py
   touch tests/http/test_errors.py
   touch tests/http/test_tracing.py
   touch tests/http/test_integration.py
   ```

4. **Implement components with error boundaries**
   - Start with async detection and execution tests
   - Add error envelope standardization
   - Implement trace context management
   - Wire everything through FastAPI middleware

## Key Components to Implement

### 1. Async Tool Adapter (`adapters.py`)
```python
async def invoke_tool_safely(
    tool_func: Callable,
    tool_name: str,
    params: dict,
    trace_id: str
) -> Any:
    """Safely invoke tool with async/sync detection."""
    # Detect async vs sync and execute appropriately
    # Handle all exceptions with proper error classification
    # Emit structured logs with trace correlation
```

### 2. Error Classification System (`errors.py`)
```python
class ErrorCode(Enum):
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    WEAVIATE_TIMEOUT = "WEAVIATE_TIMEOUT"
    PUBMED_RATE_LIMIT = "PUBMED_RATE_LIMIT"
    DATABASE_ERROR = "DATABASE_ERROR"
    # ... more specific error codes

def classify_exception(exc: Exception, tool_name: str) -> ErrorCode:
    """Map exceptions to standardized error codes."""
```

### 3. Trace Context Manager (`tracing.py`)
```python
class TraceContext:
    """Request trace context with correlation."""
    def __init__(self, trace_id: str, tool_name: str):
        self.trace_id = trace_id
        self.tool_name = tool_name
        self.start_time = time.time()
    
    def log_structured(self, level: str, message: str, **kwargs):
        """Emit structured log with trace correlation."""
```

### 4. Request Middleware (`middleware.py`)
```python
@app.middleware("http")
async def trace_requests(request: Request, call_next):
    """Add trace context to all requests."""
    # Generate trace_id, add to request state
    # Time request duration, log completion
    # Handle uncaught exceptions with proper error envelopes
```

## Error Code Standardization

Map specific exceptions to meaningful error codes:
- `weaviate.exceptions.WeaviateTimeoutError` → `WEAVIATE_TIMEOUT`
- `requests.exceptions.ConnectionError` (PubMed) → `PUBMED_CONNECTION_ERROR`
- `sqlalchemy.exc.TimeoutError` → `DATABASE_TIMEOUT`
- `pydantic.ValidationError` → `VALIDATION_ERROR`
- `ValueError` (tool-specific) → `TOOL_EXECUTION_ERROR`

## Logging Enhancement

Structured JSON logs with fields:
```json
{
  "timestamp": "2025-08-21T09:40:23.153470+00:00",
  "level": "INFO",
  "trace_id": "uuid4-string",
  "tool": "pubmed.search", 
  "route": "/v1/mcp/invoke",
  "latency_ms": 245,
  "status": "success|error",
  "error_code": "WEAVIATE_TIMEOUT",
  "message": "Tool execution completed"
}
```

## Acceptance Criteria

- [ ] All existing tools work with async adapter (backward compatibility)
- [ ] Sync tools (like ping) execute via `anyio.to_thread.run_sync`
- [ ] Async tools (like real MCP tools) execute directly with await
- [ ] All errors return standardized envelope with specific error codes
- [ ] Trace IDs are unique UUIDs generated per request
- [ ] Structured logs include trace_id, tool, latency, status
- [ ] Error classification maps common exceptions to meaningful codes
- [ ] Request middleware adds tracing to all endpoints
- [ ] Unit test coverage ≥ 90% for new async/error modules
- [ ] Integration tests verify async execution end-to-end
- [ ] All tests pass: `uv run pytest tests/http/`
- [ ] Code passes linting: `uv run ruff check`

## Testing Strategy

### Unit Tests
- Mock async/sync tools to verify execution paths
- Test error envelope generation for all error types
- Test trace_id uniqueness and format
- Test exception classification mapping

### Integration Tests  
- Execute real MCP tools through async adapter
- Verify end-to-end trace correlation in logs
- Test concurrent request handling with unique traces
- Verify structured logging output format

### Error Injection Tests
- Simulate network timeouts, database errors
- Test error boundary behavior under load
- Verify graceful degradation with proper error responses

## Notes

- This builds on T0's foundation without breaking existing functionality
- Async detection enables calling real MCP tools that may be async
- Error standardization prepares for monitoring and alerting in later phases
- Trace correlation enables request debugging and performance analysis
- All changes are backward compatible with existing API surface