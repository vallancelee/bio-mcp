"""Test router node."""
import pytest  # noqa: F401 - may be used by test framework
from bio_mcp.orchestrator.nodes.router_node import RouterNode, routing_function
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig


class TestRouterNode:
    """Test RouterNode implementation."""

    @pytest.mark.asyncio
    async def test_router_node_recent_pubs(self):
        """Test routing for recent publications intent."""
        config = OrchestratorConfig()
        node = RouterNode(config)
        
        state = OrchestratorState(
            query="recent publications on diabetes",
            config={},
            frame={
                "intent": "recent_pubs_by_topic",
                "entities": {"topic": "diabetes"},
                "filters": {}
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
            messages=[]
        )
        
        result = await node(state)
        
        # Verify routing decision
        assert "routing_decision" in result
        assert result["routing_decision"] == "pubmed_search"
        
        # Verify state updates
        assert "router" in result["node_path"]
        assert "router" in result["latencies"]
        assert len(result["messages"]) == 1
        assert "pubmed_search" in result["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_router_node_clinical_trials(self):
        """Test routing for clinical trials intent."""
        config = OrchestratorConfig()
        node = RouterNode(config)
        
        state = OrchestratorState(
            query="trials for diabetes",
            config={},
            frame={
                "intent": "indication_phase_trials",
                "entities": {"indication": "diabetes"},
                "filters": {}
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
            messages=[]
        )
        
        result = await node(state)
        
        # Verify routing decision
        assert result["routing_decision"] == "ctgov_search"

    @pytest.mark.asyncio 
    async def test_router_node_no_frame_error(self):
        """Test router node when no frame is present."""
        config = OrchestratorConfig()
        node = RouterNode(config)
        
        state = OrchestratorState(
            query="test query",
            config={},
            frame=None,  # No frame
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
            messages=[]
        )
        
        result = await node(state)
        
        # Verify error handling and fallback
        assert result["routing_decision"] == "pubmed_search"  # Default fallback
        assert len(result["errors"]) == 1
        assert result["errors"][0]["node"] == "router"

    def test_routing_function(self):
        """Test the routing function for conditional edges."""
        # Test single route
        state = OrchestratorState(
            query="test",
            config={},
            frame=None,
            routing_decision="pubmed_search",
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
            messages=[]
        )
        
        routes = routing_function(state)
        assert routes == ["pubmed_search"]
        
        # Test parallel routes 
        state["routing_decision"] = "ctgov_search|pubmed_search"
        routes = routing_function(state)
        assert set(routes) == {"ctgov_search", "pubmed_search"}