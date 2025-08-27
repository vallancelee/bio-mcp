"""Test router node."""
import pytest

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.nodes.router_node import RouterNode, routing_function
from bio_mcp.orchestrator.state import OrchestratorState


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
            normalized_query=None,
            query_entities=None,
            query_enhancement_metadata=None,
            frame={
                "intent": "recent_pubs_by_topic",
                "entities": {"topic": "diabetes"},
                "filters": {}
            },
            routing_decision=None,
            intent_confidence=None,
            entity_confidence=None,
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=[],
            answer=None,
            orchestrator_checkpoint_id=None,
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
            normalized_query=None,
            query_entities=None,
            query_enhancement_metadata=None,
            frame={
                "intent": "indication_phase_trials",
                "entities": {"indication": "diabetes"},
                "filters": {}
            },
            routing_decision=None,
            intent_confidence=None,
            entity_confidence=None,
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=[],
            answer=None,
            orchestrator_checkpoint_id=None,
            messages=[]
        )
        
        result = await node(state)
        
        # Verify routing decision (M1 limitation: returns pubmed_search instead of ctgov_search)
        assert result["routing_decision"] == "pubmed_search"

    @pytest.mark.asyncio 
    async def test_router_node_no_frame_error(self):
        """Test router node when no frame is present."""
        config = OrchestratorConfig()
        node = RouterNode(config)
        
        state = OrchestratorState(
            query="test query",
            config={},
            normalized_query=None,
            query_entities=None,
            query_enhancement_metadata=None,
            frame=None,  # No frame
            routing_decision=None,
            intent_confidence=None,
            entity_confidence=None,
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=[],
            answer=None,
            orchestrator_checkpoint_id=None,
            messages=[]
        )
        
        result = await node(state)
        
        # Verify error handling and fallback
        assert result["routing_decision"] == "pubmed_search"  # Default fallback
        assert len(result["errors"]) == 1
        assert result["errors"][0]["node"] == "router"

    def test_routing_function(self):
        """Test the routing function for conditional edges."""
        # Test with frame and high confidence
        state = OrchestratorState(
            query="test",
            config={},
            normalized_query=None,
            query_entities=None,
            query_enhancement_metadata=None,
            frame={"intent": "recent_pubs_by_topic"},
            routing_decision=None,
            intent_confidence=0.8,
            entity_confidence=None,
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=[],
            answer=None,
            orchestrator_checkpoint_id=None,
            messages=[]
        )
        
        route = routing_function(state)
        assert route == "pubmed_search"
        
        # Test with low confidence (should route to rag_search)
        state["intent_confidence"] = 0.3
        route = routing_function(state)
        # Low confidence should route to rag_search (graph_builder handles M1 limitation)
        assert route == "rag_search"