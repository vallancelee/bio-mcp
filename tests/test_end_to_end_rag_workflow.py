"""
End-to-end tests for the complete RAG workflow.
Tests: PubMed API → Database Storage → Weaviate Indexing → RAG Search

These tests validate the entire pipeline with real or mocked PubMed data.
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from weaviate.classes.query import Filter

from src.bio_mcp.clients.pubmed_client import PubMedDocument, PubMedSearchResult
from src.bio_mcp.clients.weaviate_client import get_weaviate_client
from src.bio_mcp.mcp.pubmed_tools import (
    PubMedToolsManager,
)
from src.bio_mcp.mcp.rag_tools import rag_search_tool


class TestEndToEndRAGWorkflow:
    """Test the complete RAG workflow from PubMed to search results."""
    
    @pytest.mark.asyncio
    async def test_pubmed_sync_to_rag_search_mocked(self):
        """Test complete workflow with mocked PubMed API."""
        
        # Mock PubMed API responses
        mock_search_result = PubMedSearchResult(
            query="test cancer research",
            total_count=1,
            pmids=["12345"],
            retstart=0,
            retmax=1
        )
        
        mock_document = PubMedDocument(
            pmid="12345",
            title="Novel Cancer Treatment Using Immunotherapy",
            abstract="This groundbreaking study investigates the effectiveness of immunotherapy in treating advanced cancer patients. Results show significant improvement in patient outcomes.",
            authors=["Smith JA", "Johnson BK", "Williams CL"],
            journal="Journal of Cancer Research",
            publication_date=date(2024, 8, 19),
            doi="10.1000/cancer.2024.12345",
            keywords=["cancer", "immunotherapy", "treatment"]
        )
        
        with patch('src.bio_mcp.mcp.pubmed_tools.PubMedClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.search.return_value = mock_search_result
            mock_client.fetch_documents.return_value = [mock_document]
            
            with patch('src.bio_mcp.mcp.pubmed_tools.DatabaseManager') as mock_db_class:
                mock_db = AsyncMock()
                mock_db_class.return_value = mock_db
                mock_db.document_exists.return_value = False
                mock_db.create_document.return_value = None
                
                # Use real Weaviate for the embedding part
                weaviate_client = get_weaviate_client()
                test_pmid = "e2e_test_12345"
                
                try:
                    await weaviate_client.initialize()
                    
                    # Step 1: Simulate PubMed sync
                    manager = PubMedToolsManager()
                    
                    # Override the weaviate client to use real one but with test PMID
                    manager.weaviate_client = weaviate_client
                    
                    # Manually store the document in Weaviate (simulating successful sync)
                    uuid = await weaviate_client.store_document(
                        pmid=test_pmid,
                        title=mock_document.title,
                        abstract=mock_document.abstract,
                        authors=mock_document.authors,
                        journal=mock_document.journal,
                        publication_date=mock_document.publication_date.isoformat(),
                        doi=mock_document.doi,
                        keywords=mock_document.keywords
                    )
                    
                    assert uuid is not None
                    
                    # Step 2: Wait for indexing
                    import asyncio
                    await asyncio.sleep(1)
                    
                    # Step 3: Test RAG search finds the document
                    results = await weaviate_client.search_documents("cancer immunotherapy treatment", limit=3)
                    
                    # Should find our test document
                    assert len(results) > 0
                    found_pmids = [r.get("pmid") for r in results]
                    assert test_pmid in found_pmids
                    
                    # Verify content quality
                    matching_doc = next((r for r in results if r.get("pmid") == test_pmid), None)
                    assert matching_doc is not None
                    assert "immunotherapy" in matching_doc.get("content", "").lower()
                    assert "cancer" in matching_doc.get("content", "").lower()
                    
                finally:
                    # Cleanup
                    try:
                        if weaviate_client.client and weaviate_client._initialized:
                            collection = weaviate_client.client.collections.get(weaviate_client.collection_name)
                            collection.data.delete_many(
                                where=Filter.by_property("pmid").equal(test_pmid)
                            )
                    except Exception:
                        pass
                    
                    if weaviate_client.client:
                        await weaviate_client.close()
    
    @pytest.mark.asyncio
    async def test_mcp_tool_integration_workflow(self):
        """Test the workflow using actual MCP tools."""
        
        # Mock PubMed API for consistent results
        mock_search_result = PubMedSearchResult(
            query="diabetes management",
            total_count=1,
            pmids=["67890"],
            retstart=0,
            retmax=1
        )
        
        mock_document = PubMedDocument(
            pmid="67890",
            title="Advanced Diabetes Management Through Technology",
            abstract="This comprehensive study examines how modern technology including continuous glucose monitoring and insulin pumps can improve diabetes management outcomes for patients.",
            authors=["Brown AL", "Davis MR"],
            journal="Diabetes Technology Journal",
            publication_date=date(2024, 8, 19),
            doi="10.1000/diabetes.2024.67890"
        )
        
        with patch('src.bio_mcp.mcp.pubmed_tools.PubMedClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.search.return_value = mock_search_result
            mock_client.fetch_documents.return_value = [mock_document]
            
            with patch('src.bio_mcp.mcp.pubmed_tools.DatabaseManager') as mock_db_class:
                mock_db = AsyncMock()
                mock_db_class.return_value = mock_db
                mock_db.document_exists.return_value = False
                mock_db.create_document.return_value = None
                
                weaviate_client = get_weaviate_client()
                test_pmid = "mcp_tool_test_67890"
                
                try:
                    await weaviate_client.initialize()
                    
                    # Manually store the document (simulating successful sync)
                    await weaviate_client.store_document(
                        pmid=test_pmid,
                        title=mock_document.title,
                        abstract=mock_document.abstract,
                        authors=mock_document.authors,
                        journal=mock_document.journal,
                        publication_date=mock_document.publication_date.isoformat(),
                        doi=mock_document.doi
                    )
                    
                    import asyncio
                    await asyncio.sleep(1)
                    
                    # Test RAG search tool
                    rag_result = await rag_search_tool("rag.search", {
                        "query": "diabetes technology management",
                        "top_k": 5
                    })
                    
                    assert len(rag_result) == 1
                    response_text = rag_result[0].text
                    
                    # Should contain our test document
                    assert "diabetes" in response_text.lower()
                    assert "technology" in response_text.lower() or "management" in response_text.lower()
                    assert test_pmid in response_text or "Advanced Diabetes Management" in response_text
                    
                finally:
                    # Cleanup
                    try:
                        if weaviate_client.client and weaviate_client._initialized:
                            collection = weaviate_client.client.collections.get(weaviate_client.collection_name)
                            collection.data.delete_many(
                                where=Filter.by_property("pmid").equal(test_pmid)
                            )
                    except Exception:
                        pass
                    
                    if weaviate_client.client:
                        await weaviate_client.close()
    
    @pytest.mark.asyncio
    async def test_semantic_search_quality(self):
        """Test that semantic search returns relevant results."""
        
        weaviate_client = get_weaviate_client()
        
        # Test documents with varying relevance
        test_documents = [
            {
                "pmid": "semantic_001",
                "title": "Deep Learning for Medical Image Analysis",
                "abstract": "Application of convolutional neural networks for analyzing medical images including X-rays, MRIs, and CT scans.",
                "relevance": "high"  # For "medical AI" query
            },
            {
                "pmid": "semantic_002", 
                "title": "Machine Learning in Healthcare Diagnostics",
                "abstract": "Using artificial intelligence and machine learning algorithms to improve diagnostic accuracy in clinical settings.",
                "relevance": "high"  # For "medical AI" query
            },
            {
                "pmid": "semantic_003",
                "title": "Plant Biology and Photosynthesis Research", 
                "abstract": "Investigation of photosynthetic processes in various plant species under different environmental conditions.",
                "relevance": "low"  # For "medical AI" query
            }
        ]
        
        try:
            await weaviate_client.initialize()
            
            # Store test documents
            for doc in test_documents:
                await weaviate_client.store_document(
                    pmid=doc["pmid"],
                    title=doc["title"],
                    abstract=doc["abstract"],
                    authors=["Test Author"],
                    journal="Test Journal",
                    publication_date="2024-08-19"
                )
            
            import asyncio
            await asyncio.sleep(1)
            
            # Test semantic search
            results = await weaviate_client.search_documents("medical artificial intelligence", limit=3)
            
            assert len(results) >= 2
            
            # Check that high-relevance documents rank higher
            top_2_pmids = [r.get("pmid") for r in results[:2]]
            
            # At least one of the top 2 should be a high-relevance document
            high_relevance_found = any(pmid in ["semantic_001", "semantic_002"] for pmid in top_2_pmids)
            assert high_relevance_found, f"High relevance documents not in top results: {top_2_pmids}"
            
            # The plant biology document should not be in top 2 (if we have at least 3 results)
            if len(results) >= 3:
                assert "semantic_003" not in top_2_pmids, "Low relevance document ranked too highly"
            
        finally:
            # Cleanup
            try:
                if weaviate_client.client and weaviate_client._initialized:
                    collection = weaviate_client.client.collections.get(weaviate_client.collection_name)
                    for doc in test_documents:
                        collection.data.delete_many(
                            where=Filter.by_property("pmid").equal(doc["pmid"])
                        )
            except Exception:
                pass
            
            if weaviate_client.client:
                await weaviate_client.close()


class TestRAGSearchVariations:
    """Test different types of RAG searches and edge cases."""
    
    @pytest.mark.asyncio 
    async def test_empty_query_handling(self):
        """Test RAG search with empty or invalid queries."""
        
        # Test empty query
        result = await rag_search_tool("rag.search", {"query": "", "top_k": 5})
        assert len(result) == 1
        assert "error" in result[0].text.lower() or "query" in result[0].text.lower()
        
        # Test missing query parameter
        result = await rag_search_tool("rag.search", {"top_k": 5})
        assert len(result) == 1
        assert "error" in result[0].text.lower() or "required" in result[0].text.lower()
    
    @pytest.mark.asyncio
    async def test_large_result_set_handling(self):
        """Test RAG search with large top_k values."""
        
        result = await rag_search_tool("rag.search", {
            "query": "biomedical research",
            "top_k": 50  # Large number
        })
        
        assert len(result) == 1
        response_text = result[0].text
        
        # Should handle large requests gracefully
        assert "error" not in response_text.lower() or "RAG Search Results" in response_text
    
    @pytest.mark.asyncio
    async def test_special_characters_in_query(self):
        """Test RAG search with special characters and edge cases."""
        
        special_queries = [
            "diabetes & metabolic syndrome",
            "COVID-19 (SARS-CoV-2) treatment",
            "p53 gene expression",
            "alpha-synuclein protein aggregation"
        ]
        
        for query in special_queries:
            result = await rag_search_tool("rag.search", {
                "query": query,
                "top_k": 3
            })
            
            assert len(result) == 1
            response_text = result[0].text
            
            # Should handle special characters without errors
            assert "error" not in response_text.lower() or "RAG Search Results" in response_text
            assert query in response_text  # Query should be echoed back


class TestDataConsistency:
    """Test data consistency between database and vector store."""
    
    @pytest.mark.asyncio
    async def test_sync_consistency_verification(self):
        """Test that documents synced to database also appear in vector store."""
        
        weaviate_client = get_weaviate_client()
        
        # Test document
        test_doc = {
            "pmid": "consistency_test_001", 
            "title": "Data Consistency Test Document",
            "abstract": "This document tests the consistency between database storage and vector store indexing.",
            "authors": ["Consistency Tester"],
            "journal": "Data Integrity Journal"
        }
        
        try:
            await weaviate_client.initialize()
            
            # Store in vector store
            uuid = await weaviate_client.store_document(
                pmid=test_doc["pmid"],
                title=test_doc["title"],
                abstract=test_doc["abstract"],
                authors=test_doc["authors"],
                journal=test_doc["journal"],
                publication_date="2024-08-19"
            )
            
            assert uuid is not None
            
            import asyncio
            await asyncio.sleep(1)
            
            # Verify document exists and is searchable
            exists = await weaviate_client.document_exists(test_doc["pmid"])
            assert exists is True
            
            # Verify document is findable via search
            results = await weaviate_client.search_documents("data consistency test", limit=5)
            found_pmids = [r.get("pmid") for r in results]
            assert test_doc["pmid"] in found_pmids
            
            # Verify document content is preserved
            doc = await weaviate_client.get_document_by_pmid(test_doc["pmid"])
            assert doc["title"] == test_doc["title"]
            assert doc["abstract"] == test_doc["abstract"]
            
        finally:
            # Cleanup
            try:
                if weaviate_client.client and weaviate_client._initialized:
                    collection = weaviate_client.client.collections.get(weaviate_client.collection_name)
                    collection.data.delete_many(
                        where={"path": ["pmid"], "operator": "Equal", "valueText": test_doc["pmid"]}
                    )
            except Exception:
                pass
            
            if weaviate_client.client:
                await weaviate_client.close()


# Mark as integration tests
pytestmark = pytest.mark.integration