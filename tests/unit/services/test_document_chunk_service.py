"""
Unit tests for DocumentChunkService with Weaviate BioBERT vectorizer.
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from bio_mcp.config.config import Config
from bio_mcp.models.document import Document
from bio_mcp.services.document_chunk_service import DocumentChunkService


class TestDocumentChunkService:
    """Test document chunk service with Weaviate vectorizer."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = Mock(spec=Config)
        config.biobert_model_name = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
        config.weaviate_collection_v2 = "DocumentChunk_v2_test"
        config.chunker_version = "v1.2.0"
        config.biobert_max_tokens = 512
        config.chunker_target_tokens = 325
        config.chunker_max_tokens = 450
        config.chunker_min_tokens = 120
        config.chunker_overlap_tokens = 50
        return config
    
    @pytest.fixture
    def sample_document(self):
        """Sample document for testing."""
        return Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Test Biomedical Paper",
            text="Background: This study investigates novel biomarkers. Methods: We conducted a randomized controlled trial. Results: We found significant improvements (p<0.001). Conclusions: The treatment shows promise.",
            published_at=datetime(2024, 1, 15),
            authors=["Smith, J.", "Doe, J."],
            identifiers={"doi": "10.1234/test"},
            detail={"journal": "Nature Medicine", "mesh_terms": ["biomarkers", "clinical trial"]}
        )
    
    def test_initialization(self, mock_config):
        """Test service initialization."""
        service = DocumentChunkService()
        service.config = mock_config
        
        assert service.config == mock_config
        assert service.collection_name == "DocumentChunk_v2_test"
        assert service.chunking_service is not None
        assert not service._initialized
    
    def test_build_chunk_metadata_pubmed(self, mock_config, sample_document):
        """Test metadata building for PubMed documents."""
        service = DocumentChunkService()
        service.config = mock_config
        
        chunk_metadata = {
            "section": "Results",
            "n_sentences": 2
        }
        
        meta = service._build_chunk_metadata(sample_document, chunk_metadata)
        
        assert meta["chunker_version"] == "v1.2.0"
        assert meta["vectorizer"] == "text2vec-transformers"
        assert meta["model"] == mock_config.biobert_model_name
        assert meta["section"] == "Results"
        assert meta["n_sentences"] == 2
        assert meta["src"]["pubmed"]["journal"] == "Nature Medicine"
        assert meta["src"]["pubmed"]["mesh_terms"] == ["biomarkers", "clinical trial"]
        assert meta["src"]["pubmed"]["authors"] == ["Smith, J.", "Doe, J."]
        assert meta["src"]["pubmed"]["identifiers"] == {"doi": "10.1234/test"}
    
    def test_build_chunk_metadata_generic_source(self, mock_config):
        """Test metadata building for non-PubMed sources."""
        service = DocumentChunkService()
        service.config = mock_config
        
        document = Document(
            uid="ctgov:NCT12345678",
            source="ctgov",
            source_id="NCT12345678",
            title="Clinical Trial",
            text="Test clinical trial",
            detail={"phase": "Phase 3", "status": "Recruiting"}
        )
        
        chunk_metadata = {"section": "Summary"}
        meta = service._build_chunk_metadata(document, chunk_metadata)
        
        assert meta["chunker_version"] == "v1.2.0"
        assert meta["src"]["ctgov"]["phase"] == "Phase 3"
        assert meta["src"]["ctgov"]["status"] == "Recruiting"
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, mock_config):
        """Test health check when service is healthy."""
        mock_weaviate_client = Mock()
        mock_weaviate_client.client.is_ready.return_value = True
        mock_weaviate_client.client.collections.exists.return_value = True
        
        # Mock collection stats
        mock_aggregate_response = Mock()
        mock_aggregate_response.total_count = 100
        
        mock_source_response = Mock()
        mock_group = Mock()
        mock_group.grouped_by.value = "pubmed"
        mock_group.total_count = 100
        mock_source_response.groups = [mock_group]
        
        mock_collection = Mock()
        mock_collection.aggregate.over_all.side_effect = [mock_aggregate_response, mock_source_response]
        mock_weaviate_client.client.collections.get.return_value = mock_collection
        
        service = DocumentChunkService()
        service.config = mock_config
        service.weaviate_client = mock_weaviate_client
        service._initialized = True
        
        health = await service.health_check()
        
        assert health["status"] == "healthy"
        assert health["collection"] == mock_config.weaviate_collection_v2
        assert health["total_chunks"] == 100
        assert health["sources"] == ["pubmed"]
        assert health["vectorizer"] == "text2vec-transformers"
        assert health["model"] == mock_config.biobert_model_name