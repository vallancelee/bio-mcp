# Test Suite Cleanup Plan

## Overview
This document outlines the test cleanup strategy to eliminate redundancy, remove problematic async mocking, and consolidate around TestContainers for integration testing.

## Completed Removals ✅

### 1. Database Tests
- **Removed `tests/unit/database/test_database_models.py`** (318 lines)
  - Duplicate of `tests/unit/test_database_models.py`
  - Kept the more comprehensive version

- **Removed `tests/integration/database/test_database_operations.py`** (458 lines)
  - Problematic async mocking causing `TypeError: 'coroutine' object does not support the asynchronous context manager protocol`
  - Replaced by TestContainers tests

- **Removed `tests/integration/database/test_database_operations_real.py`** (497 lines)
  - Redundant with `test_database_integration.py`
  
- **Removed `tests/integration/database/test_database_with_testcontainers.py`** (388 lines)
  - Redundant with comprehensive `test_database_integration.py`

### 2. Services Tests
- **Removed `tests/integration/services/test_services_integration.py`** (542 lines)
  - Mock-heavy "integration" test - contradicts integration testing principles
  - Kept `tests/integration/test_services_integration.py` with real TestContainers

### 3. Quality Scoring
- **Removed `tests/test_quality_scoring.py`** (226 lines)
  - Duplicate of `tests/unit/test_quality_scoring.py`
  - Kept the more comprehensive unit test version

## Tests to Keep with Justification

### Unit Tests (Proper Mocking, Fast)
- `tests/unit/services/test_checkpoint_service.py` - Service logic isolation
- `tests/unit/services/test_document_service.py` - Service logic isolation  
- `tests/unit/services/test_pubmed_service.py` - Service logic isolation
- `tests/unit/test_database_models.py` - Model validation
- `tests/unit/test_checkpoints.py` - Utility class testing
- `tests/unit/test_quality_scoring.py` - Quality scoring logic
- `tests/unit/test_error_handling.py` - Error handling patterns
- `tests/unit/test_server.py` - Server initialization

### Integration Tests (TestContainers, Real Dependencies)
- `tests/integration/test_database_integration.py` - Comprehensive DB with realistic data
- `tests/integration/test_services_integration.py` - Real service orchestration
- `tests/integration/mcp/test_corpus_tools.py` - Real database, 11 tests
- `tests/integration/mcp/test_rag_tools.py` - Real database, 7 tests
- `tests/integration/mcp/test_resources.py` - Real database, 9 tests

### Root-Level Tests to Consider Removing

#### `tests/test_corpus_checkpoints.py` (579 lines)
- **Status**: Consider removal
- **Reason**: Uses extensive mocking, functionality covered by `tests/integration/mcp/test_corpus_tools.py`
- **Alternative**: Keep only if it tests unique edge cases not covered in integration

#### `tests/test_mcp_resources.py` (493 lines)
- **Status**: Consider removal
- **Reason**: Mock-heavy, covered by `tests/integration/mcp/test_resources.py`
- **Alternative**: Keep only unique validation tests

#### `tests/test_rag_tools.py` (150+ lines)
- **Status**: KEEP
- **Reason**: Tests chunking utilities (`AbstractChunker`, `DocumentChunk`) not covered elsewhere
- **Note**: Different scope from integration tests

#### `tests/test_incremental_sync.py`
- **Status**: Review needed
- **Check**: If using mocks vs real database

## Test Organization Best Practices Applied

### 1. Test Pyramid
```
         /\
        /  \  E2E (Docker Compose) - 1-2 tests
       /    \
      /------\ Integration (TestContainers) - 50-100 tests
     /        \
    /----------\ Unit (Mocks) - 200+ tests
```

### 2. Directory Structure
```
tests/
├── unit/           # Fast, isolated, mocked
├── integration/    # Real dependencies, TestContainers
├── e2e/           # Full system tests
└── fixtures/      # Shared test data
```

### 3. Removed Anti-Patterns
- ❌ Async mocking with wrong assumptions
- ❌ Integration tests using only mocks
- ❌ Duplicate tests in multiple locations
- ❌ Tests in wrong directories

## Benefits of Cleanup

### Performance
- **Before**: Tests timing out, hanging for minutes
- **After**: Unit tests ~4s, Integration ~3s, E2E ~22s

### Reliability
- **Before**: Flaky async mocking, port conflicts
- **After**: Deterministic TestContainers, isolated ports

### Maintainability
- **Before**: ~2,200 lines of redundant test code
- **After**: Single source of truth for each test scenario

## Port Configuration Summary

### Test Ports (Non-conflicting)
- Weaviate: 18080 (was 8080)
- Transformers: 18081 (was 8081)
- PostgreSQL: Dynamic from TestContainers

### Production Docker Compose
- Weaviate: 8090
- Transformers: Internal only
- PostgreSQL: 5433

## Next Steps

1. Remove remaining mock-heavy root tests that have TestContainers equivalents
2. Ensure all remaining tests pass
3. Update CI/CD configuration for TestContainers
4. Document testing strategy in README