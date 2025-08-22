# Bio-MCP Contract Tests

This directory contains contract tests that ensure API backward compatibility during the multi-source document refactoring described in `MULTISOURCE_REFACTOR.md`.

## Purpose

These tests validate that the new Document/Chunk models and multi-source pipeline produce identical API responses to the legacy implementation, ensuring:

- **API contracts remain stable** per `contracts.md` 
- **Response schemas are unchanged** during refactoring
- **Document model integration doesn't break compatibility**
- **Error handling follows standard patterns**

## Test Organization

### Fast Contract Tests (Recommended)
- **`test_core_contracts.py`** - Core data model and schema validation without external dependencies
- **No timeouts or network calls** - Runs in <1 second
- **Best for CI/CD pipelines** - Reliable and fast

### Full Integration Contract Tests  
- **`test_api_contracts.py`** - Full API response validation with real tool calls
- **`test_json_schema_contracts.py`** - JSON schema compliance testing  
- **May skip if external dependencies unavailable** (Weaviate, database connections)
- **Includes timeout protection** - Tests will skip gracefully if services unavailable

## Test Categories

### 1. JSON Schema Compliance (`test_json_schema_contracts.py`)

Validates API responses against exact JSON schemas defined in `contracts.md`:

- **rag.search** response structure and field types
- **rag.get** document metadata format  
- **corpus.checkpoint** operations
- **Error envelope** standard format

Key validations:
- Required fields present with correct types
- No unexpected additional properties
- Enum values within allowed sets
- Pattern matching (e.g., `pmid:[0-9]+`)

### 2. API Contract Validation (`test_api_contracts.py`)

Tests high-level API contract compliance:

- Response structure consistency
- Field type validation
- Error response formatting
- Quality score object structure
- Checkpoint operations

### 3. Document Model Compatibility (`test_document_model_compatibility.py`)

Ensures the new Document/Chunk models maintain backward compatibility:

- **Document UID format stability** (`pubmed:12345678`)
- **Chunk ID format consistency** (`parent_uid:chunk_idx`)
- **Metadata preservation** through normalization pipeline
- **Database conversion** maintains all data integrity
- **API response format** unchanged after model refactoring

## Running Contract Tests

```bash
# Run fast core contract tests (recommended for CI/CD)
uv run pytest tests/contracts/test_core_contracts.py -v

# Run all contract tests (may skip if external deps unavailable)  
uv run pytest tests/contracts/ -v

# Run specific test category
uv run pytest tests/contracts/test_json_schema_contracts.py -v

# Run regression tests only
uv run pytest tests/contracts/ -k "regression" -v

# Run with timeouts for integration tests
uv run pytest tests/contracts/ -v --tb=short --timeout=30
```

## Breaking Change Detection

Several tests serve as **breaking change detectors**:

### `TestContractRegression.test_required_fields_never_removed()`
Documents current required fields for each API endpoint. If this test fails, it indicates a breaking change requiring a major version bump.

### `TestContractRegression.test_doc_id_pattern_stability()`  
Ensures the `pmid:[0-9]+` pattern never changes without major version bump.

### `TestContractRegression.test_error_code_enum_stability()`
Validates that error codes remain stable across versions.

## Schema Evolution Safety

The tests enforce safe schema evolution practices:

✅ **Allowed (minor version):**
- Adding optional fields
- Adding enum values  
- Expanding validation ranges

❌ **Breaking (major version):**
- Removing required fields
- Changing field types
- Renaming fields
- Removing enum values

## Integration with Refactoring

These tests are essential during the Document model integration:

1. **Before refactoring**: Tests document current API behavior
2. **During refactoring**: Tests catch any compatibility breaks
3. **After refactoring**: Tests verify identical API responses

## Test Dependencies

- `jsonschema` - JSON schema validation
- `pytest-asyncio` - Async test support  
- Integration test fixtures from `tests/integration/mcp/conftest.py`

## Maintenance

When adding new API endpoints:

1. Add JSON schema to appropriate test file
2. Add contract validation test
3. Document required fields in regression tests
4. Update this README with new endpoints

When making API changes:
1. Run contract tests first to understand impact
2. Update schemas if making compatible additions
3. Ensure regression tests catch breaking changes
4. Update API version if breaking changes are necessary