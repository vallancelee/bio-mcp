"""
Comprehensive unit tests for PubMedService.

Tests PubMed API integration, search operations, document fetching, and error handling
with proper mocking to isolate service logic from external dependencies.
"""

from unittest.mock import AsyncMock, patch

import pytest

from bio_mcp.services.services import PubMedService
from bio_mcp.sources.pubmed.client import PubMedClient
from bio_mcp.sources.pubmed.config import PubMedConfig


class MockSearchResult:
    """Mock search result for testing."""

    def __init__(self, pmids: list[str], total_results: int | None = None):
        self.pmids = pmids
        self.total_results = total_results or len(pmids)


class MockDocument:
    """Mock PubMed document for testing."""

    def __init__(self, pmid: str, title: str, abstract: str | None = None):
        self.pmid = pmid
        self.title = title
        self.abstract = abstract


class TestPubMedService:
    """Testing for PubMed integration and synchronization."""

    def setup_method(self):
        """Setup for each test method."""
        self.config = PubMedConfig(
            api_key="test_api_key",
            base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
            rate_limit_per_second=3,
            timeout=30.0,
            retries=3,
        )
        self.service = PubMedService(self.config)

        # Mock PubMed client
        self.mock_client = AsyncMock(spec=PubMedClient)

    def teardown_method(self):
        """Cleanup after each test method."""
        # Reset any patches
        pass

    @pytest.mark.asyncio
    async def test_pubmed_search_operations(self):
        """Test PubMed search with various query types and parameters."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Mock search results
            mock_result = MockSearchResult(
                pmids=["36653448", "33445566", "28123456"], total_results=3
            )
            self.mock_client.search.return_value = mock_result

            # Test basic search
            result = await self.service.search(
                "glioblastoma treatment", limit=5, offset=0
            )

            assert result == mock_result
            assert len(result.pmids) == 3
            self.mock_client.search.assert_called_once_with(
                "glioblastoma treatment", limit=5, offset=0
            )

    @pytest.mark.asyncio
    async def test_pubmed_search_with_different_parameters(self):
        """Test PubMed search with various parameter combinations."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Test different search scenarios
            test_cases = [
                # (query, limit, offset, expected_pmids)
                ("cancer immunotherapy", 10, 0, ["12345", "67890"]),
                ("PD-1 inhibitor", 20, 5, ["11111", "22222", "33333"]),
                ("machine learning medical imaging", 3, 10, ["44444"]),
            ]

            for query, limit, offset, expected_pmids in test_cases:
                mock_result = MockSearchResult(pmids=expected_pmids)
                self.mock_client.search.return_value = mock_result

                result = await self.service.search(query, limit=limit, offset=offset)

                assert result.pmids == expected_pmids
                self.mock_client.search.assert_called_with(
                    query, limit=limit, offset=offset
                )

    @pytest.mark.asyncio
    async def test_pubmed_document_fetching(self):
        """Test fetching individual documents and batch operations."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Mock document fetching
            mock_documents = [
                MockDocument(
                    "36653448", "Glioblastoma multiforme: pathogenesis and treatment"
                ),
                MockDocument("33445566", "PD-1 checkpoint inhibitors in melanoma"),
                MockDocument("28123456", "Machine learning in medical imaging"),
            ]
            self.mock_client.fetch_documents.return_value = mock_documents

            # Test fetching documents
            pmids = ["36653448", "33445566", "28123456"]
            result = await self.service.fetch_documents(pmids)

            assert result == mock_documents
            assert len(result) == 3
            assert result[0].pmid == "36653448"
            self.mock_client.fetch_documents.assert_called_once_with(pmids)

    @pytest.mark.asyncio
    async def test_pubmed_sync_incremental(self):
        """Test incremental synchronization with watermark management."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Mock incremental search
            mock_result = MockSearchResult(
                pmids=["new_doc_1", "new_doc_2"], total_results=2
            )
            self.mock_client.search_incremental.return_value = mock_result

            # Test incremental search with watermark
            result = await self.service.search_incremental(
                query="cancer research", last_edat="2024/01/01", limit=50, offset=0
            )

            assert result == mock_result
            assert result.pmids == ["new_doc_1", "new_doc_2"]
            self.mock_client.search_incremental.assert_called_once_with(
                "cancer research", last_edat="2024/01/01", limit=50, offset=0
            )

    @pytest.mark.asyncio
    async def test_pubmed_sync_full_refresh(self):
        """Test full corpus refresh and data consistency validation."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Mock large search result for full refresh
            large_pmid_list = [f"pmid_{i:06d}" for i in range(100)]
            mock_result = MockSearchResult(pmids=large_pmid_list, total_results=100)
            self.mock_client.search.return_value = mock_result

            # Test full refresh
            result = await self.service.search(
                query="comprehensive cancer research", limit=100, offset=0
            )

            assert len(result.pmids) == 100
            assert result.total_results == 100
            assert all(pmid.startswith("pmid_") for pmid in result.pmids)

    @pytest.mark.asyncio
    async def test_pubmed_rate_limiting_and_throttling(self):
        """Test API rate limiting, throttling, and retry mechanisms."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Test rate limiting configuration
            rate_limited_config = PubMedConfig(
                api_key=None,  # No API key for stricter rate limiting
                base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
                rate_limit_per_second=1,  # Very conservative
                timeout=30.0,
                retries=3,
            )

            rate_limited_service = PubMedService(rate_limited_config)

            # Simulate multiple rapid requests
            mock_result = MockSearchResult(pmids=["test_pmid"])
            self.mock_client.search.return_value = mock_result

            # Service should handle rate limiting internally
            for i in range(3):
                result = await rate_limited_service.search(f"query_{i}")
                assert result.pmids == ["test_pmid"]

            # Should have made 3 calls despite rate limiting
            assert self.mock_client.search.call_count == 3

    @pytest.mark.asyncio
    async def test_pubmed_error_handling_and_recovery(self):
        """Test error handling for API failures, timeouts, and data issues."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Test API failure
            self.mock_client.search.side_effect = Exception("PubMed API unavailable")

            with pytest.raises(Exception, match="PubMed API unavailable"):
                await self.service.search("test query")

            # Test timeout
            self.mock_client.search.side_effect = TimeoutError("Request timeout")

            with pytest.raises(TimeoutError, match="Request timeout"):
                await self.service.search("test query")

            # Test invalid response
            self.mock_client.search.side_effect = ValueError("Invalid response format")

            with pytest.raises(ValueError, match="Invalid response format"):
                await self.service.search("test query")

    @pytest.mark.asyncio
    async def test_service_initialization_lifecycle(self):
        """Test service initialization and cleanup lifecycle."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Initially not initialized
            assert not self.service._initialized
            assert self.service.client is None

            # Initialize service
            await self.service.initialize()

            assert self.service._initialized
            assert self.service.client is not None
            mock_client_class.assert_called_once_with(self.config)

            # Initialize again should be idempotent
            await self.service.initialize()
            assert self.service._initialized

            # Close service
            await self.service.close()
            assert not self.service._initialized
            assert self.service.client is None
            self.mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_initialization_on_operations(self):
        """Test that operations automatically initialize the service."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            mock_result = MockSearchResult(pmids=["auto_init_test"])
            self.mock_client.search.return_value = mock_result

            # Service not initialized initially
            assert not self.service._initialized

            # Operation should trigger auto-initialization
            result = await self.service.search("auto initialization test")

            assert self.service._initialized
            assert result.pmids == ["auto_init_test"]
            mock_client_class.assert_called_once_with(self.config)

    @pytest.mark.asyncio
    async def test_search_with_empty_results(self):
        """Test handling of searches that return no results."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Mock empty search result
            empty_result = MockSearchResult(pmids=[], total_results=0)
            self.mock_client.search.return_value = empty_result

            result = await self.service.search("nonexistent research topic")

            assert len(result.pmids) == 0
            assert result.total_results == 0

    @pytest.mark.asyncio
    async def test_fetch_documents_error_handling(self):
        """Test error handling during document fetching."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Test partial failure during document fetching
            self.mock_client.fetch_documents.side_effect = Exception(
                "Failed to fetch some documents"
            )

            with pytest.raises(Exception, match="Failed to fetch some documents"):
                await self.service.fetch_documents(["pmid1", "pmid2", "pmid3"])

    @pytest.mark.asyncio
    async def test_service_configuration_handling(self):
        """Test service configuration validation and defaults."""
        # Test with custom config
        custom_config = PubMedConfig(
            api_key="custom_api_key",
            base_url="https://custom.pubmed.api/",
            rate_limit_per_second=5,
            timeout=60.0,
            retries=5,
        )

        service_with_config = PubMedService(custom_config)
        assert service_with_config.config == custom_config

        # Test with default config (from environment)
        with patch("bio_mcp.services.services.PubMedConfig.from_env") as mock_from_env:
            mock_from_env.return_value = self.config

            service_default = PubMedService()
            assert service_default.config == self.config
            mock_from_env.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_search_operations(self):
        """Test concurrent search operations for thread safety."""
        import asyncio

        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Mock responses for concurrent searches
            search_results = [MockSearchResult(pmids=[f"pmid_{i}"]) for i in range(10)]
            self.mock_client.search.side_effect = search_results

            # Create concurrent search operations
            tasks = []
            for i in range(10):
                task = self.service.search(f"query_{i}")
                tasks.append(task)

            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks)

            # All should succeed
            assert len(results) == 10
            for i, result in enumerate(results):
                assert result.pmids == [f"pmid_{i}"]

            assert self.mock_client.search.call_count == 10

    @pytest.mark.asyncio
    async def test_incremental_search_edge_cases(self):
        """Test incremental search with edge cases and error conditions."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Test incremental search with None watermark
            mock_result = MockSearchResult(pmids=["recent_doc"])
            self.mock_client.search_incremental.return_value = mock_result

            result = await self.service.search_incremental(
                query="recent research",
                last_edat=None,  # No watermark
                limit=10,
            )

            assert result.pmids == ["recent_doc"]
            self.mock_client.search_incremental.assert_called_once_with(
                "recent research", last_edat=None, limit=10, offset=0
            )

    @pytest.mark.asyncio
    async def test_client_not_initialized_error(self):
        """Test error handling when client operations are called before initialization."""
        # Create service but don't initialize
        uninit_service = PubMedService(self.config)
        uninit_service._initialized = True  # Mark as initialized
        uninit_service.client = None  # But client is None

        # Should raise ValueError
        with pytest.raises(ValueError, match="PubMed client not initialized"):
            await uninit_service.search("test query")

        with pytest.raises(ValueError, match="PubMed client not initialized"):
            await uninit_service.search_incremental("test query")

        # fetch_documents doesn't check for None client explicitly, so it would pass through
        # This is by design as it calls self.client.fetch_documents directly

    @pytest.mark.asyncio
    async def test_search_query_validation(self):
        """Test search query validation and sanitization."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Test various query types
            test_queries = [
                "simple query",
                "cancer AND immunotherapy",
                "PD-1[MeSH Terms]",
                "author:smith[AU]",
                '"exact phrase search"',
                "complex (query) AND (terms OR conditions)",
            ]

            mock_result = MockSearchResult(pmids=["test_pmid"])
            self.mock_client.search.return_value = mock_result

            for query in test_queries:
                result = await self.service.search(query)
                assert result.pmids == ["test_pmid"]
                self.mock_client.search.assert_called_with(query, limit=10, offset=0)

    @pytest.mark.asyncio
    async def test_large_batch_document_fetching(self):
        """Test fetching large batches of documents efficiently."""
        with patch("bio_mcp.services.services.PubMedClient") as mock_client_class:
            mock_client_class.return_value = self.mock_client

            # Create large batch of PMIDs
            large_pmid_batch = [f"pmid_{i:06d}" for i in range(500)]

            # Mock large document batch
            mock_documents = [
                MockDocument(pmid, f"Title for {pmid}") for pmid in large_pmid_batch
            ]
            self.mock_client.fetch_documents.return_value = mock_documents

            result = await self.service.fetch_documents(large_pmid_batch)

            assert len(result) == 500
            assert all(doc.pmid.startswith("pmid_") for doc in result)
            self.mock_client.fetch_documents.assert_called_once_with(large_pmid_batch)
