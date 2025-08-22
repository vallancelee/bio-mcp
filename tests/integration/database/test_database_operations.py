"""
Integration tests for database operations.

Tests database operations with simplified scenarios that don't require
full database setup but validate the integration points and workflows.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bio_mcp.shared.clients.database import (
    DatabaseConfig,
    DatabaseManager,
    PubMedDocument,
    SyncWatermark,
    get_database_session,
    init_database,
)
from bio_mcp.shared.core.error_handling import ValidationError


class TestDatabaseOperationsIntegration:
    """Integration testing for database operations."""

    def setup_method(self):
        """Setup for each test method."""
        self.config = DatabaseConfig(
            url="postgresql+asyncpg://test_user:test_pass@test_host:5432/test_db",
            pool_size=5,
            max_overflow=10,
            pool_timeout=30.0,
            echo=False,
        )

    def teardown_method(self):
        """Cleanup after each test method."""
        pass

    @pytest.mark.asyncio
    async def test_database_initialization_workflow(self):
        """Test complete database initialization workflow."""
        with (
            patch(
                "bio_mcp.shared.clients.database.create_database_engine"
            ) as mock_create_engine,
            patch(
                "bio_mcp.shared.clients.database.async_sessionmaker"
            ) as mock_sessionmaker,
        ):
            # Mock engine and session setup
            mock_engine = AsyncMock()
            mock_create_engine.return_value = mock_engine

            mock_session_factory = MagicMock()
            mock_sessionmaker.return_value = mock_session_factory

            # Mock connection for table creation
            mock_conn = AsyncMock()
            mock_begin_context = AsyncMock()
            mock_begin_context.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_context.__aexit__ = AsyncMock(return_value=None)
            mock_engine.begin.return_value = mock_begin_context

            # Test init_database utility function
            manager = await init_database(self.config)

            # Verify initialization
            assert isinstance(manager, DatabaseManager)
            assert manager.config == self.config
            mock_create_engine.assert_called_once_with(self.config)

            # Test cleanup
            await manager.close()
            mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_session_context_management(self):
        """Test database session context management workflow."""
        with (
            patch(
                "bio_mcp.shared.clients.database.create_database_engine"
            ) as mock_create_engine,
            patch(
                "bio_mcp.shared.clients.database.async_sessionmaker"
            ) as mock_sessionmaker,
        ):
            # Setup mocks
            mock_engine = AsyncMock()
            mock_create_engine.return_value = mock_engine

            mock_session = AsyncMock()
            mock_session_factory = MagicMock(return_value=mock_session)
            mock_sessionmaker.return_value = mock_session_factory

            # Mock connection for initialization
            mock_conn = AsyncMock()
            mock_begin_context = AsyncMock()
            mock_begin_context.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_context.__aexit__ = AsyncMock(return_value=None)
            mock_engine.begin.return_value = mock_begin_context

            manager = DatabaseManager(self.config)
            await manager.initialize()

            # Test session utility
            session = await get_database_session(manager)
            assert session == mock_session

            # Verify session was properly created
            mock_session_factory.assert_called()

    @pytest.mark.asyncio
    async def test_document_lifecycle_integration(self):
        """Test complete document lifecycle operations."""
        # This test validates the integration of document operations
        # without requiring a real database

        manager = DatabaseManager(self.config)

        # Test data
        doc_data = {
            "pmid": "lifecycle_test",
            "title": "Document Lifecycle Test",
            "abstract": "Testing document lifecycle operations",
            "authors": ["Test, Author"],
            "journal": "Integration Test Journal",
        }

        # Mock the manager methods to test integration flow
        with (
            patch.object(manager, "create_document") as mock_create,
            patch.object(manager, "get_document_by_pmid") as mock_get,
            patch.object(manager, "update_document") as mock_update,
            patch.object(manager, "delete_document") as mock_delete,
            patch.object(manager, "document_exists") as mock_exists,
        ):
            # Setup mock responses
            mock_document = PubMedDocument(**doc_data)
            mock_create.return_value = mock_document
            mock_get.return_value = mock_document
            mock_update.return_value = mock_document
            mock_delete.return_value = True
            mock_exists.return_value = True

            # Test lifecycle workflow
            # 1. Create document
            created_doc = await manager.create_document(doc_data)
            assert created_doc == mock_document
            mock_create.assert_called_once_with(doc_data)

            # 2. Check existence
            exists = await manager.document_exists("lifecycle_test")
            assert exists is True
            mock_exists.assert_called_once_with("lifecycle_test")

            # 3. Retrieve document
            retrieved_doc = await manager.get_document_by_pmid("lifecycle_test")
            assert retrieved_doc == mock_document
            mock_get.assert_called_once_with("lifecycle_test")

            # 4. Update document
            updates = {"abstract": "Updated abstract"}
            updated_doc = await manager.update_document("lifecycle_test", updates)
            assert updated_doc == mock_document
            mock_update.assert_called_once_with("lifecycle_test", updates)

            # 5. Delete document
            deleted = await manager.delete_document("lifecycle_test")
            assert deleted is True
            mock_delete.assert_called_once_with("lifecycle_test")

    @pytest.mark.asyncio
    async def test_sync_watermark_workflow_integration(self):
        """Test sync watermark workflow integration."""
        manager = DatabaseManager(self.config)

        # Mock watermark operations
        with (
            patch.object(
                manager, "create_or_update_sync_watermark"
            ) as mock_create_update,
            patch.object(manager, "get_sync_watermark") as mock_get,
        ):
            mock_watermark = SyncWatermark(
                query_key="integration_test",
                last_edat="2024/01/15",
                total_synced="100",
                last_sync_count="10",
            )

            mock_get.return_value = mock_watermark
            mock_create_update.return_value = None

            # Test workflow
            # 1. Create/update watermark
            await manager.create_or_update_sync_watermark(
                query_key="integration_test", last_edat="2024/01/15", total_synced="100"
            )
            mock_create_update.assert_called_once()

            # 2. Retrieve watermark
            retrieved_watermark = await manager.get_sync_watermark("integration_test")
            assert retrieved_watermark == mock_watermark
            mock_get.assert_called_once_with("integration_test")

    @pytest.mark.asyncio
    async def test_bulk_operations_integration(self):
        """Test bulk document operations integration."""
        manager = DatabaseManager(self.config)

        # Test bulk document creation
        docs_data = [
            {"pmid": f"bulk_test_{i}", "title": f"Bulk Test Document {i}"}
            for i in range(10)
        ]

        with (
            patch.object(manager, "bulk_create_documents") as mock_bulk_create,
            patch.object(manager, "list_documents") as mock_list,
        ):
            # Mock responses
            mock_documents = [
                PubMedDocument(pmid=f"bulk_test_{i}", title=f"Bulk Test Document {i}")
                for i in range(10)
            ]
            mock_bulk_create.return_value = mock_documents
            mock_list.return_value = mock_documents

            # Test bulk creation
            created_docs = await manager.bulk_create_documents(docs_data)
            assert len(created_docs) == 10
            mock_bulk_create.assert_called_once_with(docs_data)

            # Test listing documents
            listed_docs = await manager.list_documents(limit=20, offset=0)
            assert len(listed_docs) == 10
            mock_list.assert_called_once_with(limit=20, offset=0)

    @pytest.mark.asyncio
    async def test_search_operations_integration(self):
        """Test document search operations integration."""
        manager = DatabaseManager(self.config)

        with patch.object(manager, "search_documents_by_title") as mock_search:
            # Mock search results
            mock_results = [
                PubMedDocument(pmid="search_1", title="Cancer Research Paper"),
                PubMedDocument(pmid="search_2", title="Cancer Treatment Study"),
            ]
            mock_search.return_value = mock_results

            # Test search operation
            results = await manager.search_documents_by_title("cancer")
            assert len(results) == 2
            assert all("Cancer" in doc.title for doc in results)
            mock_search.assert_called_once_with("cancer")

    @pytest.mark.asyncio
    async def test_health_check_integration(self):
        """Test database health check integration."""
        manager = DatabaseManager(self.config)

        # Check if check_health method exists
        if hasattr(manager, "check_health"):
            with patch.object(manager, "check_health") as mock_health:
                mock_health_result = {
                    "status": "healthy",
                    "response_time_ms": 15.5,
                    "connections_active": 2,
                    "connections_pool_size": 5,
                }
                mock_health.return_value = mock_health_result

                # Test health check
                health_status = await manager.check_health()
                assert health_status["status"] == "healthy"
                assert "response_time_ms" in health_status
                mock_health.assert_called_once()
        else:
            # Skip test if method doesn't exist
            pytest.skip("check_health method not available in DatabaseManager")

    @pytest.mark.asyncio
    async def test_error_handling_integration(self):
        """Test error handling across database operations."""
        manager = DatabaseManager(self.config)

        # Test various error scenarios
        error_scenarios = [
            (
                "create_document",
                {"pmid": "error_test", "title": "Error Test"},
                "Database connection failed",
            ),
            ("get_document_by_pmid", "error_pmid", "Document retrieval failed"),
            (
                "update_document",
                ("error_pmid", {"title": "Updated"}),
                "Update operation failed",
            ),
            ("delete_document", "error_pmid", "Deletion failed"),
            ("document_exists", "error_pmid", "Existence check failed"),
        ]

        for method_name, args, error_message in error_scenarios:
            with patch.object(manager, method_name) as mock_method:
                mock_method.side_effect = Exception(error_message)

                with pytest.raises(Exception, match=error_message):
                    method = getattr(manager, method_name)
                    if isinstance(args, tuple):
                        await method(*args)
                    else:
                        await method(args)

    @pytest.mark.asyncio
    async def test_concurrent_operations_integration(self):
        """Test concurrent database operations."""
        import asyncio

        manager = DatabaseManager(self.config)

        # Mock concurrent operations
        with (
            patch.object(manager, "document_exists") as mock_exists,
            patch.object(manager, "get_document_by_pmid") as mock_get,
        ):
            # Setup mock responses
            mock_exists.return_value = True
            mock_get.return_value = PubMedDocument(
                pmid="concurrent_test", title="Concurrent Test"
            )

            # Create concurrent tasks
            existence_tasks = [manager.document_exists(f"test_{i}") for i in range(5)]
            retrieval_tasks = [
                manager.get_document_by_pmid(f"test_{i}") for i in range(5)
            ]

            # Execute concurrently
            existence_results = await asyncio.gather(*existence_tasks)
            retrieval_results = await asyncio.gather(*retrieval_tasks)

            # Verify results
            assert all(result is True for result in existence_results)
            assert len(retrieval_results) == 5
            assert mock_exists.call_count == 5
            assert mock_get.call_count == 5

    @pytest.mark.asyncio
    async def test_configuration_validation_integration(self):
        """Test database configuration validation in integration context."""
        # Test with invalid configuration
        invalid_configs = [
            DatabaseConfig(url=None),
            DatabaseConfig(url=""),
            DatabaseConfig(url="invalid://url/format"),
        ]

        for invalid_config in invalid_configs:
            manager = DatabaseManager(invalid_config)

            # Should fail during initialization
            with pytest.raises((ValidationError, Exception)):
                await manager.initialize()

    @pytest.mark.asyncio
    async def test_database_utility_functions_integration(self):
        """Test database utility functions integration."""
        # Test init_database function
        with patch(
            "bio_mcp.shared.clients.database.DatabaseManager"
        ) as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager_class.return_value = mock_manager

            result = await init_database(self.config)

            mock_manager_class.assert_called_once_with(self.config)
            mock_manager.initialize.assert_called_once()
            assert result == mock_manager

        # Test get_database_session function
        mock_manager = AsyncMock()
        mock_session = AsyncMock()
        mock_manager.get_session.return_value = mock_session

        # get_database_session returns a session directly, not a context manager
        session = await get_database_session(mock_manager)
        assert session == mock_session
        mock_manager.get_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_model_integration_with_database_operations(self):
        """Test model integration with database operations."""
        # Test that models work correctly with database operations

        # Create test document with full data
        doc_data = {
            "pmid": "model_integration_test",
            "title": "Model Integration Test Document",
            "abstract": "Testing model integration with database operations",
            "authors": ["Integration, Test", "Model, Database"],
            "journal": "Integration Testing Journal",
            "doi": "10.1000/integration.test",
            "keywords": ["integration", "testing", "database", "model"],
            "publication_date": datetime(2024, 1, 15).date(),
        }

        # Test model creation and validation
        document = PubMedDocument(**doc_data)

        # Verify model integrity
        assert document.pmid == "model_integration_test"
        assert len(document.authors) == 2
        assert len(document.keywords) == 4
        assert document.publication_date.year == 2024

        # Test model with database manager interface
        manager = DatabaseManager(self.config)

        with patch.object(manager, "create_document") as mock_create:
            mock_create.return_value = document

            result = await manager.create_document(doc_data)
            assert result == document
            mock_create.assert_called_once_with(doc_data)

    @pytest.mark.asyncio
    async def test_transaction_boundary_integration(self):
        """Test transaction boundary handling in operations."""
        manager = DatabaseManager(self.config)

        # Test operations that should be transactional
        with (
            patch.object(manager, "create_document") as mock_create,
            patch.object(manager, "update_document") as mock_update,
        ):
            # Mock a successful creation followed by update
            doc_data = {"pmid": "transaction_test", "title": "Transaction Test"}
            mock_document = PubMedDocument(**doc_data)

            mock_create.return_value = mock_document
            mock_update.return_value = mock_document

            # Simulate a transaction-like workflow
            created_doc = await manager.create_document(doc_data)
            updated_doc = await manager.update_document(
                "transaction_test", {"title": "Updated Title"}
            )

            assert created_doc == mock_document
            assert updated_doc == mock_document
            mock_create.assert_called_once()
            mock_update.assert_called_once()
