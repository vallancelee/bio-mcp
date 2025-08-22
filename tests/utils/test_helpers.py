"""
Test helper utilities for Bio-MCP testing.

Provides mock service factories, test data setup utilities, and common
testing patterns for MCP tools.
"""

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

from bio_mcp.mcp.corpus_tools import CheckpointResult
from bio_mcp.mcp.rag_tools import RAGSearchResult
from tests.fixtures.biomedical_test_data import BiomedicTestCorpus


class MockServiceFactory:
    """Factory for creating consistent mock services."""

    @staticmethod
    def create_pubmed_service_mock():
        """Create mock PubMedService with realistic responses."""
        mock_service = AsyncMock()

        # Mock search method
        mock_service.search_papers = AsyncMock(
            return_value={
                "papers": ["36653448", "35987654", "34567890"],
                "count": 3,
                "query": "glioblastoma treatment",
            }
        )

        # Mock get paper method
        test_corpus = BiomedicTestCorpus()
        mock_service.get_paper = AsyncMock(
            side_effect=lambda pmid: next(
                paper.to_document_dict()
                for paper in test_corpus.ALL_PAPERS
                if paper.pmid == pmid
            )
        )

        return mock_service

    @staticmethod
    def create_weaviate_client_mock():
        """Create mock WeaviateClient with search responses."""
        mock_client = AsyncMock()

        # Mock vector search
        mock_client.search = AsyncMock(
            return_value={
                "data": {
                    "Get": {
                        "Document": [
                            {
                                "pmid": "36653448",
                                "title": "Glioblastoma multiforme: pathogenesis and treatment",
                                "score": 0.85,
                                "journal": "Nature Reviews Cancer",
                            },
                            {
                                "pmid": "35987654",
                                "title": "CRISPR-Cas9 gene editing for cancer therapy",
                                "score": 0.78,
                                "journal": "Nature Medicine",
                            },
                        ]
                    }
                }
            }
        )

        # Mock document addition
        mock_client.add_document = AsyncMock(return_value=True)

        # Mock batch operations
        mock_client.batch_add_documents = AsyncMock(
            return_value={"success": True, "added": 10, "failed": 0}
        )

        return mock_client

    @staticmethod
    def create_database_manager_mock():
        """Create mock DatabaseManager with corpus data."""
        mock_manager = AsyncMock()

        # Mock checkpoint operations
        mock_manager.create_checkpoint = AsyncMock(
            return_value=CheckpointResult(
                checkpoint_id="test_checkpoint",
                operation="create",
                success=True,
                execution_time_ms=45.2,
                checkpoint_data={
                    "name": "Test Checkpoint",
                    "description": "Test checkpoint for unit tests",
                    "total_documents": 1500,
                    "last_sync_edat": "2024-01-15",
                    "version": "1.0",
                },
            )
        )

        mock_manager.get_checkpoint = AsyncMock(
            return_value={
                "checkpoint_id": "test_checkpoint",
                "name": "Test Checkpoint",
                "description": "Test checkpoint description",
                "created_at": "2024-01-15T10:00:00Z",
                "document_count": 1500,
            }
        )

        mock_manager.list_checkpoints = AsyncMock(
            return_value={
                "checkpoints": [
                    {
                        "checkpoint_id": "checkpoint_1",
                        "name": "Cancer Research 2024",
                        "document_count": 1200,
                    },
                    {
                        "checkpoint_id": "checkpoint_2",
                        "name": "Immunotherapy Studies",
                        "document_count": 800,
                    },
                ],
                "total": 2,
            }
        )

        mock_manager.delete_checkpoint = AsyncMock(return_value=True)

        return mock_manager

    @staticmethod
    def create_rag_manager_mock():
        """Create mock RAGManager with search responses."""
        mock_manager = AsyncMock()

        # Mock search documents
        test_corpus = BiomedicTestCorpus()
        mock_manager.search_documents = AsyncMock(
            return_value=RAGSearchResult(
                query="cancer immunotherapy",
                total_results=5,
                documents=[
                    paper.to_document_dict() for paper in test_corpus.CANCER_PAPERS[:2]
                ],
                search_type="hybrid",
                performance={"total_time_ms": 150.0, "target_time_ms": 200.0},
            )
        )

        # Mock get document
        mock_manager.get_document = AsyncMock(
            return_value=test_corpus.CANCER_PAPERS[0].to_document_dict()
        )

        return mock_manager


class TestDataSetup:
    """Utilities for setting up test data and environments."""

    @staticmethod
    async def setup_biomedical_corpus(
        weaviate_client, database_manager, paper_count: int = 10
    ):
        """
        Setup biomedical test corpus in test services.

        Args:
            weaviate_client: Weaviate client instance
            database_manager: Database manager instance
            paper_count: Number of papers to add (default 10)
        """
        test_corpus = BiomedicTestCorpus()
        papers = test_corpus.ALL_PAPERS[:paper_count]

        # Add papers to vector store
        for paper in papers:
            await weaviate_client.add_document(paper.to_document_dict())

        # Add papers to database
        for paper in papers:
            await database_manager.store_document(paper.to_document_dict())

    @staticmethod
    def create_test_checkpoint_data() -> dict[str, Any]:
        """Create realistic checkpoint test data."""
        test_corpus = BiomedicTestCorpus()
        return {
            "checkpoint_id": "test_cancer_checkpoint",
            "name": "Cancer Research Test Checkpoint",
            "description": "Test checkpoint for cancer research papers",
            "query": "cancer treatment immunotherapy",
            "documents": [
                paper.to_document_dict() for paper in test_corpus.CANCER_PAPERS
            ],
            "metadata": {
                "total_documents": len(test_corpus.CANCER_PAPERS),
                "creation_date": datetime.now().isoformat(),
                "source": "test_suite",
            },
        }

    @staticmethod
    def create_search_test_scenarios() -> list[dict[str, Any]]:
        """Create comprehensive search test scenarios."""
        return [
            {
                "name": "cancer_treatment_search",
                "query": "glioblastoma treatment",
                "expected_pmids": ["36653448"],
                "search_mode": "hybrid",
                "description": "Brain cancer treatment query",
            },
            {
                "name": "gene_editing_search",
                "query": "CRISPR gene editing cancer",
                "expected_pmids": ["35987654"],
                "search_mode": "semantic",
                "description": "Gene editing technology query",
            },
            {
                "name": "immunotherapy_search",
                "query": "checkpoint inhibitor immunotherapy",
                "expected_pmids": ["33445566"],
                "search_mode": "hybrid",
                "description": "Immunotherapy mechanism query",
            },
            {
                "name": "ai_medicine_search",
                "query": "machine learning medical imaging",
                "expected_pmids": ["31789012"],
                "search_mode": "vector",
                "description": "AI in medicine query",
            },
            {
                "name": "diagnostic_search",
                "query": "liquid biopsy cancer diagnosis",
                "expected_pmids": ["34567890"],
                "search_mode": "bm25",
                "description": "Diagnostic technology query",
            },
        ]


class AsyncTestHelper:
    """Helper for async test operations."""

    @staticmethod
    async def run_with_timeout(coro, timeout_seconds: float = 5.0):
        """
        Run async operation with timeout.

        Args:
            coro: Coroutine to run
            timeout_seconds: Timeout in seconds

        Returns:
            Result of coroutine

        Raises:
            asyncio.TimeoutError: If operation times out
        """
        return await asyncio.wait_for(coro, timeout=timeout_seconds)

    @staticmethod
    async def run_concurrent_operations(operations: list, max_concurrent: int = 5):
        """
        Run multiple async operations concurrently with limit.

        Args:
            operations: List of coroutines to run
            max_concurrent: Maximum concurrent operations

        Returns:
            List of results
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_semaphore(operation):
            async with semaphore:
                return await operation

        tasks = [run_with_semaphore(op) for op in operations]
        return await asyncio.gather(*tasks, return_exceptions=True)


class MCPTestContext:
    """Context manager for MCP tool testing."""

    def __init__(self, mock_services: bool = True):
        """
        Initialize MCP test context.

        Args:
            mock_services: Whether to use mock services (True) or real services (False)
        """
        self.mock_services = mock_services
        self.patches = []
        self.mock_instances = {}

    async def __aenter__(self):
        """Setup test context with mocked services."""
        if self.mock_services:
            # Patch service getters - using correct module paths
            rag_patch = patch("bio_mcp.mcp.rag_tools.RAGToolsManager")
            checkpoint_patch = patch("bio_mcp.mcp.corpus_tools.CorpusCheckpointService")

            # Start patches
            self.mock_instances["rag"] = rag_patch.start()
            self.mock_instances["checkpoint"] = checkpoint_patch.start()

            # Configure mocks with realistic responses
            self.mock_instances[
                "rag"
            ].return_value = MockServiceFactory.create_rag_manager_mock()
            self.mock_instances[
                "checkpoint"
            ].return_value = MockServiceFactory.create_database_manager_mock()

            self.patches = [rag_patch, checkpoint_patch]

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup test context."""
        for patch_instance in self.patches:
            patch_instance.stop()


class PerformanceValidator:
    """Utilities for validating performance requirements."""

    @staticmethod
    def validate_response_time(
        execution_time_ms: float, target_ms: float = 200.0
    ) -> bool:
        """
        Validate response time meets performance targets.

        Args:
            execution_time_ms: Actual execution time in milliseconds
            target_ms: Target time in milliseconds (default 200ms)

        Returns:
            True if performance target is met
        """
        return execution_time_ms <= target_ms

    @staticmethod
    def extract_timing_from_response(response_text: str) -> float | None:
        """
        Extract timing information from MCP response text.

        Args:
            response_text: Text content from MCP response

        Returns:
            Execution time in milliseconds, or None if not found
        """
        import re

        time_match = re.search(r"(\d+\.?\d*)\s*ms", response_text)
        return float(time_match.group(1)) if time_match else None

    @staticmethod
    async def measure_operation_time(operation):
        """
        Measure execution time of async operation.

        Args:
            operation: Async operation to measure

        Returns:
            Tuple of (result, execution_time_ms)
        """
        import time

        start_time = time.time()
        result = await operation
        end_time = time.time()
        execution_time_ms = (end_time - start_time) * 1000
        return result, execution_time_ms
