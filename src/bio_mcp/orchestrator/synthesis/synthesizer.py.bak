"""Advanced result synthesis with citations and quality scoring."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import OrchestratorState

logger = get_logger(__name__)


class AnswerType(Enum):
    """Type of answer generated."""

    COMPREHENSIVE = "comprehensive"  # Full results from all sources
    PARTIAL = "partial"  # Some sources failed
    MINIMAL = "minimal"  # Only one source succeeded
    EMPTY = "empty"  # No useful results


@dataclass
class SynthesisMetrics:
    """Metrics for synthesis quality."""

    total_sources: int
    successful_sources: int
    total_results: int
    unique_results: int
    citation_count: int
    quality_score: float
    synthesis_time_ms: float
    answer_type: AnswerType


@dataclass
class Citation:
    """Citation information."""

    id: str
    source: str  # pubmed, clinicaltrials, etc.
    title: str
    authors: list[str]
    journal: str | None = None
    year: int | None = None
    pmid: str | None = None
    nct_id: str | None = None
    url: str | None = None
    relevance_score: float = 0.0


def trace_method(method_name: str):
    """Simple tracing decorator for synthesis methods."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = datetime.now(UTC)
            logger.info(f"Starting {method_name}")
            try:
                result = await func(*args, **kwargs)
                duration = (datetime.now(UTC) - start_time).total_seconds() * 1000
                logger.info(f"Completed {method_name}", extra={"duration_ms": duration})
                return result
            except Exception as e:
                duration = (datetime.now(UTC) - start_time).total_seconds() * 1000
                logger.error(
                    f"Failed {method_name}",
                    extra={"error": str(e), "duration_ms": duration},
                )
                raise

        return wrapper

    return decorator


class AdvancedSynthesizer:
    """Advanced result synthesizer with citation and quality management."""

    def __init__(self, config: OrchestratorConfig):
        self.config = config

    @trace_method("advanced_synthesis")
    async def synthesize(self, state: OrchestratorState) -> dict[str, Any]:
        """Synthesize comprehensive answer from state results."""
        start_time = datetime.now(UTC)

        # Extract and process results
        result_data = self._extract_results(state)

        # Generate citations
        citations = await self._extract_citations(result_data)

        # Score answer quality
        quality_metrics = self._score_results(result_data, citations)

        # Determine answer type
        answer_type = self._classify_answer_type(result_data)

        # Generate answer content
        answer_content = await self._generate_answer(
            state, result_data, citations, quality_metrics, answer_type
        )

        # Generate checkpoint ID
        checkpoint_id = self._generate_checkpoint_id(state, result_data)

        # Calculate synthesis metrics
        synthesis_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
        metrics = SynthesisMetrics(
            total_sources=len(result_data),
            successful_sources=len(
                [r for r in result_data.values() if r.get("results")]
            ),
            total_results=sum(len(r.get("results", [])) for r in result_data.values()),
            unique_results=len(self._deduplicate_results(result_data)),
            citation_count=len(citations),
            quality_score=quality_metrics.get("overall_score", 0.0),
            synthesis_time_ms=synthesis_time,
            answer_type=answer_type,
        )

        logger.info(
            "Synthesis completed",
            extra={
                "checkpoint_id": checkpoint_id,
                "answer_type": answer_type.value,
                "total_results": metrics.total_results,
                "citations": metrics.citation_count,
                "quality_score": metrics.quality_score,
                "synthesis_time_ms": synthesis_time,
            },
        )

        return {
            "answer": answer_content,
            "checkpoint_id": checkpoint_id,
            "citations": [self._citation_to_dict(c) for c in citations],
            "quality_metrics": quality_metrics,
            "synthesis_metrics": {
                "total_sources": metrics.total_sources,
                "successful_sources": metrics.successful_sources,
                "total_results": metrics.total_results,
                "unique_results": metrics.unique_results,
                "citation_count": metrics.citation_count,
                "quality_score": metrics.quality_score,
                "synthesis_time_ms": metrics.synthesis_time_ms,
                "answer_type": metrics.answer_type.value,
            },
            "node_path": state["node_path"] + ["advanced_synthesizer"],
            "latencies": {**state["latencies"], "synthesizer": synthesis_time},
            "messages": state["messages"]
            + [{"role": "assistant", "content": answer_content}],
        }

    def _extract_results(self, state: OrchestratorState) -> dict[str, dict[str, Any]]:
        """Extract results from all sources in state."""
        results = {}

        # PubMed results
        if state.get("pubmed_results"):
            results["pubmed"] = state["pubmed_results"]

        # ClinicalTrials results
        if state.get("ctgov_results"):
            results["clinicaltrials"] = state["ctgov_results"]

        # RAG results
        if state.get("rag_results"):
            results["rag"] = state["rag_results"]

        return results

    def _classify_answer_type(
        self, result_data: dict[str, dict[str, Any]]
    ) -> AnswerType:
        """Classify the type of answer based on available results."""
        successful_sources = [
            source
            for source, data in result_data.items()
            if data.get("results") and len(data["results"]) > 0
        ]

        total_results = sum(
            len(data.get("results", [])) for data in result_data.values()
        )

        if len(successful_sources) == 0 or total_results == 0:
            return AnswerType.EMPTY
        elif len(successful_sources) == 1 and total_results < 5:
            return AnswerType.MINIMAL
        elif len(successful_sources) < len(result_data) or total_results < 10:
            return AnswerType.PARTIAL
        else:
            return AnswerType.COMPREHENSIVE

    async def _generate_answer(
        self,
        state: OrchestratorState,
        result_data: dict[str, dict[str, Any]],
        citations: list[Citation],
        quality_metrics: dict[str, Any],
        answer_type: AnswerType,
    ) -> str:
        """Generate formatted answer content."""

        # Simple template-based generation for now
        if answer_type == AnswerType.EMPTY:
            return f"""# No Results Found

**Query:** {state.get("query", "")}

❌ No relevant results were found for your query.

## Suggestions:
- Try broader search terms
- Check spelling and terminology
- Consider alternative keywords or synonyms
- Reduce the number of filters if any were applied

*Searched sources: PubMed, ClinicalTrials.gov, and internal documents*
"""

        # Build comprehensive answer
        parts = []
        parts.append("# Biomedical Research Results")
        parts.append(f"**Query:** {state.get('query', '')}")
        parts.append(
            f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

        # Add results summary
        total_results = sum(
            len(data.get("results", [])) for data in result_data.values()
        )
        parts.append("\n## Results Summary")
        parts.append(
            f"Found **{total_results} total results** across {len(result_data)} sources:"
        )

        for source, data in result_data.items():
            source_results = data.get("results", [])
            if source_results:
                source_name = source.replace("_", " ").title()
                parts.append(f"- **{len(source_results)} {source_name} results**")

        # Add citation count
        if citations:
            parts.append(f"- **{len(citations)} citations** extracted")

        return "\n".join(parts)

    def _generate_checkpoint_id(
        self, state: OrchestratorState, result_data: dict[str, dict[str, Any]]
    ) -> str:
        """Generate deterministic checkpoint ID."""
        # Create content hash from query, frame, and result structure
        query = state.get("query", "")
        frame = state.get("frame", {})

        # Create result signature (counts and sources, not full content)
        result_signature = {
            source: {
                "count": len(data.get("results", [])),
                "has_data": bool(data.get("results")),
            }
            for source, data in result_data.items()
        }

        # Create hash input
        hash_input = f"{query}:{frame.get('intent', '')}:{result_signature}"
        content_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12]

        # Format: ckpt_YYYYMMDD_HHMMSS_HASH
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return f"ckpt_{timestamp}_{content_hash}"

    def _deduplicate_results(
        self, result_data: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Deduplicate results across sources."""
        seen_ids = set()
        unique_results = []

        for source, data in result_data.items():
            results = data.get("results", [])

            for result in results:
                # Create unique identifier
                result_id = self._get_result_id(result, source)

                if result_id not in seen_ids:
                    seen_ids.add(result_id)
                    result_with_source = {**result, "_source": source}
                    unique_results.append(result_with_source)

        return unique_results

    def _get_result_id(self, result: dict[str, Any], source: str) -> str:
        """Get unique identifier for result."""
        if source == "pubmed" and result.get("pmid"):
            return f"pmid:{result['pmid']}"
        elif source == "clinicaltrials" and result.get("nct_id"):
            return f"nct:{result['nct_id']}"
        elif result.get("title"):
            # Use title hash for other sources
            title_hash = hashlib.md5(result["title"].encode()).hexdigest()[:8]
            return f"{source}:{title_hash}"
        else:
            # Fallback to full content hash
            content_hash = hashlib.md5(str(result).encode()).hexdigest()[:8]
            return f"{source}:{content_hash}"

    def _calculate_cache_hit_rate(self, state: OrchestratorState) -> float:
        """Calculate cache hit rate from state."""
        cache_hits = state.get("cache_hits", {})
        if not cache_hits:
            return 0.0

        hits = sum(1 for hit in cache_hits.values() if hit)
        return hits / len(cache_hits)

    async def _extract_citations(
        self, result_data: dict[str, dict[str, Any]]
    ) -> list[Citation]:
        """Extract citations from all result sources."""
        all_citations = []
        citation_counter = 0

        for source, data in result_data.items():
            results = data.get("results", [])

            for result in results:
                citation_counter += 1

                if source == "pubmed":
                    citation = self._create_pubmed_citation(citation_counter, result)
                elif source == "clinicaltrials":
                    citation = self._create_clinical_trial_citation(
                        citation_counter, result
                    )
                elif source == "rag":
                    citation = self._create_rag_citation(citation_counter, result)
                else:
                    continue

                all_citations.append(citation)

        # Sort by relevance score
        all_citations.sort(key=lambda c: c.relevance_score, reverse=True)
        return all_citations

    def _create_pubmed_citation(self, counter: int, result: dict[str, Any]) -> Citation:
        """Create citation from PubMed result."""
        # Extract authors
        authors = result.get("authors", [])
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",")]

        # Extract year from date
        year = None
        if result.get("publication_date"):
            try:
                year = datetime.fromisoformat(result["publication_date"]).year
            except (ValueError, TypeError):
                pass

        return Citation(
            id=str(counter),
            source="pubmed",
            title=result.get("title", "Untitled"),
            authors=authors[:3],  # Limit to first 3 authors
            journal=result.get("journal"),
            year=year,
            pmid=result.get("pmid"),
            url=f"https://pubmed.ncbi.nlm.nih.gov/{result.get('pmid')}"
            if result.get("pmid")
            else None,
            relevance_score=self._calculate_pubmed_relevance(result),
        )

    def _create_clinical_trial_citation(
        self, counter: int, result: dict[str, Any]
    ) -> Citation:
        """Create citation from ClinicalTrials result."""
        # Extract sponsor as "author"
        sponsors = []
        if result.get("sponsor"):
            sponsors = [result["sponsor"]]

        # Extract start year
        year = None
        if result.get("start_date"):
            try:
                year = datetime.fromisoformat(result["start_date"]).year
            except (ValueError, TypeError):
                pass

        return Citation(
            id=str(counter),
            source="clinicaltrials",
            title=result.get("title", "Untitled Trial"),
            authors=sponsors,
            year=year,
            nct_id=result.get("nct_id"),
            url=f"https://clinicaltrials.gov/ct2/show/{result.get('nct_id')}"
            if result.get("nct_id")
            else None,
            relevance_score=self._calculate_trial_relevance(result),
        )

    def _create_rag_citation(self, counter: int, result: dict[str, Any]) -> Citation:
        """Create citation from RAG result."""
        return Citation(
            id=str(counter),
            source="rag",
            title=result.get("title", "Document"),
            authors=[],  # RAG typically doesn't have author info
            relevance_score=result.get("score", 0.0),
            url=result.get("url"),
        )

    def _calculate_pubmed_relevance(self, result: dict[str, Any]) -> float:
        """Calculate relevance score for PubMed result."""
        score = 0.5  # Base score

        # Recent publications get higher score
        if result.get("publication_date"):
            try:
                pub_date = datetime.fromisoformat(result["publication_date"])
                days_old = (datetime.now() - pub_date).days
                if days_old < 365:  # Within last year
                    score += 0.3
                elif days_old < 1825:  # Within last 5 years
                    score += 0.1
            except (ValueError, TypeError):
                pass

        # High-impact journals (would need journal impact factor data)
        journal = result.get("journal", "").lower()
        if any(
            name in journal for name in ["nature", "science", "cell", "nejm", "lancet"]
        ):
            score += 0.2

        return min(1.0, score)

    def _calculate_trial_relevance(self, result: dict[str, Any]) -> float:
        """Calculate relevance score for clinical trial."""
        score = 0.5  # Base score

        # Phase 3 trials are generally more significant
        phase = result.get("phase", "").lower()
        if "3" in phase:
            score += 0.3
        elif "2" in phase:
            score += 0.2

        # Active/recruiting trials are more relevant
        status = result.get("status", "").lower()
        if "recruiting" in status:
            score += 0.2
        elif "active" in status:
            score += 0.1

        # Large trials are often more significant
        enrollment = result.get("enrollment", 0)
        if enrollment > 1000:
            score += 0.2
        elif enrollment > 100:
            score += 0.1

        return min(1.0, score)

    def _score_results(
        self, result_data: dict[str, dict[str, Any]], citations: list[Citation]
    ) -> dict[str, Any]:
        """Score the overall quality of results."""
        # Simple quality scoring for now
        completeness = len(result_data) / 3.0  # Assume 3 main sources

        # Calculate recency score
        if citations:
            current_year = datetime.now().year
            recent_count = sum(
                1 for c in citations if c.year and (current_year - c.year) <= 2
            )
            recency = recent_count / len(citations)
        else:
            recency = 0.0

        # Overall score (weighted average)
        overall = (completeness * 0.6) + (recency * 0.4)

        return {
            "completeness_score": completeness,
            "recency_score": recency,
            "authority_score": 0.5,  # Placeholder
            "diversity_score": 0.5,  # Placeholder
            "relevance_score": 0.5,  # Placeholder
            "overall_score": overall,
            "total_sources": len(result_data),
            "has_systematic_reviews": False,  # Placeholder
            "has_recent_trials": any(
                result_data.get("clinicaltrials", {}).get("results", [])
            ),
            "has_multiple_perspectives": len(result_data) > 1,
            "potential_conflicts": [],
        }

    def _citation_to_dict(self, citation: Citation) -> dict[str, Any]:
        """Convert Citation dataclass to dictionary."""
        return {
            "id": citation.id,
            "source": citation.source,
            "title": citation.title,
            "authors": citation.authors,
            "journal": citation.journal,
            "year": citation.year,
            "pmid": citation.pmid,
            "nct_id": citation.nct_id,
            "url": citation.url,
            "relevance_score": citation.relevance_score,
        }
