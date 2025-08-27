"""Router node for intent-based conditional routing."""

from datetime import UTC, datetime
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import OrchestratorState

logger = get_logger(__name__)


class RouterNode:
    """Node that routes execution based on parsed intent."""

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self._setup_routing_rules()

    def _setup_routing_rules(self):
        """Setup intent to node routing rules."""
        self.routing_map = {
            "recent_pubs_by_topic": ["pubmed_search"],
            "indication_phase_trials": ["ctgov_search"],
            "trials_with_pubs": ["ctgov_search", "pubmed_search"],  # Parallel
            "hybrid_search": ["rag_search"],
            "company_pipeline": ["company_search", "ctgov_search"],
        }

    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Route based on frame intent."""
        start_time = datetime.now(UTC)
        frame = state.get("frame")

        if not frame:
            logger.error("No frame found in state for routing")
            return {
                "routing_decision": "pubmed_search",  # Default fallback
                "errors": state["errors"]
                + [
                    {
                        "node": "router",
                        "error": "No frame available for routing",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ],
                "node_path": state["node_path"] + ["router"],
            }

        intent = frame.get("intent", "recent_pubs_by_topic")

        # Get routing decision
        next_nodes = self.routing_map.get(intent, ["pubmed_search"])
        routing_decision = (
            "|".join(next_nodes) if len(next_nodes) > 1 else next_nodes[0]
        )

        # Calculate latency
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

        logger.info(
            "Routing decision made",
            extra={
                "intent": intent,
                "routing": routing_decision,
                "parallel": len(next_nodes) > 1,
                "latency_ms": latency_ms,
            },
        )

        return {
            "routing_decision": routing_decision,
            "node_path": state["node_path"] + ["router"],
            "latencies": {**state["latencies"], "router": latency_ms},
            "messages": state["messages"]
            + [{"role": "system", "content": f"Routing to: {routing_decision}"}],
        }


def routing_function(state: OrchestratorState) -> str:
    """Conditional routing function for LangGraph edges with confidence awareness."""
    frame = state.get("frame", {})
    intent = frame.get("intent", "recent_pubs_by_topic")
    intent_confidence = state.get("intent_confidence", 0.0)

    # Low confidence fallback to hybrid search (M1: still goes to pubmed_search)
    if intent_confidence < 0.5:
        logger.info(
            f"Low confidence ({intent_confidence:.2f}), routing to hybrid search"
        )
        return "rag_search"  # Note: graph_builder routes this to pubmed_search in M1

    # Map intents to tool nodes (M1 limitation: all go to pubmed_search)
    routing_map = {
        "recent_pubs_by_topic": "pubmed_search",
        "indication_phase_trials": "pubmed_search",  # Will be ctgov_search in M2
        "trials_with_pubs": "pubmed_search",  # Will support parallel in M2
        "hybrid_search": "pubmed_search",  # Will be rag_search in M2
    }

    return routing_map.get(intent, "pubmed_search")


def create_router_node(config: OrchestratorConfig):
    """Factory function to create router node."""
    return RouterNode(config)
