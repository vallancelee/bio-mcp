# RAG Step 7: Testing and Validation

**Objective:** Implement comprehensive testing suite for the complete RAG implementation V2, including unit tests, integration tests, end-to-end validation, and performance benchmarks.

**Success Criteria:**
- 100% test coverage for critical RAG components
- End-to-end workflows validated with real data
- Performance benchmarks meet all requirements
- Quality regression tests prevent degradation
- CI/CD pipeline includes all test categories
- Documentation includes testing guidelines

---

## 1. Test Strategy Overview

### 1.1 Test Pyramid Structure

```
                    E2E Tests (5%)
                  ↙              ↘
            Integration Tests (25%)
           ↙                        ↘
      Unit Tests (70%)
```

**Test Categories:**
1. **Unit Tests**: Individual component validation
2. **Integration Tests**: Service interaction validation  
3. **Contract Tests**: API compliance validation
4. **Performance Tests**: Latency and throughput validation
5. **End-to-End Tests**: Complete workflow validation
6. **Quality Tests**: Search relevance and accuracy validation

### 1.2 Testing Infrastructure
**File:** `tests/conftest.py` (enhanced)

```python
import pytest
import asyncio
import os
from typing import AsyncGenerator, Generator
from testcontainers.postgres import PostgresContainer
from testcontainers.compose import DockerCompose
import weaviate

from bio_mcp.config.config import Config
from bio_mcp.services.embedding_service_v2 import EmbeddingServiceV2
from bio_mcp.services.db_service import DatabaseService
from bio_mcp.services.s3_service import S3Service
from bio_mcp.models.document import Document, Chunk

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def docker_compose_file():
    """Docker compose file for integration tests."""
    return os.path.join(os.path.dirname(__file__), "docker-compose.test.yml")

@pytest.fixture(scope="session")
async def test_infrastructure(docker_compose_file):
    """Start test infrastructure with testcontainers."""
    with DockerCompose(
        context=os.path.dirname(docker_compose_file),
        compose_file_name="docker-compose.test.yml",
        wait=True
    ) as compose:
        # Wait for services to be ready
        await asyncio.sleep(10)
        
        yield {
            "postgres_url": "postgresql://test:test@localhost:5433/test_bio_mcp",
            "weaviate_url": "http://localhost:8081",
            "minio_url": "http://localhost:9001"
        }

@pytest.fixture
async def test_config(test_infrastructure):
    """Test configuration with infrastructure endpoints."""
    config = Config()
    config.database_url = test_infrastructure["postgres_url"]
    config.weaviate_url = test_infrastructure["weaviate_url"]
    config.s3_endpoint_url = test_infrastructure["minio_url"]
    config.weaviate_collection_v2 = "DocumentChunk_v2_test"
    
    return config

@pytest.fixture
async def db_service(test_config) -> AsyncGenerator[DatabaseService, None]:
    """Database service for testing."""
    service = DatabaseService(test_config)
    await service.connect()
    
    # Run migrations
    await service.run_migrations()
    
    yield service
    
    # Cleanup
    await service.disconnect()

@pytest.fixture
async def embedding_service(test_config) -> AsyncGenerator[EmbeddingServiceV2, None]:
    """Embedding service for testing."""
    service = EmbeddingServiceV2(test_config)
    await service.connect()
    
    # Create test collection
    await service._create_test_collection()
    
    yield service
    
    # Cleanup
    await service._cleanup_test_collection()
    await service.disconnect()

@pytest.fixture
def sample_documents() -> List[Document]:
    """Sample documents for testing."""
    return [
        Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Efficacy of Novel Diabetes Treatment in Randomized Controlled Trial",
            text="Background: Diabetes mellitus affects millions worldwide. Methods: We conducted a randomized controlled trial with 500 patients. Results: The novel treatment showed 15% improvement in HbA1c levels (p<0.001). Conclusions: This treatment represents a significant advance.",
            published_at=datetime(2024, 1, 15),
            authors=["Smith, J.", "Johnson, M."],
            identifiers={"doi": "10.1234/diabetes.2024.001"},
            detail={
                "journal": "Diabetes Care",
                "mesh_terms": ["Diabetes Mellitus", "Clinical Trial", "Therapeutics"],
                "abstract_type": "structured"
            }
        ),
        Document(
            uid="pubmed:87654321", 
            source="pubmed",
            source_id="87654321",
            title="Meta-Analysis of Cancer Immunotherapy Outcomes",
            text="Background: Cancer immunotherapy has shown promise across multiple tumor types. Methods: We systematically reviewed 45 clinical trials involving 12,000 patients. Results: Overall survival improved by 25% compared to standard care. Conclusions: Immunotherapy should be considered first-line treatment.",
            published_at=datetime(2023, 6, 20),
            authors=["Davis, R.", "Wilson, K."],
            identifiers={"doi": "10.1234/cancer.2023.045"},
            detail={
                "journal": "Journal of Clinical Oncology", 
                "mesh_terms": ["Immunotherapy", "Meta-Analysis", "Cancer"],
                "abstract_type": "structured"
            }
        ),
        Document(
            uid="pubmed:11111111",
            source="pubmed", 
            source_id="11111111",
            title="Cardiovascular Risk Factors in Modern Population",
            text="Cardiovascular disease remains the leading cause of mortality globally. This observational study examined risk factors in 10,000 participants over 15 years. Major findings include the role of lifestyle interventions in prevention.",
            published_at=datetime(2022, 3, 10),
            authors=["Brown, A."],
            detail={
                "journal": "Circulation",
                "mesh_terms": ["Cardiovascular Disease", "Risk Factors", "Prevention"],
                "abstract_type": "unstructured"
            }
        )
    ]

@pytest.fixture
def golden_queries():
    """Golden queries for quality testing."""
    return [
        {
            "query": "diabetes treatment efficacy randomized trial",
            "expected_top_result": "pubmed:12345678",
            "expected_keywords": ["diabetes", "treatment", "randomized", "efficacy"],
            "min_relevance_score": 0.7
        },
        {
            "query": "cancer immunotherapy meta-analysis survival",
            "expected_top_result": "pubmed:87654321", 
            "expected_keywords": ["cancer", "immunotherapy", "meta-analysis"],
            "min_relevance_score": 0.8
        },
        {
            "query": "cardiovascular disease prevention risk factors",
            "expected_top_result": "pubmed:11111111",
            "expected_keywords": ["cardiovascular", "prevention", "risk"],
            "min_relevance_score": 0.6
        }
    ]
```

---

## 2. Unit Tests

### 2.1 Document and Chunk Model Tests
**File:** `tests/unit/models/test_document_models_comprehensive.py`

```python
import pytest
import uuid
from datetime import datetime
from bio_mcp.models.document import Document, Chunk, MetadataBuilder, CHUNK_UUID_NAMESPACE

class TestDocumentModelValidation:
    """Comprehensive tests for Document model validation."""
    
    def test_document_creation_all_fields(self):
        """Test document creation with all fields populated."""
        doc = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678", 
            title="Test Research Paper",
            text="This is a comprehensive test of the document model with all fields populated.",
            published_at=datetime(2024, 1, 15),
            fetched_at=datetime(2024, 1, 20),
            language="en",
            authors=["Author, A.", "Researcher, B."],
            labels=["diabetes", "clinical-trial"],
            identifiers={"doi": "10.1234/test", "pmcid": "PMC123456"},
            provenance={"s3_raw_uri": "s3://bucket/test.json", "content_hash": "abc123"},
            detail={"journal": "Test Journal", "mesh_terms": ["Test", "Research"]},
            license="CC BY 4.0",
            schema_version=1
        )
        
        assert doc.uid == "pubmed:12345678"
        assert doc.get_searchable_text() == "Test Research Paper This is a comprehensive test of the document model with all fields populated."
        assert len(doc.get_content_hash()) == 64
    
    def test_document_uid_validation_edge_cases(self):
        """Test UID validation with edge cases."""
        
        # Valid edge cases
        Document(uid="a:1", source="a", source_id="1", text="test")
        Document(uid="source123:id456", source="source123", source_id="id456", text="test")
        
        # Invalid cases
        with pytest.raises(ValueError, match="UID must follow format"):
            Document(uid="no_colon", source="test", source_id="123", text="test")
        
        with pytest.raises(ValueError, match="UID must follow format"):
            Document(uid=":empty_source", source="", source_id="123", text="test")
        
        with pytest.raises(ValueError, match="UID must follow format"):
            Document(uid="source:", source="source", source_id="", text="test")
    
    def test_document_source_validation(self):
        """Test source field validation."""
        
        # Valid sources
        Document(uid="test:123", source="test", source_id="123", text="test")
        Document(uid="pubmed:123", source="pubmed", source_id="123", text="test")
        Document(uid="ctgov:123", source="ctgov", source_id="123", text="test")
        
        # Invalid sources
        with pytest.raises(ValueError, match="Source must be alphanumeric"):
            Document(uid="test-bad:123", source="test-bad", source_id="123", text="test")
        
        with pytest.raises(ValueError, match="Source must be alphanumeric"):
            Document(uid="test_bad:123", source="test_bad", source_id="123", text="test")

class TestChunkModelValidation:
    """Comprehensive tests for Chunk model validation."""
    
    def test_chunk_uuid_deterministic(self):
        """Test that chunk UUIDs are deterministic."""
        parent_uid = "pubmed:12345678"
        chunk_id = "s0"
        
        # Generate UUID multiple times
        uuid1 = Chunk.generate_uuid(parent_uid, chunk_id)
        uuid2 = Chunk.generate_uuid(parent_uid, chunk_id)
        uuid3 = str(uuid.uuid5(CHUNK_UUID_NAMESPACE, f"{parent_uid}:{chunk_id}"))
        
        assert uuid1 == uuid2 == uuid3
        assert len(uuid1) == 36  # Standard UUID length
    
    def test_chunk_creation_validation(self):
        """Test chunk creation with validation."""
        parent_uid = "pubmed:12345678"
        chunk_id = "s0"
        expected_uuid = Chunk.generate_uuid(parent_uid, chunk_id)
        
        chunk = Chunk(
            chunk_id=chunk_id,
            uuid=expected_uuid,
            parent_uid=parent_uid,
            source="pubmed",
            chunk_idx=0,
            text="This is a test chunk.",
            title="Test Paper",
            section="Background",
            published_at=datetime(2024, 1, 15),
            tokens=5,
            n_sentences=1,
            meta={"chunker_version": "v1.2.0"}
        )
        
        assert chunk.get_embedding_text() == "This is a test chunk."
        assert "Background" in chunk.get_display_context()
        assert "Test Paper" in chunk.get_display_context()
    
    def test_chunk_id_format_validation(self):
        """Test chunk_id format validation."""
        parent_uid = "test:123"
        
        # Valid chunk IDs
        valid_ids = ["s0", "s1", "s999", "w0", "w1", "w999"]
        for chunk_id in valid_ids:
            uuid_val = Chunk.generate_uuid(parent_uid, chunk_id)
            chunk = Chunk(
                chunk_id=chunk_id,
                uuid=uuid_val,
                parent_uid=parent_uid,
                source="test",
                chunk_idx=0,
                text="test"
            )
            assert chunk.chunk_id == chunk_id
        
        # Invalid chunk IDs
        invalid_ids = ["invalid", "s", "1", "x0", "s-1", "w_0"]
        for chunk_id in invalid_ids:
            with pytest.raises(ValueError, match="chunk_id must follow format"):
                uuid_val = Chunk.generate_uuid(parent_uid, chunk_id)
                Chunk(
                    chunk_id=chunk_id,
                    uuid=uuid_val,
                    parent_uid=parent_uid,
                    source="test",
                    chunk_idx=0,
                    text="test"
                )

class TestMetadataBuilder:
    """Test metadata building utilities."""
    
    def test_metadata_builder_pubmed(self):
        """Test metadata building for PubMed source."""
        metadata = MetadataBuilder.build_chunk_metadata(
            chunker_version="v1.2.0",
            tokenizer="hf:pritamdeka/BioBERT",
            source_specific={
                "mesh_terms": ["Diabetes", "Treatment"],
                "journal": "Diabetes Care",
                "pmcid": "PMC123456"
            },
            source="pubmed"
        )
        
        assert metadata["chunker_version"] == "v1.2.0"
        assert metadata["tokenizer"] == "hf:pritamdeka/BioBERT"
        assert metadata["src"]["pubmed"]["mesh_terms"] == ["Diabetes", "Treatment"]
        assert metadata["src"]["pubmed"]["journal"] == "Diabetes Care"
    
    def test_extract_top_level_fields(self):
        """Test top-level field extraction."""
        doc = Document(
            uid="pubmed:123",
            source="pubmed",
            source_id="123",
            title="Test Document",
            text="Test content",
            published_at=datetime(2024, 6, 15)
        )
        
        fields = MetadataBuilder.extract_top_level_fields(doc)
        
        assert fields["parent_uid"] == "pubmed:123"
        assert fields["source"] == "pubmed"
        assert fields["title"] == "Test Document"
        assert fields["year"] == 2024
        assert fields["published_at"] == datetime(2024, 6, 15)
```

### 2.2 Service Unit Tests
**File:** `tests/unit/services/test_chunking_service.py`

```python
import pytest
from bio_mcp.services.chunking import ChunkingService
from bio_mcp.config.config import Config
from bio_mcp.models.document import Document

class TestChunkingService:
    """Test chunking service functionality."""
    
    @pytest.fixture
    def chunking_service(self):
        config = Config()
        return ChunkingService(config)
    
    @pytest.fixture
    def structured_document(self):
        return Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Test Research Paper",
            text="Background: This study investigates novel treatments. Methods: We conducted a randomized trial with 500 patients. Results: Treatment group showed 20% improvement (p<0.001). Conclusions: The treatment is effective and safe."
        )
    
    @pytest.fixture
    def unstructured_document(self):
        return Document(
            uid="pubmed:87654321",
            source="pubmed", 
            source_id="87654321",
            title="Simple Research",
            text="This is a simple research paper without structured sections. It discusses various topics in a continuous format without clear section breaks."
        )
    
    @pytest.mark.asyncio
    async def test_structured_document_chunking(self, chunking_service, structured_document):
        """Test chunking of structured documents."""
        
        chunks = await chunking_service.chunk_document(structured_document)
        
        assert len(chunks) > 0
        
        # Check chunk properties
        for i, chunk in enumerate(chunks):
            assert chunk.parent_uid == structured_document.uid
            assert chunk.source == structured_document.source
            assert chunk.chunk_idx == i
            assert chunk.title == structured_document.title
            assert len(chunk.uuid) == 36  # Valid UUID
            assert chunk.chunk_id.startswith("s")  # Section chunks
        
        # Check section detection
        sections = [chunk.section for chunk in chunks]
        expected_sections = ["Background", "Methods", "Results", "Conclusions"]
        
        for expected in expected_sections:
            assert any(expected in section for section in sections if section)
    
    @pytest.mark.asyncio
    async def test_unstructured_document_chunking(self, chunking_service, unstructured_document):
        """Test chunking of unstructured documents."""
        
        chunks = await chunking_service.chunk_document(unstructured_document)
        
        assert len(chunks) > 0
        
        # For short unstructured docs, should be single chunk
        if len(unstructured_document.text) < 1000:
            assert len(chunks) == 1
            assert chunks[0].section == "Unstructured"
            assert chunks[0].chunk_id == "w0"
    
    @pytest.mark.asyncio
    async def test_chunk_token_limits(self, chunking_service, structured_document):
        """Test that chunks respect token limits."""
        
        chunks = await chunking_service.chunk_document(structured_document)
        
        for chunk in chunks:
            assert chunk.tokens is not None
            assert chunk.tokens <= 450  # Hard max
            assert chunk.tokens >= 10   # Reasonable minimum
    
    @pytest.mark.asyncio
    async def test_chunk_uuid_stability(self, chunking_service, structured_document):
        """Test that chunk UUIDs are stable across runs."""
        
        chunks1 = await chunking_service.chunk_document(structured_document)
        chunks2 = await chunking_service.chunk_document(structured_document)
        
        assert len(chunks1) == len(chunks2)
        
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.uuid == c2.uuid
            assert c1.chunk_id == c2.chunk_id
```

---

## 3. Integration Tests

### 3.1 End-to-End RAG Workflow
**File:** `tests/integration/test_rag_workflow.py`

```python
import pytest
from bio_mcp.mcp.rag_tools import EnhancedRAGTools
from bio_mcp.services.embedding_service_v2 import EmbeddingServiceV2
from bio_mcp.models.document import Document

@pytest.mark.integration
class TestRAGWorkflow:
    """Test complete RAG workflow integration."""
    
    @pytest.mark.asyncio
    async def test_complete_document_pipeline(
        self, 
        test_config, 
        embedding_service, 
        sample_documents
    ):
        """Test complete pipeline: store documents → search → retrieve."""
        
        # Store sample documents
        stored_uids = []
        for doc in sample_documents:
            chunk_uuids = await embedding_service.store_document_chunks(
                document=doc,
                quality_score=0.8
            )
            assert len(chunk_uuids) > 0
            stored_uids.append(doc.uid)
        
        # Test search functionality
        enhanced_rag = EnhancedRAGTools(test_config)
        
        search_results = await enhanced_rag.search_documents(
            query="diabetes treatment clinical trial",
            limit=10
        )
        
        assert len(search_results) > 0
        
        # Verify search results contain expected document
        result_uids = [result["uid"] for result in search_results]
        assert "pubmed:12345678" in result_uids
        
        # Test document retrieval
        doc_details = await enhanced_rag.get_document_details(
            document_uid="pubmed:12345678",
            include_chunks=True
        )
        
        assert doc_details is not None
        assert doc_details["uid"] == "pubmed:12345678"
        assert "chunks" in doc_details
        assert len(doc_details["chunks"]) > 0
    
    @pytest.mark.asyncio
    async def test_search_filtering(self, test_config, embedding_service, sample_documents):
        """Test search with various filters."""
        
        # Store documents
        for doc in sample_documents:
            await embedding_service.store_document_chunks(doc, quality_score=0.8)
        
        enhanced_rag = EnhancedRAGTools(test_config)
        
        # Test year filtering
        recent_results = await enhanced_rag.search_documents(
            query="treatment",
            year_range=(2024, 2024)  # Only 2024 documents
        )
        
        for result in recent_results:
            assert result.get("year") == 2024
        
        # Test source filtering
        pubmed_results = await enhanced_rag.search_documents(
            query="research",
            source_filter="pubmed"
        )
        
        for result in pubmed_results:
            assert result.get("source") == "pubmed"
        
        # Test quality filtering
        high_quality_results = await enhanced_rag.search_documents(
            query="clinical",
            quality_threshold=0.7
        )
        
        for result in high_quality_results:
            assert result.get("quality_total", 0) >= 0.7
    
    @pytest.mark.asyncio
    async def test_similar_document_search(
        self, 
        test_config, 
        embedding_service, 
        sample_documents
    ):
        """Test semantic similarity search."""
        
        # Store documents
        for doc in sample_documents:
            await embedding_service.store_document_chunks(doc, quality_score=0.8)
        
        enhanced_rag = EnhancedRAGTools(test_config)
        
        # Find documents similar to diabetes paper
        similar_docs = await enhanced_rag.search_by_semantic_similarity(
            reference_document_uid="pubmed:12345678",
            limit=5,
            exclude_self=True
        )
        
        # Should find other documents (exclude self)
        assert len(similar_docs) > 0
        
        # Reference document should not be in results
        similar_uids = [doc["uid"] for doc in similar_docs]
        assert "pubmed:12345678" not in similar_uids
    
    @pytest.mark.asyncio
    async def test_idempotent_storage(
        self, 
        test_config, 
        embedding_service, 
        sample_documents
    ):
        """Test that storing same document multiple times doesn't create duplicates."""
        
        test_doc = sample_documents[0]
        
        # Store document first time
        chunks1 = await embedding_service.store_document_chunks(test_doc)
        
        # Store same document again
        chunks2 = await embedding_service.store_document_chunks(test_doc)
        
        # Should have same chunk UUIDs
        assert chunks1 == chunks2
        
        # Search should not return duplicates
        enhanced_rag = EnhancedRAGTools(test_config)
        results = await enhanced_rag.search_documents(
            query=test_doc.title,
            limit=10
        )
        
        # Count occurrences of our test document
        matching_results = [r for r in results if r["uid"] == test_doc.uid]
        assert len(matching_results) == 1  # Should appear only once
```

### 3.2 Performance Integration Tests
**File:** `tests/integration/test_rag_performance_integration.py`

```python
import pytest
import asyncio
import time
from bio_mcp.mcp.rag_tools import EnhancedRAGTools
from bio_mcp.models.document import Document

@pytest.mark.integration
@pytest.mark.performance
class TestRAGPerformanceIntegration:
    """Integration tests for RAG performance requirements."""
    
    @pytest.mark.asyncio
    async def test_large_dataset_search_performance(
        self, 
        test_config, 
        embedding_service
    ):
        """Test search performance with larger dataset."""
        
        # Create larger test dataset
        documents = []
        for i in range(100):  # 100 documents
            doc = Document(
                uid=f"test:{i:06d}",
                source="test",
                source_id=f"{i:06d}",
                title=f"Research Paper {i}: Biomedical Study",
                text=f"Background: This is research paper {i} about biomedical topics. Methods: We used standard research methodology. Results: Significant findings were observed (p<0.05). Conclusions: This research contributes to the field.",
                published_at=datetime(2024, 1, 1)
            )
            documents.append(doc)
        
        # Store all documents
        start_time = time.time()
        
        for doc in documents:
            await embedding_service.store_document_chunks(doc, quality_score=0.5)
        
        storage_time = time.time() - start_time
        storage_rate = len(documents) / storage_time
        
        print(f"Storage rate: {storage_rate:.1f} documents/second")
        assert storage_rate > 5  # Should store at least 5 docs/second
        
        # Test search performance
        enhanced_rag = EnhancedRAGTools(test_config)
        
        search_queries = [
            "biomedical research methodology",
            "clinical findings results",
            "research paper analysis",
            "significant biomedical study",
            "standard methodology findings"
        ]
        
        search_times = []
        
        for query in search_queries:
            start_time = time.time()
            
            results = await enhanced_rag.search_documents(
                query=query,
                limit=10
            )
            
            search_time = time.time() - start_time
            search_times.append(search_time)
            
            assert len(results) > 0
        
        avg_search_time = sum(search_times) / len(search_times)
        max_search_time = max(search_times)
        
        print(f"Average search time: {avg_search_time*1000:.1f}ms")
        print(f"Max search time: {max_search_time*1000:.1f}ms")
        
        # Performance requirements (relaxed for test environment)
        assert avg_search_time < 0.5  # 500ms average
        assert max_search_time < 1.0  # 1s max
    
    @pytest.mark.asyncio
    async def test_concurrent_search_performance(
        self, 
        test_config, 
        embedding_service, 
        sample_documents
    ):
        """Test concurrent search performance."""
        
        # Store sample documents
        for doc in sample_documents:
            await embedding_service.store_document_chunks(doc, quality_score=0.8)
        
        enhanced_rag = EnhancedRAGTools(test_config)
        
        async def search_task(query_id: int):
            """Individual search task."""
            results = await enhanced_rag.search_documents(
                query=f"research treatment {query_id}",
                limit=5
            )
            return len(results)
        
        # Run concurrent searches
        concurrent_count = 20
        start_time = time.time()
        
        tasks = [search_task(i) for i in range(concurrent_count)]
        results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # All searches should succeed
        assert all(result > 0 for result in results)
        
        # Performance requirement
        throughput = concurrent_count / total_time
        print(f"Concurrent search throughput: {throughput:.1f} searches/second")
        assert throughput > 5  # At least 5 concurrent searches/second
    
    @pytest.mark.asyncio
    async def test_memory_usage_stability(
        self, 
        test_config, 
        embedding_service
    ):
        """Test that memory usage remains stable during operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform many operations
        for i in range(50):
            doc = Document(
                uid=f"memory_test:{i}",
                source="test",
                source_id=str(i),
                title=f"Memory Test Document {i}",
                text=f"This is memory test document {i} with some content to process.",
                published_at=datetime(2024, 1, 1)
            )
            
            await embedding_service.store_document_chunks(doc)
            
            # Periodically check memory
            if i % 10 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - initial_memory
                
                print(f"Memory after {i} operations: {current_memory:.1f}MB (+{memory_increase:.1f}MB)")
                
                # Memory should not grow excessively
                assert memory_increase < 500  # Less than 500MB increase
```

---

## 4. Quality and Regression Tests

### 4.1 Search Quality Tests
**File:** `tests/quality/test_search_quality.py`

```python
import pytest
from bio_mcp.mcp.rag_tools import EnhancedRAGTools

@pytest.mark.quality
class TestSearchQuality:
    """Test search quality and relevance."""
    
    @pytest.mark.asyncio
    async def test_golden_query_results(
        self, 
        test_config, 
        embedding_service, 
        sample_documents, 
        golden_queries
    ):
        """Test that golden queries return expected results."""
        
        # Store sample documents
        for doc in sample_documents:
            await embedding_service.store_document_chunks(doc, quality_score=0.8)
        
        enhanced_rag = EnhancedRAGTools(test_config)
        
        for golden_query in golden_queries:
            query = golden_query["query"]
            expected_top_result = golden_query["expected_top_result"]
            min_relevance = golden_query["min_relevance_score"]
            
            results = await enhanced_rag.search_documents(
                query=query,
                limit=10
            )
            
            assert len(results) > 0, f"No results for query: {query}"
            
            # Check that expected document is in top results
            top_uids = [result["uid"] for result in results[:3]]
            assert expected_top_result in top_uids, f"Expected {expected_top_result} in top 3 for query: {query}"
            
            # Check relevance scores
            top_result = results[0]
            assert top_result["final_score"] >= min_relevance, f"Top result score {top_result['final_score']} below minimum {min_relevance} for query: {query}"
    
    @pytest.mark.asyncio
    async def test_section_relevance_boosting(
        self, 
        test_config, 
        embedding_service, 
        sample_documents
    ):
        """Test that Results and Conclusions sections get appropriate boosting."""
        
        # Store documents
        for doc in sample_documents:
            await embedding_service.store_document_chunks(doc, quality_score=0.8)
        
        enhanced_rag = EnhancedRAGTools(test_config)
        
        # Query that should find Results sections
        results = await enhanced_rag.search_documents(
            query="treatment improvement results outcome",
            limit=10
        )
        
        # Check that Results sections are well-represented
        sections_found = []
        for result in results:
            sections_found.extend(result.get("sections_found", []))
        
        assert "Results" in sections_found, "Results section should be found for outcome query"
        
        # Check for section boost in scoring
        for result in results[:3]:  # Top 3 results
            if "Results" in result.get("sections_found", []):
                assert result.get("final_score", 0) > 0.5, "Results section should have boosted score"
    
    @pytest.mark.asyncio
    async def test_clinical_content_boosting(
        self, 
        test_config, 
        embedding_service, 
        sample_documents
    ):
        """Test that clinical content gets boosted for clinical queries."""
        
        # Store documents
        for doc in sample_documents:
            await embedding_service.store_document_chunks(doc, quality_score=0.8)
        
        enhanced_rag = EnhancedRAGTools(test_config)
        
        # Clinical query
        results = await enhanced_rag.search_documents(
            query="randomized controlled trial clinical efficacy",
            limit=10,
            boost_clinical=True
        )
        
        # Top results should have clinical boost
        for result in results[:2]:
            clinical_boost = result.get("clinical_boost", 0)
            if "randomized" in result.get("abstract", "").lower():
                assert clinical_boost > 0, "Clinical content should receive boost for clinical query"
    
    @pytest.mark.asyncio
    async def test_abstract_reconstruction_quality(
        self, 
        test_config, 
        embedding_service, 
        sample_documents
    ):
        """Test quality of abstract reconstruction."""
        
        # Store documents
        for doc in sample_documents:
            await embedding_service.store_document_chunks(doc, quality_score=0.8)
        
        enhanced_rag = EnhancedRAGTools(test_config)
        
        results = await enhanced_rag.search_documents(
            query="research methodology",
            limit=5
        )
        
        for result in results:
            title = result.get("title", "")
            abstract = result.get("abstract", "")
            
            if title and abstract:
                # Title should not be duplicated in abstract
                assert not abstract.startswith(title), f"Title '{title}' duplicated in abstract"
                
                # Abstract should be coherent
                assert len(abstract.split()) >= 10, "Abstract should have sufficient content"
                assert not abstract.startswith("[Section]"), "Section headers should be cleaned"
                
                # Abstract should end properly
                assert abstract.strip(), "Abstract should not be empty or just whitespace"
```

### 4.2 Regression Tests
**File:** `tests/regression/test_rag_regression.py`

```python
import pytest
import json
import os
from bio_mcp.mcp.rag_tools import EnhancedRAGTools

@pytest.mark.regression
class TestRAGRegression:
    """Regression tests to prevent quality degradation."""
    
    @pytest.fixture
    def baseline_results_file(self):
        """Path to baseline results file."""
        return os.path.join(os.path.dirname(__file__), "baseline_results.json")
    
    @pytest.mark.asyncio
    async def test_search_quality_regression(
        self, 
        test_config, 
        embedding_service, 
        sample_documents, 
        baseline_results_file
    ):
        """Test that search quality doesn't regress from baseline."""
        
        # Store documents
        for doc in sample_documents:
            await embedding_service.store_document_chunks(doc, quality_score=0.8)
        
        enhanced_rag = EnhancedRAGTools(test_config)
        
        # Standard test queries
        test_queries = [
            "diabetes treatment efficacy",
            "cancer immunotherapy outcomes", 
            "cardiovascular risk prevention"
        ]
        
        current_results = {}
        
        for query in test_queries:
            results = await enhanced_rag.search_documents(
                query=query,
                limit=5
            )
            
            # Extract key metrics
            current_results[query] = {
                "top_score": results[0]["final_score"] if results else 0,
                "avg_score": sum(r["final_score"] for r in results) / len(results) if results else 0,
                "result_count": len(results),
                "top_uid": results[0]["uid"] if results else None
            }
        
        # Load baseline results if they exist
        if os.path.exists(baseline_results_file):
            with open(baseline_results_file, 'r') as f:
                baseline_results = json.load(f)
            
            # Compare against baseline
            for query in test_queries:
                if query in baseline_results:
                    baseline = baseline_results[query]
                    current = current_results[query]
                    
                    # Score should not degrade significantly (allow 5% tolerance)
                    score_ratio = current["avg_score"] / baseline["avg_score"] if baseline["avg_score"] > 0 else 1
                    assert score_ratio >= 0.95, f"Score regression for query '{query}': {score_ratio:.3f}"
                    
                    # Should return similar number of results
                    assert abs(current["result_count"] - baseline["result_count"]) <= 1
        
        else:
            # Save current results as new baseline
            with open(baseline_results_file, 'w') as f:
                json.dump(current_results, f, indent=2)
            
            pytest.skip("Created new baseline results file")
    
    @pytest.mark.asyncio
    async def test_performance_regression(
        self, 
        test_config, 
        embedding_service, 
        sample_documents
    ):
        """Test that performance doesn't regress."""
        import time
        
        # Store documents
        for doc in sample_documents:
            await embedding_service.store_document_chunks(doc, quality_score=0.8)
        
        enhanced_rag = EnhancedRAGTools(test_config)
        
        # Measure search performance
        start_time = time.time()
        
        results = await enhanced_rag.search_documents(
            query="clinical research methodology",
            limit=10
        )
        
        search_time = time.time() - start_time
        
        # Performance regression thresholds
        assert search_time < 1.0, f"Search time regression: {search_time:.3f}s exceeds 1.0s threshold"
        assert len(results) > 0, "Should return results"
```

---

## 5. CI/CD Integration

### 5.1 GitHub Actions Workflow
**File:** `.github/workflows/test-rag.yml`

```yaml
name: RAG Testing Suite

on:
  push:
    branches: [ main, develop ]
    paths:
      - 'src/bio_mcp/**'
      - 'tests/**'
      - 'pyproject.toml'
  pull_request:
    branches: [ main ]
    paths:
      - 'src/bio_mcp/**'
      - 'tests/**'

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install UV
      run: curl -LsSf https://astral.sh/uv/install.sh | sh
    
    - name: Install dependencies
      run: uv sync --dev
    
    - name: Run unit tests
      run: uv run pytest tests/unit/ -v --cov=src/bio_mcp --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  integration-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_USER: test
          POSTGRES_DB: test_bio_mcp
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5433:5432
      
      weaviate:
        image: semitechnologies/weaviate:1.25.0
        env:
          QUERY_DEFAULTS_LIMIT: 25
          DEFAULT_VECTORIZER_MODULE: 'none'
          ENABLE_MODULES: ''
          CLUSTER_HOSTNAME: 'node1'
        ports:
          - 8081:8080
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install UV
      run: curl -LsSf https://astral.sh/uv/install.sh | sh
    
    - name: Install dependencies
      run: uv sync --dev
    
    - name: Wait for services
      run: |
        sleep 30
        curl -f http://localhost:8081/v1/.well-known/ready
    
    - name: Run integration tests
      run: uv run pytest tests/integration/ -v --timeout=300
      env:
        BIO_MCP_DATABASE_URL: postgresql://test:test@localhost:5433/test_bio_mcp
        BIO_MCP_WEAVIATE_URL: http://localhost:8081

  quality-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install UV
      run: curl -LsSf https://astral.sh/uv/install.sh | sh
    
    - name: Install dependencies
      run: uv sync --dev
    
    - name: Run quality tests
      run: uv run pytest tests/quality/ -v --timeout=600
    
    - name: Run regression tests
      run: uv run pytest tests/regression/ -v --timeout=300

  performance-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install UV
      run: curl -LsSf https://astral.sh/uv/install.sh | sh
    
    - name: Install dependencies
      run: uv sync --dev
    
    - name: Run performance tests
      run: uv run pytest tests/performance/ -v --timeout=900 --benchmark-only
    
    - name: Upload performance results
      uses: actions/upload-artifact@v3
      with:
        name: performance-results
        path: benchmark-results.json
```

### 5.2 Test Configuration
**File:** `tests/docker-compose.test.yml`

```yaml
version: '3.8'

services:
  postgres-test:
    image: postgres:15
    environment:
      POSTGRES_DB: test_bio_mcp
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test"]
      interval: 10s
      timeout: 5s
      retries: 5

  weaviate-test:
    image: semitechnologies/weaviate:1.25.0
    ports:
      - "8081:8080"
    environment:
      QUERY_DEFAULTS_LIMIT: 25
      DEFAULT_VECTORIZER_MODULE: 'none'
      ENABLE_MODULES: 'text2vec-transformers'
      CLUSTER_HOSTNAME: 'node1'
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/v1/.well-known/ready"]
      interval: 10s
      timeout: 5s
      retries: 10

  minio-test:
    image: minio/minio:latest
    ports:
      - "9001:9000"
      - "9091:9001"
    environment:
      MINIO_ACCESS_KEY: testkey
      MINIO_SECRET_KEY: testsecret
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
```

---

## 6. Success Validation

### 6.1 Comprehensive Checklist
- [ ] **Unit Tests (70% of test suite)**
  - [ ] Document and Chunk model validation (100% coverage)
  - [ ] Chunking service functionality (100% coverage)
  - [ ] Embedding service core methods (95% coverage)
  - [ ] RAG tools individual functions (95% coverage)
  - [ ] Query processing and result formatting (100% coverage)

- [ ] **Integration Tests (25% of test suite)**
  - [ ] Complete document pipeline (store → search → retrieve)
  - [ ] Search filtering and boosting mechanisms
  - [ ] Idempotent storage operations
  - [ ] Service interaction workflows
  - [ ] Performance with realistic datasets

- [ ] **Quality Tests (Quality Assurance)**
  - [ ] Golden query result validation
  - [ ] Section and clinical boosting effectiveness
  - [ ] Abstract reconstruction quality
  - [ ] Search relevance meets minimum thresholds
  - [ ] Regression prevention mechanisms

- [ ] **Performance Tests**
  - [ ] Search latency <200ms average (test environment)
  - [ ] Concurrent search throughput >5 searches/second
  - [ ] Memory usage stability under load
  - [ ] Large dataset handling (100+ documents)

- [ ] **CI/CD Integration**
  - [ ] Automated test execution on PR/push
  - [ ] Test result reporting and coverage tracking
  - [ ] Performance benchmark tracking
  - [ ] Quality regression detection

### 6.2 Test Coverage Requirements
- **Overall Coverage**: >90%
- **Critical Components**: 100% (models, core services)
- **Integration Workflows**: 85%
- **Performance Validation**: All key metrics measured

### 6.3 Quality Gates
1. **All unit tests pass** (zero tolerance for failures)
2. **Integration tests pass** (critical workflows verified)
3. **Performance benchmarks met** (latency and throughput)
4. **Quality regression tests pass** (no degradation from baseline)
5. **Coverage thresholds met** (>90% overall, 100% critical)

---

## Next Steps

After completing this testing implementation:

1. **Execute Full Test Suite**: Run all test categories to establish baseline
2. **Performance Benchmarking**: Establish performance baselines for monitoring
3. **Quality Metrics Collection**: Gather search quality metrics for ongoing optimization
4. **Documentation Update**: Document testing procedures and quality gates
5. **Production Deployment**: Deploy with confidence based on comprehensive testing

**Estimated Time:** 3-4 days
**Dependencies:** All previous RAG steps (1-6)
**Risk Level:** Low (comprehensive validation reduces deployment risk)

**Final Implementation Status**: With completion of this step, the RAG Implementation V2 will be fully validated and ready for production deployment with:
- Robust multi-source document and chunk models
- Advanced section-aware chunking with deterministic IDs
- BioBERT-powered embedding with quality boosting
- Comprehensive data re-ingestion capabilities
- Enhanced search with clinical and recency boosting
- Complete testing coverage ensuring quality and performance