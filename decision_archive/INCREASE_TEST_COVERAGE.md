# Test Coverage Expansion Implementation Plan

## Overview

This document outlines a comprehensive plan to increase Bio-MCP test coverage from the current **38.4%** to **65%+** by focusing on high-impact areas. The plan prioritizes business-critical functionality and follows a test-driven development approach.

## Current Coverage Status

### Overall Project Coverage: 38.4%
- **Total Statements**: 4,483
- **Covered Statements**: 1,899  
- **Tests Passing**: 231/232 (99.6% pass rate)

### Coverage by Layer
- **HTTP Infrastructure**: 72.5% ✅ (Production Ready)
- **MCP Tools**: 41.4% ✅ (Human workflows validated)
- **Data Models**: 100% ✅ (Complete)
- **Services Layer**: 14% ❌ (Major gap)
- **Database Client**: 28% ❌ (Needs improvement)
- **External Clients**: 15-17% ❌ (Integration dependent)

## Target Coverage Goals

### Phase-by-Phase Targets
1. **Phase 1**: 38.4% → 50% (+12pp) - Services Layer
2. **Phase 2**: 50% → 59% (+9pp) - Database Client  
3. **Phase 3**: 59% → 66% (+7pp) - External Clients
4. **Phase 4**: 66% → 70%+ (+4pp) - Core Components

### Module-Specific Targets
- **Services Layer**: 14% → 60% (+239 statements)
- **Database Client**: 28% → 70% (+180 statements)
- **Weaviate Client**: 16% → 50% (+100 statements)
- **PubMed Client**: 17% → 50% (+120 statements)
- **Logging/Error Handling**: 30% → 80% (+80 statements)

## Implementation Plan

### Phase 1: Services Layer Testing (Priority 1)
**Timeline**: Week 1-2  
**Expected Gain**: +12 percentage points overall coverage

#### 1.1 Document Service Testing
**File**: `tests/unit/test_document_service.py`  
**Target**: `services/services.py` DocumentService class

```python
class TestDocumentService:
    """Comprehensive testing for document storage and retrieval."""
    
    async def test_document_lifecycle_operations(self):
        """Test complete document lifecycle: create → store → retrieve → update → delete."""
        
    async def test_document_validation_and_normalization(self):
        """Test document validation, field normalization, and data sanitization."""
        
    async def test_batch_document_operations(self):
        """Test bulk document insertion, update, and deletion operations."""
        
    async def test_document_search_and_filtering(self):
        """Test document search with various filters and pagination."""
        
    async def test_document_metadata_handling(self):
        """Test handling of document metadata, tags, and categorization."""
        
    async def test_document_error_scenarios(self):
        """Test error handling for invalid data, conflicts, and edge cases."""
```

#### 1.2 Checkpoint Service Testing
**File**: `tests/unit/test_checkpoint_service.py`  
**Target**: `services/services.py` CorpusCheckpointService class

```python
class TestCorpusCheckpointService:
    """Comprehensive testing for checkpoint management operations."""
    
    async def test_checkpoint_creation_and_validation(self):
        """Test checkpoint creation with validation, metadata, and constraints."""
        
    async def test_checkpoint_hierarchy_and_lineage(self):
        """Test parent-child checkpoint relationships and lineage tracking."""
        
    async def test_checkpoint_versioning_and_snapshots(self):
        """Test checkpoint versioning, snapshots, and rollback capabilities."""
        
    async def test_checkpoint_query_and_filtering(self):
        """Test checkpoint listing with filtering, sorting, and pagination."""
        
    async def test_checkpoint_permissions_and_access(self):
        """Test checkpoint access control and permission management."""
        
    async def test_checkpoint_cleanup_and_archival(self):
        """Test checkpoint deletion, archival, and cleanup operations."""
```

#### 1.3 PubMed Service Testing
**File**: `tests/unit/test_pubmed_service.py`  
**Target**: `services/services.py` PubMedService class

```python
class TestPubMedService:
    """Testing for PubMed integration and synchronization."""
    
    async def test_pubmed_search_operations(self):
        """Test PubMed search with various query types and parameters."""
        
    async def test_pubmed_document_fetching(self):
        """Test fetching individual documents and batch operations."""
        
    async def test_pubmed_sync_incremental(self):
        """Test incremental synchronization with watermark management."""
        
    async def test_pubmed_sync_full_refresh(self):
        """Test full corpus refresh and data consistency validation."""
        
    async def test_pubmed_rate_limiting_and_throttling(self):
        """Test API rate limiting, throttling, and retry mechanisms."""
        
    async def test_pubmed_error_handling_and_recovery(self):
        """Test error handling for API failures, timeouts, and data issues."""
```

#### 1.4 Integration Testing
**File**: `tests/integration/test_services_integration.py`

```python
class TestServicesIntegration:
    """Integration testing across multiple services."""
    
    async def test_document_to_checkpoint_workflow(self):
        """Test complete workflow: PubMed sync → Document storage → Checkpoint creation."""
        
    async def test_cross_service_error_propagation(self):
        """Test error handling and rollback across service boundaries."""
        
    async def test_service_initialization_and_dependencies(self):
        """Test service startup, dependency injection, and health validation."""
        
    async def test_concurrent_service_operations(self):
        """Test concurrent operations across multiple services."""
```

### Phase 2: Database Client Testing (Priority 2)
**Timeline**: Week 3  
**Expected Gain**: +9 percentage points overall coverage

#### 2.1 Database Client Core Testing
**File**: `tests/unit/test_database_client.py`  
**Target**: `shared/clients/database.py`

```python
class TestDatabaseManager:
    """Comprehensive database client testing."""
    
    async def test_connection_management_and_pooling(self):
        """Test connection establishment, pooling, and lifecycle management."""
        
    async def test_transaction_handling_and_rollbacks(self):
        """Test transaction management, commits, rollbacks, and savepoints."""
        
    async def test_query_building_and_execution(self):
        """Test SQL query building, parameter binding, and execution."""
        
    async def test_crud_operations_comprehensive(self):
        """Test Create, Read, Update, Delete operations with edge cases."""
        
    async def test_batch_operations_and_performance(self):
        """Test bulk operations, batch inserts, and performance optimization."""
        
    async def test_migration_and_schema_management(self):
        """Test database migrations, schema validation, and versioning."""
        
    async def test_connection_recovery_and_failover(self):
        """Test connection recovery, failover handling, and resilience."""
```

#### 2.2 Database Operations Testing
**File**: `tests/integration/test_database_operations.py`

```python
class TestDatabaseOperationsIntegration:
    """Integration testing for database operations."""
    
    async def test_real_database_crud_lifecycle(self):
        """Test CRUD operations against real PostgreSQL testcontainer."""
        
    async def test_complex_queries_and_joins(self):
        """Test complex queries, joins, and aggregations with real data."""
        
    async def test_concurrent_database_access(self):
        """Test concurrent access patterns and locking behavior."""
        
    async def test_database_performance_under_load(self):
        """Test database performance with realistic data volumes."""
```

### Phase 3: External Client Testing (Priority 3)
**Timeline**: Week 4  
**Expected Gain**: +7 percentage points overall coverage

#### 3.1 Weaviate Client Testing
**File**: `tests/unit/test_weaviate_client_mocked.py`  
**Target**: `shared/clients/weaviate_client.py`

```python
class TestWeaviateClientMocked:
    """Mocked testing for Weaviate client operations."""
    
    async def test_vector_search_operations(self):
        """Test vector similarity search with mocked Weaviate responses."""
        
    async def test_hybrid_search_functionality(self):
        """Test hybrid (vector + BM25) search with realistic scenarios."""
        
    async def test_document_indexing_and_embedding(self):
        """Test document indexing, embedding generation, and storage."""
        
    async def test_schema_management_and_validation(self):
        """Test schema creation, validation, and class management."""
        
    async def test_batch_operations_and_optimization(self):
        """Test batch document operations and performance optimization."""
        
    async def test_weaviate_error_handling_and_retry(self):
        """Test error handling, retry logic, and connection recovery."""
```

#### 3.2 PubMed Client Testing
**File**: `tests/unit/test_pubmed_client_mocked.py`  
**Target**: `sources/pubmed/client.py`

```python
class TestPubMedClientMocked:
    """Mocked testing for PubMed API client."""
    
    async def test_pubmed_search_api_integration(self):
        """Test PubMed search API with mocked responses and pagination."""
        
    async def test_pubmed_efetch_document_retrieval(self):
        """Test document fetching with various formats and error handling."""
        
    async def test_pubmed_rate_limiting_compliance(self):
        """Test API rate limiting compliance and throttling mechanisms."""
        
    async def test_pubmed_query_building_and_validation(self):
        """Test query construction, validation, and optimization."""
        
    async def test_pubmed_response_parsing_and_normalization(self):
        """Test response parsing, data normalization, and validation."""
        
    async def test_pubmed_error_scenarios_and_recovery(self):
        """Test error handling for API failures, timeouts, and malformed data."""
```

### Phase 4: Core Components Testing (Priority 4)
**Timeline**: Week 5  
**Expected Gain**: +4 percentage points overall coverage

#### 4.1 Logging and Configuration Testing
**File**: `tests/unit/test_logging_and_config.py`

```python
class TestLoggingConfiguration:
    """Testing for logging configuration and management."""
    
    def test_logger_initialization_and_configuration(self):
        """Test logger setup, configuration loading, and initialization."""
        
    def test_log_formatting_and_structured_logging(self):
        """Test log formatting, structured logging, and JSON output."""
        
    def test_log_level_management_and_filtering(self):
        """Test log level configuration, filtering, and dynamic updates."""
        
    def test_sensitive_data_redaction(self):
        """Test sensitive data redaction and sanitization in logs."""
```

#### 4.2 Error Handling Testing
**File**: `tests/unit/test_error_handling.py`

```python
class TestErrorHandling:
    """Comprehensive error handling and recovery testing."""
    
    def test_error_classification_and_categorization(self):
        """Test error classification, categorization, and severity assignment."""
        
    def test_error_recovery_strategies(self):
        """Test error recovery mechanisms and fallback strategies."""
        
    def test_error_context_preservation(self):
        """Test error context preservation and debugging information."""
        
    def test_user_friendly_error_messages(self):
        """Test user-friendly error message generation and localization."""
```

## Implementation Guidelines

### Testing Best Practices

#### 1. Test Structure and Organization
```python
# Standard test structure
class TestServiceName:
    """Brief description of what this test class covers."""
    
    def setup_method(self):
        """Setup for each test method."""
        
    @pytest.mark.asyncio
    async def test_specific_functionality(self):
        """Test one specific piece of functionality."""
        # Arrange
        # Act  
        # Assert
        
    def teardown_method(self):
        """Cleanup after each test method."""
```

#### 2. Mocking Strategy
```python
# Use consistent mocking patterns
@patch('bio_mcp.services.external_service')
async def test_with_mocked_external_service(self, mock_service):
    """Test with external service mocked for reliability."""
    
    # Configure mock behavior
    mock_service.return_value = expected_response
    
    # Test the functionality
    result = await service_under_test.method()
    
    # Verify behavior and mock interactions
    assert result == expected_result
    mock_service.assert_called_once_with(expected_params)
```

#### 3. Test Data Management
```python
# Use realistic test data
class TestDataFactory:
    """Factory for generating realistic test data."""
    
    @staticmethod
    def create_document():
        """Create a realistic document for testing."""
        return {
            "pmid": "12345678",
            "title": "Realistic Cancer Research Paper",
            "abstract": "Comprehensive abstract with biomedical content...",
            "journal": "Nature Medicine",
            "authors": ["Smith, J.", "Johnson, A."],
            "publication_date": "2024-01-15"
        }
```

#### 4. Coverage Validation
```python
# Validate coverage improvements
def test_coverage_target_achieved():
    """Validate that coverage targets are met."""
    coverage_report = get_coverage_report()
    assert coverage_report.services_coverage >= 60
    assert coverage_report.database_coverage >= 70
    assert coverage_report.overall_coverage >= 65
```

### Test Execution Strategy

#### 1. Development Workflow
```bash
# Run tests during development
uv run pytest tests/unit/test_document_service.py -v
uv run pytest tests/unit/test_document_service.py::TestDocumentService::test_specific_method -v

# Run with coverage
uv run pytest tests/unit/test_document_service.py --cov=bio_mcp.services --cov-report=term
```

#### 2. Continuous Integration
```bash
# CI pipeline testing
uv run pytest tests/unit/ tests/integration/ --cov=bio_mcp --cov-report=html
uv run pytest tests/unit/ tests/integration/ --cov-fail-under=65
```

#### 3. Performance Testing
```bash
# Performance validation
uv run pytest tests/integration/ -m "performance" --timeout=30
```

## Success Metrics

### Coverage Targets by Phase
- **Phase 1 Completion**: Overall coverage ≥ 50%
- **Phase 2 Completion**: Overall coverage ≥ 59%  
- **Phase 3 Completion**: Overall coverage ≥ 66%
- **Phase 4 Completion**: Overall coverage ≥ 70%

### Quality Metrics
- **Test Pass Rate**: Maintain ≥ 99%
- **Test Execution Time**: ≤ 60 seconds for unit tests
- **Integration Test Time**: ≤ 5 minutes for full suite
- **Code Quality**: No decrease in existing functionality

### Functional Validation
- **Service Reliability**: All core services tested with realistic scenarios
- **Error Handling**: Comprehensive error condition coverage
- **Performance**: Service operations meet performance targets
- **Integration**: Cross-service workflows validated

## Risk Mitigation

### Common Testing Challenges

#### 1. External Service Dependencies
```python
# Solution: Comprehensive mocking
@pytest.fixture
def mock_external_services():
    """Mock all external services for reliable testing."""
    with patch('bio_mcp.clients.pubmed') as mock_pubmed, \
         patch('bio_mcp.clients.weaviate') as mock_weaviate:
        yield mock_pubmed, mock_weaviate
```

#### 2. Async Operation Testing
```python
# Solution: Proper async test patterns
@pytest.mark.asyncio
async def test_async_operation():
    """Test async operations with proper error handling."""
    async with AsyncTestContext() as context:
        result = await async_operation()
        assert result is not None
```

#### 3. Database Testing Complexity
```python
# Solution: Use testcontainers for isolation
@pytest.fixture(scope="function")
async def test_database():
    """Provide isolated database for each test."""
    with PostgresContainer("postgres:13") as postgres:
        database_url = postgres.get_connection_url()
        yield database_url
```

#### 4. Test Data Management
```python
# Solution: Consistent test data factories
@pytest.fixture
def biomedical_test_data():
    """Provide consistent biomedical test data."""
    return BiomedicTestDataFactory.create_realistic_corpus()
```

## Monitoring and Maintenance

### Coverage Monitoring
```bash
# Regular coverage analysis
uv run python scripts/coverage.py --target=65 --fail-under=60
```

### Test Quality Assessment
```bash
# Test quality metrics
uv run pytest --cov=bio_mcp --cov-report=html --cov-branch
uv run pytest --durations=10  # Identify slow tests
```

### Continuous Improvement
1. **Weekly coverage reviews** to track progress
2. **Monthly test quality audits** to maintain standards
3. **Quarterly testing strategy reviews** to adapt approach

## Implementation Timeline

### Week 1: Services Layer Foundation
- Day 1-2: Document Service testing implementation
- Day 3-4: Checkpoint Service testing implementation  
- Day 5: PubMed Service testing implementation

### Week 2: Services Layer Completion
- Day 1-2: Services integration testing
- Day 3-4: Error handling and edge cases
- Day 5: Coverage validation and optimization

### Week 3: Database Client Testing
- Day 1-3: Database Manager comprehensive testing
- Day 4-5: Database operations integration testing

### Week 4: External Client Testing  
- Day 1-3: Weaviate client mocked testing
- Day 4-5: PubMed client mocked testing

### Week 5: Core Components and Finalization
- Day 1-2: Logging and error handling testing
- Day 3-4: Performance and reliability testing
- Day 5: Final coverage validation and documentation

## Expected Outcomes

### Coverage Progression
- **Week 1**: 38.4% → 44% (+6pp)
- **Week 2**: 44% → 50% (+6pp)  
- **Week 3**: 50% → 59% (+9pp)
- **Week 4**: 59% → 66% (+7pp)
- **Week 5**: 66% → 70%+ (+4pp)

### Quality Improvements
- **Service Reliability**: Comprehensive testing of all core services
- **Error Resilience**: Validated error handling across all components
- **Performance Validation**: Confirmed performance targets under realistic loads
- **Integration Confidence**: End-to-end workflows thoroughly tested

### Business Value
- **Production Readiness**: Increased confidence in system reliability
- **Development Velocity**: Faster development with comprehensive test coverage
- **Maintenance Efficiency**: Easier debugging and issue resolution
- **User Experience**: More reliable biomedical research workflows

## Getting Started

### Immediate Next Steps
1. **Create the services testing directory structure**:
   ```bash
   mkdir -p tests/unit/services
   mkdir -p tests/integration/services
   ```

2. **Start with Document Service testing**:
   ```bash
   touch tests/unit/test_document_service.py
   # Begin implementation following the plan above
   ```

3. **Set up coverage monitoring**:
   ```bash
   uv run pytest tests/unit/test_document_service.py --cov=bio_mcp.services --cov-report=term
   ```

4. **Validate coverage improvement**:
   ```bash
   # Track progress against baseline of 38.4%
   uv run pytest tests/unit/ tests/integration/ --cov=bio_mcp --cov-report=term
   ```

This implementation plan provides a clear roadmap to increase Bio-MCP test coverage from 38.4% to 70%+ while maintaining high code quality and focusing on business-critical functionality.