"""
Tests for hybrid search functionality (Phase 4B.1).
Tests BM25, semantic, and hybrid search modes with quality reranking.

Run with: pytest tests/test_hybrid_search.py -v -s
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.bio_mcp.rag_tools import RAGToolsManager, rag_search_tool


class TestHybridSearchFunctionality:
    """Test hybrid search capabilities."""
    
    @pytest.mark.asyncio
    async def test_rag_search_tool_hybrid_mode(self):
        """Test RAG search tool with hybrid search mode."""
        with patch('src.bio_mcp.rag_tools.get_rag_manager') as mock_get_manager:
            # Mock the manager and its search method
            mock_manager = AsyncMock(spec=RAGToolsManager)
            mock_get_manager.return_value = mock_manager
            
            # Mock hybrid search results with boosted scores
            mock_search_result = AsyncMock()
            mock_search_result.query = "CRISPR gene editing"
            mock_search_result.total_results = 2
            mock_search_result.search_type = "hybrid"
            mock_search_result.documents = [
                {
                    "uuid": "test-uuid-1",
                    "pmid": "12345678",
                    "title": "CRISPR-Cas9 Gene Editing in Human Cells",
                    "abstract": "Novel CRISPR applications in therapeutic gene editing...",
                    "journal": "Nature Biotechnology",
                    "publication_date": "2024-01-15",
                    "score": 0.85,
                    "boosted_score": 0.935,  # 10% quality boost
                    "quality_boost": 0.1,
                    "content": "CRISPR-Cas9 represents a revolutionary approach to gene editing with applications in treating genetic diseases...",
                    "search_mode": "hybrid"
                },
                {
                    "uuid": "test-uuid-2", 
                    "pmid": "87654321",
                    "title": "Gene Therapy Using CRISPR Technology",
                    "abstract": "Clinical applications of CRISPR in gene therapy...",
                    "journal": "Cell",
                    "publication_date": "2023-12-01",
                    "score": 0.78,
                    "boosted_score": 0.858,  # Quality boost for top journal
                    "quality_boost": 0.1,
                    "content": "Gene therapy approaches using CRISPR-Cas systems have shown promise in clinical trials...",
                    "search_mode": "hybrid"
                }
            ]
            
            mock_manager.search_documents.return_value = mock_search_result
            
            # Test hybrid search with quality reranking
            result = await rag_search_tool("rag.search", {
                "query": "CRISPR gene editing",
                "top_k": 5,
                "search_mode": "hybrid",
                "rerank_by_quality": True
            })
            
            assert len(result) == 1
            response_text = result[0].text
            
            # Verify hybrid search indicators
            assert "Hybrid RAG Search Results" in response_text
            assert "Hybrid (BM25 + Vector)" in response_text
            assert "Quality boosting: ON" in response_text
            assert "2 documents found" in response_text
            
            # Verify document content with enhanced scoring
            assert "CRISPR-Cas9 Gene Editing in Human Cells" in response_text
            assert "PMID: 12345678" in response_text
            assert "Score: 0.850" in response_text
            assert "0.935" in response_text  # Boosted score
            assert "🔀" in response_text  # Hybrid mode indicator
            
            # Verify manager was called with correct parameters
            mock_manager.search_documents.assert_called_once_with(
                query="CRISPR gene editing",
                top_k=5,
                search_mode="hybrid",
                rerank_by_quality=True
            )
    
    @pytest.mark.asyncio
    async def test_rag_search_tool_bm25_mode(self):
        """Test RAG search tool with BM25-only mode."""
        with patch('src.bio_mcp.rag_tools.get_rag_manager') as mock_get_manager:
            mock_manager = AsyncMock(spec=RAGToolsManager)
            mock_get_manager.return_value = mock_manager
            
            # Mock BM25 search results
            mock_search_result = AsyncMock()
            mock_search_result.query = "diabetes management"
            mock_search_result.total_results = 1
            mock_search_result.search_type = "bm25"
            mock_search_result.documents = [
                {
                    "uuid": "bm25-uuid-1",
                    "pmid": "11111111",
                    "title": "Diabetes Management Strategies in Clinical Practice",
                    "abstract": "Comprehensive approaches to managing type 2 diabetes...",
                    "journal": "Diabetes Care",
                    "publication_date": "2023-06-15",
                    "score": 4.2,  # BM25 scores are different scale
                    "boosted_score": 4.2,  # No boost applied
                    "quality_boost": 0,
                    "content": "Clinical guidelines for diabetes management include lifestyle interventions and pharmacological treatments...",
                    "search_mode": "bm25"
                }
            ]
            
            mock_manager.search_documents.return_value = mock_search_result
            
            # Test BM25 search
            result = await rag_search_tool("rag.search", {
                "query": "diabetes management", 
                "search_mode": "bm25",
                "rerank_by_quality": False
            })
            
            assert len(result) == 1
            response_text = result[0].text
            
            # Verify BM25 search indicators
            assert "Keyword (BM25)" in response_text
            assert "Quality boosting: OFF" in response_text
            assert "🔎" in response_text  # BM25 mode indicator
            assert "Score: 4.200" in response_text
            
            # Verify manager was called with BM25 parameters
            mock_manager.search_documents.assert_called_once_with(
                query="diabetes management",
                top_k=10,  # Default value
                search_mode="bm25",
                rerank_by_quality=False
            )
    
    @pytest.mark.asyncio
    async def test_rag_search_tool_semantic_mode(self):
        """Test RAG search tool with semantic-only mode."""
        with patch('src.bio_mcp.rag_tools.get_rag_manager') as mock_get_manager:
            mock_manager = AsyncMock(spec=RAGToolsManager)
            mock_get_manager.return_value = mock_manager
            
            # Mock semantic search results
            mock_search_result = AsyncMock()
            mock_search_result.query = "cancer immunotherapy"
            mock_search_result.total_results = 1
            mock_search_result.search_type = "semantic"
            mock_search_result.documents = [
                {
                    "uuid": "semantic-uuid-1",
                    "pmid": "22222222",
                    "title": "Novel Immunotherapy Approaches in Cancer Treatment",
                    "abstract": "Checkpoint inhibitors and CAR-T cell therapy...",
                    "journal": "Nature Medicine",
                    "publication_date": "2024-03-10",
                    "score": 0.92,
                    "distance": 0.08,  # Vector distance
                    "boosted_score": 1.012,  # Quality boost for recent + top journal
                    "quality_boost": 0.1,
                    "content": "Immunotherapy has revolutionized cancer treatment through checkpoint inhibition...",
                    "search_mode": "semantic"
                }
            ]
            
            mock_manager.search_documents.return_value = mock_search_result
            
            # Test semantic search
            result = await rag_search_tool("rag.search", {
                "query": "cancer immunotherapy",
                "search_mode": "semantic",
                "top_k": 3
            })
            
            assert len(result) == 1
            response_text = result[0].text
            
            # Verify semantic search indicators
            assert "Semantic (Vector)" in response_text
            assert "🧠" in response_text  # Semantic mode indicator
            assert "Score: 0.920" in response_text
            assert "1.012" in response_text  # Boosted score shown
            
    @pytest.mark.asyncio
    async def test_search_mode_validation(self):
        """Test that invalid search modes default to hybrid."""
        with patch('src.bio_mcp.rag_tools.get_rag_manager') as mock_get_manager:
            mock_manager = AsyncMock(spec=RAGToolsManager)
            mock_get_manager.return_value = mock_manager
            
            mock_search_result = AsyncMock()
            mock_search_result.query = "test query"
            mock_search_result.total_results = 0
            mock_search_result.search_type = "hybrid"  # Should default to hybrid
            mock_search_result.documents = []
            
            mock_manager.search_documents.return_value = mock_search_result
            
            # Test with invalid search mode
            await rag_search_tool("rag.search", {
                "query": "test query",
                "search_mode": "invalid_mode"  # Should default to hybrid
            })
            
            # Verify manager was called with hybrid mode (default fallback)
            mock_manager.search_documents.assert_called_once_with(
                query="test query",
                top_k=10,
                search_mode="hybrid",  # Should default to this
                rerank_by_quality=True
            )


class TestRAGManagerHybridSearch:
    """Test RAG manager hybrid search implementation."""
    
    @pytest.mark.asyncio
    async def test_quality_boost_algorithm(self):
        """Test the enhanced quality boost algorithm."""
        from datetime import UTC, datetime
        manager = RAGToolsManager()
        
        current_year = datetime.now(UTC).year
        recent_year = current_year  # Current year should get boost
        old_year = current_year - 5  # 5 years ago should not get boost
        
        # Mock search results with different quality indicators
        mock_results = [
            {
                "pmid": "test1",
                "title": "Test Paper 1",
                "journal": "Nature",  # Should get journal boost
                "publication_date": f"{recent_year}-01-01",  # Should get recency boost
                "score": 0.8,
                "quality_total": 5
            },
            {
                "pmid": "test2", 
                "title": "Test Paper 2",
                "journal": "Generic Journal",
                "publication_date": f"{old_year}-01-01",  # Should NOT get recency boost
                "score": 0.85,
                "quality_total": 0
            },
            {
                "pmid": "test3",
                "title": "Test Paper 3", 
                "journal": "Cell",  # Should get journal boost
                "publication_date": f"{old_year}-01-01",  # Should NOT get recency boost
                "score": 0.75,
                "quality_total": 10
            }
        ]
        
        # Apply quality boost
        boosted_results = manager._apply_quality_boost(mock_results.copy())
        
        # Verify boosts were applied correctly
        assert len(boosted_results) == 3
        
        # Test paper 1: Nature journal (0.1) + recent date (0.05) + quality_total/20 (5/20=0.25) = 0.4 total boost
        paper1 = next(r for r in boosted_results if r["pmid"] == "test1")
        expected_boost1 = 0.1 + 0.05 + 0.25  # journal + recency + quality
        assert abs(paper1["quality_boost"] - expected_boost1) < 0.01
        assert abs(paper1["boosted_score"] - (0.8 * (1 + expected_boost1))) < 0.01
        
        # Test paper 2: No boosts (old paper, generic journal, no quality)
        paper2 = next(r for r in boosted_results if r["pmid"] == "test2")
        assert paper2["quality_boost"] == 0
        assert paper2["boosted_score"] == 0.85
        
        # Test paper 3: Cell journal (0.1) + quality_total/20 (10/20=0.5) = 0.6 total boost (no recency boost for old paper)
        paper3 = next(r for r in boosted_results if r["pmid"] == "test3")
        expected_boost3 = 0.1 + 0.5  # journal + quality (no recency for old paper)
        assert abs(paper3["quality_boost"] - expected_boost3) < 0.01
        
        # Results should be sorted by boosted score (descending)
        scores = [r["boosted_score"] for r in boosted_results]
        assert scores == sorted(scores, reverse=True)


class TestSearchModeParameters:
    """Test search mode parameter handling."""
    
    @pytest.mark.asyncio 
    async def test_default_parameters(self):
        """Test that default parameters are applied correctly."""
        with patch('src.bio_mcp.rag_tools.get_rag_manager') as mock_get_manager:
            mock_manager = AsyncMock(spec=RAGToolsManager)
            mock_get_manager.return_value = mock_manager
            
            mock_search_result = AsyncMock()
            mock_search_result.query = "test"
            mock_search_result.total_results = 0
            mock_search_result.search_type = "hybrid"
            mock_search_result.documents = []
            
            mock_manager.search_documents.return_value = mock_search_result
            
            # Test with minimal parameters
            await rag_search_tool("rag.search", {
                "query": "test query"
            })
            
            # Verify defaults were used
            mock_manager.search_documents.assert_called_once_with(
                query="test query",
                top_k=10,  # Default
                search_mode="hybrid",  # Default
                rerank_by_quality=True  # Default
            )
    
    @pytest.mark.asyncio
    async def test_parameter_bounds(self):
        """Test that parameter bounds are enforced.""" 
        with patch('src.bio_mcp.rag_tools.get_rag_manager') as mock_get_manager:
            mock_manager = AsyncMock(spec=RAGToolsManager)
            mock_get_manager.return_value = mock_manager
            
            mock_search_result = AsyncMock()
            mock_search_result.query = "test"
            mock_search_result.total_results = 0
            mock_search_result.search_type = "hybrid"
            mock_search_result.documents = []
            
            mock_manager.search_documents.return_value = mock_search_result
            
            # Test with out-of-bounds top_k
            await rag_search_tool("rag.search", {
                "query": "test query",
                "top_k": 100  # Should be capped at 50
            })
            
            # Verify top_k was capped
            mock_manager.search_documents.assert_called_once_with(
                query="test query",
                top_k=50,  # Should be capped
                search_mode="hybrid",
                rerank_by_quality=True
            )


# Pytest configuration for hybrid search tests
pytestmark = pytest.mark.unit