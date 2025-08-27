"""Tool execution nodes for LangGraph orchestrator."""

from datetime import UTC, datetime
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.types import OrchestratorState
from bio_mcp.sources.pubmed.client import PubMedClient, PubMedConfig

logger = get_logger(__name__)


class BaseToolNode:
    """Base class for tool execution nodes."""

    def __init__(self, config: OrchestratorConfig, tool_name: str):
        self.config = config
        self.tool_name = tool_name

    def _error_response(
        self, state: OrchestratorState, error_msg: str
    ) -> dict[str, Any]:
        """Generate error response."""
        return {
            "errors": state["errors"]
            + [
                {
                    "node": self.tool_name,
                    "error": error_msg,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ],
            "node_path": state["node_path"] + [self.tool_name],
        }


class PubMedSearchNode(BaseToolNode):
    """Node for executing PubMed searches."""

    def __init__(self, config: OrchestratorConfig):
        super().__init__(config, "pubmed_search")
        pubmed_config = PubMedConfig()
        self.client = PubMedClient(pubmed_config)

    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Execute PubMed search using normalized query."""
        start_time = datetime.now(UTC)

        # Use normalized query if available, fallback to original query and frame
        search_term = state.get("normalized_query")

        if not search_term:
            # Fallback to original query
            search_term = state.get("query")

        if not search_term:
            # Final fallback to frame entities (backward compatibility)
            frame = state.get("frame", {})
            entities = frame.get("entities", {})
            topic = entities.get("topic")
            indication = entities.get("indication")
            search_term = topic or indication

        if not search_term:
            return self._error_response(
                state, "No search term found in normalized_query, query, or frame"
            )

        logger.info(f"PubMed searching with term: '{search_term[:100]}...'")

        # Log enhancement details if available
        enhancement_metadata = state.get("query_enhancement_metadata") or {}
        if enhancement_metadata.get("enhancement_applied"):
            logger.info(
                f"Using enhanced query (was: '{enhancement_metadata.get('original_query', 'unknown')[:50]}...')"
            )

        try:
            # Search for PMIDs
            search_result = await self.client.search(query=search_term, limit=20)

            # Fetch full documents
            documents = []
            if search_result.pmids:
                doc_details = await self.client.fetch_documents(search_result.pmids)
                documents = [
                    {
                        "pmid": doc.pmid,
                        "title": doc.title,
                        "authors": doc.authors or [],
                        "year": doc.publication_date.year
                        if doc.publication_date
                        else None,
                        "abstract": doc.abstract,
                    }
                    for doc in doc_details
                ]

            # Calculate latency
            latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

            # Prepare results
            pubmed_results = {
                "total_count": search_result.total_count,
                "results": documents,
                "query": search_term,
            }

            logger.info(
                "PubMed search completed",
                extra={
                    "search_term": search_term,
                    "total_count": search_result.total_count,
                    "returned_count": len(documents),
                    "latency_ms": latency_ms,
                },
            )

            return {
                "pubmed_results": pubmed_results,
                "tool_calls_made": state["tool_calls_made"] + ["pubmed_search"],
                "cache_hits": {
                    **state["cache_hits"],
                    "pubmed_search": False,
                },  # Simple implementation
                "latencies": {**state["latencies"], "pubmed_search": latency_ms},
                "node_path": state["node_path"] + ["pubmed_search"],
                "messages": state["messages"]
                + [
                    {
                        "role": "system",
                        "content": f"PubMed search completed: {len(documents)} results",
                    }
                ],
            }

        except Exception as e:
            logger.error(
                "PubMed search failed",
                extra={"search_term": search_term, "error": str(e)},
            )

            # Calculate latency even for errors
            latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

            return {
                "pubmed_results": None,
                "tool_calls_made": state["tool_calls_made"] + ["pubmed_search"],
                "cache_hits": {**state["cache_hits"], "pubmed_search": False},
                "latencies": {**state["latencies"], "pubmed_search": latency_ms},
                "errors": state["errors"]
                + [
                    {
                        "node": "pubmed_search",
                        "error": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ],
                "node_path": state["node_path"] + ["pubmed_search"],
                "messages": state["messages"]
                + [{"role": "system", "content": f"PubMed search failed: {e!s}"}],
            }


# Factory functions
def create_pubmed_search_node(config: OrchestratorConfig):
    """Factory function to create PubMed search node."""
    return PubMedSearchNode(config)
