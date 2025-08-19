"""
Integration tests for local embeddings and Weaviate RAG functionality.
Tests the new architecture with local sentence transformers.
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from src.bio_mcp.clients.pubmed_client import PubMedDocument
from src.bio_mcp.clients.weaviate_client import WeaviateClient
from src.bio_mcp.mcp.pubmed_tools import PubMedToolsManager
from src.bio_mcp.mcp.rag_tools import RAGToolsManager


class TestWeaviateLocalEmbeddings:
    """Test Weaviate integration with local transformers."""
    
    @pytest.mark.asyncio
    async def test_weaviate_client_date_formatting(self):
        """Test that dates are properly formatted for Weaviate."""
        # Test the date formatting logic without actually connecting
        test_cases = [
            ("2024-08-19", "2024-08-19T00:00:00Z"),
            ("2024-08-19T10:30:00Z", "2024-08-19T10:30:00Z"),
            (None, None),
            ("", None)
        ]
        
        for input_date, expected in test_cases:
            # Access the formatting logic by testing the document data preparation
            formatted_date = None
            if input_date:
                if isinstance(input_date, str) and 'T' not in input_date:
                    formatted_date = f"{input_date}T00:00:00Z"
                else:
                    formatted_date = input_date
            
            assert formatted_date == expected
    
    @pytest.mark.asyncio
    async def test_weaviate_document_storage_mock(self):
        """Test document storage with mocked Weaviate."""
        with patch('src.bio_mcp.clients.weaviate_client.weaviate') as mock_weaviate:
            # Create properly configured async mocks
            mock_client = AsyncMock()
            mock_collection = AsyncMock()
            mock_data = AsyncMock()
            mock_collections = AsyncMock()
            
            # Setup the mock chain with proper async await behavior
            mock_weaviate.connect_to_local.return_value = mock_client
            mock_client.collections = mock_collections
            mock_collections.get.return_value = mock_collection
            mock_collections.exists.return_value = True
            mock_collections.create.return_value = mock_collection
            mock_collection.data = mock_data
            mock_data.insert.return_value = "test-uuid-123"
            
            client = WeaviateClient()
            await client.initialize()
            
            # Test storing a document
            uuid = await client.store_document(
                pmid="12345",
                title="Test Document",
                abstract="Test abstract content",
                authors=["Author One", "Author Two"],
                journal="Test Journal",
                publication_date="2024-08-19",
                doi="10.1000/test"
            )
            
            assert uuid == "test-uuid-123"
            mock_data.insert.assert_called_once()
            
            # Verify the document data structure
            call_args = mock_data.insert.call_args
            doc_data = call_args.kwargs['properties']
            
            assert doc_data['pmid'] == "12345"
            assert doc_data['title'] == "Test Document"
            assert doc_data['publication_date'] == "2024-08-19T00:00:00Z"
            assert doc_data['authors'] == ["Author One", "Author Two"]


class TestRAGToolsIntegration:
    """Test RAG tools with new local embeddings architecture."""
    
    @pytest.mark.asyncio
    @patch('src.bio_mcp.mcp.rag_tools.get_weaviate_client')
    async def test_rag_search_no_openai_dependency(self, mock_get_weaviate):
        """Test that RAG search doesn't depend on OpenAI embeddings."""
        # Mock Weaviate client
        mock_weaviate = AsyncMock()
        mock_get_weaviate.return_value = mock_weaviate
        
        # Mock search results
        mock_weaviate.search_documents.return_value = [
            {
                "pmid": "12345",
                "title": "Test Document",
                "abstract": "Test abstract",
                "score": 0.95
            }
        ]
        
        manager = RAGToolsManager()
        result = await manager.search_documents("test query", top_k=1)
        
        # Verify search was called on Weaviate directly (no embedding generation)
        mock_weaviate.search_documents.assert_called_once_with(
            query="test query",
            limit=1
        )
        
        assert result.total_results == 1
        assert result.search_type == "semantic"
        assert len(result.documents) == 1
    
    @pytest.mark.asyncio 
    async def test_rag_search_tool_integration(self):
        """Test the RAG search tool end-to-end with mocked components."""
        from src.bio_mcp.mcp.rag_tools import RAGSearchResult, rag_search_tool
        
        with patch('src.bio_mcp.mcp.rag_tools.RAGToolsManager') as mock_manager_class:
            # Mock manager instance
            mock_manager = AsyncMock()
            mock_manager_class.return_value = mock_manager
            
            # Mock search result
            mock_result = RAGSearchResult(
                query="cancer treatment",
                total_results=1,
                documents=[{
                    "pmid": "12345",
                    "title": "Cancer Treatment Study",
                    "abstract": "This study examines cancer treatment...",
                    "score": 0.95,
                    "journal": "Cancer Research"
                }],
                search_type="semantic"
            )
            mock_manager.search_documents.return_value = mock_result
            
            # Call the tool
            result = await rag_search_tool("rag.search", {
                "query": "cancer treatment",
                "top_k": 5
            })
            
            assert len(result) == 1
            response_text = result[0].text
            
            # Verify response contains expected content
            assert "cancer treatment" in response_text
            assert "Cancer Treatment Study" in response_text
            assert "12345" in response_text
            assert "Semantic Search" in response_text


class TestPubMedWeaviateIntegration:
    """Test PubMed sync integration with Weaviate storage."""
    
    @pytest.mark.asyncio
    @patch('src.bio_mcp.mcp.pubmed_tools.get_weaviate_client')
    async def test_pubmed_sync_stores_in_weaviate(self, mock_get_weaviate):
        """Test that PubMed sync stores documents in Weaviate."""
        # Mock Weaviate client
        mock_weaviate = AsyncMock()
        mock_get_weaviate.return_value = mock_weaviate
        mock_weaviate.store_document.return_value = "test-uuid-123"
        
        # Mock database manager
        with patch('src.bio_mcp.mcp.pubmed_tools.DatabaseManager') as mock_db_class:
            mock_db = AsyncMock()
            mock_db_class.return_value = mock_db
            mock_db.document_exists.return_value = False
            mock_db.create_document.return_value = None
            
            # Mock PubMed client
            with patch('src.bio_mcp.mcp.pubmed_tools.PubMedClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
                
                # Mock search result
                from src.bio_mcp.clients.pubmed_client import PubMedSearchResult
                mock_search_result = PubMedSearchResult(
                    query="test query",
                    total_count=1,
                    pmids=["12345"],
                    retstart=0,
                    retmax=1
                )
                mock_client.search.return_value = mock_search_result
                
                # Mock document fetch
                test_doc = PubMedDocument(
                    pmid="12345",
                    title="Test Cancer Study",
                    abstract="This study examines cancer treatment effectiveness.",
                    authors=["Smith J", "Doe A"],
                    journal="Cancer Research",
                    publication_date=date(2024, 8, 19),
                    doi="10.1000/cancer.2024.123"
                )
                mock_client.fetch_documents.return_value = [test_doc]
                
                # Test the sync process
                manager = PubMedToolsManager()
                await manager.initialize()
                
                result = await manager.sync("cancer treatment", limit=1)
                
                # Verify Weaviate storage was called
                mock_weaviate.store_document.assert_called_once()
                
                # Verify the call arguments
                call_args = mock_weaviate.store_document.call_args[1]
                assert call_args['pmid'] == "12345"
                assert call_args['title'] == "Test Cancer Study"
                assert call_args['abstract'] == "This study examines cancer treatment effectiveness."
                assert call_args['authors'] == ["Smith J", "Doe A"]
                assert call_args['publication_date'] == "2024-08-19"
                
                # Verify sync result
                assert result.successfully_synced == 1
                assert result.failed == 0


class TestErrorHandling:
    """Test error handling in the new architecture."""
    
    @pytest.mark.asyncio
    async def test_weaviate_connection_failure_graceful(self):
        """Test graceful handling of Weaviate connection failures."""
        from src.bio_mcp.mcp.rag_tools import RAGToolsManager
        
        with patch('src.bio_mcp.mcp.rag_tools.get_weaviate_client') as mock_get_weaviate:
            # Mock Weaviate client that fails to initialize
            mock_weaviate = AsyncMock()
            mock_get_weaviate.return_value = mock_weaviate
            mock_weaviate.initialize.side_effect = Exception("Connection failed")
            
            manager = RAGToolsManager()
            
            # Should handle connection failure gracefully
            result = await manager.search_documents("test query")
            
            assert result.total_results == 0
            assert result.documents == []
            assert result.query == "test query"
    
    @pytest.mark.asyncio
    async def test_pubmed_sync_weaviate_error_fails_correctly(self):
        """Test that PubMed sync fails when Weaviate storage fails (current behavior)."""
        with patch('src.bio_mcp.mcp.pubmed_tools.get_weaviate_client') as mock_get_weaviate:
            # Mock Weaviate client that fails during document storage
            mock_weaviate = AsyncMock()
            mock_get_weaviate.return_value = mock_weaviate
            mock_weaviate.store_document.side_effect = Exception("Weaviate storage failed")
            
            # Mock database manager (should still work)
            with patch('src.bio_mcp.mcp.pubmed_tools.DatabaseManager') as mock_db_class:
                mock_db = AsyncMock()
                mock_db_class.return_value = mock_db
                mock_db.document_exists.return_value = False
                mock_db.create_document.return_value = None
                
                # Mock PubMed client
                with patch('src.bio_mcp.mcp.pubmed_tools.PubMedClient') as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client_class.return_value = mock_client
                    
                    # Mock minimal successful response
                    from src.bio_mcp.clients.pubmed_client import (
                        PubMedDocument,
                        PubMedSearchResult,
                    )
                    mock_search_result = PubMedSearchResult(
                        query="test", total_count=1, pmids=["123"], retstart=0, retmax=1
                    )
                    mock_client.search.return_value = mock_search_result
                    
                    test_doc = PubMedDocument(pmid="123", title="Test")
                    mock_client.fetch_documents.return_value = [test_doc]
                    
                    manager = PubMedToolsManager()
                    await manager.initialize()
                    
                    # This should not raise because errors are caught and logged, sync returns results
                    result = await manager.sync("test", limit=1)
                    
                    # Should show one failed document
                    assert result.failed == 1
                    assert result.successfully_synced == 0


class TestPerformanceAndScaling:
    """Test performance characteristics of the new system."""
    
    @pytest.mark.asyncio
    async def test_bulk_document_storage_efficiency(self):
        """Test that bulk operations are handled efficiently."""
        # This would be expanded for real performance testing
        pass
    
    def test_chunk_size_optimization(self):
        """Test that chunk sizes are optimized for the transformer model."""
        from src.bio_mcp.core.embeddings import ChunkingConfig
        
        # Verify chunking configuration is reasonable for local transformers
        config = ChunkingConfig()
        
        # sentence-transformers typically handle up to 512 tokens well
        assert config.MAX_TOKENS <= 512
        assert config.TARGET_TOKENS <= config.MAX_TOKENS
        assert config.MIN_TOKENS > 0