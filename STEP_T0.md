# T0: HTTP Skeleton Plan

**Goal:** Create the foundational FastAPI application with basic tool registry and endpoints.

## TDD Approach (Red-Green-Refactor)

1. **Write failing test for tool registry discovery**
   - Test that `build_registry()` discovers existing MCP tools
   - Verify it maps tool names like `pubmed.search`, `rag.search` to callable functions
   - Assert registry structure and tool metadata

2. **Write failing test for `/v1/mcp/tools` endpoint**
   - Test GET request returns list of available tools
   - Verify JSON response format
   - Check tool names match registry

3. **Write failing test for basic `/v1/mcp/invoke` with mock tool**
   - Test POST with `{tool, params}` payload
   - Mock a simple tool to avoid external dependencies
   - Verify response format: `{ok, result, trace_id, tool}`

4. **Implement minimal FastAPI app to make tests pass**
   - Create bare-bones endpoints that satisfy tests
   - Use hardcoded responses initially

5. **Refactor: extract components with clean separation**
   - Extract registry logic to separate module
   - Create adapter layer for tool invocation
   - Implement dependency injection

## Clean Code Principles

- **Single Responsibility:** 
  - `registry.py` - tool discovery and mapping
  - `adapters.py` - HTTP ↔ tool translation
  - `app.py` - FastAPI routing and wiring

- **Dependency Injection:** Registry injected into app, not hardcoded
- **Clear naming:** `build_registry()`, `invoke_tool()`, `health_check()`
- **No magic strings:** Enums for tool names and response states

## File Structure
```
src/bio_mcp/http/
├── __init__.py
├── app.py          # FastAPI routes
├── registry.py     # Tool discovery
├── adapters.py     # Tool invocation
└── lifecycle.py    # Health checks

src/bio_mcp/main_http.py  # uvicorn entrypoint
```

## Implementation Steps

1. **Create directory structure**
   ```bash
   mkdir -p src/bio_mcp/http
   touch src/bio_mcp/http/{__init__.py,app.py,adapters.py,lifecycle.py,registry.py}
   touch src/bio_mcp/main_http.py
   ```

2. **Add FastAPI dependencies**
   ```bash
   uv add fastapi "uvicorn[standard]" anyio httpx
   ```

3. **Write tests first (TDD)**
   ```bash
   mkdir -p tests/http
   touch tests/http/{__init__.py,test_registry.py,test_app.py,test_adapters.py}
   ```

4. **Implement components**
   - Start with registry tests and implementation
   - Add app tests and basic FastAPI routes
   - Create adapter layer for tool invocation
   - Wire everything together with DI

## Acceptance Criteria

- [ ] `make run-http` starts server on :8080
- [ ] `curl :8080/healthz` → 200
- [ ] `curl :8080/v1/mcp/tools` → list of tools
- [ ] Simple tool invocation round-trips successfully
- [ ] Unit test coverage ≥ 90% for new HTTP modules
- [ ] All tests pass: `uv run pytest tests/http/`
- [ ] Code passes linting: `uv run ruff check`

## Notes

- This establishes the HTTP foundation while keeping stdio MCP unchanged
- Focus on minimal viable implementation that passes tests
- No external dependencies (DB, Weaviate) in this stage - use mocks
- Registry should discover actual MCP tools from existing codebase