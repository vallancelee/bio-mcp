# MCP Tools Testing Implementation Plan

## Overview

This document outlines the comprehensive testing strategy for Bio-MCP's Model Context Protocol (MCP) tools. The hybrid approach combines unit tests for focused validation and integration tests for end-to-end workflows.

## Target Modules & Coverage Impact

| Module | Statements | Current Coverage | Target Coverage | Estimated Gain |
|--------|------------|------------------|-----------------|----------------|
| `mcp/corpus_tools.py` | 191 (151 missed) | 17% | 80% | +121 statements |
| `mcp/rag_tools.py` | 160 (127 missed) | 16% | 85% | +108 statements |
| `mcp/resources.py` | 149 (121 missed) | 15% | 75% | +91 statements |
| **TOTAL** | **500 (399 missed)** | **16%** | **81%** | **+320 statements** |

**Expected Overall Coverage Impact**: +9.8 percentage points (37% → 47%)

## Test Architecture

### Hybrid Testing Strategy

1. **Unit Tests**: Fast, focused validation of individual functions
   - Argument parsing and validation
   - Error handling and edge cases
   - MCP response formatting
   - Mocked service dependencies

2. **Integration Tests**: End-to-end workflows with real services
   - Full tool execution pipelines
   - Real database and vector store interactions
   - Authentic biomedical data scenarios
   - MCP protocol compliance

3. **Mock MCP Server Tests**: Tool registration and protocol validation
   - Tool registration with MCP server
   - Schema validation
   - Protocol-level testing

## Implementation Plan

### Phase 1: Test Infrastructure Setup

#### 1.1 Unit Test Framework
```python
# tests/unit/mcp/test_corpus_tools.py
# tests/unit/mcp/test_rag_tools.py  
# tests/unit/mcp/test_resources.py
```

**Test Utilities:**
- MCP response validation helpers
- Mock service factories
- Common test data generators

#### 1.2 Integration Test Framework
```python
# tests/integration/mcp/test_mcp_tools_integration.py
```

**Infrastructure:**
- Reuse existing PostgreSQL + Weaviate testcontainers
- Biomedical test corpus with realistic data
- MCP server mock for protocol testing

### Phase 2: Corpus Tools Testing (`mcp/corpus_tools.py`)

#### 2.1 Unit Tests
```python
class TestCorpusToolsUnit:
    """Unit tests for corpus checkpoint tools."""
    
    @patch('bio_mcp.mcp.corpus_tools.get_checkpoint_manager')
    async def test_checkpoint_create_success(self, mock_manager):
        """Test successful checkpoint creation with mocked service."""
        
    async def test_checkpoint_create_validation_errors(self):
        """Test argument validation failures."""
        
    async def test_checkpoint_get_not_found(self):
        """Test checkpoint retrieval with non-existent ID."""
        
    async def test_response_formatting(self):
        """Test MCP TextContent response formatting."""
```

**Key Test Scenarios:**
- ✅ Valid checkpoint creation with all parameters
- ✅ Missing required parameters (name, description)
- ✅ Invalid parameter types and values
- ✅ Service failure handling
- ✅ MCP response format validation
- ✅ Execution time tracking

#### 2.2 Integration Tests
```python
class TestCorpusToolsIntegration:
    """Integration tests with real database."""
    
    async def test_checkpoint_full_lifecycle(self, database_manager):
        """Test create → get → list → delete with real database."""
        
    async def test_checkpoint_with_biomedical_corpus(self, database_manager):
        """Test checkpoint creation with realistic biomedical data."""
        
    async def test_checkpoint_lineage_tracking(self, database_manager):
        """Test parent-child checkpoint relationships."""
```

**Key Test Scenarios:**
- ✅ Complete checkpoint lifecycle with real data
- ✅ Checkpoint creation with biomedical corpus metadata
- ✅ List checkpoints with pagination and filtering
- ✅ Delete checkpoint with dependency checking
- ✅ Checkpoint lineage and version tracking
- ✅ Concurrent checkpoint operations

### Phase 3: RAG Tools Testing (`mcp/rag_tools.py`)

#### 3.1 Unit Tests
```python
class TestRAGToolsUnit:
    """Unit tests for RAG search and retrieval tools."""
    
    @patch('bio_mcp.mcp.rag_tools.get_rag_manager')
    async def test_rag_search_parameter_validation(self, mock_manager):
        """Test search parameter validation."""
        
    async def test_search_mode_selection(self):
        """Test semantic, BM25, and hybrid search mode handling."""
        
    async def test_quality_scoring_calculation(self):
        """Test journal quality scoring and result ranking."""
```

**Key Test Scenarios:**
- ✅ Query parameter validation (length, format)
- ✅ Search mode validation (semantic, bm25, hybrid)
- ✅ Limit and offset parameter handling
- ✅ Filter parameter parsing (date ranges, journals)
- ✅ Quality score calculation and ranking
- ✅ Result formatting for MCP responses

#### 3.2 Integration Tests
```python
class TestRAGToolsIntegration:
    """Integration tests with real vector store and database."""
    
    async def test_semantic_search_biomedical_queries(self, weaviate_client, database_manager):
        """Test semantic search with biomedical research queries."""
        
    async def test_hybrid_search_ranking(self, weaviate_client, database_manager):
        """Test hybrid search result ranking and quality scoring."""
        
    async def test_document_retrieval_by_pmid(self, database_manager):
        """Test document retrieval with real PMIDs."""
```

**Key Test Scenarios:**
- ✅ Semantic search with biomedical terminology
- ✅ BM25 keyword search accuracy
- ✅ Hybrid search combining vector and keyword scores
- ✅ Quality-based result reranking
- ✅ Document retrieval with metadata enrichment
- ✅ Large result set handling and pagination
- ✅ Search filters (date ranges, journal impact factors)

### Phase 4: Resources Testing (`mcp/resources.py`)

#### 4.1 Unit Tests
```python
class TestResourcesUnit:
    """Unit tests for MCP resource endpoints."""
    
    @patch('bio_mcp.mcp.resources.get_resource_manager')
    async def test_resource_uri_parsing(self, mock_manager):
        """Test resource URI parsing and validation."""
        
    async def test_resource_listing_format(self):
        """Test resource listing response format."""
```

**Key Test Scenarios:**
- ✅ URI parsing and validation
- ✅ Resource type identification
- ✅ Resource metadata generation
- ✅ Content formatting for different resource types
- ✅ Error handling for invalid URIs

#### 4.2 Integration Tests
```python
class TestResourcesIntegration:
    """Integration tests for MCP resources with real data."""
    
    async def test_corpus_resource_generation(self, database_manager):
        """Test corpus resource generation from real database."""
        
    async def test_checkpoint_resource_content(self, database_manager):
        """Test checkpoint resource content generation."""
```

**Key Test Scenarios:**
- ✅ Corpus statistics resource generation
- ✅ Checkpoint metadata resource content
- ✅ System status resource generation
- ✅ Resource content caching and updates

### Phase 5: MCP Protocol Testing

#### 5.1 Mock MCP Server Tests
```python
class TestMCPProtocolCompliance:
    """Test MCP protocol compliance and tool registration."""
    
    async def test_tool_registration(self):
        """Test tool registration with MCP server."""
        
    async def test_tool_schema_validation(self):
        """Test tool schema compliance with MCP spec."""
        
    async def test_tool_execution_protocol(self):
        """Test tool execution through MCP protocol."""
```

**Key Test Scenarios:**
- ✅ Tool registration and discovery
- ✅ Schema validation against MCP specification
- ✅ Request/response protocol compliance
- ✅ Error handling through MCP protocol
- ✅ Tool metadata and documentation

## Test Data Strategy

### Biomedical Test Corpus
```python
class BiomedicMCPTestData:
    """Realistic biomedical test data for MCP tools."""
    
    # Cancer research papers
    CANCER_PAPERS = [...]
    
    # Immunotherapy studies  
    IMMUNOTHERAPY_PAPERS = [...]
    
    # Machine learning in medicine
    ML_MEDICINE_PAPERS = [...]
    
    # Checkpoint test scenarios
    CHECKPOINT_SCENARIOS = [...]
```

### MCP Response Validation
```python
class MCPResponseValidator:
    """Validate MCP responses against expected formats."""
    
    def validate_text_content(self, response: TextContent) -> bool:
        """Validate TextContent response format."""
        
    def validate_search_results(self, results: list[dict]) -> bool:
        """Validate search result structure."""
```

## Test Execution Strategy

### 1. Development Testing
```bash
# Unit tests only (fast feedback)
uv run pytest tests/unit/mcp/ -v

# Integration tests (comprehensive)
uv run pytest tests/integration/mcp/ -v

# Full MCP test suite
uv run pytest tests/unit/mcp/ tests/integration/mcp/ -v
```

### 2. Coverage Analysis
```bash
# MCP modules coverage
uv run pytest tests/unit/mcp/ tests/integration/mcp/ \
  --cov=bio_mcp.mcp --cov-report=term

# Overall project impact
uv run pytest tests/unit tests/integration \
  --cov=bio_mcp --cov-report=term
```

### 3. CI/CD Integration
- Run unit tests on every commit
- Run integration tests on pull requests
- Generate coverage reports for review
- Validate MCP protocol compliance

## Success Criteria

### Coverage Targets
- **Corpus Tools**: 80% coverage (+121 statements)
- **RAG Tools**: 85% coverage (+108 statements)  
- **Resources**: 75% coverage (+91 statements)
- **Overall Project**: 47% coverage (+9.8pp improvement)

### Quality Metrics
- ✅ All MCP tools have both unit and integration test coverage
- ✅ MCP protocol compliance validated
- ✅ Realistic biomedical scenarios tested
- ✅ Error handling comprehensively tested
- ✅ Performance characteristics validated
- ✅ Test execution time under 5 minutes

### Functional Validation
- ✅ All MCP tools work with real biomedical data
- ✅ Search results are relevant and properly ranked
- ✅ Checkpoint operations maintain data integrity
- ✅ Resource endpoints provide accurate information
- ✅ Error messages are helpful and actionable

## Implementation Timeline

### Week 1: Infrastructure & Unit Tests
- Set up test infrastructure and utilities
- Implement unit tests for all MCP tools
- Create biomedical test data generators

### Week 2: Integration Tests & Protocol Testing
- Implement integration tests with testcontainers
- Add MCP protocol compliance testing
- Validate against realistic biomedical scenarios

### Week 3: Optimization & Documentation
- Optimize test execution performance
- Add comprehensive test documentation
- Integration with CI/CD pipeline

## Maintenance Strategy

### Test Data Management
- Regular updates to biomedical test corpus
- Version control for test scenarios
- Automated test data generation

### Coverage Monitoring
- Regular coverage analysis and reporting
- Identification of coverage gaps
- Continuous improvement of test scenarios

### Protocol Evolution
- Monitor MCP specification updates
- Adapt tests for protocol changes
- Maintain backward compatibility testing

---

**Target Outcome**: Comprehensive MCP tools testing that improves overall project coverage from 37% to 47% while ensuring robust, well-tested biomedical research functionality.