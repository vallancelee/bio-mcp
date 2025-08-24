# Integration Testing Guide

This directory contains integration tests for the Bio-MCP project, with a focus on testing real system interactions rather than mocked components.

## Test Structure

### Database Integration Tests
- **Location**: `tests/integration/database/`
- **Approach**: Uses PostgreSQL testcontainers for real database testing
- **Fixtures**: `postgres_container`, `db_manager`, `clean_db`

### RAG Quality Integration Tests
- **Location**: `tests/integration/test_rag_quality.py`
- **Approach**: Uses Docker Compose Weaviate with pre-populated test data
- **Purpose**: Tests RAG Step 6 improvements (section boosting, query enhancement, abstract reconstruction)

### MCP Tools Integration Tests
- **Location**: `tests/integration/mcp/`
- **Approach**: Uses both PostgreSQL testcontainers and Docker Compose Weaviate
- **Purpose**: End-to-end testing of MCP tool implementations

## RAG Quality Test Setup

The RAG quality integration tests use a sophisticated setup to ensure consistent, reliable testing:

### Test Data Management

**Pre-populated Test Data**:
- Test documents are defined in `tests/fixtures/rag_test_data.py`
- 5 biomedical documents covering diabetes, cancer, COVID-19, heart disease, and ML
- Each document has structured sections (Background, Methods, Results, Conclusions)
- Quality scores range from 0.8 to 1.0 for testing quality boosting

**Session-scoped Fixture**:
```python
@pytest_asyncio.fixture(scope="session")
async def populated_weaviate():
    """Populates Weaviate once per test session with biomedical test data."""
```

### Why This Approach?

**Advantages over individual test data creation**:
1. **Consistency**: Same test data across all tests
2. **Performance**: Data populated once per session, not per test
3. **Reliability**: No race conditions or test interdependencies
4. **Maintenance**: Single source of truth for test data
5. **Real Integration**: Uses actual Weaviate with OpenAI embeddings

**Advantages over testcontainers**:
1. **Compatibility**: Uses same Docker Compose as development environment
2. **Complexity Support**: Handles multi-container Weaviate setup (transformers, OpenAI modules)
3. **Debug Friendly**: Containers persist for inspection during development
4. **Resource Efficient**: Shared across multiple test runs

### Test Categories

**Section Boosting Tests**:
- Verify that Results and Conclusions sections get higher scores
- Use clinical trial queries to find structured content
- Check `sections_found` metadata in results

**Query Enhancement Tests**:
- Test biomedical term expansion (COVID-19 → coronavirus, SARS-CoV-2)
- Compare enhanced vs unenhanced queries
- Verify `enhanced_query` flag in performance metadata

**Abstract Reconstruction Tests**:
- Ensure titles are not duplicated in abstracts
- Verify clean text assembly from multiple chunks
- Test document-level vs chunk-level results

**Performance Tests**:
- Check timing metadata inclusion
- Verify performance tracking works end-to-end
- Test search mode switching

## Running RAG Quality Tests

### Prerequisites
```bash
# 1. Start Weaviate via Docker Compose
docker-compose up -d weaviate

# 2. Set OpenAI API key
export OPENAI_API_KEY="your-openai-api-key"
```

### Run Tests
```bash
# Run all RAG quality tests
uv run pytest tests/integration/test_rag_quality.py -v

# Run specific test
uv run pytest tests/integration/test_rag_quality.py::TestRAGQuality::test_section_boosting -v

# Run with output capture
uv run pytest tests/integration/test_rag_quality.py -v -s
```

### Expected Behavior

**First Run**: Tests populate Weaviate with test data (~5-10 seconds)
**Subsequent Runs**: Tests reuse existing data (much faster)
**Cleanup**: Test data is removed after test session completes

## Troubleshooting

### Common Issues

**Tests Skip with "OPENAI_API_KEY required"**:
- Ensure API key is exported in environment
- Check API key is valid and has credits

**"Connection refused" errors**:
- Ensure Weaviate is running: `docker-compose ps`
- Check port 8080 is not occupied by other services

**"No results found" errors**:
- Test data may not be populated correctly
- Check Weaviate logs: `docker-compose logs weaviate`
- Verify OpenAI API key has embedding permissions

**Date format errors**:
- Fixed in DocumentChunkService to use proper ISO format
- Should not occur with current implementation

### Debug Tips

**Inspect Weaviate Data**:
```bash
# Check collection stats
curl http://localhost:8080/v1/objects

# Check specific collection
curl http://localhost:8080/v1/objects?class=DocumentChunk_v2&limit=5
```

**Verbose Test Output**:
```bash
# See detailed test execution
uv run pytest tests/integration/test_rag_quality.py -v -s --tb=short
```

## Contributing

When adding new RAG tests:

1. **Add test data** to `tests/fixtures/rag_test_data.py` if needed
2. **Use existing fixtures** (`populated_weaviate`, `test_queries`)
3. **Include descriptive error messages** in assertions
4. **Test both positive and negative cases**
5. **Document expected behavior** in docstrings

When modifying RAG functionality:

1. **Update test data** if data format changes
2. **Update expected sections** if chunking logic changes  
3. **Update query mappings** if enhancement logic changes
4. **Run full test suite** to check for regressions