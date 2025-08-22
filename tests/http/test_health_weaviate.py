"""Tests for Weaviate health checker."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from bio_mcp.http.health.interface import HealthCheckResult
from bio_mcp.http.health.weaviate import WeaviateHealthChecker


class TestWeaviateHealthChecker:
    """Test Weaviate connectivity health checker."""

    @pytest.fixture
    def weaviate_checker(self):
        """Create Weaviate health checker for testing."""
        return WeaviateHealthChecker("http://localhost:8080", timeout_seconds=3.0)

    def test_checker_name(self, weaviate_checker):
        """Test health checker name property."""
        assert weaviate_checker.name == "weaviate"

    def test_checker_timeout(self, weaviate_checker):
        """Test custom timeout configuration."""
        assert weaviate_checker.timeout_seconds == 3.0

    def test_checker_default_timeout(self):
        """Test default timeout configuration."""
        checker = WeaviateHealthChecker("http://localhost:8080")
        assert checker.timeout_seconds == 5.0

    @pytest.mark.asyncio
    async def test_check_health_successful_connection(self, weaviate_checker):
        """Test successful Weaviate health check."""
        # Mock Weaviate client and responses
        mock_client = AsyncMock()

        # Mock cluster health check
        mock_client.cluster.get_nodes_status.return_value = {
            "nodes": [{"name": "node-1", "status": "HEALTHY", "version": "1.24.0"}]
        }

        # Mock schema check
        mock_client.schema.get.return_value = {
            "classes": [{"class": "PubmedDocument", "vectorizer": "none"}]
        }

        # Mock live/ready endpoints
        mock_client.is_live.return_value = True
        mock_client.is_ready.return_value = True

        with patch(
            "bio_mcp.http.health.weaviate.weaviate.connect_to_weaviate_cloud"
        ) as mock_connect:

            @asynccontextmanager
            async def mock_weaviate_context():
                yield mock_client

            mock_connect.return_value = mock_weaviate_context()

            result = await weaviate_checker.check_health()

        assert isinstance(result, HealthCheckResult)
        assert result.healthy is True
        assert "weaviate" in result.message.lower()
        assert result.checker_name == "weaviate"
        assert result.check_duration_ms > 0
        assert result.details is not None
        assert result.details["cluster_status"] == "healthy"
        assert "schema_classes" in result.details

    @pytest.mark.asyncio
    async def test_check_health_connection_failed(self, weaviate_checker):
        """Test Weaviate health check with connection failure."""

        with patch(
            "bio_mcp.http.health.weaviate.weaviate.connect_to_weaviate_cloud"
        ) as mock_connect:
            mock_connect.side_effect = Exception("Weaviate connection timeout")

            result = await weaviate_checker.check_health()

        assert result.healthy is False
        assert "failed" in result.message.lower()
        assert result.details is not None
        assert "error" in result.details
        assert result.details["error"] == "Weaviate connection timeout"

    @pytest.mark.asyncio
    async def test_check_health_cluster_unhealthy(self, weaviate_checker):
        """Test Weaviate health check with unhealthy cluster."""
        mock_client = AsyncMock()

        # Mock unhealthy cluster
        mock_client.cluster.get_nodes_status.return_value = {
            "nodes": [{"name": "node-1", "status": "UNHEALTHY", "version": "1.24.0"}]
        }

        mock_client.is_live.return_value = True
        mock_client.is_ready.return_value = True

        with patch(
            "bio_mcp.http.health.weaviate.weaviate.connect_to_weaviate_cloud"
        ) as mock_connect:

            @asynccontextmanager
            async def mock_weaviate_context():
                yield mock_client

            mock_connect.return_value = mock_weaviate_context()

            result = await weaviate_checker.check_health()

        assert result.healthy is False
        assert "cluster" in result.message.lower()
        assert result.details is not None
        assert result.details["cluster_status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_health_schema_missing(self, weaviate_checker):
        """Test Weaviate health check with missing schema."""
        mock_client = AsyncMock()

        # Mock healthy cluster but missing schema
        mock_client.cluster.get_nodes_status.return_value = {
            "nodes": [{"name": "node-1", "status": "HEALTHY", "version": "1.24.0"}]
        }

        # Empty schema
        mock_client.schema.get.return_value = {"classes": []}

        mock_client.is_live.return_value = True
        mock_client.is_ready.return_value = True

        with patch(
            "bio_mcp.http.health.weaviate.weaviate.connect_to_weaviate_cloud"
        ) as mock_connect:

            @asynccontextmanager
            async def mock_weaviate_context():
                yield mock_client

            mock_connect.return_value = mock_weaviate_context()

            result = await weaviate_checker.check_health()

        assert result.healthy is False
        assert "schema" in result.message.lower()
        assert result.details is not None
        assert result.details["schema_classes"] == []
        assert result.details["missing_classes"] == ["PubmedDocument"]
