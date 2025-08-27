"""Integration tests for LangGraph nodes."""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.graph_builder import build_orchestrator_graph


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
            "normalized_query": None,
            "query_entities": None,
            "query_enhancement_metadata": None,
            "frame": None,
            "routing_decision": None,
            "intent_confidence": None,
            "entity_confidence": None,
            "pubmed_results": None,
            "ctgov_results": None,
            "rag_results": None,
            "tool_calls_made": [],
            "cache_hits": {},
            "latencies": {},
            "errors": [],
            "node_path": [],
            "answer": None,
            "orchestrator_checkpoint_id": None,
            "messages": []
        }
        
        # Need thread_id for checkpointer
        config_dict = {"configurable": {"thread_id": "test-thread"}}
        result = await compiled.ainvoke(initial_state, config=config_dict)
        
        # Verify execution
        assert result["answer"] is not None
        assert result["orchestrator_checkpoint_id"] is not None  # Updated field name
        assert "llm_parse" in result["node_path"]  # Updated node name
        assert "router" in result["node_path"] 
        assert "synthesizer" in result["node_path"]
        assert len(result["messages"]) > 0
        
        # Should have gone through PubMed route for this query
        assert "pubmed_search" in result["node_path"]
        assert "pubmed_search" in result["tool_calls_made"]