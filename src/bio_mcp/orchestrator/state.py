"""LangGraph state management and runtime logic (types moved to types.py)."""

from typing import Any

# Import types from dedicated types module to avoid circular dependencies
from bio_mcp.orchestrator.types import OrchestratorState


def create_initial_state(
    query: str, config: dict[str, Any] | None = None
) -> OrchestratorState:
    """Create initial orchestrator state for a query."""
    return OrchestratorState(
        # Input
        query=query,
        config=config or {},
        # Query normalization
        normalized_query=None,
        query_entities=None,
        query_enhancement_metadata=None,
        # Processing stages
        frame=None,
        routing_decision=None,
        # LLM Parser confidence scores
        intent_confidence=None,
        entity_confidence=None,
        # Tool results
        pubmed_results=None,
        ctgov_results=None,
        rag_results=None,
        # Metadata
        tool_calls_made=[],
        cache_hits={},
        latencies={},
        errors=[],
        node_path=[],
        # Output
        answer=None,
        orchestrator_checkpoint_id=None,
        # Messages
        messages=[],
    )


def merge_state_updates(
    state: OrchestratorState, updates: dict[str, Any]
) -> OrchestratorState:
    """Merge updates into orchestrator state safely."""
    # Create a copy of the state
    new_state = state.copy()

    # Apply updates
    for key, value in updates.items():
        if key in new_state:
            new_state[key] = value
        else:
            # Log warning for unknown keys but don't fail
            import logging

            logging.getLogger(__name__).warning(f"Unknown state key in update: {key}")

    return new_state


def get_state_summary(state: OrchestratorState) -> dict[str, Any]:
    """Get a summary of current state for debugging."""
    return {
        "query": state["query"][:100] + "..."
        if len(state["query"]) > 100
        else state["query"],
        "frame_intent": state["frame"]["intent"] if state["frame"] else None,
        "routing_decision": state["routing_decision"],
        "tool_calls_count": len(state["tool_calls_made"]),
        "node_path": state["node_path"],
        "has_answer": state["answer"] is not None,
        "error_count": len(state["errors"]),
        "checkpoint_id": state["orchestrator_checkpoint_id"],
    }
