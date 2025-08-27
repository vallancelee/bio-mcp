"""Core LangGraph setup for bio-mcp orchestrator."""

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import OrchestratorState

logger = get_logger(__name__)


class BioMCPGraph:
    """LangGraph-based orchestrator for bio-mcp."""

    def __init__(self, config: OrchestratorConfig | None = None):
        self.config = config or OrchestratorConfig()
        self._graph = None
        self._compiled_graph = None
        self._checkpointer = None

    def build_graph(self) -> StateGraph:
        """Build the orchestrator state graph."""
        if self._graph is not None:
            return self._graph

        workflow = StateGraph(OrchestratorState)

        # Placeholder nodes - will be implemented in M1
        workflow.add_node("parse_frame", self._parse_frame_placeholder)
        workflow.add_node("route_intent", self._route_intent_placeholder)
        workflow.add_node("synthesize", self._synthesize_placeholder)

        # Basic flow structure
        workflow.set_entry_point("parse_frame")
        workflow.add_edge("parse_frame", "route_intent")
        workflow.add_edge("route_intent", "synthesize")  # Simplified for now
        workflow.add_edge("synthesize", END)

        self._graph = workflow
        logger.info("Built orchestrator graph with placeholder nodes")
        return workflow

    def compile_graph(self):
        """Compile the graph with checkpointing."""
        if self._compiled_graph is not None:
            return self._compiled_graph

        if self._graph is None:
            self.build_graph()

        # Set up memory checkpointer for state persistence (M0 scaffolding)
        self._checkpointer = MemorySaver()

        self._compiled_graph = self._graph.compile(
            checkpointer=self._checkpointer, debug=self.config.langgraph.debug_mode
        )

        logger.info("Compiled orchestrator graph with checkpointing")
        return self._compiled_graph

    async def invoke(
        self, query: str, config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute the graph for a single query."""
        graph = self.compile_graph()

        initial_state = OrchestratorState(
            query=query,
            config=config or {},
            normalized_query=None,
            query_entities=None,
            query_enhancement_metadata=None,
            frame=None,
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
            messages=[],
        )

        try:
            # LangGraph requires a thread_id when using checkpointer
            config = {"configurable": {"thread_id": "default-thread"}}
            result = await graph.ainvoke(initial_state, config=config)
            logger.info(
                "Graph execution completed",
                extra={
                    "query": query,
                    "tool_calls": len(result.get("tool_calls_made", [])),
                    "errors": len(result.get("errors", [])),
                    "node_path": result.get("node_path", []),
                },
            )
            return result

        except Exception as e:
            logger.error(
                "Graph execution failed", extra={"query": query, "error": str(e)}
            )
            raise

    async def stream(self, query: str, config: dict[str, Any] | None = None):
        """Stream graph execution results."""
        graph = self.compile_graph()

        initial_state = OrchestratorState(
            query=query,
            config=config or {},
            normalized_query=None,
            query_entities=None,
            query_enhancement_metadata=None,
            frame=None,
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
            messages=[],
        )

        # LangGraph requires a thread_id when using checkpointer
        config = {"configurable": {"thread_id": "default-thread"}}
        async for chunk in graph.astream(initial_state, config=config):
            yield chunk

    # Placeholder node implementations (will be replaced in M1)

    def _parse_frame_placeholder(self, state: OrchestratorState) -> dict[str, Any]:
        """Placeholder frame parser node."""
        logger.info("Parsing frame (placeholder)")
        return {
            "frame": {
                "intent": "recent_pubs_by_topic",
                "entities": {"topic": state["query"]},
                "filters": {},
                "fetch_policy": "cache_then_network",
                "time_budget_ms": 5000,
            },
            "node_path": state["node_path"] + ["parse_frame"],
            "messages": state["messages"]
            + [{"role": "system", "content": f"Parsed query: {state['query']}"}],
        }

    def _route_intent_placeholder(self, state: OrchestratorState) -> dict[str, Any]:
        """Placeholder router node."""
        frame = state["frame"]
        intent = frame["intent"] if frame else "recent_pubs_by_topic"

        logger.info(f"Routing intent: {intent}")
        return {
            "routing_decision": intent,
            "node_path": state["node_path"] + ["route_intent"],
            "messages": state["messages"]
            + [{"role": "system", "content": f"Routed to intent: {intent}"}],
        }

    def _synthesize_placeholder(self, state: OrchestratorState) -> dict[str, Any]:
        """Placeholder synthesizer node."""
        query = state["query"]

        # Generate simple response
        answer = f"Placeholder response for: {query}"
        orchestrator_checkpoint_id = f"session_{hash(query) % 10000}"

        logger.info("Synthesizing response (placeholder)")
        return {
            "answer": answer,
            "orchestrator_checkpoint_id": orchestrator_checkpoint_id,
            "node_path": state["node_path"] + ["synthesize"],
            "messages": state["messages"] + [{"role": "assistant", "content": answer}],
        }
