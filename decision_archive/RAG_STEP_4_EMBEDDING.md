# RAG Step 4: BioBERT Embedding Pipeline

**Objective:** Integrate BioBERT embedding model with deterministic chunk storage, metadata propagation, and idempotent upserts using the new DocumentChunk_v2 collection.

**Success Criteria:**
- BioBERT model properly configured in Weaviate
- Deterministic UUIDs enable idempotent chunk storage
- Complete metadata propagation from Document to Chunk
- Tokenizer parity between chunking and embedding
- Performance meets requirements (>100 chunks/sec)

---

## 1. BioBERT Model Integration

### 1.1 Update Weaviate Configuration
**File:** `src/bio_mcp/config/config.py`

```python
import os
from typing import Optional

class Config:
    # ... existing config ...
    
    # BioBERT Embedding Configuration
    biobert_model_name: str = os.getenv(
        "BIO_MCP_EMBED_MODEL", 
        "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
    )
    biobert_inference_api: Optional[str] = os.getenv("BIO_MCP_HUGGINGFACE_API_URL")
    biobert_api_key: Optional[str] = os.getenv("HUGGINGFACE_API_KEY")
    biobert_max_tokens: int = int(os.getenv("BIO_MCP_EMBED_MAX_TOKENS", "512"))
    
    # Tokenizer Configuration (must match embedding model)
    chunker_tokenizer: str = os.getenv(
        "BIO_MCP_CHUNKER_TOKENIZER", 
        "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
    )
    chunker_version: str = os.getenv("BIO_MCP_CHUNKER_VERSION", "v1.2.0")
    
    # Collection Configuration
    weaviate_collection_v2: str = os.getenv("BIO_MCP_WEAVIATE_COLLECTION_V2", "DocumentChunk_v2")
```

### 1.2 Enhanced Embedding Service
**File:** `src/bio_mcp/services/embedding_service_v2.py`

```python
from __future__ import annotations
import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.query import Filter
from transformers import AutoTokenizer

from bio_mcp.config.config import Config
from bio_mcp.models.document import Document, Chunk
from bio_mcp.services.chunking import ChunkingService

logger = logging.getLogger(__name__)

class EmbeddingServiceV2:
    """Enhanced embedding service for BioBERT integration with DocumentChunk_v2."""
    
    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[weaviate.WeaviateClient] = None
        self.chunking_service = ChunkingService(config)
        self.tokenizer = None
        self._initialize_tokenizer()
    
    def _initialize_tokenizer(self) -> None:
        """Initialize tokenizer to match embedding model."""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.biobert_model_name,
                trust_remote_code=False
            )
            logger.info(f"Initialized tokenizer: {self.config.biobert_model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize tokenizer: {e}")
            # Fallback to simple whitespace tokenizer
            self.tokenizer = None
    
    async def connect(self) -> None:
        """Connect to Weaviate with proper error handling."""
        try:
            if self.config.biobert_api_key:
                # Use Hugging Face API
                self.client = weaviate.connect_to_local(
                    host=self.config.weaviate_url.replace("http://", "").replace("https://", ""),
                    headers={"X-HuggingFace-Api-Key": self.config.biobert_api_key}
                )
            else:
                # Use local Weaviate
                self.client = weaviate.connect_to_local(
                    host=self.config.weaviate_url.replace("http://", "").replace("https://", "")
                )
            
            logger.info("Connected to Weaviate successfully")
            
            # Verify collection exists
            if not self.client.collections.exists(self.config.weaviate_collection_v2):
                raise RuntimeError(f"Collection {self.config.weaviate_collection_v2} does not exist")
                
        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Weaviate."""
        if self.client:
            self.client.close()
            self.client = None
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens using the same tokenizer as the embedding model."""
        if self.tokenizer:
            try:
                tokens = self.tokenizer.encode(text, add_special_tokens=True)
                return len(tokens)
            except Exception as e:
                logger.warning(f"Tokenizer failed, using fallback: {e}")
        
        # Fallback: rough approximation
        return len(text.split())
    
    def _build_chunk_metadata(
        self, 
        document: Document, 
        chunk_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build complete metadata for chunk storage."""
        # Start with chunking metadata
        meta = {
            "chunker_version": self.config.chunker_version,
            "tokenizer": self.config.chunker_tokenizer,
            **chunk_metadata
        }
        
        # Add source-specific metadata
        if document.source == "pubmed":
            meta["src"] = {
                "pubmed": {
                    **document.detail,
                    "identifiers": document.identifiers,
                    "authors": document.authors or [],
                    "provenance": document.provenance
                }
            }
        else:
            # Generic source handling
            meta["src"] = {
                document.source: {
                    **document.detail,
                    "identifiers": document.identifiers,
                    "authors": document.authors or [],
                    "provenance": document.provenance
                }
            }
        
        return meta
    
    async def store_document_chunks(
        self, 
        document: Document,
        quality_score: Optional[float] = None
    ) -> List[str]:
        """
        Chunk document and store in Weaviate with deterministic UUIDs.
        Returns list of chunk UUIDs for tracking.
        """
        if not self.client:
            await self.connect()
        
        try:
            # Generate chunks
            chunks = await self.chunking_service.chunk_document(document)
            
            if not chunks:
                logger.warning(f"No chunks generated for document {document.uid}")
                return []
            
            collection = self.client.collections.get(self.config.weaviate_collection_v2)
            chunk_uuids = []
            
            for chunk in chunks:
                # Validate token count using our tokenizer
                actual_tokens = self._count_tokens(chunk.text)
                if chunk.tokens != actual_tokens:
                    logger.debug(f"Token count mismatch for {chunk.uuid}: {chunk.tokens} vs {actual_tokens}")
                    chunk.tokens = actual_tokens
                
                # Build complete metadata
                chunk.meta = self._build_chunk_metadata(document, chunk.meta)
                
                # Prepare properties for Weaviate
                properties = {
                    "parent_uid": chunk.parent_uid,
                    "source": chunk.source,
                    "section": chunk.section or "Unstructured", 
                    "title": chunk.title or "",
                    "text": chunk.text,
                    "published_at": document.published_at.isoformat() if document.published_at else None,
                    "year": document.published_at.year if document.published_at else None,
                    "tokens": chunk.tokens,
                    "n_sentences": chunk.n_sentences,
                    "quality_total": quality_score or 0.0,
                    "meta": chunk.meta
                }
                
                # Remove None values
                properties = {k: v for k, v in properties.items() if v is not None}
                
                # Insert with deterministic UUID (idempotent)
                try:
                    collection.data.insert(
                        uuid=chunk.uuid,
                        properties=properties
                    )
                    chunk_uuids.append(chunk.uuid)
                    logger.debug(f"Stored chunk {chunk.uuid} for document {document.uid}")
                    
                except Exception as e:
                    logger.error(f"Failed to store chunk {chunk.uuid}: {e}")
                    # Continue with other chunks
            
            logger.info(f"Stored {len(chunk_uuids)} chunks for document {document.uid}")
            return chunk_uuids
            
        except Exception as e:
            logger.error(f"Failed to store document chunks for {document.uid}: {e}")
            raise
    
    async def search_chunks(
        self,
        query: str,
        limit: int = 10,
        source_filter: Optional[str] = None,
        year_filter: Optional[tuple[int, int]] = None,
        section_filter: Optional[List[str]] = None,
        quality_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search chunks with filtering and quality boosting.
        """
        if not self.client:
            await self.connect()
        
        try:
            collection = self.client.collections.get(self.config.weaviate_collection_v2)
            
            # Build filter conditions
            where_conditions = []
            
            if source_filter:
                where_conditions.append(
                    Filter.by_property("source").equal(source_filter)
                )
            
            if year_filter:
                start_year, end_year = year_filter
                where_conditions.append(
                    Filter.by_property("year").greater_or_equal(start_year)
                )
                where_conditions.append(
                    Filter.by_property("year").less_or_equal(end_year)
                )
            
            if section_filter:
                section_conditions = [
                    Filter.by_property("section").equal(section)
                    for section in section_filter
                ]
                if len(section_conditions) == 1:
                    where_conditions.append(section_conditions[0])
                else:
                    where_conditions.append(Filter.any_of(section_conditions))
            
            if quality_threshold:
                where_conditions.append(
                    Filter.by_property("quality_total").greater_or_equal(quality_threshold)
                )
            
            # Combine conditions
            where_filter = None
            if where_conditions:
                if len(where_conditions) == 1:
                    where_filter = where_conditions[0]
                else:
                    where_filter = Filter.all_of(where_conditions)
            
            # Execute hybrid search
            response = collection.query.hybrid(
                query=query,
                limit=limit,
                where=where_filter,
                return_metadata=["score", "distance"]
            )
            
            # Process results with quality boosting
            results = []
            for item in response.objects:
                # Apply section boost
                section_boost = 0.0
                section = item.properties.get("section", "")
                if section == "Results":
                    section_boost = 0.1
                elif section == "Conclusions":
                    section_boost = 0.05
                
                # Apply quality boost
                quality_total = item.properties.get("quality_total", 0.0)
                quality_boost = quality_total / 10.0  # Scale 0-1 quality to 0-0.1 boost
                
                # Calculate final score
                base_score = item.metadata.score or 0.0
                final_score = base_score * (1 + section_boost + quality_boost)
                
                result = {
                    "uuid": str(item.uuid),
                    "parent_uid": item.properties.get("parent_uid"),
                    "source": item.properties.get("source"),
                    "title": item.properties.get("title"),
                    "text": item.properties.get("text"),
                    "section": item.properties.get("section"),
                    "published_at": item.properties.get("published_at"),
                    "year": item.properties.get("year"),
                    "tokens": item.properties.get("tokens"),
                    "quality_total": quality_total,
                    "score": final_score,
                    "base_score": base_score,
                    "section_boost": section_boost,
                    "quality_boost": quality_boost,
                    "meta": item.properties.get("meta", {})
                }
                results.append(result)
            
            # Re-sort by final score
            results.sort(key=lambda x: x["score"], reverse=True)
            
            logger.info(f"Found {len(results)} chunks for query: '{query[:50]}...'")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search chunks: {e}")
            raise
    
    async def get_chunk_by_uuid(self, chunk_uuid: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific chunk by UUID."""
        if not self.client:
            await self.connect()
        
        try:
            collection = self.client.collections.get(self.config.weaviate_collection_v2)
            
            response = collection.query.fetch_object_by_id(chunk_uuid)
            
            if response:
                return {
                    "uuid": str(response.uuid),
                    "parent_uid": response.properties.get("parent_uid"),
                    "source": response.properties.get("source"),
                    "title": response.properties.get("title"),
                    "text": response.properties.get("text"),
                    "section": response.properties.get("section"),
                    "published_at": response.properties.get("published_at"),
                    "year": response.properties.get("year"),
                    "tokens": response.properties.get("tokens"),
                    "quality_total": response.properties.get("quality_total"),
                    "meta": response.properties.get("meta", {})
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get chunk {chunk_uuid}: {e}")
            return None
    
    async def delete_document_chunks(self, parent_uid: str) -> int:
        """Delete all chunks for a document. Returns count of deleted chunks."""
        if not self.client:
            await self.connect()
        
        try:
            collection = self.client.collections.get(self.config.weaviate_collection_v2)
            
            # Find all chunks for this document
            response = collection.query.fetch_objects(
                where=Filter.by_property("parent_uid").equal(parent_uid),
                limit=1000  # Adjust based on max chunks per document
            )
            
            chunk_count = len(response.objects)
            
            if chunk_count > 0:
                # Delete by filter
                collection.data.delete_many(
                    where=Filter.by_property("parent_uid").equal(parent_uid)
                )
                logger.info(f"Deleted {chunk_count} chunks for document {parent_uid}")
            
            return chunk_count
            
        except Exception as e:
            logger.error(f"Failed to delete chunks for document {parent_uid}: {e}")
            raise
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics for monitoring."""
        if not self.client:
            await self.connect()
        
        try:
            collection = self.client.collections.get(self.config.weaviate_collection_v2)
            
            # Get total count
            aggregate_response = collection.aggregate.over_all(total_count=True)
            total_count = aggregate_response.total_count
            
            # Get source breakdown
            source_response = collection.aggregate.over_all(
                group_by="source"
            )
            
            source_counts = {}
            for group in source_response.groups:
                source = group.grouped_by["source"]
                count = group.total_count
                source_counts[source] = count
            
            return {
                "total_chunks": total_count,
                "source_breakdown": source_counts,
                "collection_name": self.config.weaviate_collection_v2,
                "model_name": self.config.biobert_model_name
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}
```

---

## 2. Service Integration

### 2.1 Update Main Services
**File:** `src/bio_mcp/services/services.py`

```python
from bio_mcp.services.embedding_service_v2 import EmbeddingServiceV2

class Services:
    def __init__(self, config: Config):
        # ... existing services ...
        self.embedding_v2 = EmbeddingServiceV2(config)
    
    async def start(self) -> None:
        """Start all services."""
        # ... existing startup ...
        await self.embedding_v2.connect()
    
    async def stop(self) -> None:
        """Stop all services."""
        # ... existing shutdown ...
        await self.embedding_v2.disconnect()
```

### 2.2 Update PubMed Pipeline
**File:** `src/bio_mcp/sources/pubmed/pipeline.py`

```python
from bio_mcp.services.embedding_service_v2 import EmbeddingServiceV2
from bio_mcp.models.document import Document

class PubMedPipeline:
    def __init__(self, services: Services):
        self.services = services
        self.embedding_v2 = services.embedding_v2
    
    async def process_document(
        self, 
        normalized_doc: Dict[str, Any],
        quality_score: Optional[float] = None
    ) -> str:
        """Process a normalized PubMed document through the embedding pipeline."""
        
        # Convert to Document model
        document = Document(
            uid=f"pubmed:{normalized_doc['pmid']}",
            source="pubmed",
            source_id=str(normalized_doc['pmid']),
            title=normalized_doc.get('title'),
            text=normalized_doc.get('abstract', ''),
            published_at=normalized_doc.get('published_at'),
            fetched_at=normalized_doc.get('fetched_at'),
            language=normalized_doc.get('language'),
            authors=normalized_doc.get('authors', []),
            identifiers=normalized_doc.get('identifiers', {}),
            provenance=normalized_doc.get('provenance', {}),
            detail=normalized_doc.get('detail', {})
        )
        
        # Store chunks with quality score
        chunk_uuids = await self.embedding_v2.store_document_chunks(
            document=document,
            quality_score=quality_score
        )
        
        logger.info(f"Processed document {document.uid}: {len(chunk_uuids)} chunks")
        return document.uid
```

---

## 3. Configuration Updates

### 3.1 Environment Variables
**File:** `.env.example`

```bash
# BioBERT Embedding Configuration
BIO_MCP_EMBED_MODEL=pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb
BIO_MCP_HUGGINGFACE_API_URL=https://api-inference.huggingface.co/models/pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb
HUGGINGFACE_API_KEY=your_hf_api_key_here
BIO_MCP_EMBED_MAX_TOKENS=512

# Chunking Configuration (must match embedding model)
BIO_MCP_CHUNKER_TOKENIZER=pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb
BIO_MCP_CHUNKER_VERSION=v1.2.0

# Weaviate V2 Configuration
BIO_MCP_WEAVIATE_COLLECTION_V2=DocumentChunk_v2
```

### 3.2 Docker Configuration
**File:** `docker-compose.yml` (additions)

```yaml
services:
  # ... existing services ...
  
  weaviate:
    environment:
      # ... existing environment ...
      ENABLE_MODULES: 'text2vec-huggingface'
      HUGGINGFACE_APIKEY: '${HUGGINGFACE_API_KEY:-}'
      DEFAULT_VECTORIZER_MODULE: 'text2vec-huggingface'
```

---

## 4. Testing Implementation

### 4.1 Unit Tests
**File:** `tests/unit/services/test_embedding_service_v2.py`

```python
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from bio_mcp.services.embedding_service_v2 import EmbeddingServiceV2
from bio_mcp.models.document import Document
from bio_mcp.config.config import Config

class TestEmbeddingServiceV2:
    """Test BioBERT embedding service."""
    
    @pytest.fixture
    def config(self):
        return Config(
            biobert_model_name="pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
            weaviate_collection_v2="DocumentChunk_v2_test",
            chunker_version="v1.2.0"
        )
    
    @pytest.fixture
    def sample_document(self):
        return Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Test Biomedical Paper",
            text="Background: This study investigates... Methods: We conducted... Results: We found significant improvements (p<0.001).",
            published_at=datetime(2024, 1, 15),
            authors=["Smith, J.", "Doe, J."],
            identifiers={"doi": "10.1234/test"},
            detail={"journal": "Nature Medicine", "mesh_terms": ["test", "biomedical"]}
        )
    
    def test_token_counting(self, config):
        """Test token counting with BioBERT tokenizer."""
        service = EmbeddingServiceV2(config)
        
        text = "This is a test sentence with biomedical terms."
        token_count = service._count_tokens(text)
        
        assert isinstance(token_count, int)
        assert token_count > 0
        # Should be more accurate than simple word splitting
        assert token_count != len(text.split())
    
    def test_metadata_building(self, config, sample_document):
        """Test metadata building for chunks."""
        service = EmbeddingServiceV2(config)
        
        chunk_metadata = {
            "section": "Results",
            "n_sentences": 2
        }
        
        meta = service._build_chunk_metadata(sample_document, chunk_metadata)
        
        assert meta["chunker_version"] == "v1.2.0"
        assert meta["tokenizer"] == config.chunker_tokenizer
        assert meta["section"] == "Results"
        assert meta["src"]["pubmed"]["journal"] == "Nature Medicine"
        assert meta["src"]["pubmed"]["mesh_terms"] == ["test", "biomedical"]
    
    @pytest.mark.asyncio
    async def test_store_document_chunks_mock(self, config, sample_document):
        """Test document chunk storage with mocked dependencies."""
        service = EmbeddingServiceV2(config)
        
        # Mock chunking service
        service.chunking_service = Mock()
        service.chunking_service.chunk_document = AsyncMock(return_value=[
            Mock(
                uuid="chunk-uuid-1",
                parent_uid="pubmed:12345678",
                source="pubmed",
                text="Background: This study investigates...",
                section="Background",
                tokens=10,
                n_sentences=1,
                meta={}
            )
        ])
        
        # Mock Weaviate client
        mock_collection = Mock()
        mock_collection.data.insert = Mock()
        
        service.client = Mock()
        service.client.collections.get.return_value = mock_collection
        
        # Test storage
        chunk_uuids = await service.store_document_chunks(
            document=sample_document,
            quality_score=0.8
        )
        
        assert len(chunk_uuids) == 1
        assert chunk_uuids[0] == "chunk-uuid-1"
        
        # Verify insert was called with correct properties
        mock_collection.data.insert.assert_called_once()
        call_args = mock_collection.data.insert.call_args
        
        assert call_args[1]['uuid'] == "chunk-uuid-1"
        properties = call_args[1]['properties']
        assert properties['parent_uid'] == "pubmed:12345678"
        assert properties['source'] == "pubmed"
        assert properties['quality_total'] == 0.8
        assert 'meta' in properties
```

### 4.2 Integration Tests
**File:** `tests/integration/services/test_embedding_integration.py`

```python
import pytest
from datetime import datetime

from bio_mcp.services.embedding_service_v2 import EmbeddingServiceV2
from bio_mcp.models.document import Document
from bio_mcp.config.config import Config

@pytest.mark.integration
class TestEmbeddingIntegration:
    """Integration tests for embedding service with real Weaviate."""
    
    @pytest.fixture
    def config(self):
        return Config(
            weaviate_url="http://localhost:8080",
            weaviate_collection_v2="DocumentChunk_v2_test",
            biobert_model_name="pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
        )
    
    @pytest.fixture
    def sample_document(self):
        return Document(
            uid="pubmed:99999999",
            source="pubmed", 
            source_id="99999999",
            title="Integration Test Document",
            text="Background: This is a test abstract for integration testing. Methods: We used automated testing frameworks. Results: All tests passed successfully (p<0.001). Conclusions: The system works as expected.",
            published_at=datetime(2024, 1, 15),
            authors=["Test, A."],
            detail={"journal": "Test Journal", "mesh_terms": ["testing", "integration"]}
        )
    
    @pytest.mark.asyncio
    async def test_full_embedding_pipeline(self, config, sample_document, weaviate_setup):
        """Test complete embedding pipeline with real Weaviate."""
        service = EmbeddingServiceV2(config)
        
        try:
            await service.connect()
            
            # Store document chunks
            chunk_uuids = await service.store_document_chunks(
                document=sample_document,
                quality_score=0.9
            )
            
            assert len(chunk_uuids) > 0
            
            # Verify chunks are searchable
            results = await service.search_chunks(
                query="integration testing",
                limit=10
            )
            
            assert len(results) > 0
            
            # Verify we can retrieve specific chunk
            first_chunk = await service.get_chunk_by_uuid(chunk_uuids[0])
            assert first_chunk is not None
            assert first_chunk["parent_uid"] == sample_document.uid
            
            # Verify quality boosting works
            assert first_chunk["quality_total"] == 0.9
            
            # Test deletion
            deleted_count = await service.delete_document_chunks(sample_document.uid)
            assert deleted_count == len(chunk_uuids)
            
        finally:
            await service.disconnect()
    
    @pytest.mark.asyncio
    async def test_idempotent_storage(self, config, sample_document, weaviate_setup):
        """Test that storing the same document twice doesn't create duplicates."""
        service = EmbeddingServiceV2(config)
        
        try:
            await service.connect()
            
            # Store document first time
            chunk_uuids_1 = await service.store_document_chunks(sample_document)
            
            # Store document second time (should be idempotent)
            chunk_uuids_2 = await service.store_document_chunks(sample_document)
            
            # Should have same UUIDs
            assert chunk_uuids_1 == chunk_uuids_2
            
            # Verify no duplicates in search
            results = await service.search_chunks(
                query=sample_document.title,
                limit=50
            )
            
            parent_uid_matches = [
                r for r in results 
                if r["parent_uid"] == sample_document.uid
            ]
            
            # Should only find the original chunks, not duplicates
            assert len(parent_uid_matches) == len(chunk_uuids_1)
            
        finally:
            await service.disconnect()
            # Cleanup
            await service.delete_document_chunks(sample_document.uid)
```

---

## 5. Performance Requirements

### 5.1 Benchmarking Script
**File:** `scripts/benchmark_embedding.py`

```python
#!/usr/bin/env python3
"""Benchmark embedding service performance."""

import asyncio
import time
from typing import List
from datetime import datetime

from bio_mcp.config.config import Config
from bio_mcp.services.embedding_service_v2 import EmbeddingServiceV2
from bio_mcp.models.document import Document

async def benchmark_storage(service: EmbeddingServiceV2, documents: List[Document]) -> dict:
    """Benchmark chunk storage performance."""
    start_time = time.time()
    total_chunks = 0
    
    for doc in documents:
        chunk_uuids = await service.store_document_chunks(doc)
        total_chunks += len(chunk_uuids)
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    return {
        "documents_processed": len(documents),
        "total_chunks": total_chunks,
        "elapsed_seconds": elapsed,
        "docs_per_second": len(documents) / elapsed,
        "chunks_per_second": total_chunks / elapsed
    }

async def benchmark_search(service: EmbeddingServiceV2, queries: List[str]) -> dict:
    """Benchmark search performance."""
    start_time = time.time()
    total_results = 0
    
    for query in queries:
        results = await service.search_chunks(query, limit=10)
        total_results += len(results)
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    return {
        "queries_processed": len(queries),
        "total_results": total_results,
        "elapsed_seconds": elapsed,
        "queries_per_second": len(queries) / elapsed
    }

async def main():
    config = Config()
    service = EmbeddingServiceV2(config)
    
    # Create test documents
    test_docs = []
    for i in range(50):
        doc = Document(
            uid=f"test:{i}",
            source="test",
            source_id=str(i),
            title=f"Test Document {i}",
            text=f"Background: This is test document {i}. Methods: We tested performance. Results: Performance was measured. Conclusions: Results are documented.",
            published_at=datetime.now()
        )
        test_docs.append(doc)
    
    test_queries = [
        "test performance",
        "biomedical research",
        "clinical trial results",
        "therapeutic efficacy",
        "adverse events"
    ]
    
    try:
        await service.connect()
        
        # Benchmark storage
        print("Benchmarking storage...")
        storage_results = await benchmark_storage(service, test_docs)
        print(f"Storage: {storage_results['chunks_per_second']:.1f} chunks/sec")
        
        # Benchmark search
        print("Benchmarking search...")
        search_results = await benchmark_search(service, test_queries)
        print(f"Search: {search_results['queries_per_second']:.1f} queries/sec")
        
        # Requirements check
        if storage_results['chunks_per_second'] >= 100:
            print("✅ Storage performance requirement met (>100 chunks/sec)")
        else:
            print("❌ Storage performance requirement not met")
        
        if search_results['queries_per_second'] >= 10:
            print("✅ Search performance requirement met (>10 queries/sec)")
        else:
            print("❌ Search performance requirement not met")
        
    finally:
        # Cleanup
        for doc in test_docs:
            await service.delete_document_chunks(doc.uid)
        await service.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6. Success Validation

### 6.1 Checklist
- [ ] BioBERT model properly configured in Weaviate
- [ ] Tokenizer matches embedding model for accurate chunking
- [ ] Deterministic UUIDs enable idempotent storage
- [ ] Complete metadata propagation from Document to Chunk
- [ ] Quality scoring and section boosting work correctly
- [ ] Performance meets requirements (>100 chunks/sec storage, >10 queries/sec search)
- [ ] Integration tests pass with real Weaviate
- [ ] Error handling and logging properly implemented

### 6.2 Performance Requirements
- **Storage**: >100 chunks/second
- **Search**: >10 queries/second with quality boosting
- **Memory**: <500MB peak usage for embedding service
- **Latency**: <100ms average search response time

---

## Next Steps

After completing this step:
1. Proceed to **RAG_STEP_5_REINGEST.md** for data re-ingestion workflow
2. Run benchmark tests to validate performance
3. Test idempotent storage with sample PubMed data

**Estimated Time:** 2-3 days
**Dependencies:** RAG_STEP_1_MODELS.md, RAG_STEP_2_CHUNKING.md, RAG_STEP_3_WEAVIATE.md
**Risk Level:** Medium (external model dependency, performance requirements)