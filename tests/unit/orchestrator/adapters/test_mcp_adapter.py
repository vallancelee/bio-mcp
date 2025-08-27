"""Test MCP tool adapter."""

from unittest.mock import AsyncMock, Mock

import pytest

from bio_mcp.orchestrator.adapters.mcp_adapter import MCPToolAdapter
from bio_mcp.orchestrator.config import OrchestratorConfig


class TestMCPToolAdapter:
    """Test MCPToolAdapter implementation."""

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test successful MCP tool execution."""
        config = OrchestratorConfig()
        db_manager = Mock()
        adapter = MCPToolAdapter(config, db_manager)

        # Mock tool
        mock_tool = Mock()
        mock_tool.execute = AsyncMock(
            return_value={
                "results": [{"pmid": "12345", "title": "Test Article"}],
                "total": 1,
            }
        )
        adapter._tools = {"pubmed.search": mock_tool}

        result = await adapter.execute_tool("pubmed.search", {"term": "diabetes"})

        assert result.success
        assert result.data["total"] == 1
        assert result.data["results"][0]["pmid"] == "12345"
        assert not result.cache_hit
        assert result.node_name == "pubmed.search"
        mock_tool.execute.assert_called_once_with({"term": "diabetes"})

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """Test tool not found error."""
        config = OrchestratorConfig()
        db_manager = Mock()
        adapter = MCPToolAdapter(config, db_manager)

        result = await adapter.execute_tool("nonexistent.tool", {"arg": "value"})

        assert not result.success
        assert result.error_code == "TOOL_NOT_FOUND"
        assert "nonexistent.tool not available" in result.error_message

    @pytest.mark.asyncio
    async def test_batch_execute(self):
        """Test batch execution of multiple tools."""
        config = OrchestratorConfig()
        db_manager = Mock()
        adapter = MCPToolAdapter(config, db_manager)

        # Mock tools
        pubmed_tool = Mock()
        pubmed_tool.execute = AsyncMock(return_value={"results": [{"pmid": "pub1"}]})

        ctgov_tool = Mock()
        ctgov_tool.execute = AsyncMock(return_value={"results": [{"nct": "NCT123"}]})

        adapter._tools = {
            "pubmed.search": pubmed_tool,
            "clinicaltrials.search": ctgov_tool,
        }

        tool_calls = [
            {"tool": "pubmed.search", "args": {"term": "diabetes"}},
            {"tool": "clinicaltrials.search", "args": {"condition": "diabetes"}},
        ]

        results = await adapter.batch_execute(tool_calls, max_concurrency=2)

        assert len(results) == 2
        assert all(result.success for result in results)
        pubmed_tool.execute.assert_called_once()
        ctgov_tool.execute.assert_called_once()
