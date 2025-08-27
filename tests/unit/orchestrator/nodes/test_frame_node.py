"""Test frame parser node."""

import pytest

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.nodes.frame_node import FrameParserNode
from bio_mcp.orchestrator.state import OrchestratorState


class TestFrameParserNode:
    """Test FrameParserNode implementation."""

    @pytest.mark.asyncio
    async def test_frame_parser_node_success(self):
        """Test successful frame parsing."""
        config = OrchestratorConfig()
        node = FrameParserNode(config)

        state = OrchestratorState(
            query="recent publications on GLP-1 agonists",
            config={},
            frame=None,
            routing_decision=None,
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=[],
            answer=None,
            session_id=None,
            messages=[],
        )

        result = await node(state)

        # Verify frame was parsed correctly
        assert "frame" in result
        assert result["frame"]["intent"] == "recent_pubs_by_topic"
        assert "GLP-1 agonists" in result["frame"]["entities"]["topic"]

        # Verify state updates
        assert "parse_frame" in result["node_path"]
        assert "parse_frame" in result["latencies"]
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "system"

    @pytest.mark.asyncio
    async def test_frame_parser_node_error_handling(self):
        """Test error handling in frame parser."""
        config = OrchestratorConfig()
        node = FrameParserNode(config)

        # Test with empty query that should cause parsing error
        state = OrchestratorState(
            query="",
            config={},
            frame=None,
            routing_decision=None,
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=[],
            answer=None,
            session_id=None,
            messages=[],
        )

        result = await node(state)

        # Verify error handling
        assert len(result["errors"]) == 1
        assert result["errors"][0]["node"] == "parse_frame"
        assert "parse_frame" in result["node_path"]
        assert len(result["messages"]) == 1
        assert "error" in result["messages"][0]["content"].lower()
