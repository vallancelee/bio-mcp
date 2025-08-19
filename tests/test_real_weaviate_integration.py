"""
Real integration tests for Weaviate with local transformers.
These tests require Weaviate to be running with the transformers module.

Run with: pytest tests/test_real_weaviate_integration.py -v -s
"""

import asyncio
from datetime import UTC

import pytest
from weaviate.classes.query import Filter

from src.bio_mcp.rag_tools import RAGToolsManager, rag_search_tool
from src.bio_mcp.weaviate_client import get_weaviate_client


class TestRealWeaviateIntegration:
    """Test actual Weaviate operations with local transformers."""
    
    @pytest.mark.asyncio
    async def test_weaviate_connection_and_health(self):
        """Test that Weaviate is accessible and healthy."""
        client = get_weaviate_client()
        
        try:
            await client.initialize()
            
            # Test health check
            health = await client.health_check()
            
            assert health["status"] in ["healthy", "degraded"]
            assert health["ready"] is True
            assert health["collection_exists"] is True
            assert client.url in health["url"]
            
        finally:
            if client.client:
                await client.close()
    
    @pytest.mark.asyncio
    async def test_document_storage_and_retrieval(self):
        """Test storing and retrieving documents with automatic embeddings."""
        client = get_weaviate_client()
        
        try:
            await client.initialize()
            
            # Store a test document
            test_pmid = "test_real_integration_001"
            uuid = await client.store_document(
                pmid=test_pmid,
                title="Local Embeddings Test Document",
                abstract="This document tests the integration of local sentence transformers with Weaviate for biomedical text processing and semantic search capabilities.",
                authors=["Test Author", "Integration Tester"],
                journal="Journal of Test Integration",
                publication_date="2024-08-19",
                doi="10.1000/test.integration.001",
                keywords=["testing", "integration", "embeddings"]
            )
            
            assert uuid is not None
            assert isinstance(uuid, str)
            
            # Verify document exists
            exists = await client.document_exists(test_pmid)
            assert exists is True
            
            # Retrieve the document
            doc = await client.get_document_by_pmid(test_pmid)
            assert doc is not None
            assert doc["pmid"] == test_pmid
            assert doc["title"] == "Local Embeddings Test Document"
            # Weaviate returns datetime objects, so check the date part
            from datetime import datetime
            expected_date = datetime(2024, 8, 19, 0, 0, tzinfo=UTC)
            assert doc["publication_date"] == expected_date
            
        finally:
            # Cleanup: try to remove test document
            try:
                if client.client and client._initialized:
                    collection = client.client.collections.get(client.collection_name)
                    # Delete by PMID filter
                    collection.data.delete_many(
                        where=Filter.by_property("pmid").equal(test_pmid)
                    )
            except Exception:
                pass  # Cleanup is best effort
            
            if client.client:
                await client.close()
    
    @pytest.mark.asyncio
    async def test_semantic_search_functionality(self):
        """Test semantic search with local embeddings."""
        client = get_weaviate_client()
        
        # Test documents with different topics
        test_docs = [
            {
                "pmid": "test_search_001",
                "title": "Cardiovascular Disease Prevention",
                "abstract": "This study examines methods for preventing heart disease through diet and exercise interventions.",
                "keywords": ["cardiology", "prevention", "heart"]
            },
            {
                "pmid": "test_search_002", 
                "title": "Cancer Immunotherapy Research",
                "abstract": "Novel approaches to cancer treatment using immune system modulation and checkpoint inhibitors.",
                "keywords": ["oncology", "immunotherapy", "cancer"]
            },
            {
                "pmid": "test_search_003",
                "title": "Diabetes Management Strategies",
                "abstract": "Comprehensive approaches to managing type 2 diabetes including medication and lifestyle changes.",
                "keywords": ["diabetes", "endocrinology", "management"]
            }
        ]
        
        try:
            await client.initialize()
            
            # Store test documents
            stored_uuids = []
            for doc in test_docs:
                uuid = await client.store_document(
                    pmid=doc["pmid"],
                    title=doc["title"],
                    abstract=doc["abstract"],
                    authors=["Test Author"],
                    journal="Test Journal",
                    publication_date="2024-08-19",
                    keywords=doc["keywords"]
                )
                stored_uuids.append(uuid)
            
            # Wait a moment for indexing
            await asyncio.sleep(1)
            
            # Test semantic searches
            search_tests = [
                ("heart disease prevention", "test_search_001", "cardiology"),
                ("cancer treatment immune", "test_search_002", "immunotherapy"), 
                ("diabetes blood sugar", "test_search_003", "diabetes")
            ]
            
            for query, expected_pmid, expected_topic in search_tests:
                results = await client.search_documents(query, limit=3)
                
                # Should find relevant documents
                assert len(results) > 0, f"No results found for query: {query}"
                
                # Check if the expected document is in results (top result preferred)
                pmids_found = [r.get("pmid") for r in results]
                assert expected_pmid in pmids_found, f"Expected PMID {expected_pmid} not found in results for query: {query}"
                
                # Verify semantic relevance - expected document should be highly ranked
                top_result = results[0]
                assert expected_topic in top_result.get("content", "").lower() or \
                       expected_topic in str(top_result.get("keywords", [])).lower(), \
                       f"Top result not semantically relevant for query: {query}"
            
        finally:
            # Cleanup test documents
            try:
                if client.client and client._initialized:
                    collection = client.client.collections.get(client.collection_name)
                    for doc in test_docs:
                        collection.data.delete_many(
                            where=Filter.by_property("pmid").equal(doc["pmid"])
                        )
            except Exception:
                pass
            
            if client.client:
                await client.close()
    
    @pytest.mark.asyncio
    async def test_embedding_quality_and_similarity(self):
        """Test that semantic similarity works correctly."""
        client = get_weaviate_client()
        
        # Similar documents should have high similarity
        similar_docs = [
            {
                "pmid": "similar_001",
                "title": "Heart Attack Prevention",
                "abstract": "Preventing myocardial infarction through lifestyle modifications and medications."
            },
            {
                "pmid": "similar_002", 
                "title": "Cardiovascular Risk Reduction",
                "abstract": "Reducing the risk of heart disease and stroke through preventive measures."
            },
            {
                "pmid": "different_001",
                "title": "Quantum Computing Applications",
                "abstract": "Advanced quantum algorithms for solving complex computational problems."
            }
        ]
        
        try:
            await client.initialize()
            
            # Store test documents
            for doc in similar_docs:
                await client.store_document(
                    pmid=doc["pmid"],
                    title=doc["title"],
                    abstract=doc["abstract"],
                    authors=["Test Author"],
                    journal="Test Journal",
                    publication_date="2024-08-19"
                )
            
            await asyncio.sleep(1)  # Allow indexing
            
            # Search for cardiovascular content
            results = await client.search_documents("heart disease prevention", limit=3)
            
            assert len(results) >= 2
            
            # The two similar documents should rank higher than the different one
            top_pmids = [r.get("pmid") for r in results[:2]]
            assert "similar_001" in top_pmids or "similar_002" in top_pmids
            
            # The quantum computing document should not be in top results
            if len(results) >= 3:
                assert results[2].get("pmid") == "different_001" or \
                       "different_001" not in [r.get("pmid") for r in results[:2]]
            
        finally:
            # Cleanup
            try:
                if client.client and client._initialized:
                    collection = client.client.collections.get(client.collection_name)
                    for doc in similar_docs:
                        collection.data.delete_many(
                            where=Filter.by_property("pmid").equal(doc["pmid"])
                        )
            except Exception:
                pass
            
            if client.client:
                await client.close()


class TestRAGToolsRealIntegration:
    """Test RAG tools with real Weaviate backend."""
    
    @pytest.mark.asyncio
    async def test_rag_search_tool_real_results(self):
        """Test RAG search tool with real Weaviate data."""
        # First ensure we have some test data
        client = get_weaviate_client()
        
        try:
            await client.initialize()
            
            # Add a test document if collection is empty
            test_pmid = "rag_tool_test_001"
            await client.store_document(
                pmid=test_pmid,
                title="RAG Tool Testing Document",
                abstract="This document is specifically designed to test the RAG search tool functionality with real embeddings.",
                authors=["RAG Tester"],
                journal="RAG Test Journal",
                publication_date="2024-08-19"
            )
            
            await asyncio.sleep(1)  # Allow indexing
            
            # Test the RAG search tool
            result = await rag_search_tool("rag.search", {
                "query": "RAG search tool functionality",
                "top_k": 3
            })
            
            assert len(result) == 1
            response_text = result[0].text
            
            # Should contain search results
            assert "RAG Search Results" in response_text
            assert "Semantic Search" in response_text
            
            # Should find our test document
            assert "RAG Tool Testing Document" in response_text or \
                   test_pmid in response_text or \
                   "found" in response_text.lower()
            
        finally:
            # Cleanup
            try:
                if client.client and client._initialized:
                    collection = client.client.collections.get(client.collection_name)
                    collection.data.delete_many(
                        where=Filter.by_property("pmid").equal(test_pmid)
                    )
            except Exception:
                pass
            
            if client.client:
                await client.close()
    
    @pytest.mark.asyncio
    async def test_rag_manager_search_with_real_data(self):
        """Test RAG manager search functionality."""
        manager = RAGToolsManager()
        
        try:
            # Test search (should work with existing data in the vector store)
            result = await manager.search_documents("biomedical research", top_k=2)
            
            assert isinstance(result.query, str)
            assert result.search_type == "semantic"
            assert isinstance(result.total_results, int)
            assert isinstance(result.documents, list)
            
            # If we have documents in the store, verify structure
            if result.total_results > 0:
                doc = result.documents[0]
                assert "pmid" in doc
                assert "title" in doc
                # Score should be present from Weaviate
                assert "score" in doc or "distance" in doc
            
        finally:
            # RAGToolsManager doesn't need explicit cleanup
            pass


class TestPerformanceWithRealData:
    """Test performance characteristics with real embeddings."""
    
    @pytest.mark.asyncio
    async def test_bulk_storage_performance(self):
        """Test storing multiple documents efficiently."""
        client = get_weaviate_client()
        
        # Create multiple test documents
        test_docs = []
        for i in range(5):  # Small batch for testing
            test_docs.append({
                "pmid": f"perf_test_{i:03d}",
                "title": f"Performance Test Document {i}",
                "abstract": f"This is test document number {i} for testing bulk storage performance and indexing speed.",
                "authors": [f"Author {i}"],
                "journal": "Performance Test Journal"
            })
        
        try:
            await client.initialize()
            
            import time
            start_time = time.time()
            
            # Store documents sequentially (could be optimized with batch operations)
            stored_count = 0
            for doc in test_docs:
                uuid = await client.store_document(
                    pmid=doc["pmid"],
                    title=doc["title"], 
                    abstract=doc["abstract"],
                    authors=doc["authors"],
                    journal=doc["journal"],
                    publication_date="2024-08-19"
                )
                if uuid:
                    stored_count += 1
            
            storage_time = time.time() - start_time
            
            # Verify all documents were stored
            assert stored_count == len(test_docs)
            
            # Performance should be reasonable (adjust threshold as needed)
            avg_time_per_doc = storage_time / len(test_docs)
            assert avg_time_per_doc < 5.0, f"Average storage time too slow: {avg_time_per_doc:.2f}s per document"
            
            # Test search performance
            search_start = time.time()
            results = await client.search_documents("performance test document", limit=5)
            search_time = time.time() - search_start
            
            # Search should be fast
            assert search_time < 2.0, f"Search time too slow: {search_time:.2f}s"
            
            # Should find our test documents
            assert len(results) >= min(5, len(test_docs))
            
        finally:
            # Cleanup
            try:
                if client.client and client._initialized:
                    collection = client.client.collections.get(client.collection_name)
                    for doc in test_docs:
                        collection.data.delete_many(
                            where=Filter.by_property("pmid").equal(doc["pmid"])
                        )
            except Exception:
                pass
            
            if client.client:
                await client.close()


# Pytest configuration for real integration tests
pytestmark = pytest.mark.integration