"""
Simplified integration tests for MCP resources interface.

Tests resource endpoints with real PostgreSQL database using TestContainers,
focusing on core functionality without complex mocking.
"""

import pytest
from mcp.types import Resource

from bio_mcp.mcp.resources import list_resources, read_resource
from tests.utils.mcp_validators import MCPResponseValidator

# Mark all tests to not use weaviate by default
pytestmark = pytest.mark.no_weaviate


class TestResourcesIntegrationSimplified:
    """Simplified integration tests for MCP resource endpoints."""

    def setup_method(self):
        """Setup test fixtures."""
        self.validator = MCPResponseValidator()

    @pytest.mark.asyncio
    async def test_list_resources_success(self):
        """Test successful resource listing."""
        result = await list_resources()

        # Should return list of Resource objects
        assert isinstance(result, list)
        assert len(result) > 0

        # Each item should be a Resource
        for resource in result:
            assert isinstance(resource, Resource)
            assert hasattr(resource, "uri")
            assert hasattr(resource, "name")
            assert str(resource.uri).startswith("bio-mcp://")

    @pytest.mark.asyncio
    async def test_read_corpus_status_resource(self, sample_documents):
        """Test reading corpus status resource."""
        result = await read_resource("bio-mcp://corpus/status")

        assert isinstance(result, str)
        # Should be valid JSON-like content
        assert "{" in result and "}" in result
        # Should contain corpus information
        assert "corpus" in result.lower() or "documents" in result.lower()

    @pytest.mark.asyncio
    async def test_read_corpus_checkpoints_resource(self, sample_checkpoint):
        """Test reading corpus checkpoints resource."""
        result = await read_resource("bio-mcp://corpus/checkpoints")

        assert isinstance(result, str)
        # Should be valid JSON-like content
        assert "{" in result and "}" in result
        # Should contain checkpoint information
        assert "checkpoint" in result.lower()
        # Should include our sample checkpoint
        assert sample_checkpoint in result or "Test Checkpoint" in result

    @pytest.mark.asyncio
    async def test_read_system_health_resource(self):
        """Test reading system health resource."""
        result = await read_resource("bio-mcp://system/health")

        assert isinstance(result, str)
        # Should be valid JSON-like content
        assert "{" in result and "}" in result
        # Should contain health information
        assert "health" in result.lower() or "status" in result.lower()

    @pytest.mark.asyncio
    async def test_read_sync_recent_resource(self):
        """Test reading recent sync activities resource."""
        result = await read_resource("bio-mcp://sync/recent")

        assert isinstance(result, str)
        # Should be valid JSON-like content
        assert "{" in result and "}" in result
        # Should contain sync information
        assert "sync" in result.lower()

    @pytest.mark.asyncio
    async def test_read_nonexistent_resource(self):
        """Test reading non-existent resource."""
        result = await read_resource("bio-mcp://invalid/resource")

        assert isinstance(result, str)
        assert "not found" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_resource_uris_consistency(self):
        """Test that listed resources can be read."""
        # Get all resources
        resources = await list_resources()

        # Try to read each resource
        for resource in resources:
            uri = str(resource.uri)
            result = await read_resource(uri)

            # Should get valid content (not an error)
            assert isinstance(result, str)
            assert len(result) > 0
            # Should not be a generic error (though specific errors are OK)
            assert (
                not result.startswith("Error reading resource")
                or "not found" in result.lower()
            )

    @pytest.mark.asyncio
    async def test_resource_metadata_consistency(self):
        """Test resource metadata is consistent."""
        resources = await list_resources()

        for resource in resources:
            # Check basic metadata
            assert len(resource.name) > 0
            assert len(str(resource.uri)) > 0
            assert resource.description is None or len(resource.description) > 0
            assert resource.mimeType == "application/json"

    @pytest.mark.asyncio
    async def test_resources_with_sample_data(
        self, sample_documents, sample_checkpoint
    ):
        """Test resources reflect sample data correctly."""
        # Test corpus status shows document count
        status_result = await read_resource("bio-mcp://corpus/status")
        # Should reflect that we have documents (exact count may vary)
        assert "document" in status_result.lower()

        # Test checkpoints resource shows our sample
        checkpoint_result = await read_resource("bio-mcp://corpus/checkpoints")
        assert (
            sample_checkpoint in checkpoint_result
            or "Test Checkpoint" in checkpoint_result
        )

        # Test that all main resources are accessible
        main_uris = [
            "bio-mcp://corpus/status",
            "bio-mcp://corpus/checkpoints",
            "bio-mcp://sync/recent",
            "bio-mcp://system/health",
        ]

        for uri in main_uris:
            result = await read_resource(uri)
            assert isinstance(result, str)
            assert len(result) > 10  # Should have substantial content
            assert "{" in result  # Should be JSON-like
