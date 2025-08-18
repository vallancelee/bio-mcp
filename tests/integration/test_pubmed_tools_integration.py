"""
Integration tests for PubMed tools with real PostgreSQL database.
Phase 3A: Basic Biomedical Tools - End-to-end testing with testcontainers.
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from bio_mcp.database import DatabaseConfig
from bio_mcp.pubmed_client import PubMedConfig, PubMedDocument, PubMedSearchResult
from bio_mcp.pubmed_tools import (
    PubMedToolsManager,
    pubmed_get_tool,
    pubmed_sync_tool,
)


@pytest.fixture(scope="session")
def postgres_container():
    """Provide a PostgreSQL testcontainer for integration testing."""
    with PostgresContainer(
        image="postgres:15-alpine",
        port=5432,
        username="testuser",
        password="testpass",
        dbname="testdb",
    ) as postgres:
        # Convert to async connection URL
        sync_url = postgres.get_connection_url()
        async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")

        yield {"url": async_url, "sync_url": sync_url, "container": postgres}


@pytest_asyncio.fixture
async def tools_manager(postgres_container):
    """Provide a configured PubMedToolsManager for testing."""
    # Create configs with test database
    pubmed_config = PubMedConfig(api_key="test_key")
    db_config = DatabaseConfig(url=postgres_container["url"], echo=False)

    manager = PubMedToolsManager()

    # Mock the config creation to use our test configs
    with (
        patch("bio_mcp.pubmed_tools.PubMedConfig.from_env", return_value=pubmed_config),
        patch("bio_mcp.pubmed_tools.DatabaseConfig.from_env", return_value=db_config),
    ):
        await manager.initialize()

        yield manager

        await manager.close()


class TestPubMedDatabaseOperations:
    """Test core database operations with real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_document_storage_and_retrieval(self, tools_manager):
        """Test storing and retrieving documents from database."""
        # Store a document
        doc_data = {
            "pmid": "db_test_001",
            "title": "Database Test Article",
            "abstract": "This is a database integration test.",
            "authors": ["DB Author"],
            "journal": "Integration Journal",
            "publication_date": date(2023, 12, 1),
            "doi": "10.1000/db.001",
            "keywords": ["database", "test"],
        }

        await tools_manager.database_manager.create_document(doc_data)

        # Retrieve the document
        result = await tools_manager.get_document("db_test_001")

        assert result.found is True
        assert result.pmid == "db_test_001"
        assert result.title == "Database Test Article"
        assert result.abstract == "This is a database integration test."
        assert "DB Author" in result.authors
        assert result.journal == "Integration Journal"
        assert result.publication_date == date(2023, 12, 1)
        assert result.doi == "10.1000/db.001"

    @pytest.mark.asyncio
    async def test_sync_workflow_with_database(self, tools_manager):
        """Test complete sync workflow with real database."""
        # Mock PubMed API responses
        mock_search_result = PubMedSearchResult(
            query="integration test", total_count=2, pmids=["sync_001", "sync_002"]
        )

        mock_documents = [
            PubMedDocument(
                pmid="sync_001",
                title="Sync Test Article 1",
                abstract="First sync test article.",
                authors=["Sync Author 1"],
                journal="Sync Journal",
                publication_date=date(2023, 12, 1),
            ),
            PubMedDocument(
                pmid="sync_002",
                title="Sync Test Article 2",
                abstract="Second sync test article.",
                authors=["Sync Author 2"],
                journal="Sync Journal",
                publication_date=date(2023, 12, 2),
            ),
        ]

        with (
            patch.object(
                tools_manager.pubmed_client, "search", new_callable=AsyncMock
            ) as mock_search,
            patch.object(
                tools_manager.pubmed_client, "fetch_documents", new_callable=AsyncMock
            ) as mock_fetch,
        ):
            mock_search.return_value = mock_search_result
            mock_fetch.return_value = mock_documents

            # Perform sync
            sync_result = await tools_manager.sync("integration test", limit=5)

            assert sync_result.total_requested == 2
            assert sync_result.successfully_synced == 2
            assert sync_result.already_existed == 0
            assert sync_result.failed == 0

            # Verify documents were stored in database
            doc1 = await tools_manager.get_document("sync_001")
            doc2 = await tools_manager.get_document("sync_002")

            assert doc1.found is True
            assert doc1.title == "Sync Test Article 1"
            assert doc2.found is True
            assert doc2.title == "Sync Test Article 2"


class TestMCPToolsWithDatabase:
    """Test MCP tools with real database integration."""

    @pytest.mark.asyncio
    async def test_get_tool_database_integration(self, tools_manager):
        """Test pubmed.get tool with real database."""
        # Store a document in database first
        doc_data = {
            "pmid": "mcp_test_001",
            "title": "MCP Integration Test",
            "abstract": "This is for MCP tool testing with database.",
            "authors": ["MCP Author"],
            "journal": "MCP Journal",
            "publication_date": date(2023, 11, 1),
            "doi": "10.1000/mcp.001",
        }
        await tools_manager.database_manager.create_document(doc_data)

        arguments = {"pmid": "mcp_test_001"}

        with patch(
            "bio_mcp.pubmed_tools.get_tools_manager", return_value=tools_manager
        ):
            response = await pubmed_get_tool("pubmed.get", arguments)

            assert len(response) == 1
            response_text = response[0].text
            assert "mcp_test_001" in response_text
            assert "MCP Integration Test" in response_text
            assert "This is for MCP tool testing with database." in response_text
            assert "MCP Author" in response_text

    @pytest.mark.asyncio
    async def test_sync_tool_database_integration(self, tools_manager):
        """Test pubmed.sync tool with real database storage."""
        arguments = {"query": "database sync test", "limit": 2}

        # Mock PubMed responses
        mock_search_result = PubMedSearchResult(
            query="database sync test", total_count=2, pmids=["db_sync_1", "db_sync_2"]
        )

        mock_documents = [
            PubMedDocument(
                pmid="db_sync_1",
                title="DB Sync Study 1",
                abstract="First study abstract",
            ),
            PubMedDocument(
                pmid="db_sync_2",
                title="DB Sync Study 2",
                abstract="Second study abstract",
            ),
        ]

        with (
            patch("bio_mcp.pubmed_tools.get_tools_manager", return_value=tools_manager),
            patch.object(
                tools_manager.pubmed_client, "search", new_callable=AsyncMock
            ) as mock_search,
            patch.object(
                tools_manager.pubmed_client, "fetch_documents", new_callable=AsyncMock
            ) as mock_fetch,
        ):
            mock_search.return_value = mock_search_result
            mock_fetch.return_value = mock_documents

            response = await pubmed_sync_tool("pubmed.sync", arguments)

            assert len(response) == 1
            response_text = response[0].text
            assert "database sync test" in response_text
            assert "Successfully synced: 2" in response_text

            # Verify documents were stored in database
            doc1 = await tools_manager.database_manager.get_document_by_pmid(
                "db_sync_1"
            )
            doc2 = await tools_manager.database_manager.get_document_by_pmid(
                "db_sync_2"
            )
            assert doc1 is not None
            assert doc2 is not None
            assert doc1.title == "DB Sync Study 1"
            assert doc2.title == "DB Sync Study 2"


class TestEndToEndWorkflow:
    """Test complete end-to-end research workflows."""

    @pytest.mark.asyncio
    async def test_complete_research_workflow(self, tools_manager):
        """Test complete research workflow: search → sync → retrieve."""

        # Mock search and document data
        mock_search_result = PubMedSearchResult(
            query="end-to-end test", total_count=3, pmids=["e2e_1", "e2e_2", "e2e_3"]
        )

        mock_documents = [
            PubMedDocument(
                pmid="e2e_1",
                title="End-to-End Test Study 1",
                abstract="First end-to-end test study.",
                authors=["E2E Author 1"],
                publication_date=date(2023, 12, 1),
            ),
            PubMedDocument(
                pmid="e2e_2",
                title="End-to-End Test Study 2",
                abstract="Second end-to-end test study.",
                authors=["E2E Author 2"],
                publication_date=date(2023, 12, 2),
            ),
            PubMedDocument(
                pmid="e2e_3",
                title="End-to-End Test Study 3",
                abstract="Third end-to-end test study.",
                authors=["E2E Author 3"],
                publication_date=date(2023, 12, 3),
            ),
        ]

        with (
            patch.object(
                tools_manager.pubmed_client, "search", new_callable=AsyncMock
            ) as mock_search,
            patch.object(
                tools_manager.pubmed_client, "fetch_documents", new_callable=AsyncMock
            ) as mock_fetch,
        ):
            mock_search.return_value = mock_search_result
            mock_fetch.return_value = mock_documents

            # Step 1: Search (returns PMIDs)
            search_result = await tools_manager.search("end-to-end test", limit=5)
            assert search_result.total_count == 3
            assert len(search_result.pmids) == 3

            # Step 2: Sync documents to database
            sync_result = await tools_manager.sync("end-to-end test", limit=5)
            assert sync_result.successfully_synced == 3
            assert sync_result.failed == 0

            # Step 3: Retrieve documents individually (should come from database now)
            for pmid in ["e2e_1", "e2e_2", "e2e_3"]:
                doc_result = await tools_manager.get_document(pmid)
                assert doc_result.found is True
                assert doc_result.pmid == pmid
                assert "End-to-End Test Study" in doc_result.title

            # Step 4: Verify database contains all documents
            all_docs = await tools_manager.database_manager.list_documents(limit=10)
            e2e_pmids = {doc.pmid for doc in all_docs if doc.pmid.startswith("e2e_")}
            assert len(e2e_pmids) == 3
            assert e2e_pmids == {"e2e_1", "e2e_2", "e2e_3"}
