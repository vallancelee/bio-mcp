"""
Integration testing across multiple services.

Tests cross-service workflows, error propagation, service coordination,
and realistic scenarios that involve multiple service interactions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bio_mcp.services.services import (
    CorpusCheckpointService,
    DocumentService,
    PubMedService,
    SyncOrchestrator,
    VectorService,
)
from bio_mcp.shared.clients.database import DatabaseConfig
from bio_mcp.sources.pubmed.config import PubMedConfig


class MockSearchResult:
    """Mock search result for testing."""

    def __init__(self, pmids: list[str], total_results: int = None):
        self.pmids = pmids
        self.total_results = total_results or len(pmids)


class MockDocument:
    """Mock PubMed document for testing."""

    def __init__(self, pmid: str, title: str, abstract: str = None):
        self.pmid = pmid
        self.title = title
        self.abstract = abstract
        self.authors = ["Smith, J.", "Johnson, A."]
        self.journal = "Nature Medicine"
        self.publication_date = None
        self.doi = f"10.1038/nm.{pmid}"
        self.keywords = ["cancer", "research"]

    def to_database_format(self):
        """Convert to database format."""
        return {
            "pmid": self.pmid,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "journal": self.journal,
            "publication_date": self.publication_date,
            "doi": self.doi,
            "keywords": self.keywords,
        }


class TestServicesIntegration:
    """Integration testing across multiple services."""

    def setup_method(self):
        """Setup for each test method."""
        self.db_config = DatabaseConfig(
            url="postgresql+asyncpg://test_user:test_pass@test_host:5432/test_db",
            pool_size=5,
            max_overflow=10,
            pool_timeout=30.0,
            echo=False,
        )

        self.pubmed_config = PubMedConfig(
            api_key="test_api_key",
            base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
            rate_limit_per_second=3,
            timeout=30.0,
            retries=3,
        )

    def teardown_method(self):
        """Cleanup after each test method."""
        pass

    @pytest.mark.asyncio
    async def test_document_to_checkpoint_workflow(self):
        """Test complete workflow: PubMed sync → Document storage → Checkpoint creation."""

        # Mock all services
        with (
            patch("bio_mcp.services.services.DatabaseManager") as mock_db_mgr,
            patch("bio_mcp.services.services.PubMedClient") as mock_pubmed_client,
            patch("bio_mcp.services.services.get_weaviate_client") as mock_weaviate,
        ):
            # Setup service mocks
            mock_db = AsyncMock()
            mock_db_mgr.return_value = mock_db

            mock_pubmed = AsyncMock()
            mock_pubmed_client.return_value = mock_pubmed

            mock_vector_client = AsyncMock()
            mock_weaviate.return_value = mock_vector_client

            # Create services
            document_service = DocumentService(self.db_config)
            checkpoint_service = CorpusCheckpointService(self.db_config)
            pubmed_service = PubMedService(self.pubmed_config)

            # === Phase 1: Search PubMed ===
            mock_search_result = MockSearchResult(["12345", "67890", "11111"])
            mock_pubmed.search.return_value = mock_search_result

            search_result = await pubmed_service.search(
                "glioblastoma treatment", limit=10
            )
            assert len(search_result.pmids) == 3

            # === Phase 2: Check existing documents ===
            mock_db.document_exists.side_effect = [
                False,
                False,
                True,
            ]  # Two new, one exists

            new_pmids = []
            for pmid in search_result.pmids:
                exists = await document_service.document_exists(pmid)
                if not exists:
                    new_pmids.append(pmid)

            assert new_pmids == ["12345", "67890"]  # 11111 already exists

            # === Phase 3: Fetch and store new documents ===
            mock_documents = [
                MockDocument("12345", "New Glioblastoma Research"),
                MockDocument("67890", "Immunotherapy for Brain Tumors"),
            ]
            mock_pubmed.fetch_documents.return_value = mock_documents

            documents = await pubmed_service.fetch_documents(new_pmids)
            assert len(documents) == 2

            # Store documents
            for doc in documents:
                await document_service.create_document(doc.to_database_format())

            # Verify document creation calls
            assert mock_db.create_document.call_count == 2

            # === Phase 4: Create checkpoint for this research ===
            mock_checkpoint = MagicMock()
            mock_checkpoint.checkpoint_id = "glioblastoma_research_2024"
            mock_db.create_corpus_checkpoint.return_value = mock_checkpoint

            checkpoint = await checkpoint_service.create_checkpoint(
                checkpoint_id="glioblastoma_research_2024",
                name="Glioblastoma Research 2024",
                description="Research checkpoint for glioblastoma treatment studies",
                primary_queries=["glioblastoma treatment"],
            )

            assert checkpoint.checkpoint_id == "glioblastoma_research_2024"
            mock_db.create_corpus_checkpoint.assert_called_once()

    @pytest.mark.asyncio
    async def test_cross_service_error_propagation(self):
        """Test error handling and rollback across service boundaries."""

        with (
            patch("bio_mcp.services.services.DatabaseManager") as mock_db_mgr,
            patch("bio_mcp.services.services.PubMedClient") as mock_pubmed_client,
        ):
            mock_db = AsyncMock()
            mock_db_mgr.return_value = mock_db

            mock_pubmed = AsyncMock()
            mock_pubmed_client.return_value = mock_pubmed

            document_service = DocumentService(self.db_config)
            pubmed_service = PubMedService(self.pubmed_config)

            # === Test 1: PubMed search failure ===
            mock_pubmed.search.side_effect = Exception("PubMed API unavailable")

            with pytest.raises(Exception, match="PubMed API unavailable"):
                await pubmed_service.search("test query")

            # === Test 2: Document storage failure ===
            mock_search_result = MockSearchResult(["12345"])
            mock_pubmed.search.return_value = mock_search_result
            mock_pubmed.search.side_effect = None  # Clear previous side effect

            # PubMed search succeeds
            search_result = await pubmed_service.search("test query")
            assert len(search_result.pmids) == 1

            # But document storage fails
            mock_db.create_document.side_effect = Exception("Database connection lost")

            with pytest.raises(Exception, match="Database connection lost"):
                await document_service.create_document(
                    {"pmid": "12345", "title": "Test"}
                )

            # === Test 3: Service initialization failure ===
            # Create a fresh service to test initialization failure
            fresh_document_service = DocumentService(self.db_config)
            mock_db.initialize.side_effect = Exception("Database unavailable")

            with pytest.raises(Exception, match="Database unavailable"):
                await fresh_document_service.initialize()

    @pytest.mark.asyncio
    async def test_service_initialization_and_dependencies(self):
        """Test service startup, dependency injection, and health validation."""

        with (
            patch("bio_mcp.services.services.DatabaseManager") as mock_db_mgr,
            patch("bio_mcp.services.services.PubMedClient") as mock_pubmed_client,
            patch("bio_mcp.services.services.get_weaviate_client") as mock_weaviate,
        ):
            # Setup mocks
            mock_db = AsyncMock()
            mock_db_mgr.return_value = mock_db

            mock_pubmed = AsyncMock()
            mock_pubmed_client.return_value = mock_pubmed

            mock_vector_client = AsyncMock()
            mock_weaviate.return_value = mock_vector_client

            # Create services
            document_service = DocumentService(self.db_config)
            checkpoint_service = CorpusCheckpointService(self.db_config)
            pubmed_service = PubMedService(self.pubmed_config)
            vector_service = VectorService()

            # Test individual service initialization
            services = [
                document_service,
                checkpoint_service,
                pubmed_service,
                vector_service,
            ]

            for service in services:
                assert not service._initialized
                await service.initialize()
                assert service._initialized

            # Test service health checks through operations
            mock_db.document_exists.return_value = True
            result = await document_service.document_exists("test_pmid")
            assert result is True

            mock_checkpoint = MagicMock()
            mock_db.get_corpus_checkpoint.return_value = mock_checkpoint
            checkpoint = await checkpoint_service.get_checkpoint("test_checkpoint")
            assert checkpoint == mock_checkpoint

            mock_search_result = MockSearchResult(["test_pmid"])
            mock_pubmed.search.return_value = mock_search_result
            search_result = await pubmed_service.search("test query")
            assert len(search_result.pmids) == 1

            # Test service cleanup
            for service in services:
                await service.close()
                assert not service._initialized

    @pytest.mark.asyncio
    async def test_concurrent_service_operations(self):
        """Test concurrent operations across multiple services."""
        import asyncio

        with (
            patch("bio_mcp.services.services.DatabaseManager") as mock_db_mgr,
            patch("bio_mcp.services.services.PubMedClient") as mock_pubmed_client,
        ):
            mock_db = AsyncMock()
            mock_db_mgr.return_value = mock_db

            mock_pubmed = AsyncMock()
            mock_pubmed_client.return_value = mock_pubmed

            # Create multiple service instances
            document_services = [DocumentService(self.db_config) for _ in range(3)]
            pubmed_services = [PubMedService(self.pubmed_config) for _ in range(3)]

            # Mock responses
            mock_db.document_exists.return_value = True
            mock_search_result = MockSearchResult(["concurrent_test"])
            mock_pubmed.search.return_value = mock_search_result

            # Create concurrent tasks
            doc_tasks = [
                service.document_exists(f"pmid_{i}")
                for i, service in enumerate(document_services)
            ]
            search_tasks = [
                service.search(f"query_{i}")
                for i, service in enumerate(pubmed_services)
            ]

            # Execute all tasks concurrently
            all_tasks = doc_tasks + search_tasks
            results = await asyncio.gather(*all_tasks)

            # Verify all operations completed
            assert len(results) == 6

            # Check document existence results
            for i in range(3):
                assert results[i] is True

            # Check search results
            for i in range(3, 6):
                assert len(results[i].pmids) == 1

    @pytest.mark.asyncio
    async def test_sync_orchestrator_integration(self):
        """Test the SyncOrchestrator that coordinates multiple services."""

        with (
            patch("bio_mcp.services.services.DatabaseManager") as mock_db_mgr,
            patch("bio_mcp.services.services.PubMedClient") as mock_pubmed_client,
            patch("bio_mcp.services.services.get_weaviate_client") as mock_weaviate,
        ):
            # Setup mocks
            mock_db = AsyncMock()
            mock_db_mgr.return_value = mock_db

            mock_pubmed = AsyncMock()
            mock_pubmed_client.return_value = mock_pubmed

            mock_vector_client = AsyncMock()
            mock_weaviate.return_value = mock_vector_client

            # Create orchestrator
            orchestrator = SyncOrchestrator()

            # Mock search results
            mock_search_result = MockSearchResult(["orch_1", "orch_2", "orch_3"])
            mock_pubmed.search.return_value = mock_search_result

            # Mock document existence checks
            mock_db.document_exists.side_effect = [
                False,
                True,
                False,
            ]  # 2 new, 1 existing

            # Mock document fetching
            mock_documents = [
                MockDocument("orch_1", "Orchestrator Test 1"),
                MockDocument("orch_3", "Orchestrator Test 3"),
            ]
            mock_pubmed.fetch_documents.return_value = mock_documents

            # Mock vector storage
            mock_vector_client.store_document.return_value = "vector_id"

            # Execute orchestrated sync
            result = await orchestrator.sync_documents("orchestrator test", limit=5)

            # Verify result structure
            assert "total_requested" in result
            assert "successfully_synced" in result
            assert "already_existed" in result
            assert "failed" in result
            assert "pmids_synced" in result
            assert "pmids_failed" in result

            # Verify the sync process worked
            assert result["total_requested"] == 3
            assert result["already_existed"] == 1  # orch_2 existed

            # Verify service interactions
            mock_pubmed.search.assert_called_once_with(
                "orchestrator test", limit=5, offset=0
            )
            assert mock_db.document_exists.call_count == 3
            mock_pubmed.fetch_documents.assert_called_once_with(["orch_1", "orch_3"])

    @pytest.mark.asyncio
    async def test_error_recovery_strategies(self):
        """Test error recovery mechanisms across service boundaries."""

        with (
            patch("bio_mcp.services.services.DatabaseManager") as mock_db_mgr,
            patch("bio_mcp.services.services.PubMedClient") as mock_pubmed_client,
        ):
            mock_db = AsyncMock()
            mock_db_mgr.return_value = mock_db

            mock_pubmed = AsyncMock()
            mock_pubmed_client.return_value = mock_pubmed

            document_service = DocumentService(self.db_config)
            pubmed_service = PubMedService(self.pubmed_config)

            # === Test retry behavior ===

            # First call fails, second succeeds
            mock_db.document_exists.side_effect = [
                Exception("Temporary database error"),
                True,
            ]

            # First call should fail
            with pytest.raises(Exception, match="Temporary database error"):
                await document_service.document_exists("retry_test")

            # Reset side effect for second call
            mock_db.document_exists.side_effect = None
            mock_db.document_exists.return_value = True

            # Second call should succeed
            result = await document_service.document_exists("retry_test")
            assert result is True

            # === Test graceful degradation ===

            # PubMed search fails, but we can still work with existing data
            mock_pubmed.search.side_effect = Exception("PubMed temporarily unavailable")

            with pytest.raises(Exception, match="PubMed temporarily unavailable"):
                await pubmed_service.search("degradation test")

            # But document operations should still work
            mock_doc = {"pmid": "existing_doc", "title": "Existing Document"}
            mock_db.create_document.return_value = None

            await document_service.create_document(mock_doc)
            mock_db.create_document.assert_called_with(mock_doc)

    @pytest.mark.asyncio
    async def test_data_consistency_across_services(self):
        """Test data consistency when multiple services modify shared state."""

        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_mgr:
            mock_db = AsyncMock()
            mock_db_mgr.return_value = mock_db

            # Create multiple service instances that share the database
            document_service_1 = DocumentService(self.db_config)
            document_service_2 = DocumentService(self.db_config)
            checkpoint_service = CorpusCheckpointService(self.db_config)

            # === Test document creation consistency ===

            # Service 1 creates a document
            mock_doc_1 = {"pmid": "consistency_test_1", "title": "Consistency Test 1"}
            await document_service_1.create_document(mock_doc_1)

            # Service 2 should see the document exists
            mock_db.document_exists.return_value = True
            exists = await document_service_2.document_exists("consistency_test_1")
            assert exists is True

            # === Test checkpoint-document relationship consistency ===

            # Create checkpoint referencing documents
            mock_checkpoint = MagicMock()
            mock_checkpoint.checkpoint_id = "consistency_checkpoint"
            mock_db.create_corpus_checkpoint.return_value = mock_checkpoint

            checkpoint = await checkpoint_service.create_checkpoint(
                checkpoint_id="consistency_checkpoint",
                name="Consistency Test Checkpoint",
                description="Testing data consistency across services",
            )

            # Both services should see consistent state
            mock_db.get_corpus_checkpoint.return_value = mock_checkpoint
            retrieved_checkpoint = await checkpoint_service.get_checkpoint(
                "consistency_checkpoint"
            )
            assert retrieved_checkpoint.checkpoint_id == "consistency_checkpoint"

    @pytest.mark.asyncio
    async def test_service_health_monitoring(self):
        """Test health monitoring and status checking across services."""

        with (
            patch("bio_mcp.services.services.DatabaseManager") as mock_db_mgr,
            patch("bio_mcp.services.services.PubMedClient") as mock_pubmed_client,
        ):
            mock_db = AsyncMock()
            mock_db_mgr.return_value = mock_db

            mock_pubmed = AsyncMock()
            mock_pubmed_client.return_value = mock_pubmed

            # Create services
            services = {
                "document": DocumentService(self.db_config),
                "checkpoint": CorpusCheckpointService(self.db_config),
                "pubmed": PubMedService(self.pubmed_config),
            }

            # Test health checks through basic operations
            health_status = {}

            # Document service health
            try:
                mock_db.document_exists.return_value = True
                await services["document"].document_exists("health_check")
                health_status["document"] = "healthy"
            except Exception as e:
                health_status["document"] = f"unhealthy: {e}"

            # Checkpoint service health
            try:
                mock_db.list_corpus_checkpoints.return_value = []
                await services["checkpoint"].list_checkpoints(limit=1)
                health_status["checkpoint"] = "healthy"
            except Exception as e:
                health_status["checkpoint"] = f"unhealthy: {e}"

            # PubMed service health
            try:
                mock_search_result = MockSearchResult(["health_check"])
                mock_pubmed.search.return_value = mock_search_result
                await services["pubmed"].search("health check", limit=1)
                health_status["pubmed"] = "healthy"
            except Exception as e:
                health_status["pubmed"] = f"unhealthy: {e}"

            # All services should be healthy
            assert all(status == "healthy" for status in health_status.values())

            # Test degraded health scenario
            mock_db.document_exists.side_effect = Exception("Database slow")

            try:
                await services["document"].document_exists("health_check_degraded")
                health_status["document"] = "healthy"
            except Exception as e:
                health_status["document"] = f"unhealthy: {e!s}"

            assert "Database slow" in health_status["document"]
