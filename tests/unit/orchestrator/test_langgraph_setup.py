"""Test LangGraph orchestrator setup."""

import pytest

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.graph import BioMCPGraph


class TestLangGraphSetup:
    """Test basic LangGraph setup."""

    def test_config_creation(self):
        """Test orchestrator config creation."""
        config = OrchestratorConfig()
        assert config.default_budget_ms == 5000
        assert config.langgraph.debug_mode is False
        assert config.max_parallel_nodes == 5

    def test_graph_creation(self):
        """Test graph creation."""
        graph_builder = BioMCPGraph()
        graph = graph_builder.build_graph()

        # Check graph structure
        assert graph is not None
        assert "parse_frame" in graph.nodes
        assert "route_intent" in graph.nodes
        assert "synthesize" in graph.nodes

    def test_graph_compilation(self):
        """Test graph compilation with checkpointing."""
        graph_builder = BioMCPGraph()
        compiled_graph = graph_builder.compile_graph()

        assert compiled_graph is not None
        assert graph_builder._checkpointer is not None

    @pytest.mark.asyncio
    async def test_basic_execution(self):
        """Test basic graph execution with placeholders."""
        graph_builder = BioMCPGraph()
        result = await graph_builder.invoke("test query about diabetes")

        # Check result structure
        assert result["query"] == "test query about diabetes"
        assert result["answer"] is not None
        assert result["orchestrator_checkpoint_id"] is not None
        assert len(result["node_path"]) > 0
        assert "parse_frame" in result["node_path"]
        assert "synthesize" in result["node_path"]

    @pytest.mark.asyncio
    async def test_state_updates(self):
        """Test that state updates work correctly."""
        graph_builder = BioMCPGraph()
        result = await graph_builder.invoke("GLP-1 research")

        # Check state was properly updated through nodes
        assert result["frame"] is not None
        assert result["frame"]["intent"] == "recent_pubs_by_topic"
        assert result["routing_decision"] is not None
        assert len(result["messages"]) > 0

    @pytest.mark.asyncio
    async def test_streaming_execution(self):
        """Test streaming graph execution."""
        graph_builder = BioMCPGraph()
        chunks = []

        async for chunk in graph_builder.stream("Alzheimer drug trials"):
            chunks.append(chunk)

        # Should receive multiple chunks
        assert len(chunks) > 0

        # Last chunk should have final results
        final_chunk = chunks[-1]
        assert any("synthesize" in chunk for chunk in chunks)
