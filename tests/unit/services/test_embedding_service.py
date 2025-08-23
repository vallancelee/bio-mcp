"""
Unit tests for EmbeddingService.

Tests both the new chunk-based embedding workflow and backward compatibility
with the legacy document-based approach.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from bio_mcp.models.document import Document
from bio_mcp.services.embedding_service import EmbeddingService


class TestEmbeddingService:
    """Test the EmbeddingService class."""

    def test_initialization(self):
        """Test service initialization."""
        service = EmbeddingService()

        assert service.weaviate_client is None
        assert service.chunker is not None
        assert not service._initialized

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test service initialization process."""
        # Mock Weaviate client
        mock_weaviate = AsyncMock()
        mock_weaviate.initialize = AsyncMock()

        with patch(
            "bio_mcp.services.embedding_service.get_weaviate_client",
            return_value=mock_weaviate,
        ):
            service = EmbeddingService()

            with patch.object(
                service, "_ensure_chunk_collection_exists", new_callable=AsyncMock
            ) as mock_ensure:
                await service.initialize()

                assert service._initialized
                assert service.weaviate_client == mock_weaviate
                mock_weaviate.initialize.assert_called_once()
                mock_ensure.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_document_chunks(self):
        """Test storing document as chunks."""
        # Create test document
        doc = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Test Document",
            text="Background: This is a test.\nMethods: Testing approach.\nResults: Good results.\nConclusions: Success.",
            published_at=datetime(2023, 6, 15, tzinfo=UTC),
            authors=["Smith, J", "Johnson, M"],
            identifiers={"doi": "10.1000/test.doi"},
            provenance={"s3_uri": "s3://bucket/test.json"},
            detail={"quality_total": 85},
        )

        # Mock Weaviate client and collection
        mock_collection = Mock()
        mock_collection.data.insert.return_value = "uuid-123"

        mock_weaviate = Mock()
        mock_weaviate.client.collections.get.return_value = mock_collection

        service = EmbeddingService(weaviate_client=mock_weaviate)
        service._initialized = True

        # Store document chunks
        uuids = await service.store_document_chunks(doc)

        # Should generate multiple chunks for structured content
        assert len(uuids) > 1
        assert all(uuid == "uuid-123" for uuid in uuids)

        # Verify collection.data.insert was called for each chunk
        assert mock_collection.data.insert.call_count == len(uuids)

        # Check first call arguments
        first_call = mock_collection.data.insert.call_args_list[0]
        chunk_data = first_call[1]["properties"]
        assert chunk_data["parent_uid"] == "pubmed:12345678"
        assert chunk_data["source"] == "pubmed"
        assert "chunk_id" in chunk_data
        assert "text" in chunk_data

    @pytest.mark.asyncio
    async def test_search_chunks_semantic(self):
        """Test semantic chunk search."""
        # Mock search response
        mock_obj = Mock()
        mock_obj.properties = {
            "chunk_id": "pubmed:12345678:0",
            "parent_uid": "pubmed:12345678",
            "source": "pubmed",
            "chunk_idx": 0,
            "text": "Background: This is a test.",
            "title": "Test Document",
            "section": "Background",
            "tokens": 25,
            "published_at": "2023-06-15T00:00:00+00:00",
            "meta": {"chunk_strategy": "structured"},
        }
        mock_obj.uuid = "uuid-123"
        mock_obj.metadata.score = 0.95
        mock_obj.metadata.distance = 0.05

        mock_response = Mock()
        mock_response.objects = [mock_obj]

        mock_collection = Mock()
        mock_collection.query.near_text.return_value = mock_response

        mock_weaviate = Mock()
        mock_weaviate.client.collections.get.return_value = mock_collection

        service = EmbeddingService(weaviate_client=mock_weaviate)
        service._initialized = True

        # Perform search
        results = await service.search_chunks(
            "test query", limit=5, search_mode="semantic"
        )

        assert len(results) == 1
        result = results[0]
        assert result["chunk_id"] == "pubmed:12345678:0"
        assert result["parent_uid"] == "pubmed:12345678"
        assert result["source"] == "pubmed"
        assert result["text"] == "Background: This is a test."
        assert result["score"] == 0.95
        assert result["distance"] == 0.05

        # Verify near_text was called correctly
        mock_collection.query.near_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_chunks_hybrid(self):
        """Test hybrid chunk search."""
        # Mock search response
        mock_obj = Mock()
        mock_obj.properties = {
            "chunk_id": "pubmed:87654321:1",
            "parent_uid": "pubmed:87654321",
            "source": "pubmed",
            "chunk_idx": 1,
            "text": "Methods: Advanced testing techniques.",
            "title": "Advanced Study",
            "section": "Methods",
            "tokens": 20,
            "meta": {},
        }
        mock_obj.uuid = "uuid-456"
        mock_obj.metadata.score = 0.88
        mock_obj.metadata.explain_score = "hybrid score explanation"

        mock_response = Mock()
        mock_response.objects = [mock_obj]

        mock_collection = Mock()
        mock_collection.query.hybrid.return_value = mock_response

        mock_weaviate = Mock()
        mock_weaviate.client.collections.get.return_value = mock_collection

        service = EmbeddingService(weaviate_client=mock_weaviate)
        service._initialized = True

        # Perform hybrid search
        results = await service.search_chunks(
            "testing methods", search_mode="hybrid", alpha=0.7
        )

        assert len(results) == 1
        result = results[0]
        assert result["chunk_id"] == "pubmed:87654321:1"
        assert result["section"] == "Methods"
        assert result["score"] == 0.88
        assert result["explain_score"] == "hybrid score explanation"

        # Verify hybrid was called with correct alpha
        mock_collection.query.hybrid.assert_called_once()
        call_args = mock_collection.query.hybrid.call_args
        assert call_args[1]["alpha"] == 0.7

    @pytest.mark.asyncio
    async def test_search_chunks_bm25(self):
        """Test BM25 chunk search."""
        mock_obj = Mock()
        mock_obj.properties = {
            "chunk_id": "pubmed:99999999:0",
            "parent_uid": "pubmed:99999999",
            "source": "pubmed",
            "chunk_idx": 0,
            "text": "Keywords: testing, methodology, biomedical research.",
            "title": "Keyword Study",
            "section": "Keywords",
            "tokens": 15,
            "meta": {},
        }
        mock_obj.uuid = "uuid-789"
        mock_obj.metadata.score = 0.75

        mock_response = Mock()
        mock_response.objects = [mock_obj]

        mock_collection = Mock()
        mock_collection.query.bm25.return_value = mock_response

        mock_weaviate = Mock()
        mock_weaviate.client.collections.get.return_value = mock_collection

        service = EmbeddingService(weaviate_client=mock_weaviate)
        service._initialized = True

        # Perform BM25 search
        results = await service.search_chunks("biomedical", search_mode="bm25")

        assert len(results) == 1
        result = results[0]
        assert result["chunk_id"] == "pubmed:99999999:0"
        assert result["score"] == 0.75

        # Verify bm25 was called
        mock_collection.query.bm25.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_chunk_by_id(self):
        """Test retrieving a specific chunk by ID."""
        mock_obj = Mock()
        mock_obj.properties = {
            "chunk_id": "pubmed:12345678:0",
            "parent_uid": "pubmed:12345678",
            "source": "pubmed",
            "chunk_idx": 0,
            "text": "This is the first chunk.",
            "title": "Test Document",
            "section": "Background",
            "tokens": 20,
            "meta": {"chunk_strategy": "structured"},
        }
        mock_obj.uuid = "uuid-123"

        mock_response = Mock()
        mock_response.objects = [mock_obj]

        mock_collection = Mock()
        mock_collection.query.fetch_objects.return_value = mock_response

        mock_weaviate = Mock()
        mock_weaviate.client.collections.get.return_value = mock_collection

        service = EmbeddingService(weaviate_client=mock_weaviate)
        service._initialized = True

        # Get chunk by ID
        result = await service.get_chunk_by_id("pubmed:12345678:0")

        assert result is not None
        assert result["chunk_id"] == "pubmed:12345678:0"
        assert result["parent_uid"] == "pubmed:12345678"
        assert result["text"] == "This is the first chunk."
        assert result["uuid"] == "uuid-123"

        # Verify fetch_objects was called with correct filter
        mock_collection.query.fetch_objects.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_chunk_by_id_not_found(self):
        """Test retrieving a chunk that doesn't exist."""
        mock_response = Mock()
        mock_response.objects = []  # No results

        mock_collection = Mock()
        mock_collection.query.fetch_objects.return_value = mock_response

        mock_weaviate = Mock()
        mock_weaviate.client.collections.get.return_value = mock_collection

        service = EmbeddingService(weaviate_client=mock_weaviate)
        service._initialized = True

        # Try to get non-existent chunk
        result = await service.get_chunk_by_id("nonexistent:chunk:id")

        assert result is None

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check when service is healthy."""
        mock_weaviate = Mock()
        mock_weaviate.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_weaviate.client.collections.exists.return_value = True

        service = EmbeddingService(weaviate_client=mock_weaviate)
        service._initialized = True

        health = await service.health_check()

        assert health["status"] == "healthy"
        assert health["chunk_collection_exists"]
        assert health["chunker_available"]

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        """Test health check when service is degraded."""
        mock_weaviate = Mock()
        mock_weaviate.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_weaviate.client.collections.exists.return_value = (
            False  # Collection missing
        )

        service = EmbeddingService(weaviate_client=mock_weaviate)
        service._initialized = True

        health = await service.health_check()

        assert health["status"] == "degraded"
        assert not health["chunk_collection_exists"]

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self):
        """Test health check when service is not initialized."""
        service = EmbeddingService()

        health = await service.health_check()

        assert health["status"] == "error"
        assert "not initialized" in health["message"]

    @pytest.mark.asyncio
    async def test_close(self):
        """Test service cleanup."""
        mock_weaviate = AsyncMock()

        service = EmbeddingService(weaviate_client=mock_weaviate)
        service._initialized = True

        await service.close()

        assert not service._initialized
        assert service.weaviate_client is None
        mock_weaviate.close.assert_called_once()


class TestEmbeddingServiceIntegration:
    """Integration tests for EmbeddingService with real chunking."""

    @pytest.mark.asyncio
    async def test_document_to_chunks_workflow(self):
        """Test the complete workflow from Document to stored chunks."""
        # Create a realistic document
        doc = Document(
            uid="pubmed:integration_test",
            source="pubmed",
            source_id="integration_test",
            title="Multi-source Document Analysis",
            text="Background: Document processing is important.\nMethods: We used advanced algorithms.\nResults: The system works well.\nConclusions: This approach is effective.",
            published_at=datetime(2023, 1, 15, tzinfo=UTC),
            authors=["Researcher, A", "Scientist, B"],
            identifiers={"doi": "10.1000/integration.test"},
            provenance={"test": True},
            detail={"journal": "Test Journal", "impact_factor": 5.2},
        )

        # Mock Weaviate to capture chunk storage
        stored_chunks = []

        def mock_insert(properties, uuid=None):
            stored_chunks.append(properties)
            return uuid or f"uuid-{len(stored_chunks)}"

        mock_collection = Mock()
        mock_collection.data.insert.side_effect = mock_insert

        mock_weaviate = Mock()
        mock_weaviate.client.collections.get.return_value = mock_collection

        service = EmbeddingService(weaviate_client=mock_weaviate)
        service._initialized = True

        # Store document chunks
        uuids = await service.store_document_chunks(doc)

        # Verify we got at least one chunk
        assert len(uuids) >= 1
        assert len(stored_chunks) == len(uuids)

        # Verify chunk structure
        for chunk_data in stored_chunks:
            assert chunk_data["parent_uid"] == "pubmed:integration_test"
            assert chunk_data["source"] == "pubmed"
            assert "chunk_id" in chunk_data
            assert "text" in chunk_data
            assert "tokens" in chunk_data

        # Verify first chunk contains title
        first_chunk = stored_chunks[0]
        assert "Multi-source Document Analysis" in first_chunk["text"]

        # Verify different sections are represented in the chunked content
        chunk_texts = [chunk["text"] for chunk in stored_chunks]
        combined_text = " ".join(chunk_texts)
        # Enhanced chunking may combine sections - check for key content
        assert "processing is important" in combined_text
        assert "advanced algorithms" in combined_text
        assert "system works well" in combined_text
        assert "approach is effective" in combined_text
