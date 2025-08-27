"""LangGraph state schema for bio-mcp orchestrator."""

from datetime import datetime
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# Core state for the orchestrator graph
class OrchestratorState(TypedDict):
    """Central state for bio-mcp orchestrator workflow."""

    # Input data
    query: str
    config: dict[str, Any]

    # Query normalization
    normalized_query: str | None  # Enhanced/optimized query for search
    query_entities: dict[str, Any] | None  # Extracted entities (drugs, companies)
    query_enhancement_metadata: dict[str, Any] | None  # Normalization details

    # Processing stages
    frame: dict[str, Any] | None  # Parsed query intent
    routing_decision: str | None  # Which path to take

    # LLM Parser confidence scores
    intent_confidence: float | None
    entity_confidence: dict[str, float] | None

    # Tool execution results
    pubmed_results: dict[str, Any] | None
    ctgov_results: dict[str, Any] | None
    rag_results: dict[str, Any] | None

    # Metadata and tracing
    tool_calls_made: list[str]
    cache_hits: dict[str, bool]
    latencies: dict[str, float]
    errors: list[dict[str, Any]]
    node_path: list[str]  # Execution path through graph

    # Output
    answer: str | None
    orchestrator_checkpoint_id: (
        str | None
    )  # Renamed to avoid LangGraph reserved field collision

    # Messages for tracing and debugging
    messages: Annotated[list[dict[str, Any]], add_messages]


class FrameModel(BaseModel):
    """Pydantic model for Frame validation."""

    intent: str
    entities: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    tool_hints: dict[str, Any] = Field(default_factory=dict)
    fetch_policy: str = "cache_then_network"
    time_budget_ms: int = 5000
    parallel_limit: int = Field(default=5, description="Max parallel operations")

    # LLM parser fields
    intent_confidence: float = Field(
        default=1.0, description="Confidence in intent classification"
    )
    entity_confidence: dict[str, float] = Field(
        default_factory=dict, description="Per-entity confidence scores"
    )
    parser_version: str = Field(
        default="v2025.08.27-a", description="Parser version for tracking"
    )


class NodeResult(BaseModel):
    """Standard result format for graph nodes."""

    success: bool
    data: Any = None
    error_code: str | None = None
    error_message: str | None = None
    cache_hit: bool = False
    rows: int = 0
    latency_ms: float = 0
    node_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
