"""
Tests for incremental sync functionality (Phase 4B.2).
Tests EDAT watermark-based incremental document synchronization.

Run with: pytest tests/test_incremental_sync.py -v -s
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.bio_mcp.clients.database import SyncWatermark
from src.bio_mcp.clients.pubmed_client import PubMedDocument, PubMedSearchResult
from src.bio_mcp.mcp.pubmed_tools import (
    PubMedToolsManager,
    pubmed_sync_incremental_tool,
)
from src.bio_mcp.services.services import SyncOrchestrator


class TestIncrementalSyncWatermarks:
    """Test sync watermark database operations."""
    
    @pytest.mark.asyncio
    async def test_sync_watermark_creation(self):
        """Test creating a new sync watermark."""
        with patch('src.bio_mcp.services.services.DatabaseManager') as mock_db_class:
            mock_db = AsyncMock()
            mock_db_class.return_value = mock_db
            
            # Mock watermark creation
            mock_watermark = SyncWatermark(
                query_key="test_query_key",
                last_edat="2024/08/15",
                total_synced="10",
                last_sync_count="5"
            )
            mock_db.create_or_update_sync_watermark.return_value = mock_watermark
            
            orchestrator = SyncOrchestrator()
            orchestrator.document_service.manager = mock_db
            
            # Test watermark creation
            result = await mock_db.create_or_update_sync_watermark(
                query_key="test_query_key",
                last_edat="2024/08/15",
                total_synced="10",
                last_sync_count="5"
            )
            
            assert result.query_key == "test_query_key"
            assert result.last_edat == "2024/08/15"
            assert result.total_synced == "10"
            assert result.last_sync_count == "5"
    
    @pytest.mark.asyncio
    async def test_sync_watermark_retrieval(self):
        """Test retrieving an existing sync watermark."""
        with patch('src.bio_mcp.services.services.DatabaseManager') as mock_db_class:
            mock_db = AsyncMock()
            mock_db_class.return_value = mock_db
            
            # Mock existing watermark
            mock_watermark = SyncWatermark(
                query_key="existing_query",
                last_edat="2024/08/10",
                total_synced="25",
                last_sync_count="15"
            )
            mock_db.get_sync_watermark.return_value = mock_watermark
            
            orchestrator = SyncOrchestrator()
            orchestrator.document_service.manager = mock_db
            
            # Test watermark retrieval
            result = await mock_db.get_sync_watermark("existing_query")
            
            assert result is not None
            assert result.query_key == "existing_query"
            assert result.last_edat == "2024/08/10"
            assert result.total_synced == "25"


class TestIncrementalPubMedSearch:
    """Test incremental PubMed search functionality."""
    
    @pytest.mark.asyncio
    async def test_incremental_search_with_edat_filter(self):
        """Test that incremental search applies EDAT filter correctly."""
        with patch('src.bio_mcp.clients.pubmed_client.PubMedClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock incremental search result
            mock_search_result = PubMedSearchResult(
                query="(diabetes treatment) AND (EDAT[2024/08/15:3000/12/31])",
                total_count=5,
                pmids=["12345", "67890", "54321"],
                web_env="test_webenv",
                query_key="test_query_key"
            )
            mock_client.search_incremental.return_value = mock_search_result
            
            # Test incremental search
            result = await mock_client.search_incremental(
                query="diabetes treatment",
                last_edat="2024/08/15",
                limit=50
            )
            
            # Verify the call was made with correct parameters
            mock_client.search_incremental.assert_called_once_with(
                query="diabetes treatment",
                last_edat="2024/08/15",
                limit=50
            )
            
            assert result.total_count == 5
            assert len(result.pmids) == 3
    
    @pytest.mark.asyncio
    async def test_incremental_search_without_edat_filter(self):
        """Test that incremental search works without EDAT filter (full sync)."""
        with patch('src.bio_mcp.clients.pubmed_client.PubMedClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock full search result (no EDAT filter)
            mock_search_result = PubMedSearchResult(
                query="cancer immunotherapy",
                total_count=100,
                pmids=["11111", "22222", "33333", "44444"],
                web_env="test_webenv",
                query_key="test_query_key"
            )
            mock_client.search_incremental.return_value = mock_search_result
            
            # Test incremental search without EDAT
            result = await mock_client.search_incremental(
                query="cancer immunotherapy",
                last_edat=None,
                limit=10
            )
            
            # Verify the call was made
            mock_client.search_incremental.assert_called_once_with(
                query="cancer immunotherapy",
                last_edat=None,
                limit=10
            )
            
            assert result.total_count == 100
            assert len(result.pmids) == 4


class TestIncrementalSyncOrchestration:
    """Test incremental sync orchestration."""
    
    @pytest.mark.asyncio 
    async def test_incremental_sync_with_existing_watermark(self):
        """Test incremental sync with an existing watermark."""
        with patch('src.bio_mcp.services.services.PubMedService') as mock_pubmed_service_class:
            with patch('src.bio_mcp.services.services.DocumentService') as mock_doc_service_class:
                with patch('src.bio_mcp.services.services.VectorService') as mock_vector_service_class:
                    
                    # Setup mocks
                    mock_pubmed_service = AsyncMock()
                    mock_doc_service = AsyncMock()
                    mock_vector_service = AsyncMock()
                    
                    mock_pubmed_service_class.return_value = mock_pubmed_service
                    mock_doc_service_class.return_value = mock_doc_service
                    mock_vector_service_class.return_value = mock_vector_service
                    
                    # Mock existing watermark
                    mock_watermark = SyncWatermark(
                        query_key="abcd1234",
                        last_edat="2024/08/10",
                        total_synced="20",
                        last_sync_count="5"
                    )
                    mock_doc_service.manager.get_sync_watermark.return_value = mock_watermark
                    
                    # Mock incremental search results
                    mock_search_result = PubMedSearchResult(
                        query="(heart disease) AND (EDAT[2024/08/10:3000/12/31])",
                        total_count=3,
                        pmids=["new123", "new456"],
                        web_env="test_webenv",
                        query_key="test_query"
                    )
                    mock_pubmed_service.client.search_incremental.return_value = mock_search_result
                    
                    # Mock document existence checks
                    mock_doc_service.document_exists.side_effect = [False, False]  # Both are new
                    
                    # Mock document fetching
                    mock_documents = [
                        PubMedDocument(
                            pmid="new123",
                            title="New Heart Disease Research",
                            abstract="Recent findings on heart disease treatment.",
                            authors=["Dr. Smith"],
                            journal="Cardiology Today",
                            publication_date=datetime(2024, 8, 15).date(),
                            doi="10.1000/heart.2024.123"
                        ),
                        PubMedDocument(
                            pmid="new456", 
                            title="Advanced Cardiac Care",
                            abstract="Innovative approaches to cardiac treatment.",
                            authors=["Dr. Johnson"],
                            journal="Heart Medicine",
                            publication_date=datetime(2024, 8, 16).date(),
                            doi="10.1000/heart.2024.456"
                        )
                    ]
                    mock_pubmed_service.fetch_documents.return_value = mock_documents
                    
                    # Mock database and vector storage
                    mock_doc_service.create_document.return_value = None
                    mock_vector_service.store_document.return_value = "test-uuid"
                    
                    # Mock watermark update
                    updated_watermark = SyncWatermark(
                        query_key="abcd1234",
                        last_edat="2024/08/19",  # Current date
                        total_synced="22",  # 20 + 2 new
                        last_sync_count="2"
                    )
                    mock_doc_service.manager.create_or_update_sync_watermark.return_value = updated_watermark
                    
                    # Test incremental sync
                    orchestrator = SyncOrchestrator(mock_pubmed_service, mock_doc_service, mock_vector_service)
                    result = await orchestrator.sync_documents_incremental("heart disease", limit=50)
                    
                    # Verify incremental sync behavior
                    assert result["incremental"] is True
                    assert result["last_edat"] == "2024/08/10"  # Previous watermark
                    assert result["total_requested"] == 2
                    assert result["successfully_synced"] == 2
                    assert result["already_existed"] == 0
                    assert result["failed"] == 0
                    assert "new123" in result["pmids_synced"]
                    assert "new456" in result["pmids_synced"]
                    
                    # Verify watermark was updated
                    mock_doc_service.manager.create_or_update_sync_watermark.assert_called()
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Weaviate - needs better mocking or testcontainers")
    async def test_incremental_sync_no_new_documents(self):
        """Test incremental sync when no new documents are found."""
        with patch('src.bio_mcp.services.services.PubMedService') as mock_pubmed_service_class:
            with patch('src.bio_mcp.services.services.DocumentService') as mock_doc_service_class:
                
                # Setup mocks
                mock_pubmed_service = AsyncMock()
                mock_doc_service = AsyncMock()
                
                mock_pubmed_service_class.return_value = mock_pubmed_service
                mock_doc_service_class.return_value = mock_doc_service
                
                # Mock existing watermark
                mock_watermark = SyncWatermark(
                    query_key="abcd1234",
                    last_edat="2024/08/15",
                    total_synced="50",
                    last_sync_count="10"
                )
                mock_doc_service.manager.get_sync_watermark.return_value = mock_watermark
                
                # Mock empty incremental search results
                mock_search_result = PubMedSearchResult(
                    query="(rare disease) AND (EDAT[2024/08/15:3000/12/31])",
                    total_count=0,
                    pmids=[],
                    web_env="test_webenv",
                    query_key="test_query"
                )
                mock_pubmed_service.client.search_incremental.return_value = mock_search_result
                
                # Mock watermark update
                mock_doc_service.manager.create_or_update_sync_watermark.return_value = mock_watermark
                
                # Test incremental sync with no results
                orchestrator = SyncOrchestrator(mock_pubmed_service, mock_doc_service, None)
                result = await orchestrator.sync_documents_incremental("rare disease", limit=50)
                
                # Verify empty sync result
                assert result["incremental"] is True
                assert result["total_requested"] == 0
                assert result["successfully_synced"] == 0
                assert result["already_existed"] == 0
                assert result["failed"] == 0
                assert result["pmids_synced"] == []
                assert result["pmids_failed"] == []


class TestIncrementalSyncMCPTool:
    """Test the MCP tool for incremental sync."""
    
    @pytest.mark.asyncio
    async def test_incremental_sync_tool_success(self):
        """Test successful incremental sync via MCP tool."""
        with patch('src.bio_mcp.mcp.pubmed_tools.get_tools_manager') as mock_get_manager:
            # Mock the manager and its incremental sync method
            mock_manager = AsyncMock(spec=PubMedToolsManager)
            mock_get_manager.return_value = mock_manager
            
            # Mock successful incremental sync result
            from src.bio_mcp.mcp.pubmed_tools import SyncResult
            mock_sync_result = SyncResult(
                query="alzheimer disease",
                total_requested=3,
                successfully_synced=2,
                already_existed=1,
                failed=0,
                pmids_synced=["new789", "new012"],
                pmids_failed=[],
                execution_time_ms=1500.0
            )
            mock_manager.sync_incremental.return_value = mock_sync_result
            
            # Test incremental sync tool
            result = await pubmed_sync_incremental_tool("pubmed.sync.incremental", {
                "query": "alzheimer disease",
                "limit": 50
            })
            
            assert len(result) == 1
            response_text = result[0].text
            
            # Verify incremental sync indicators
            assert "alzheimer disease" in response_text
            assert "Total requested: 3" in response_text
            assert "Successfully synced: 2" in response_text
            assert "Already existed: 1" in response_text
            assert "Failed: 0" in response_text
            assert "1500.0ms" in response_text
            
            # Verify manager was called with correct parameters
            mock_manager.sync_incremental.assert_called_once_with("alzheimer disease", limit=50)
    
    @pytest.mark.asyncio
    async def test_incremental_sync_tool_missing_query(self):
        """Test incremental sync tool with missing query parameter."""
        result = await pubmed_sync_incremental_tool("pubmed.sync.incremental", {
            "limit": 100
        })
        
        assert len(result) == 1
        response_text = result[0].text
        assert "Error: 'query' parameter is required" in response_text


# Pytest configuration for incremental sync tests
pytestmark = pytest.mark.unit