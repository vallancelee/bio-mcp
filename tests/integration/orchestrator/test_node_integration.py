"""Integration tests for LangGraph nodes."""
import pytest  # noqa: F401 - may be used by test framework
from bio_mcp.orchestrator.graph_builder import build_orchestrator_graph
from bio_mcp.orchestrator.config import OrchestratorConfig
from langgraph.checkpoint.memory import MemorySaver


class TestNodeIntegration:
    """Test integration of all nodes working together."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_graph_execution(self):
        """Test complete graph execution with real nodes."""
        config = OrchestratorConfig()
        graph = build_orchestrator_graph(config)
        
        # Compile with checkpointing
        checkpointer = MemorySaver()
        compiled = graph.compile(checkpointer=checkpointer)
        
        # Execute a query
        initial_state = {
            "query": "recent papers on diabetes",
            "config": {},
            "frame": None,
            "routing_decision": None,
            "pubmed_results": None,
            "ctgov_results": None,
            "rag_results": None,
            "tool_calls_made": [],
            "cache_hits": {},
            "latencies": {},
            "errors": [],
            "node_path": [],
            "answer": None,
            "session_id": None,
            "messages": []
        }
        
        # Need thread_id for checkpointer
        config_dict = {"configurable": {"thread_id": "test-thread"}}
        result = await compiled.ainvoke(initial_state, config=config_dict)
        
        # Verify execution
        assert result["answer"] is not None
        assert result["session_id"] is not None
        assert "parse_frame" in result["node_path"]
        assert "router" in result["node_path"] 
        assert "synthesizer" in result["node_path"]
        assert len(result["messages"]) > 0
        
        # Should have gone through PubMed route for this query
        assert "pubmed_search" in result["node_path"]
        assert "pubmed_search" in result["tool_calls_made"]