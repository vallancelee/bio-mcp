"""
Tests for MCP resource endpoints (Phase 4B.4).
Tests resource listing, reading, and error handling for Bio-MCP server.

Run with: pytest tests/test_mcp_resources.py -v -s
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import Resource

from bio_mcp.mcp.resources import (
    BioMCPResourceManager,
    ResourceResult,
    get_resource_manager,
    list_resources,
    read_resource,
)


class TestBioMCPResourceManager:
    """Test the core resource manager functionality."""

    @pytest.mark.asyncio
    async def test_resource_manager_initialization(self):
        """Test resource manager initialization."""
        manager = BioMCPResourceManager()

        # Create mocked services directly
        mock_doc_service = AsyncMock()
        mock_checkpoint_service = AsyncMock()

        # Replace the services in the manager
        manager.document_service = mock_doc_service
        manager.checkpoint_service = mock_checkpoint_service

        assert not manager.initialized

        await manager.initialize()

        assert manager.initialized
        mock_doc_service.initialize.assert_called_once()
        mock_checkpoint_service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_resources_success(self):
        """Test successful resource listing."""
        manager = BioMCPResourceManager()
        manager.initialized = True  # Skip initialization

        result = await manager.list_resources()

        assert result.success is True
        assert result.operation == "list"
        assert result.resource_uri == "bio-mcp://"
        assert result.data is not None
        assert (
            len(result.data) == 4
        )  # corpus/status, corpus/checkpoints, sync/recent, system/health

        # Verify specific resources
        resource_uris = [r["uri"] for r in result.data]
        assert "bio-mcp://corpus/status" in resource_uris
        assert "bio-mcp://corpus/checkpoints" in resource_uris
        assert "bio-mcp://sync/recent" in resource_uris
        assert "bio-mcp://system/health" in resource_uris

    @pytest.mark.asyncio
    async def test_get_corpus_status_success(self):
        """Test successful corpus status retrieval."""
        with patch(
            "src.bio_mcp.services.services.DocumentService"
        ) as mock_doc_service_class:
            mock_doc_service = AsyncMock()
            mock_doc_service_class.return_value = mock_doc_service
            mock_doc_service._initialized = True

            manager = BioMCPResourceManager()
            manager.document_service = mock_doc_service
            manager.initialized = True

            result = await manager.get_corpus_status()

            assert result.success is True
            assert result.operation == "read"
            assert result.resource_uri == "bio-mcp://corpus/status"
            assert result.data is not None

            # Verify data structure
            data = result.data
            assert "corpus_statistics" in data
            assert "sync_status" in data
            assert "system_info" in data
            assert data["system_info"]["database_status"] == "Connected"

    @pytest.mark.asyncio
    async def test_get_corpus_checkpoints_success(self):
        """Test successful corpus checkpoints retrieval."""
        with patch(
            "src.bio_mcp.services.services.CorpusCheckpointService"
        ) as mock_checkpoint_service_class:
            mock_checkpoint_service = AsyncMock()
            mock_checkpoint_service_class.return_value = mock_checkpoint_service

            # Mock checkpoint data
            from datetime import UTC, datetime

            from src.bio_mcp.clients.database import CorpusCheckpoint

            mock_checkpoints = [
                CorpusCheckpoint(
                    checkpoint_id="test_checkpoint_1",
                    name="Test Checkpoint 1",
                    description="First test checkpoint",
                    total_documents="100",
                    version="1.0",
                    created_at=datetime.now(UTC),
                    primary_queries=["test query"],
                ),
                CorpusCheckpoint(
                    checkpoint_id="test_checkpoint_2",
                    name="Test Checkpoint 2",
                    description="Second test checkpoint",
                    total_documents="200",
                    version="1.1",
                    created_at=datetime.now(UTC),
                    primary_queries=["another query"],
                ),
            ]

            mock_checkpoint_service.list_checkpoints.return_value = mock_checkpoints

            manager = BioMCPResourceManager()
            manager.checkpoint_service = mock_checkpoint_service
            manager.initialized = True

            result = await manager.get_corpus_checkpoints()

            assert result.success is True
            assert result.operation == "read"
            assert result.resource_uri == "bio-mcp://corpus/checkpoints"
            assert result.data is not None

            # Verify data structure
            data = result.data
            assert "total_checkpoints" in data
            assert "checkpoints" in data
            assert data["total_checkpoints"] == 2
            assert len(data["checkpoints"]) == 2
            assert data["checkpoints"][0]["checkpoint_id"] == "test_checkpoint_1"
            assert data["checkpoints"][1]["checkpoint_id"] == "test_checkpoint_2"

    @pytest.mark.asyncio
    async def test_get_recent_sync_activities_success(self):
        """Test successful recent sync activities retrieval."""
        manager = BioMCPResourceManager()
        manager.initialized = True

        result = await manager.get_recent_sync_activities()

        assert result.success is True
        assert result.operation == "read"
        assert result.resource_uri == "bio-mcp://sync/recent"
        assert result.data is not None

        # Verify data structure
        data = result.data
        assert "recent_syncs" in data
        assert "active_queries" in data
        assert "sync_status" in data
        assert data["sync_status"] == "Ready"

    @pytest.mark.asyncio
    async def test_get_system_health_success(self):
        """Test successful system health retrieval."""
        with (
            patch(
                "src.bio_mcp.services.services.DocumentService"
            ) as mock_doc_service_class,
            patch(
                "src.bio_mcp.services.services.CorpusCheckpointService"
            ) as mock_checkpoint_service_class,
        ):
            mock_doc_service = AsyncMock()
            mock_checkpoint_service = AsyncMock()
            mock_doc_service_class.return_value = mock_doc_service
            mock_checkpoint_service_class.return_value = mock_checkpoint_service
            mock_doc_service._initialized = True
            mock_checkpoint_service._initialized = True

            manager = BioMCPResourceManager()
            manager.document_service = mock_doc_service
            manager.checkpoint_service = mock_checkpoint_service
            manager.initialized = True

            result = await manager.get_system_health()

            assert result.success is True
            assert result.operation == "read"
            assert result.resource_uri == "bio-mcp://system/health"
            assert result.data is not None

            # Verify data structure
            data = result.data
            assert "overall_status" in data
            assert "components" in data
            assert "metrics" in data
            assert data["overall_status"] == "Healthy"
            assert data["components"]["database"]["status"] == "Connected"
            assert data["components"]["checkpoint_service"]["status"] == "Connected"


class TestMCPResourceEndpoints:
    """Test the MCP resource endpoint functions."""

    @pytest.mark.asyncio
    async def test_list_resources_endpoint_success(self):
        """Test the list_resources endpoint function."""
        with patch(
            "src.bio_mcp.mcp.resources.get_resource_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            mock_result = ResourceResult(
                resource_uri="bio-mcp://",
                operation="list",
                success=True,
                execution_time_ms=50.0,
                data=[
                    {
                        "uri": "bio-mcp://corpus/status",
                        "name": "Corpus Status",
                        "description": "Current corpus statistics",
                        "mimeType": "application/json",
                    },
                    {
                        "uri": "bio-mcp://corpus/checkpoints",
                        "name": "Corpus Checkpoints",
                        "description": "List of checkpoints",
                        "mimeType": "application/json",
                    },
                ],
            )
            mock_manager.list_resources.return_value = mock_result

            resources = await list_resources()

            assert len(resources) == 2
            assert all(isinstance(r, Resource) for r in resources)
            assert str(resources[0].uri) == "bio-mcp://corpus/status"
            assert resources[0].name == "Corpus Status"
            assert str(resources[1].uri) == "bio-mcp://corpus/checkpoints"
            assert resources[1].name == "Corpus Checkpoints"

    @pytest.mark.asyncio
    async def test_list_resources_endpoint_error(self):
        """Test the list_resources endpoint with error."""
        with patch(
            "src.bio_mcp.mcp.resources.get_resource_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            mock_result = ResourceResult(
                resource_uri="bio-mcp://",
                operation="list",
                success=False,
                execution_time_ms=50.0,
                error_message="Database connection failed",
            )
            mock_manager.list_resources.return_value = mock_result

            resources = await list_resources()

            assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_read_resource_corpus_status(self):
        """Test reading corpus status resource."""
        with patch(
            "src.bio_mcp.mcp.resources.get_resource_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            mock_result = ResourceResult(
                resource_uri="bio-mcp://corpus/status",
                operation="read",
                success=True,
                execution_time_ms=75.0,
                data={
                    "corpus_statistics": {"total_documents": "500"},
                    "sync_status": {"active_queries": 3},
                    "system_info": {"database_status": "Connected"},
                },
            )
            mock_manager.get_corpus_status.return_value = mock_result

            content = await read_resource("bio-mcp://corpus/status")

            # Parse the JSON to verify structure
            data = json.loads(content)
            assert "corpus_statistics" in data
            assert "sync_status" in data
            assert "system_info" in data
            assert data["corpus_statistics"]["total_documents"] == "500"

    @pytest.mark.asyncio
    async def test_read_resource_corpus_checkpoints(self):
        """Test reading corpus checkpoints resource."""
        with patch(
            "src.bio_mcp.mcp.resources.get_resource_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            mock_result = ResourceResult(
                resource_uri="bio-mcp://corpus/checkpoints",
                operation="read",
                success=True,
                execution_time_ms=85.0,
                data={
                    "total_checkpoints": 2,
                    "checkpoints": [
                        {"checkpoint_id": "checkpoint_1", "name": "Test 1"},
                        {"checkpoint_id": "checkpoint_2", "name": "Test 2"},
                    ],
                },
            )
            mock_manager.get_corpus_checkpoints.return_value = mock_result

            content = await read_resource("bio-mcp://corpus/checkpoints")

            # Parse the JSON to verify structure
            data = json.loads(content)
            assert "total_checkpoints" in data
            assert "checkpoints" in data
            assert data["total_checkpoints"] == 2
            assert len(data["checkpoints"]) == 2

    @pytest.mark.asyncio
    async def test_read_resource_sync_recent(self):
        """Test reading recent sync activities resource."""
        with patch(
            "src.bio_mcp.mcp.resources.get_resource_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            mock_result = ResourceResult(
                resource_uri="bio-mcp://sync/recent",
                operation="read",
                success=True,
                execution_time_ms=60.0,
                data={"recent_syncs": [], "active_queries": 0, "sync_status": "Ready"},
            )
            mock_manager.get_recent_sync_activities.return_value = mock_result

            content = await read_resource("bio-mcp://sync/recent")

            # Parse the JSON to verify structure
            data = json.loads(content)
            assert "recent_syncs" in data
            assert "active_queries" in data
            assert "sync_status" in data
            assert data["sync_status"] == "Ready"

    @pytest.mark.asyncio
    async def test_read_resource_system_health(self):
        """Test reading system health resource."""
        with patch(
            "src.bio_mcp.mcp.resources.get_resource_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            mock_result = ResourceResult(
                resource_uri="bio-mcp://system/health",
                operation="read",
                success=True,
                execution_time_ms=45.0,
                data={
                    "overall_status": "Healthy",
                    "components": {
                        "database": {"status": "Connected"},
                        "checkpoint_service": {"status": "Connected"},
                    },
                },
            )
            mock_manager.get_system_health.return_value = mock_result

            content = await read_resource("bio-mcp://system/health")

            # Parse the JSON to verify structure
            data = json.loads(content)
            assert "overall_status" in data
            assert "components" in data
            assert data["overall_status"] == "Healthy"

    @pytest.mark.asyncio
    async def test_read_resource_not_found(self):
        """Test reading a non-existent resource."""
        content = await read_resource("bio-mcp://invalid/resource")

        assert "Resource not found" in content
        assert "bio-mcp://invalid/resource" in content

    @pytest.mark.asyncio
    async def test_read_resource_error(self):
        """Test reading resource with error."""
        with patch(
            "src.bio_mcp.mcp.resources.get_resource_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            mock_result = ResourceResult(
                resource_uri="bio-mcp://corpus/status",
                operation="read",
                success=False,
                execution_time_ms=100.0,
                error_message="Service unavailable",
            )
            mock_manager.get_corpus_status.return_value = mock_result

            content = await read_resource("bio-mcp://corpus/status")

            assert "Error reading resource" in content
            assert "Service unavailable" in content


class TestResourceManagerSingleton:
    """Test the global resource manager singleton pattern."""

    def test_get_resource_manager_singleton(self):
        """Test that get_resource_manager returns the same instance."""
        manager1 = get_resource_manager()
        manager2 = get_resource_manager()

        assert manager1 is manager2
        assert isinstance(manager1, BioMCPResourceManager)


class TestResourceErrorHandling:
    """Test error handling in resource operations."""

    @pytest.mark.asyncio
    async def test_resource_manager_service_initialization_error(self):
        """Test handling of service initialization errors."""
        manager = BioMCPResourceManager()

        # Create mock services that will raise errors
        mock_doc_service = AsyncMock()
        mock_checkpoint_service = AsyncMock()
        mock_doc_service.initialize.side_effect = Exception(
            "Database connection failed"
        )

        # Replace the services in the manager
        manager.document_service = mock_doc_service
        manager.checkpoint_service = mock_checkpoint_service

        # Should handle initialization error gracefully
        with pytest.raises(Exception, match="Database connection failed"):
            await manager.initialize()

    @pytest.mark.asyncio
    async def test_resource_read_with_service_error(self):
        """Test resource reading with service errors."""
        with patch(
            "src.bio_mcp.services.services.CorpusCheckpointService"
        ) as mock_checkpoint_service_class:
            mock_checkpoint_service = AsyncMock()
            mock_checkpoint_service_class.return_value = mock_checkpoint_service
            mock_checkpoint_service.list_checkpoints.side_effect = Exception(
                "Service error"
            )

            manager = BioMCPResourceManager()
            manager.checkpoint_service = mock_checkpoint_service
            manager.initialized = True

            result = await manager.get_corpus_checkpoints()

            assert result.success is False
            assert "Service error" in result.error_message


# Pytest configuration for MCP resource tests
pytestmark = pytest.mark.unit
