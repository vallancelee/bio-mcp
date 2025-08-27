"""
LangGraph Orchestrator Integration for BioInvest AI Copilot POC
"""

import os

# Import the actual LangGraph orchestrator from Bio-MCP
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../.."))

# Import LangGraph dependencies - fail fast if not available
from bio_mcp.config.logging_config import get_logger
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

logger = get_logger(__name__)


class LangGraphOrchestrator:
    """LangGraph-powered orchestrator for biomedical research queries."""

    def __init__(self):
        """Initialize the LangGraph orchestrator."""
        self.graph = None
        self.compiled_graph = None
        self.checkpointer_ctx = None
        self.checkpointer = None

    async def initialize(self):
        """Initialize the LangGraph orchestrator asynchronously."""
        try:
            logger.info("Initializing LangGraph orchestrator...")

            # Import here to avoid circular imports
            from bio_mcp.orchestrator.config import OrchestratorConfig
            from bio_mcp.orchestrator.graph_builder import build_orchestrator_graph

            config = OrchestratorConfig()

            # Build the graph
            self.graph = build_orchestrator_graph(config)

            # Create async checkpointer context manager for state persistence
            self.checkpointer_ctx = AsyncSqliteSaver.from_conn_string(":memory:")
            self.checkpointer = await self.checkpointer_ctx.__aenter__()

            # Compile the graph with checkpointing
            self.compiled_graph = self.graph.compile(checkpointer=self.checkpointer)

            logger.info(
                "LangGraph orchestrator initialized successfully with async checkpointing"
            )

        except Exception as e:
            logger.error(f"LangGraph orchestrator initialization failed: {e}")
            if self.checkpointer_ctx:
                try:
                    await self.checkpointer_ctx.__aexit__(None, None, None)
                except Exception:
                    pass
            raise RuntimeError(f"LangGraph orchestrator setup failed: {e}") from e

    async def cleanup(self):
        """Clean up resources when orchestrator is no longer needed."""
        if self.checkpointer_ctx:
            try:
                await self.checkpointer_ctx.__aexit__(None, None, None)
                self.checkpointer_ctx = None
                self.checkpointer = None
                logger.info("LangGraph async checkpointer cleaned up successfully")
            except Exception as e:
                logger.warning(f"Error during async checkpointer cleanup: {e}")
        else:
            logger.info("LangGraph orchestrator cleaned up successfully")

    def __del__(self):
        """Destructor to ensure cleanup on object deletion."""
        # Cannot call async methods from __del__, cleanup must be done explicitly
        if self.checkpointer_ctx:
            logger.warning(
                "LangGraph orchestrator destroyed without proper async cleanup"
            )

    async def execute_research_query(
        self,
        query: str,
        sources: list[str],
        options: dict[str, Any],
        stream_callback: callable | None = None,
    ) -> dict[str, Any]:
        """
        Execute research query using LangGraph orchestrator.

        Args:
            query: The research query
            sources: List of data sources to query
            options: Query options (max_results, priority, etc.)
            stream_callback: Callback for streaming updates

        Returns:
            Complete research results with synthesis
        """

        if not self.compiled_graph:
            raise RuntimeError("LangGraph orchestrator not properly initialized")

        # Store the original query text to ensure it's preserved
        self._current_query = query

        # Store intermediate source results as they're generated
        self._captured_sources = {}

        try:
            # Create unique thread for this query
            thread_id = str(uuid.uuid4())

            # Import state here to avoid circular imports
            from bio_mcp.orchestrator.state import OrchestratorState

            # Create initial state
            initial_state = OrchestratorState(
                query=query,
                config={
                    "sources": sources,
                    "max_results_per_source": options.get("max_results_per_source", 50),
                    "priority": options.get("priority", "balanced"),
                    "include_synthesis": options.get("include_synthesis", True),
                },
                # Query normalization fields
                normalized_query=None,
                query_entities=None,
                query_enhancement_metadata=None,
                # Processing stages
                frame=None,
                routing_decision=None,
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
                answer=None,
                orchestrator_checkpoint_id=None,
                messages=[],
            )

            logger.info(f"Starting LangGraph execution for query: {query[:100]}")

            # Execute the graph with streaming
            final_state = None
            node_count = 0

            if stream_callback:
                # Stream intermediate states and capture source results
                async for state in self.compiled_graph.astream(
                    initial_state, {"configurable": {"thread_id": thread_id}}
                ):
                    node_count += 1
                    current_node = list(state.keys())[0] if state else "unknown"

                    # Update final state
                    if state:
                        final_state = list(state.values())[0]

                        # Capture source results from intermediate state
                        self._capture_source_results(current_node, final_state)

                        # Send progress updates
                        await stream_callback(
                            {
                                "event": "node_started",
                                "data": {
                                    "node": current_node,
                                    "step": node_count,
                                    "timestamp": datetime.now(UTC).isoformat(),
                                },
                            }
                        )

                        # Send node completion
                        await stream_callback(
                            {
                                "event": "node_completed",
                                "data": {
                                    "node": current_node,
                                    "step": node_count,
                                    "results_preview": self._get_results_preview(
                                        final_state
                                    ),
                                    "timestamp": datetime.now(UTC).isoformat(),
                                },
                            }
                        )
            else:
                # Execute without streaming, but still capture intermediate states
                async for state in self.compiled_graph.astream(
                    initial_state, {"configurable": {"thread_id": thread_id}}
                ):
                    node_count += 1
                    current_node = list(state.keys())[0] if state else "unknown"

                    if state:
                        final_state = list(state.values())[0]
                        # Capture source results even without streaming callback
                        self._capture_source_results(current_node, final_state)

            logger.info(f"LangGraph execution completed in {node_count} steps")

            # Format results for POC frontend
            return await self._format_langgraph_results(final_state, stream_callback)

        except Exception as e:
            logger.error(f"LangGraph execution failed: {e}")
            if stream_callback:
                await stream_callback(
                    {
                        "event": "orchestration_failed",
                        "data": {
                            "error": f"LangGraph execution error: {str(e)}",
                            "error_type": type(e).__name__,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    }
                )
            raise RuntimeError(f"LangGraph orchestration failed: {e}") from e

    def _capture_source_results(self, current_node: str, state):
        """Capture source results from intermediate states during LangGraph execution."""

        # Only capture results from tool execution nodes
        if current_node in ["pubmed_search", "ctgov_search", "rag_search"]:
            logger.info(f"Capturing results from {current_node}")

            # Map node names to result field names and capture results
            field_mapping = {
                "pubmed_search": ("pubmed_results", "pubmed"),
                "ctgov_search": ("ctgov_results", "clinical_trials"),
                "rag_search": ("rag_results", "rag"),
            }

            if current_node in field_mapping:
                state_field, source_key = field_mapping[current_node]

                # Extract results from state
                source_data = self._safe_get_state_field(state, state_field)
                if source_data:
                    self._captured_sources[source_key] = source_data
                    logger.info(
                        f"Captured {source_key} results: {type(source_data)} with keys {list(source_data.keys()) if isinstance(source_data, dict) else 'Not a dict'}"
                    )
                else:
                    logger.warning(
                        f"No results found in state field '{state_field}' for {current_node}"
                    )

    def _safe_get_state_field(self, state, field_name, default=None):
        """Safely get a field from state (dict or object)."""
        if isinstance(state, dict):
            return state.get(field_name, default)
        else:
            return getattr(state, field_name, default)

    def _get_results_preview(self, state) -> dict[str, Any]:
        """Extract preview of results from current state."""
        preview = {}

        pubmed_results = self._safe_get_state_field(state, "pubmed_results")
        if pubmed_results:
            if isinstance(pubmed_results, dict) and "results" in pubmed_results:
                preview["pubmed_count"] = len(pubmed_results["results"])

        ctgov_results = self._safe_get_state_field(state, "ctgov_results")
        if ctgov_results:
            if isinstance(ctgov_results, dict) and "studies" in ctgov_results:
                preview["clinical_trials_count"] = len(ctgov_results["studies"])

        rag_results = self._safe_get_state_field(state, "rag_results")
        if rag_results:
            if isinstance(rag_results, dict) and "documents" in rag_results:
                preview["rag_count"] = len(rag_results["documents"])

        return preview

    async def _format_langgraph_results(
        self, final_state, stream_callback: callable | None = None
    ) -> dict[str, Any]:
        """Format LangGraph results for POC frontend consumption."""

        # Debug: Log the actual final_state structure
        logger.info(f"Final state type: {type(final_state)}")
        if isinstance(final_state, dict):
            logger.info(f"Final state keys: {list(final_state.keys())}")
            logger.info(f"Final state query: {final_state.get('query', 'NOT FOUND')}")
            # Log the full content to see what's actually in the state
            for key, value in final_state.items():
                if key == "answer" and value:
                    logger.info(f"  {key}: has answer (type: {type(value).__name__})")
                    # Try to parse the answer to see if it contains structured data
                    if isinstance(value, str):
                        logger.info(
                            f"  answer content (first 200 chars): {value[:200]}..."
                        )
                    elif isinstance(value, dict):
                        logger.info(f"  answer keys: {list(value.keys())}")
                elif key == "messages":
                    logger.info(
                        f"  {key}: {len(value) if isinstance(value, list) else type(value).__name__} messages"
                    )
                    # Log message types to see if they contain results
                    if isinstance(value, list) and value:
                        for i, msg in enumerate(value[-3:]):  # Last 3 messages
                            if isinstance(msg, dict):
                                logger.info(f"    msg{i}: keys={list(msg.keys())}")
                else:
                    logger.info(f"  {key}: {value}")
        else:
            logger.info(
                f"Final state attributes: {dir(final_state) if hasattr(final_state, '__dict__') else 'No dir available'}"
            )
            if hasattr(final_state, "query"):
                logger.info(f"Final state query attribute: {final_state.query}")

        # Use captured source results instead of trying to extract from final state
        raw_sources = getattr(self, "_captured_sources", {}).copy()

        logger.info(
            f"Using captured sources: {list(raw_sources.keys()) if raw_sources else 'none captured'}"
        )

        # Transform captured sources to the format expected by synthesis service
        # The synthesis service expects sources[source_name] = [list_of_results]
        sources = {}
        for source_name, source_data in raw_sources.items():
            if isinstance(source_data, dict) and "results" in source_data:
                # Extract the results array from the Bio-MCP response structure
                sources[source_name] = source_data["results"]
                logger.info(
                    f"Transformed {source_name}: {len(source_data['results'])} results"
                )
            else:
                # Fallback for unexpected structure
                logger.warning(
                    f"Unexpected source data structure for {source_name}: {type(source_data)}"
                )
                sources[source_name] = source_data

        # Fallback to final state extraction if no sources were captured
        if not sources:
            logger.warning(
                "No sources captured during execution, attempting final state extraction"
            )

            pubmed_results = self._safe_get_state_field(final_state, "pubmed_results")
            if pubmed_results:
                sources["pubmed"] = pubmed_results

            ctgov_results = self._safe_get_state_field(final_state, "ctgov_results")
            if ctgov_results:
                sources["clinical_trials"] = ctgov_results

            rag_results = self._safe_get_state_field(final_state, "rag_results")
            if rag_results:
                sources["rag"] = rag_results

        # Generate synthesis from LangGraph results
        if stream_callback:
            await stream_callback(
                {
                    "event": "synthesis_started",
                    "data": {"timestamp": datetime.now(UTC).isoformat()},
                }
            )

        # Use the synthesizer results if available from the graph
        synthesis = final_state.get("synthesis")
        if not synthesis:
            # Generate synthesis from collected results
            synthesis = await self._generate_synthesis_from_langgraph(
                final_state, sources
            )

        if stream_callback:
            await stream_callback(
                {
                    "event": "synthesis_completed",
                    "data": {
                        "insights_count": len(synthesis.get("key_insights", [])),
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                }
            )

        # Create metadata from LangGraph execution using safe field access
        metadata = {
            "langgraph_enabled": True,
            "tool_calls_made": self._safe_get_state_field(
                final_state, "tool_calls_made", []
            ),
            "cache_hits": self._safe_get_state_field(final_state, "cache_hits", {}),
            "latencies": self._safe_get_state_field(final_state, "latencies", {}),
            "errors": self._safe_get_state_field(final_state, "errors", []),
            "execution_path": self._reconstruct_execution_path(final_state),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Debug: Log what we're about to return
        result = {"sources": sources, "synthesis": synthesis, "metadata": metadata}

        logger.info(
            f"LangGraph returning sources: {list(sources.keys()) if sources else 'empty'}"
        )
        if sources:
            for source, data in sources.items():
                if isinstance(data, dict):
                    logger.info(
                        f"  {source}: keys={list(data.keys())}, has results={bool(data.get('results', []))}"
                    )
                else:
                    logger.info(f"  {source}: type={type(data)}")

        return result

    def _reconstruct_execution_path(self, state) -> list[str]:
        """Reconstruct the execution path through the graph."""
        path = ["parse_frame", "router"]  # Always start with these

        # Add tool nodes that were executed using safe field access
        if self._safe_get_state_field(state, "pubmed_results"):
            path.append("pubmed_search")
        if self._safe_get_state_field(state, "ctgov_results"):
            path.append("ctgov_search")
        if self._safe_get_state_field(state, "rag_results"):
            path.append("rag_search")

        # Always end with synthesizer if we got here
        path.append("synthesizer")

        return path

    async def _generate_synthesis_from_langgraph(
        self, state, sources: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate synthesis from LangGraph state and source results."""

        # Import synthesis service from original POC
        from ..services.synthesis import SynthesisService

        synthesis_service = SynthesisService()

        # Use the preserved query text first, fallback to state
        query_text = getattr(self, "_current_query", None)
        if not query_text:
            query_text = self._safe_get_state_field(state, "query", "Unknown query")

        logger.info(
            f"Using query text for synthesis: {query_text[:100] if query_text else 'None'}"
        )

        config = self._safe_get_state_field(state, "config", {})

        synthesis = await synthesis_service.synthesize_results(
            query=query_text, results=sources, options=config
        )

        # Enhance with LangGraph metadata
        synthesis["generation_metadata"]["langgraph_enabled"] = True
        synthesis["generation_metadata"]["execution_path"] = (
            self._reconstruct_execution_path(state)
        )
        synthesis["generation_metadata"]["tool_calls"] = len(
            state.get("tool_calls_made", [])
        )

        return synthesis

    def get_graph_visualization(self) -> dict[str, Any]:
        """Get a visualization of the LangGraph workflow."""
        if not self.graph:
            return {"error": "Graph not initialized"}

        try:
            # Export graph structure for frontend visualization
            nodes = []
            edges = []

            # This is a simplified representation - in production you'd use
            # the actual LangGraph visualization tools
            nodes = [
                {"id": "parse_frame", "label": "Parse Frame", "type": "processor"},
                {"id": "router", "label": "Intent Router", "type": "decision"},
                {"id": "pubmed_search", "label": "PubMed Search", "type": "tool"},
                {"id": "synthesizer", "label": "AI Synthesizer", "type": "processor"},
            ]

            edges = [
                {"from": "parse_frame", "to": "router"},
                {"from": "router", "to": "pubmed_search"},
                {"from": "pubmed_search", "to": "synthesizer"},
            ]

            return {
                "nodes": nodes,
                "edges": edges,
                "config": {
                    "max_iterations": 50,
                    "checkpoint_enabled": True,
                    "tracing_enabled": True,
                },
            }

        except Exception as e:
            logger.error(f"Failed to generate graph visualization: {e}")
            return {"error": str(e)}
