"""
Tests for cleaned up VectorService with Document/Chunk model.

Tests the VectorService after legacy adapter cleanup, using only
the new Document/Chunk approach.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from bio_mcp.models.document import Document
from bio_mcp.services.services import VectorService


class TestVectorService:
    """Test VectorService with cleaned up API."""

    def test_initialization(self):
        """Test VectorService initialization."""
        service = VectorService()

        assert service.embedding_service is None
        assert not service._initialized

    @pytest.mark.asyncio
    @patch("bio_mcp.services.services.EmbeddingService")
    async def test_initialize(self, mock_embedding_class):
        """Test VectorService initialization process."""
        mock_embedding = AsyncMock()
        mock_embedding_class.return_value = mock_embedding

        service = VectorService()
        await service.initialize()

        assert service._initialized
        assert service.embedding_service is not None
        mock_embedding.initialize.assert_called_once()

    @pytest.mark.asyncio
    @patch("bio_mcp.services.services.EmbeddingService")
    async def test_store_document_chunks(self, mock_embedding_class):
        """Test storing document as chunks."""
        mock_embedding = AsyncMock()
        mock_embedding.store_document_chunks.return_value = ["uuid1", "uuid2", "uuid3"]
        mock_embedding_class.return_value = mock_embedding

        service = VectorService()
        await service.initialize()

        # Create test document
        document = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Test Document",
            text="This is a test abstract for chunking.",
            published_at=datetime(2023, 1, 1, tzinfo=UTC),
            authors=["Test Author"],
            identifiers={"doi": "10.1000/test"},
            provenance={"test": True},
            detail={"journal": "Test Journal"},
        )

        result = await service.store_document_chunks(document)

        assert result == ["uuid1", "uuid2", "uuid3"]
        mock_embedding.store_document_chunks.assert_called_once_with(document)

    @pytest.mark.asyncio
    @patch("bio_mcp.services.services.EmbeddingService")
    async def test_search_chunks(self, mock_embedding_class):
        """Test searching chunks."""
        mock_embedding = AsyncMock()
        mock_results = [
            {"uuid": "uuid1", "text": "chunk 1", "score": 0.9},
            {"uuid": "uuid2", "text": "chunk 2", "score": 0.8},
        ]
        mock_embedding.search_chunks.return_value = mock_results
        mock_embedding_class.return_value = mock_embedding

        service = VectorService()
        await service.initialize()

        result = await service.search_chunks(
            query="test query", limit=10, search_mode="semantic"
        )

        assert result == mock_results
        mock_embedding.search_chunks.assert_called_once_with(
            query="test query",
            limit=10,
            search_mode="semantic",
            alpha=0.5,
            filters=None,
        )

    @pytest.mark.asyncio
    @patch("bio_mcp.services.services.EmbeddingService")
    async def test_store_document_legacy_api(self, mock_embedding_class):
        """Test storing document using legacy parameter API."""
        mock_embedding = AsyncMock()
        mock_embedding.store_document_chunks.return_value = ["uuid1", "uuid2"]
        mock_embedding_class.return_value = mock_embedding

        service = VectorService()
        await service.initialize()

        # Test legacy API - should internally convert to Document
        result = await service.store_document(
            pmid="12345678",
            title="Legacy Test",
            abstract="This is a legacy API test.",
            authors=["Legacy Author"],
            journal="Legacy Journal",
            publication_date="2023-01-01",
            doi="10.1000/legacy",
            keywords=["test", "legacy"],
        )

        assert result == ["uuid1", "uuid2"]
        # Should have called store_document_chunks with a Document object
        mock_embedding.store_document_chunks.assert_called_once()

        # Verify the Document was created correctly
        call_args = mock_embedding.store_document_chunks.call_args[0]
        document = call_args[0]

        assert isinstance(document, Document)
        assert document.uid == "pubmed:12345678"
        assert document.source == "pubmed"
        assert document.source_id == "12345678"
        assert document.title == "Legacy Test"
        assert document.text == "This is a legacy API test."
        assert document.authors == ["Legacy Author"]
        assert document.identifiers["doi"] == "10.1000/legacy"
        assert document.detail["journal"] == "Legacy Journal"
        assert document.detail["keywords"] == ["test", "legacy"]

    @pytest.mark.asyncio
    @patch("bio_mcp.services.services.EmbeddingService")
    async def test_search_documents_legacy_api(self, mock_embedding_class):
        """Test searching using legacy document API."""
        mock_embedding = AsyncMock()
        mock_results = [{"pmid": "123", "title": "doc"}]
        mock_embedding.search_chunks.return_value = mock_results
        mock_embedding_class.return_value = mock_embedding

        service = VectorService()
        await service.initialize()

        result = await service.search_documents("test query", limit=5)

        assert result == mock_results
        mock_embedding.search_chunks.assert_called_once_with(
            query="test query", limit=5, search_mode="semantic", alpha=0.5, filters=None
        )

    @pytest.mark.asyncio
    async def test_error_when_not_initialized(self):
        """Test error when trying to use service before initialization."""
        service = VectorService()

        document = Document(
            uid="pubmed:123",
            source="pubmed",
            source_id="123",
            title="Test",
            text="Test content",
        )

        # Should auto-initialize and work
        with patch(
            "bio_mcp.services.services.EmbeddingService"
        ) as mock_embedding_class:
            mock_embedding = AsyncMock()
            mock_embedding.store_document_chunks.return_value = ["uuid1"]
            mock_embedding_class.return_value = mock_embedding

            result = await service.store_document_chunks(document)
            assert result == ["uuid1"]

    @pytest.mark.asyncio
    @patch("bio_mcp.services.services.EmbeddingService")
    async def test_close(self, mock_embedding_class):
        """Test closing VectorService."""
        mock_embedding = AsyncMock()
        mock_embedding_class.return_value = mock_embedding

        service = VectorService()
        await service.initialize()
        await service.close()

        assert not service._initialized
        assert service.embedding_service is None
        mock_embedding.close.assert_called_once()


class TestVectorServiceErrorHandling:
    """Test error handling in VectorService."""

    @pytest.mark.asyncio
    async def test_store_chunks_without_embedding_service(self):
        """Test error when embedding service is not available."""
        service = VectorService()
        service._initialized = True  # Mark as initialized but without embedding service

        document = Document(
            uid="pubmed:123",
            source="pubmed",
            source_id="123",
            title="Test",
            text="Test content",
        )

        with pytest.raises(ValueError, match="Embedding service not initialized"):
            await service.store_document_chunks(document)

    @pytest.mark.asyncio
    async def test_search_chunks_without_embedding_service(self):
        """Test error when searching without embedding service."""
        service = VectorService()
        service._initialized = True  # Mark as initialized but without embedding service

        with pytest.raises(ValueError, match="Embedding service not initialized"):
            await service.search_chunks("test query")

    @pytest.mark.asyncio
    async def test_store_document_without_embedding_service(self):
        """Test error when storing document without embedding service."""
        service = VectorService()
        service._initialized = True  # Mark as initialized but without embedding service

        with pytest.raises(ValueError, match="Embedding service not initialized"):
            await service.store_document(
                pmid="123", title="Test", abstract="Test content"
            )
