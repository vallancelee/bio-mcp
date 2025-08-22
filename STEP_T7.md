# T7: MCP Tools Testing Implementation Plan

**Goal:** Implement comprehensive testing for Bio-MCP's Model Context Protocol tools to improve reliability and user confidence from 16% to 80%+ coverage on MCP modules.

## TDD Approach (Red-Green-Refactor)

1. **Write failing tests for MCP tools reliability**
   - Test all MCP tool parameter validation and error handling
   - Test realistic biomedical data scenarios with authentic corpus
   - Test MCP protocol compliance and response formatting
   - Test cross-integration between tools (rag → corpus → pubmed)

2. **Create biomedical test infrastructure**
   - Build realistic test corpus with cancer, immunotherapy, ML papers
   - Create MCP response validation helpers
   - Set up testcontainers for integration testing
   - Mock service factories for unit testing

3. **Implement comprehensive test coverage**
   - Unit tests for argument parsing, validation, error handling
   - Integration tests with real database and vector store
   - End-to-end workflow tests with biomedical scenarios
   - Performance and reliability validation

## Phase 1: Test Infrastructure Setup (Day 1-2)

### 1.1 Biomedical Test Data Generator
**File**: `tests/fixtures/biomedical_test_data.py`

```python
class BiomedicTestCorpus:
    """Realistic biomedical test data for MCP tools validation."""
    
    # Cancer research papers (realistic PMIDs and metadata)
    CANCER_PAPERS = [
        {
            "pmid": "36653448",
            "title": "Glioblastoma multiforme: pathogenesis and treatment",
            "abstract": "Glioblastoma multiforme (GBM) is the most aggressive primary brain tumor...",
            "journal": "Nature Reviews Cancer",
            "publication_date": "2023-01-18",
            "mesh_terms": ["Glioblastoma", "Brain Neoplasms", "Antineoplastic Agents"],
            "authors": ["Smith, J.", "Johnson, A.", "Wilson, R."]
        },
        # Additional realistic cancer papers...
    ]
    
    # Immunotherapy studies
    IMMUNOTHERAPY_PAPERS = [...]
    
    # Machine learning in medicine papers  
    ML_MEDICINE_PAPERS = [...]
    
    # Clinical trial scenarios
    CHECKPOINT_SCENARIOS = [...]
```

### 1.2 MCP Response Validation Framework
**File**: `tests/utils/mcp_validators.py`

```python
class MCPResponseValidator:
    """Validate MCP responses against expected formats."""
    
    def validate_text_content(self, response: TextContent) -> bool:
        """Validate TextContent response structure and content."""
        assert response.type == "text"
        assert isinstance(response.text, str)
        assert len(response.text) > 0
        return True
    
    def validate_search_results(self, response_text: str) -> dict:
        """Parse and validate search result structure."""
        # Extract structured data from MCP text response
        # Validate contains: query, results count, PMIDs, execution time
        pass
    
    def validate_error_response(self, response_text: str) -> bool:
        """Validate error response format and helpful messages."""
        assert "❌ Error:" in response_text
        assert len(response_text) < 500  # Not too verbose
        return True
```

### 1.3 Test Utilities and Mocks
**File**: `tests/utils/test_helpers.py`

```python
class MockServiceFactory:
    """Factory for creating consistent mock services."""
    
    @staticmethod
    def create_pubmed_service_mock():
        """Create mock PubMedService with realistic responses."""
        pass
    
    @staticmethod  
    def create_weaviate_client_mock():
        """Create mock WeaviateClient with search responses."""
        pass
    
    @staticmethod
    def create_database_manager_mock():
        """Create mock DatabaseManager with corpus data."""
        pass
```

## Phase 2: RAG Tools Testing (Day 3-4)

### 2.1 Unit Tests for RAG Tools
**File**: `tests/unit/mcp/test_rag_tools.py`

```python
class TestRAGToolsUnit:
    """Unit tests for RAG search and retrieval tools."""
    
    @patch('bio_mcp.mcp.rag_tools.get_rag_manager')
    async def test_rag_search_parameter_validation(self, mock_manager):
        """Test search parameter validation with edge cases."""
        # Test empty query
        result = await rag_search_tool("rag.search", {"query": ""})
        validator = MCPResponseValidator()
        validator.validate_error_response(result[0].text)
        
        # Test invalid search_mode
        result = await rag_search_tool("rag.search", {
            "query": "cancer", 
            "search_mode": "invalid_mode"
        })
        # Should fallback to "hybrid" mode gracefully
        
        # Test top_k limits (min 1, max 50)
        result = await rag_search_tool("rag.search", {
            "query": "cancer",
            "top_k": 100  # Should clamp to 50
        })
        
        # Test alpha parameter validation (0.0-1.0)
        result = await rag_search_tool("rag.search", {
            "query": "cancer",
            "alpha": -0.5  # Should clamp to 0.0
        })
    
    async def test_hybrid_search_mode_selection(self):
        """Test semantic, BM25, and hybrid search mode handling."""
        test_corpus = BiomedicTestCorpus()
        
        with patch('bio_mcp.mcp.rag_tools.get_rag_manager') as mock_manager:
            mock_manager.return_value.search_documents = AsyncMock(return_value=RAGSearchResult(
                query="glioblastoma treatment",
                total_results=5,
                documents=test_corpus.CANCER_PAPERS[:5],
                search_type="hybrid"
            ))
            
            # Test hybrid mode (default)
            result = await rag_search_tool("rag.search", {
                "query": "glioblastoma treatment"
            })
            
            response_text = result[0].text
            assert "🔀" in response_text  # Hybrid mode indicator
            assert "Hybrid (BM25 + Vector" in response_text
            
            # Test semantic mode
            result = await rag_search_tool("rag.search", {
                "query": "glioblastoma treatment",
                "search_mode": "semantic"
            })
            
            response_text = result[0].text
            assert "🧠" in response_text  # Semantic mode indicator
    
    async def test_quality_scoring_integration(self):
        """Test quality score calculation and boost display."""
        with patch('bio_mcp.mcp.rag_tools.get_rag_manager') as mock_manager:
            # Create documents with quality scores and boosts
            boosted_docs = [
                {
                    "pmid": "36653448",
                    "title": "High-impact paper",
                    "score": 0.85,
                    "boosted_score": 0.935,  # 10% boost
                    "journal": "Nature"
                }
            ]
            
            mock_manager.return_value.search_documents = AsyncMock(return_value=RAGSearchResult(
                query="cancer research",
                total_results=1,
                documents=boosted_docs,
                search_type="hybrid"
            ))
            
            result = await rag_search_tool("rag.search", {
                "query": "cancer research",
                "rerank_by_quality": True
            })
            
            response_text = result[0].text
            assert "0.935 (+10.0%)" in response_text  # Quality boost displayed
            assert "Quality boosting: ON" in response_text
    
    async def test_performance_target_validation(self):
        """Test performance monitoring meets <200ms target."""
        with patch('bio_mcp.mcp.rag_tools.get_rag_manager') as mock_manager:
            mock_manager.return_value.search_documents = AsyncMock(return_value=RAGSearchResult(
                query="test query",
                total_results=1,
                documents=[{"pmid": "123", "title": "Test"}],
                search_type="hybrid",
                performance={
                    "total_time_ms": 150.0,  # Under target
                    "target_time_ms": 200.0
                }
            ))
            
            result = await rag_search_tool("rag.search", {"query": "test query"})
            response_text = result[0].text
            assert "✅ Performance: 150.0ms" in response_text
```

### 2.2 Integration Tests for RAG Tools  
**File**: `tests/integration/mcp/test_rag_integration.py`

```python
class TestRAGToolsIntegration:
    """Integration tests with real vector store and database."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_biomedical_search(self, weaviate_client, database_manager):
        """Test complete search workflow with realistic biomedical data."""
        # Setup: Insert biomedical test corpus into Weaviate
        test_corpus = BiomedicTestCorpus()
        
        for paper in test_corpus.CANCER_PAPERS[:3]:
            await weaviate_client.add_document(paper)
        
        # Test: Search for cancer-related terms
        result = await rag_search_tool("rag.search", {
            "query": "glioblastoma treatment options",
            "search_mode": "hybrid",
            "top_k": 5
        })
        
        validator = MCPResponseValidator()
        validator.validate_text_content(result[0])
        
        search_data = validator.validate_search_results(result[0].text)
        assert search_data["total_results"] > 0
        assert "glioblastoma" in result[0].text.lower()
        
    @pytest.mark.asyncio  
    async def test_cross_source_quality_ranking(self, weaviate_client, database_manager):
        """Test quality-aware reranking with different journal impact factors."""
        test_papers = [
            {
                "pmid": "1001", 
                "title": "Nature Cancer Paper",
                "journal": "Nature",
                "abstract": "High impact cancer research",
                "score": 0.80
            },
            {
                "pmid": "1002",
                "title": "Local Journal Paper", 
                "journal": "Local Medical Journal",
                "abstract": "Similar cancer research",
                "score": 0.82  # Higher base score but lower journal impact
            }
        ]
        
        for paper in test_papers:
            await weaviate_client.add_document(paper)
        
        # Test with quality boosting enabled
        result = await rag_search_tool("rag.search", {
            "query": "cancer research",
            "rerank_by_quality": True,
            "top_k": 2
        })
        
        # Nature paper should rank higher due to quality boost
        response_text = result[0].text
        lines = response_text.split('\n')
        first_result = [line for line in lines if "1." in line][0]
        assert "Nature Cancer Paper" in first_result
```

## Phase 3: Corpus Tools Testing (Day 5-6)

### 3.1 Unit Tests for Corpus Tools
**File**: `tests/unit/mcp/test_corpus_tools.py`

```python
class TestCorpusToolsUnit:
    """Unit tests for corpus checkpoint tools."""
    
    @patch('bio_mcp.mcp.corpus_tools.get_checkpoint_manager')
    async def test_checkpoint_create_validation(self, mock_manager):
        """Test checkpoint creation parameter validation."""
        # Test missing required parameters
        result = await corpus_checkpoint_create_tool("corpus.checkpoint.create", {
            "checkpoint_id": "test_checkpoint"
            # Missing 'name' parameter
        })
        
        validator = MCPResponseValidator()
        validator.validate_error_response(result[0].text)
        assert "name" in result[0].text.lower()
        
        # Test valid checkpoint creation
        mock_manager.return_value.create_checkpoint = AsyncMock(return_value=CheckpointResult(
            checkpoint_id="test_checkpoint",
            operation="create", 
            success=True,
            execution_time_ms=45.2,
            checkpoint_data={
                "name": "Cancer Research Checkpoint",
                "description": "Checkpoint for cancer research corpus",
                "total_documents": 1500,
                "last_sync_edat": "2024-01-15",
                "version": "1.0"
            }
        ))
        
        result = await corpus_checkpoint_create_tool("corpus.checkpoint.create", {
            "checkpoint_id": "test_checkpoint",
            "name": "Cancer Research Checkpoint", 
            "description": "Checkpoint for cancer research corpus"
        })
        
        response_text = result[0].text
        assert "✅ Corpus checkpoint created successfully" in response_text
        assert "Cancer Research Checkpoint" in response_text
        assert "1500" in response_text  # Total documents
        assert "45.2ms" in response_text  # Execution time
    
    async def test_checkpoint_list_pagination(self):
        """Test checkpoint listing with pagination parameters."""
        with patch('bio_mcp.mcp.corpus_tools.get_checkpoint_manager') as mock_manager:
            # Test default pagination
            result = await corpus_checkpoint_list_tool("corpus.checkpoint.list", {})
            # Should use default limit=20, offset=0
            
            # Test custom pagination
            result = await corpus_checkpoint_list_tool("corpus.checkpoint.list", {
                "limit": 5,
                "offset": 10
            })
            
            # Test invalid pagination (negative values)
            result = await corpus_checkpoint_list_tool("corpus.checkpoint.list", {
                "limit": -5,
                "offset": -2
            })
            # Should handle gracefully with defaults
```

### 3.2 Integration Tests for Corpus Tools
**File**: `tests/integration/mcp/test_corpus_integration.py`

```python
class TestCorpusToolsIntegration:
    """Integration tests with real database."""
    
    @pytest.mark.asyncio
    async def test_checkpoint_lifecycle_workflow(self, database_manager):
        """Test complete checkpoint lifecycle: create → get → list → delete."""
        # Create checkpoint
        create_result = await corpus_checkpoint_create_tool("corpus.checkpoint.create", {
            "checkpoint_id": "integration_test_checkpoint",
            "name": "Integration Test Checkpoint",
            "description": "Test checkpoint for integration testing"
        })
        
        assert "✅ Corpus checkpoint created successfully" in create_result[0].text
        
        # Get checkpoint
        get_result = await corpus_checkpoint_get_tool("corpus.checkpoint.get", {
            "checkpoint_id": "integration_test_checkpoint"
        })
        
        assert "Integration Test Checkpoint" in get_result[0].text
        
        # List checkpoints (should include our checkpoint)
        list_result = await corpus_checkpoint_list_tool("corpus.checkpoint.list", {})
        assert "integration_test_checkpoint" in list_result[0].text
        
        # Delete checkpoint
        delete_result = await corpus_checkpoint_delete_tool("corpus.checkpoint.delete", {
            "checkpoint_id": "integration_test_checkpoint"
        })
        
        assert "✅ Checkpoint deleted successfully" in delete_result[0].text
        
        # Verify deletion (get should fail)
        get_after_delete = await corpus_checkpoint_get_tool("corpus.checkpoint.get", {
            "checkpoint_id": "integration_test_checkpoint"
        })
        
        assert "❌" in get_after_delete[0].text  # Should be error response
```

## Phase 4: Resources Testing (Day 7)

### 4.1 Unit Tests for Resources
**File**: `tests/unit/mcp/test_resources.py`

```python
class TestResourcesUnit:
    """Unit tests for MCP resource endpoints."""
    
    @patch('bio_mcp.mcp.resources.get_resource_manager')
    async def test_resource_uri_parsing(self, mock_manager):
        """Test resource URI parsing and validation."""
        # Test valid corpus resource URI
        mock_manager.return_value.get_resource = AsyncMock(return_value={
            "uri": "corpus://bio_mcp/stats",
            "type": "corpus_statistics", 
            "data": {"total_documents": 1500, "last_sync": "2024-01-15"}
        })
        
        # Test invalid URI format
        # Test missing resource handling
        pass
    
    async def test_resource_content_formatting(self):
        """Test resource content formatting for different types."""
        # Test corpus statistics resource
        # Test checkpoint metadata resource
        # Test system status resource
        pass
```

## Phase 5: End-to-End Workflow Testing (Day 8)

### 5.1 Cross-Tool Integration Tests
**File**: `tests/integration/mcp/test_e2e_workflows.py`

```python
class TestEndToEndWorkflows:
    """Test complete biomedical research workflows."""
    
    @pytest.mark.asyncio
    async def test_research_discovery_workflow(self, full_system_setup):
        """Test: Search → Get Document → Create Checkpoint → List Resources."""
        # 1. Search for biomedical papers
        search_result = await rag_search_tool("rag.search", {
            "query": "CRISPR gene editing cancer",
            "search_mode": "hybrid",
            "top_k": 3
        })
        
        # Extract PMID from search results
        pmid = self._extract_pmid_from_search(search_result[0].text)
        
        # 2. Get detailed document information
        get_result = await rag_get_tool("rag.get", {
            "doc_id": pmid
        })
        
        assert "📄 **Document Details**" in get_result[0].text
        
        # 3. Create checkpoint for this research area
        checkpoint_result = await corpus_checkpoint_create_tool("corpus.checkpoint.create", {
            "checkpoint_id": "crispr_research_checkpoint",
            "name": "CRISPR Cancer Research",
            "description": "Checkpoint for CRISPR-based cancer research papers"
        })
        
        assert "✅" in checkpoint_result[0].text
        
        # 4. Verify workflow completion by listing resources
        # This validates the complete system integration
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, full_system_setup):
        """Test system behavior during error conditions."""
        # Test search with invalid parameters  
        # Test graceful degradation when Weaviate unavailable
        # Test checkpoint operations with database errors
        pass
    
    def _extract_pmid_from_search(self, search_text: str) -> str:
        """Helper to extract PMID from search result text."""
        import re
        pmid_match = re.search(r'PMID: (\d+)', search_text)
        return pmid_match.group(1) if pmid_match else "12345678"
```

## Phase 6: Performance and Reliability Testing (Day 9-10)

### 6.1 Performance Tests
**File**: `tests/performance/test_mcp_performance.py`

```python
class TestMCPPerformance:
    """Performance and reliability tests for MCP tools."""
    
    @pytest.mark.asyncio
    async def test_search_performance_targets(self, weaviate_client):
        """Test search performance meets <200ms targets."""
        import time
        
        # Load realistic corpus size (1000+ documents)
        test_corpus = BiomedicTestCorpus()
        await self._load_test_corpus(weaviate_client, test_corpus.ALL_PAPERS[:1000])
        
        # Test multiple search scenarios
        test_queries = [
            "cancer immunotherapy",
            "CRISPR gene editing",  
            "machine learning radiology",
            "glioblastoma treatment options"
        ]
        
        for query in test_queries:
            start_time = time.time()
            
            result = await rag_search_tool("rag.search", {
                "query": query,
                "search_mode": "hybrid",
                "top_k": 10
            })
            
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            # Should meet 200ms target for hybrid search
            assert latency_ms < 200, f"Query '{query}' took {latency_ms:.1f}ms (target: <200ms)"
    
    @pytest.mark.asyncio
    async def test_concurrent_tool_usage(self, full_system_setup):
        """Test system reliability under concurrent tool usage."""
        import asyncio
        
        # Simulate concurrent users
        async def simulate_user_session():
            # Search -> Get -> Checkpoint workflow
            await rag_search_tool("rag.search", {"query": "cancer research"})
            await rag_get_tool("rag.get", {"doc_id": "12345678"})
            await corpus_checkpoint_list_tool("corpus.checkpoint.list", {})
        
        # Run 10 concurrent user sessions
        tasks = [simulate_user_session() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete successfully
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Found {len(exceptions)} exceptions in concurrent usage"
```

### 6.2 Reliability Tests
**File**: `tests/reliability/test_mcp_reliability.py`

```python
class TestMCPReliability:
    """Reliability and error handling tests."""
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self, database_manager):
        """Test graceful degradation when services unavailable."""
        # Test search when Weaviate unavailable
        with patch('bio_mcp.mcp.rag_tools.get_rag_manager') as mock_manager:
            mock_manager.return_value.search_documents = AsyncMock(
                side_effect=Exception("Weaviate connection failed")
            )
            
            result = await rag_search_tool("rag.search", {"query": "test"})
            
            # Should return helpful error message
            assert "❌ Error during hybrid RAG search" in result[0].text
            assert len(result[0].text) < 200  # Not too verbose
    
    async def test_input_sanitization(self):
        """Test handling of malicious or malformed inputs."""
        # Test extremely long queries
        long_query = "cancer " * 1000
        result = await rag_search_tool("rag.search", {"query": long_query})
        # Should handle gracefully
        
        # Test special characters and injection attempts
        malicious_query = "'; DROP TABLE documents; --"
        result = await rag_search_tool("rag.search", {"query": malicious_query})
        # Should sanitize and handle safely
```

## Implementation Success Criteria

### Coverage Targets (Per MCP_TESTING.md)
- **RAG Tools**: 16% → 85% coverage (+108 statements)
- **Corpus Tools**: 17% → 80% coverage (+121 statements)  
- **Resources**: 15% → 75% coverage (+91 statements)
- **Overall Project**: 37% → 47% coverage (+9.8pp improvement)

### Quality Metrics
- ✅ All MCP tools have both unit and integration test coverage
- ✅ Realistic biomedical scenarios tested with authentic data
- ✅ Error handling comprehensively tested with helpful messages
- ✅ Performance targets validated (<200ms hybrid search)
- ✅ Cross-tool workflows tested end-to-end
- ✅ Concurrent usage reliability validated

### Test Execution Performance
- ✅ Unit tests complete in <30 seconds
- ✅ Integration tests complete in <2 minutes  
- ✅ Full test suite completes in <5 minutes
- ✅ Tests are deterministic and don't flake

## Running the Tests

```bash
# Unit tests (fast feedback)
uv run pytest tests/unit/mcp/ -v

# Integration tests (comprehensive)  
uv run pytest tests/integration/mcp/ -v

# Full MCP test suite
uv run pytest tests/unit/mcp/ tests/integration/mcp/ -v

# Performance tests
uv run pytest tests/performance/ -v

# Coverage analysis
uv run pytest tests/unit/mcp/ tests/integration/mcp/ \
  --cov=bio_mcp.mcp --cov-report=term --cov-report=html

# Coverage target validation
uv run python scripts/coverage.py
```

## Definition of Done

- ✅ **Reliability**: All MCP tools have comprehensive unit and integration tests
- ✅ **Coverage**: Overall project coverage increases from 37% to 47%
- ✅ **Real Data**: Tests use realistic biomedical corpus (cancer, immunotherapy, ML papers)
- ✅ **Performance**: Hybrid search consistently meets <200ms targets
- ✅ **Error Handling**: All error paths tested with helpful user messages
- ✅ **End-to-End**: Complete research workflows validated (search → get → checkpoint)
- ✅ **Reliability**: System handles concurrent usage and graceful degradation
- ✅ **Documentation**: Test coverage reports and biomedical scenarios documented

This creates a **rock-solid foundation** users can trust for biomedical research workflows.