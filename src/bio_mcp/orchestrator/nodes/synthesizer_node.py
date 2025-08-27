"""Synthesizer node for generating final answers."""

from datetime import UTC, datetime
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import OrchestratorState

logger = get_logger(__name__)


class SynthesizerNode:
    """Node that synthesizes results into final answer."""

    def __init__(self, config: OrchestratorConfig):
        self.config = config

    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Synthesize results into final answer."""
        start_time = datetime.now(UTC)

        # Gather all results
        pubmed_results = state.get("pubmed_results")
        ctgov_results = state.get("ctgov_results")
        rag_results = state.get("rag_results")

        # Generate answer based on available results
        answer = self._generate_answer(
            query=state["query"],
            frame=state.get("frame"),
            pubmed=pubmed_results,
            ctgov=ctgov_results,
            rag=rag_results,
        )

        # Generate session ID (using simple approach for M1)
        session_id = f"session_{hash(state['query']) % 10000}"

        # Calculate latency
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

        logger.info(
            "Answer synthesized",
            extra={
                "session_id": session_id,
                "answer_length": len(answer),
                "latency_ms": latency_ms,
                "tool_calls": len(state.get("tool_calls_made", [])),
                "cache_hit_rate": self._calculate_cache_hit_rate(state),
            },
        )

        return {
            "answer": answer,
            "orchestrator_checkpoint_id": session_id,
            "node_path": state["node_path"] + ["synthesizer"],
            "latencies": {**state["latencies"], "synthesizer": latency_ms},
            "messages": state["messages"] + [{"role": "assistant", "content": answer}],
        }

    def _generate_answer(
        self,
        query: str,
        frame: dict | None,
        pubmed: dict | None,
        ctgov: dict | None,
        rag: dict | None,
    ) -> str:
        """Generate answer from available results."""
        answer_parts = []

        # Header
        intent = frame.get("intent", "unknown") if frame else "unknown"
        answer_parts.append("## Query Analysis")
        answer_parts.append(f"Intent: {intent}")

        if frame and frame.get("entities"):
            entities = frame["entities"]
            entity_lines = [f"- {k}: {v}" for k, v in entities.items() if v]
            if entity_lines:
                answer_parts.append("Entities identified:")
                answer_parts.extend(entity_lines)

        answer_parts.append("\n## Results")

        # PubMed results
        if pubmed and pubmed.get("results"):
            answer_parts.append(
                f"\n### PubMed Publications ({len(pubmed['results'])} found)"
            )
            for i, pub in enumerate(pubmed["results"][:5], 1):
                answer_parts.append(
                    f"{i}. **{pub.get('title', 'Untitled')}**\n"
                    f"   - PMID: {pub.get('pmid', 'N/A')}\n"
                    f"   - Authors: {', '.join(pub.get('authors', [])[:3])}...\n"
                    f"   - Year: {pub.get('year', 'N/A')}"
                )

        # ClinicalTrials results
        if ctgov and ctgov.get("results"):
            answer_parts.append(
                f"\n### Clinical Trials ({len(ctgov['results'])} found)"
            )
            for i, trial in enumerate(ctgov["results"][:5], 1):
                answer_parts.append(
                    f"{i}. **{trial.get('title', 'Untitled')}**\n"
                    f"   - NCT ID: {trial.get('nct_id', 'N/A')}\n"
                    f"   - Phase: {trial.get('phase', 'N/A')}\n"
                    f"   - Status: {trial.get('status', 'N/A')}\n"
                    f"   - Sponsor: {trial.get('sponsor', 'N/A')}"
                )

        # RAG results
        if rag and rag.get("results"):
            answer_parts.append(
                f"\n### Related Documents ({len(rag['results'])} found)"
            )
            for i, doc in enumerate(rag["results"][:3], 1):
                answer_parts.append(
                    f"{i}. {doc.get('title', 'Untitled')}\n"
                    f"   - Score: {doc.get('score', 0):.3f}\n"
                    f"   - {doc.get('snippet', 'No snippet available')[:200]}..."
                )

        # Summary
        total_results = (
            len(pubmed.get("results", []))
            if pubmed
            else 0 + len(ctgov.get("results", []))
            if ctgov
            else 0 + len(rag.get("results", []))
            if rag
            else 0
        )

        if total_results == 0:
            answer_parts.append("\n*No results found for your query.*")
        else:
            answer_parts.append(f"\n---\n*Total results found: {total_results}*")

        return "\n".join(answer_parts)

    def _calculate_cache_hit_rate(self, state: OrchestratorState) -> float:
        """Calculate cache hit rate from state."""
        cache_hits = state.get("cache_hits", {})
        if not cache_hits:
            return 0.0

        total = len(cache_hits)
        hits = sum(1 for hit in cache_hits.values() if hit)
        return hits / total if total > 0 else 0.0


def create_synthesizer_node(config: OrchestratorConfig):
    """Factory function to create synthesizer node."""
    return SynthesizerNode(config)
