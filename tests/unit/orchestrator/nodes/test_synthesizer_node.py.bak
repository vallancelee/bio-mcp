"""Test synthesizer node."""

import pytest

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.nodes.synthesizer_node import SynthesizerNode
from bio_mcp.orchestrator.state import OrchestratorState


class TestSynthesizerNode:
    """Test SynthesizerNode implementation."""

    @pytest.mark.asyncio
    async def test_synthesizer_node_with_pubmed_results(self):
        """Test synthesizing with PubMed results."""
        config = OrchestratorConfig()
        node = SynthesizerNode(config)

        state = OrchestratorState(
            query="recent publications on diabetes",
            config={},
            frame={"intent": "recent_pubs_by_topic", "entities": {"topic": "diabetes"}},
            routing_decision=None,
            pubmed_results={
                "total_count": 2,
                "results": [
                    {
                        "pmid": "123456",
                        "title": "Diabetes Research Study",
                        "authors": ["Dr. Smith", "Dr. Jones"],
                        "year": 2023,
                        "abstract": "This is a study about diabetes.",
                    }
                ],
            },
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=["pubmed_search"],
            cache_hits={"pubmed_search": False},
            latencies={"pubmed_search": 1500.0},
            errors=[],
            node_path=["parse_frame", "router", "pubmed_search"],
            answer=None,
            session_id=None,
            messages=[],
        )

        result = await node(state)

        # Verify answer was generated
        assert "answer" in result
        assert result["answer"] is not None
        assert "diabetes" in result["answer"].lower()
        assert "Diabetes Research Study" in result["answer"]

        # Verify checkpoint ID
        assert "session_id" in result
        assert result["session_id"] is not None
        assert result["session_id"].startswith("session_")

        # Verify state updates
        assert "synthesizer" in result["node_path"]
        assert "synthesizer" in result["latencies"]
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_synthesizer_node_no_results(self):
        """Test synthesizing when no results are available."""
        config = OrchestratorConfig()
        node = SynthesizerNode(config)

        state = OrchestratorState(
            query="test query with no results",
            config={},
            frame={
                "intent": "recent_pubs_by_topic",
                "entities": {"topic": "nonexistent topic"},
            },
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

        # Should still generate an answer
        assert "answer" in result
        assert result["answer"] is not None
        assert "No results found" in result["answer"]
        assert "session_id" in result
        assert "synthesizer" in result["node_path"]
