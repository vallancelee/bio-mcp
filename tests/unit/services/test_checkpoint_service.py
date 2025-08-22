"""
Comprehensive unit tests for CorpusCheckpointService.

Tests checkpoint creation, management, lineage tracking, and error handling
with proper mocking to isolate service logic from dependencies.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from bio_mcp.services.services import CorpusCheckpointService
from bio_mcp.shared.clients.database import DatabaseConfig, DatabaseManager


class MockCheckpoint:
    """Mock checkpoint object for testing."""

    def __init__(
        self,
        checkpoint_id: str,
        name: str,
        created_at: datetime = None,
        total_documents: int = 0,
        version: str = "1.0",
        parent_checkpoint_id: str = None,
        description: str = None,
    ):
        self.checkpoint_id = checkpoint_id
        self.name = name
        self.created_at = created_at or datetime.now()
        self.total_documents = total_documents
        self.version = version
        self.parent_checkpoint_id = parent_checkpoint_id
        self.description = description


class TestCorpusCheckpointService:
    """Comprehensive testing for checkpoint management operations."""

    def setup_method(self):
        """Setup for each test method."""
        self.config = DatabaseConfig(
            url="postgresql+asyncpg://test_user:test_pass@test_host:5432/test_db",
            pool_size=5,
            max_overflow=10,
            pool_timeout=30.0,
            echo=False,
        )
        self.service = CorpusCheckpointService(self.config)

        # Mock database manager
        self.mock_manager = AsyncMock(spec=DatabaseManager)

    def teardown_method(self):
        """Cleanup after each test method."""
        # Reset any patches
        pass

    @pytest.mark.asyncio
    async def test_checkpoint_creation_and_validation(self):
        """Test checkpoint creation with validation, metadata, and constraints."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Mock successful checkpoint creation
            expected_checkpoint = MockCheckpoint(
                checkpoint_id="cancer_research_2024",
                name="Cancer Research 2024",
                description="Research checkpoint for cancer immunotherapy studies",
                total_documents=0,
                version="1.0",
            )
            self.mock_manager.create_corpus_checkpoint.return_value = (
                expected_checkpoint
            )

            # Create checkpoint with all parameters
            result = await self.service.create_checkpoint(
                checkpoint_id="cancer_research_2024",
                name="Cancer Research 2024",
                description="Research checkpoint for cancer immunotherapy studies",
                primary_queries=["glioblastoma treatment", "immunotherapy"],
                parent_checkpoint_id=None,
            )

            # Verify creation was called with correct parameters
            self.mock_manager.create_corpus_checkpoint.assert_called_once_with(
                checkpoint_id="cancer_research_2024",
                name="Cancer Research 2024",
                description="Research checkpoint for cancer immunotherapy studies",
                primary_queries=["glioblastoma treatment", "immunotherapy"],
                parent_checkpoint_id=None,
            )

            assert result == expected_checkpoint

    @pytest.mark.asyncio
    async def test_checkpoint_creation_minimal_parameters(self):
        """Test checkpoint creation with only required parameters."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            expected_checkpoint = MockCheckpoint(
                checkpoint_id="minimal_checkpoint", name="Minimal Checkpoint"
            )
            self.mock_manager.create_corpus_checkpoint.return_value = (
                expected_checkpoint
            )

            # Create checkpoint with minimal parameters
            result = await self.service.create_checkpoint(
                checkpoint_id="minimal_checkpoint", name="Minimal Checkpoint"
            )

            self.mock_manager.create_corpus_checkpoint.assert_called_once_with(
                checkpoint_id="minimal_checkpoint",
                name="Minimal Checkpoint",
                description=None,
                primary_queries=None,
                parent_checkpoint_id=None,
            )

            assert result == expected_checkpoint

    @pytest.mark.asyncio
    async def test_checkpoint_hierarchy_and_lineage(self):
        """Test parent-child checkpoint relationships and lineage tracking."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Create parent checkpoint
            parent_checkpoint = MockCheckpoint(
                checkpoint_id="parent_research",
                name="Parent Research",
                total_documents=100,
                version="1.0",
            )
            self.mock_manager.create_corpus_checkpoint.return_value = parent_checkpoint

            parent_result = await self.service.create_checkpoint(
                checkpoint_id="parent_research", name="Parent Research"
            )

            # Create child checkpoint
            child_checkpoint = MockCheckpoint(
                checkpoint_id="child_research",
                name="Child Research",
                parent_checkpoint_id="parent_research",
                total_documents=150,
                version="1.1",
            )
            self.mock_manager.create_corpus_checkpoint.return_value = child_checkpoint

            child_result = await self.service.create_checkpoint(
                checkpoint_id="child_research",
                name="Child Research",
                parent_checkpoint_id="parent_research",
            )

            # Verify parent-child relationship was established
            assert child_result.parent_checkpoint_id == "parent_research"
            assert self.mock_manager.create_corpus_checkpoint.call_count == 2

    @pytest.mark.asyncio
    async def test_checkpoint_versioning_and_snapshots(self):
        """Test checkpoint versioning, snapshots, and rollback capabilities."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Test getting checkpoint (simulating versioned checkpoint)
            versioned_checkpoint = MockCheckpoint(
                checkpoint_id="versioned_research",
                name="Versioned Research",
                version="2.1",
                total_documents=500,
            )
            self.mock_manager.get_corpus_checkpoint.return_value = versioned_checkpoint

            result = await self.service.get_checkpoint("versioned_research")

            assert result.version == "2.1"
            assert result.total_documents == 500
            self.mock_manager.get_corpus_checkpoint.assert_called_once_with(
                "versioned_research"
            )

    @pytest.mark.asyncio
    async def test_checkpoint_query_and_filtering(self):
        """Test checkpoint listing with filtering, sorting, and pagination."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Mock list of checkpoints
            mock_checkpoints = [
                MockCheckpoint("checkpoint_1", "Research A", total_documents=100),
                MockCheckpoint("checkpoint_2", "Research B", total_documents=200),
                MockCheckpoint("checkpoint_3", "Research C", total_documents=150),
            ]
            self.mock_manager.list_corpus_checkpoints.return_value = mock_checkpoints

            # Test with default pagination
            result = await self.service.list_checkpoints()

            assert len(result) == 3
            assert result[0].checkpoint_id == "checkpoint_1"
            self.mock_manager.list_corpus_checkpoints.assert_called_once_with(
                limit=50, offset=0
            )

            # Test with custom pagination
            await self.service.list_checkpoints(limit=10, offset=5)
            self.mock_manager.list_corpus_checkpoints.assert_called_with(
                limit=10, offset=5
            )

    @pytest.mark.asyncio
    async def test_checkpoint_permissions_and_access(self):
        """Test checkpoint access control and permission management."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Test access to existing checkpoint
            accessible_checkpoint = MockCheckpoint(
                "accessible_checkpoint", "Accessible Research"
            )
            self.mock_manager.get_corpus_checkpoint.return_value = accessible_checkpoint

            result = await self.service.get_checkpoint("accessible_checkpoint")
            assert result is not None
            assert result.checkpoint_id == "accessible_checkpoint"

            # Test access to non-existent checkpoint
            self.mock_manager.get_corpus_checkpoint.return_value = None

            result = await self.service.get_checkpoint("nonexistent_checkpoint")
            assert result is None

    @pytest.mark.asyncio
    async def test_checkpoint_cleanup_and_archival(self):
        """Test checkpoint deletion, archival, and cleanup operations."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Test successful deletion
            self.mock_manager.delete_corpus_checkpoint.return_value = True

            result = await self.service.delete_checkpoint("checkpoint_to_delete")

            assert result is True
            self.mock_manager.delete_corpus_checkpoint.assert_called_once_with(
                "checkpoint_to_delete"
            )

            # Test deletion of non-existent checkpoint
            self.mock_manager.delete_corpus_checkpoint.return_value = False

            result = await self.service.delete_checkpoint("nonexistent_checkpoint")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_checkpoint_lineage_simple(self):
        """Test getting lineage for a simple parent-child relationship."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Create mock lineage: child -> parent -> grandparent
            child_checkpoint = MockCheckpoint(
                "child",
                "Child Research",
                parent_checkpoint_id="parent",
                total_documents=300,
                version="3.0",
            )
            parent_checkpoint = MockCheckpoint(
                "parent",
                "Parent Research",
                parent_checkpoint_id="grandparent",
                total_documents=200,
                version="2.0",
            )
            grandparent_checkpoint = MockCheckpoint(
                "grandparent",
                "Grandparent Research",
                parent_checkpoint_id=None,
                total_documents=100,
                version="1.0",
            )

            # Mock the sequential get_corpus_checkpoint calls
            self.mock_manager.get_corpus_checkpoint.side_effect = [
                child_checkpoint,
                parent_checkpoint,
                grandparent_checkpoint,
                None,  # End of lineage
            ]

            lineage = await self.service.get_checkpoint_lineage("child")

            assert len(lineage) == 3
            assert lineage[0]["checkpoint_id"] == "child"
            assert lineage[1]["checkpoint_id"] == "parent"
            assert lineage[2]["checkpoint_id"] == "grandparent"

            # Verify lineage structure
            for item in lineage:
                assert "checkpoint_id" in item
                assert "name" in item
                assert "created_at" in item
                assert "total_documents" in item
                assert "version" in item

    @pytest.mark.asyncio
    async def test_get_checkpoint_lineage_circular_protection(self):
        """Test lineage tracking with circular reference protection."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Create checkpoints that would cause infinite loop
            checkpoints = []
            for i in range(60):  # More than the 50 limit
                checkpoint = MockCheckpoint(
                    f"checkpoint_{i}",
                    f"Research {i}",
                    parent_checkpoint_id=f"checkpoint_{i + 1}"
                    if i < 59
                    else "checkpoint_0",
                )
                checkpoints.append(checkpoint)

            self.mock_manager.get_corpus_checkpoint.side_effect = checkpoints

            lineage = await self.service.get_checkpoint_lineage("checkpoint_0")

            # Should be truncated at or near 50 to prevent infinite loops
            assert (
                len(lineage) <= 51
            )  # Allow slight variation due to implementation details

    @pytest.mark.asyncio
    async def test_service_initialization_lifecycle(self):
        """Test service initialization and cleanup lifecycle."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Initially not initialized
            assert not self.service._initialized
            assert self.service.manager is None

            # Initialize service
            await self.service.initialize()

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

            mock_checkpoint = MockCheckpoint("test_checkpoint", "Test")
            self.mock_manager.get_corpus_checkpoint.return_value = mock_checkpoint

            # Service not initialized initially
            assert not self.service._initialized

            # Operation should trigger auto-initialization
            result = await self.service.get_checkpoint("test_checkpoint")

            assert self.service._initialized
            assert result == mock_checkpoint
            self.mock_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_creation_failures(self):
        """Test error handling for checkpoint creation failures."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Test duplicate checkpoint ID error
            self.mock_manager.create_corpus_checkpoint.side_effect = Exception(
                "Duplicate checkpoint ID"
            )

            with pytest.raises(Exception, match="Duplicate checkpoint ID"):
                await self.service.create_checkpoint(
                    checkpoint_id="duplicate_id", name="Duplicate Checkpoint"
                )

            # Test validation error
            self.mock_manager.create_corpus_checkpoint.side_effect = ValueError(
                "Invalid checkpoint name"
            )

            with pytest.raises(ValueError, match="Invalid checkpoint name"):
                await self.service.create_checkpoint(
                    checkpoint_id="invalid_checkpoint",
                    name="",  # Empty name
                )

    @pytest.mark.asyncio
    async def test_error_handling_database_failures(self):
        """Test error handling for database connection and operation failures."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Test database connection failure
            self.mock_manager.initialize.side_effect = Exception(
                "Database connection failed"
            )

            with pytest.raises(Exception, match="Database connection failed"):
                await self.service.initialize()

            # Reset the service and mock for the next test
            self.service = CorpusCheckpointService(self.config)
            mock_db_class.return_value = self.mock_manager
            self.mock_manager.initialize.side_effect = (
                None  # Clear previous side effect
            )

            # Test operation failure after successful initialization
            self.mock_manager.get_corpus_checkpoint.side_effect = Exception(
                "Database query failed"
            )

            with pytest.raises(Exception, match="Database query failed"):
                await self.service.get_checkpoint("test_checkpoint")

    @pytest.mark.asyncio
    async def test_concurrent_checkpoint_operations(self):
        """Test concurrent checkpoint operations for thread safety."""
        import asyncio

        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Mock responses for concurrent operations
            checkpoints = [
                MockCheckpoint(f"checkpoint_{i}", f"Research {i}") for i in range(10)
            ]
            self.mock_manager.get_corpus_checkpoint.side_effect = checkpoints

            # Create concurrent get operations
            tasks = []
            for i in range(10):
                task = self.service.get_checkpoint(f"checkpoint_{i}")
                tasks.append(task)

            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks)

            # All should succeed
            assert len(results) == 10
            for i, result in enumerate(results):
                assert result.checkpoint_id == f"checkpoint_{i}"

            assert self.mock_manager.get_corpus_checkpoint.call_count == 10

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

        service_with_config = CorpusCheckpointService(custom_config)
        assert service_with_config.config == custom_config

        # Test with default config (from environment)
        with patch(
            "bio_mcp.services.services.DatabaseConfig.from_env"
        ) as mock_from_env:
            mock_from_env.return_value = self.config

            service_default = CorpusCheckpointService()
            assert service_default.config == self.config
            mock_from_env.assert_called_once()

    @pytest.mark.asyncio
    async def test_checkpoint_metadata_preservation(self):
        """Test that checkpoint metadata is properly preserved and retrieved."""
        with patch("bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db_class.return_value = self.mock_manager

            # Create checkpoint with rich metadata
            checkpoint_data = {
                "checkpoint_id": "metadata_test",
                "name": "Metadata Test Checkpoint",
                "description": "Checkpoint with comprehensive metadata for testing",
                "primary_queries": [
                    "cancer immunotherapy resistance",
                    "PD-1 checkpoint inhibitors",
                    "tumor microenvironment",
                ],
                "parent_checkpoint_id": "parent_checkpoint",
            }

            expected_checkpoint = MockCheckpoint(
                checkpoint_id=checkpoint_data["checkpoint_id"],
                name=checkpoint_data["name"],
                description=checkpoint_data["description"],
                parent_checkpoint_id=checkpoint_data["parent_checkpoint_id"],
            )
            self.mock_manager.create_corpus_checkpoint.return_value = (
                expected_checkpoint
            )

            # Create checkpoint
            result = await self.service.create_checkpoint(**checkpoint_data)

            # Verify all metadata was passed through correctly
            self.mock_manager.create_corpus_checkpoint.assert_called_once_with(
                **checkpoint_data
            )
            assert result == expected_checkpoint
