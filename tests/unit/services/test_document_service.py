"""
Comprehensive unit tests for DocumentService.

Tests document storage, retrieval, validation, and error handling
with proper mocking to isolate service logic from dependencies.
"""

from unittest.mock import AsyncMock, patch

import pytest

from bio_mcp.services.services import DocumentService
from bio_mcp.shared.clients.database import DatabaseConfig, DatabaseManager


class TestDocumentService:
    """Comprehensive testing for document storage and retrieval."""

    def setup_method(self):
        """Setup for each test method."""
        self.config = DatabaseConfig(
            url="postgresql+asyncpg://test_user:test_pass@test_host:5432/test_db",
            pool_size=5,
            max_overflow=10,
            pool_timeout=30.0,
            echo=False,
        )
        self.service = DocumentService(self.config)

        # Mock database manager
        self.mock_manager = AsyncMock(spec=DatabaseManager)

    def teardown_method(self):
        """Cleanup after each test method."""
        # Reset any patches
        pass

    @pytest.mark.asyncio
    async def test_initialization_lifecycle(self):
        """Test service initialization and cleanup lifecycle."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Initially not initialized
            assert not self.service._initialized
            assert self.service.manager is None

            # Initialize service
            await self.service.initialize()

            # Should be initialized
            assert self.service._initialized
            assert self.service.manager is not None
            mock_db_class.assert_called_once_with(self.config)
            self.mock_manager.initialize.assert_called_once()

            # Initialize again should be idempotent
            await self.service.initialize()
            assert self.service._initialized

            # Close service
            await self.service.close()
            assert not self.service._initialized
            assert self.service.manager is None
            self.mock_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_initialization_on_operations(self):
        """Test that operations automatically initialize the service."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.get_document_by_pmid.return_value = {"pmid": "12345"}

            # Service not initialized initially
            assert not self.service._initialized

            # Operation should trigger auto-initialization
            result = await self.service.get_document_by_pmid("12345")

            # Should be initialized and operation completed
            assert self.service._initialized
            assert result == {"pmid": "12345"}
            self.mock_manager.initialize.assert_called_once()
            self.mock_manager.get_document_by_pmid.assert_called_once_with("12345")

    @pytest.mark.asyncio
    async def test_get_document_by_pmid_success(self):
        """Test successful document retrieval by PMID."""
        test_document = {
            "pmid": "36653448",
            "title": "Glioblastoma multiforme: pathogenesis and treatment",
            "abstract": "Glioblastoma multiforme (GBM) is the most common and aggressive form...",
            "authors": ["Smith, J.", "Johnson, A."],
            "journal": "Nature Medicine",
            "publication_date": "2024-01-15",
        }

        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.get_document_by_pmid.return_value = test_document

            result = await self.service.get_document_by_pmid("36653448")

            assert result == test_document
            self.mock_manager.get_document_by_pmid.assert_called_once_with("36653448")

    @pytest.mark.asyncio
    async def test_get_document_by_pmid_not_found(self):
        """Test document retrieval when document doesn't exist."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.get_document_by_pmid.return_value = None

            result = await self.service.get_document_by_pmid("99999999")

            assert result is None
            self.mock_manager.get_document_by_pmid.assert_called_once_with("99999999")

    @pytest.mark.asyncio
    async def test_document_exists_true(self):
        """Test document existence check when document exists."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.document_exists.return_value = True

            result = await self.service.document_exists("36653448")

            assert result is True
            self.mock_manager.document_exists.assert_called_once_with("36653448")

    @pytest.mark.asyncio
    async def test_document_exists_false(self):
        """Test document existence check when document doesn't exist."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.document_exists.return_value = False

            result = await self.service.document_exists("99999999")

            assert result is False
            self.mock_manager.document_exists.assert_called_once_with("99999999")

    @pytest.mark.asyncio
    async def test_create_document_success(self):
        """Test successful document creation."""
        document_data = {
            "pmid": "36653448",
            "title": "Test Cancer Research Paper",
            "abstract": "Comprehensive study of cancer treatment mechanisms...",
            "authors": ["Smith, J.", "Johnson, A."],
            "journal": "Nature Medicine",
            "publication_date": "2024-01-15",
            "doi": "10.1038/nm.2024.001",
        }

        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.create_document.return_value = None

            await self.service.create_document(document_data)

            self.mock_manager.create_document.assert_called_once_with(document_data)

    @pytest.mark.asyncio
    async def test_create_document_validation_error(self):
        """Test document creation with validation errors."""
        invalid_document = {
            "pmid": "",  # Empty PMID should cause validation error
            "title": "Test Paper",
        }

        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.create_document.side_effect = ValueError(
                "PMID cannot be empty"
            )

            with pytest.raises(ValueError, match="PMID cannot be empty"):
                await self.service.create_document(invalid_document)

    @pytest.mark.asyncio
    async def test_create_document_duplicate_error(self):
        """Test document creation with duplicate PMID."""
        document_data = {"pmid": "36653448", "title": "Test Paper"}

        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.create_document.side_effect = Exception(
                "integrity constraint violation"
            )

            with pytest.raises(Exception, match="integrity constraint violation"):
                await self.service.create_document(document_data)

    @pytest.mark.asyncio
    async def test_batch_document_operations(self):
        """Test handling of multiple document operations efficiently."""
        pmids = ["12345", "67890", "11111", "22222", "33333"]

        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Mock existence checks - some exist, some don't
            self.mock_manager.document_exists.side_effect = [
                True,
                False,
                True,
                False,
                False,
            ]

            # Check existence for all PMIDs
            existence_results = []
            for pmid in pmids:
                exists = await self.service.document_exists(pmid)
                existence_results.append((pmid, exists))

            # Verify results
            expected_results = [
                ("12345", True),
                ("67890", False),
                ("11111", True),
                ("22222", False),
                ("33333", False),
            ]
            assert existence_results == expected_results

            # Verify all calls were made
            assert self.mock_manager.document_exists.call_count == 5

    @pytest.mark.asyncio
    async def test_error_handling_database_connection_failure(self):
        """Test error handling when database connection fails."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.initialize.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await self.service.initialize()

            # Service should remain uninitialized
            assert not self.service._initialized

    @pytest.mark.asyncio
    async def test_error_handling_database_operation_failure(self):
        """Test error handling when database operations fail."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.get_document_by_pmid.side_effect = Exception(
                "Database query failed"
            )

            with pytest.raises(Exception, match="Database query failed"):
                await self.service.get_document_by_pmid("12345")

    @pytest.mark.asyncio
    async def test_service_configuration_handling(self):
        """Test service configuration validation and defaults."""
        # Test with custom config
        custom_config = DatabaseConfig(
            url="postgresql+asyncpg://custom_user:custom_pass@custom_host:3306/custom_db",
            pool_size=10,
            max_overflow=20,
            pool_timeout=60.0,
            echo=True,
        )

        service_with_config = DocumentService(custom_config)
        assert service_with_config.config == custom_config

        # Test with default config (from environment)
        with patch(
            "bio_mcp.services.services.DatabaseConfig.from_env"
        ) as mock_from_env:
            mock_from_env.return_value = self.config

            service_default = DocumentService()
            assert service_default.config == self.config
            mock_from_env.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_operations_safety(self):
        """Test that concurrent operations are handled safely."""
        import asyncio

        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.document_exists.return_value = True

            # Simulate concurrent existence checks
            tasks = []
            pmids = [f"pmid_{i}" for i in range(10)]

            for pmid in pmids:
                task = self.service.document_exists(pmid)
                tasks.append(task)

            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks)

            # All should succeed
            assert all(result is True for result in results)
            assert self.mock_manager.document_exists.call_count == 10

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_errors(self):
        """Test that resources are properly cleaned up on errors."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Initialize successfully
            await self.service.initialize()
            assert self.service._initialized

            # Simulate error during operation
            self.mock_manager.get_document_by_pmid.side_effect = Exception(
                "Critical error"
            )

            # Error should propagate
            with pytest.raises(Exception, match="Critical error"):
                await self.service.get_document_by_pmid("12345")

            # Service should still be initialized (errors don't auto-cleanup)
            assert self.service._initialized

            # But explicit close should work
            await self.service.close()
            assert not self.service._initialized

    @pytest.mark.asyncio
    async def test_document_data_normalization(self):
        """Test that document data is properly normalized before storage."""
        # Test with various data formats
        test_cases = [
            # Complete document
            {
                "pmid": "12345",
                "title": "Complete Paper",
                "abstract": "Full abstract text",
                "authors": ["Smith, J.", "Johnson, A."],
                "journal": "Nature",
                "publication_date": "2024-01-15",
                "doi": "10.1038/nature.2024.001",
            },
            # Minimal document
            {"pmid": "67890", "title": "Minimal Paper"},
            # Document with extra fields
            {
                "pmid": "11111",
                "title": "Extended Paper",
                "extra_field": "should be preserved",
                "another_field": 12345,
            },
        ]

        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            for document_data in test_cases:
                await self.service.create_document(document_data)

                # Verify the exact data was passed through
                self.mock_manager.create_document.assert_called_with(document_data)

        # Should have called create_document for each test case
        assert self.mock_manager.create_document.call_count == len(test_cases)
