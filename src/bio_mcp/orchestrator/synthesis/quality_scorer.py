"""Quality scoring for synthesis results."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.synthesis.synthesizer import Citation

logger = get_logger(__name__)


@dataclass
class QualityMetrics:
    """Quality metrics for synthesized results."""

    completeness_score: float  # How complete is the answer
    recency_score: float  # How recent are the results
    authority_score: float  # Authority/reliability of sources
    diversity_score: float  # Diversity of sources/perspectives
    relevance_score: float  # Relevance to query
    overall_score: float  # Overall quality score

    # Detailed metrics
    total_sources: int
    primary_source_count: int  # High-quality sources
    recent_results_count: int  # Results from last 2 years
    high_impact_count: int  # High-impact publications/trials

    # Quality flags
    has_systematic_reviews: bool
    has_recent_trials: bool
    has_multiple_perspectives: bool
    potential_conflicts: list[str]


class QualityScorer:
    """Scores the quality of synthesized results."""

    def __init__(self):
        self.high_impact_journals = {
            "nature",
            "science",
            "cell",
            "nejm",
            "lancet",
            "jama",
            "bmj",
            "plos one",
            "nature medicine",
            "cell metabolism",
        }

        self.systematic_review_keywords = {
            "systematic review",
            "meta-analysis",
            "cochrane review",
            "pooled analysis",
            "umbrella review",
        }

    def score_results(
        self, result_data: dict[str, dict[str, Any]], citations: list[Citation]
    ) -> QualityMetrics:
        """Score the overall quality of results."""

        # Calculate individual scores
        completeness = self._score_completeness(result_data)
        recency = self._score_recency(citations)
        authority = self._score_authority(citations)
        diversity = self._score_diversity(result_data, citations)
        relevance = self._score_relevance(citations)

        # Calculate overall score (weighted average)
        overall = (
            completeness * 0.25
            + recency * 0.2
            + authority * 0.25
            + diversity * 0.15
            + relevance * 0.15
        )

        # Detailed metrics
        total_sources = len(result_data)
        primary_sources = self._count_primary_sources(citations)
        recent_results = self._count_recent_results(citations)
        high_impact = self._count_high_impact(citations)

        # Quality flags
        has_systematic = self._has_systematic_reviews(citations)
        has_recent_trials = self._has_recent_trials(result_data)
        has_perspectives = self._has_multiple_perspectives(result_data)
        conflicts = self._detect_conflicts(result_data, citations)

        return QualityMetrics(
            completeness_score=completeness,
            recency_score=recency,
            authority_score=authority,
            diversity_score=diversity,
            relevance_score=relevance,
            overall_score=overall,
            total_sources=total_sources,
            primary_source_count=primary_sources,
            recent_results_count=recent_results,
            high_impact_count=high_impact,
            has_systematic_reviews=has_systematic,
            has_recent_trials=has_recent_trials,
            has_multiple_perspectives=has_perspectives,
            potential_conflicts=conflicts,
        )

    def _score_completeness(self, result_data: dict[str, dict[str, Any]]) -> float:
        """Score completeness based on source coverage."""
        expected_sources = {"pubmed", "clinicaltrials", "rag"}
        available_sources = set(result_data.keys())

        # Base score from source coverage
        coverage_score = len(available_sources) / len(expected_sources)

        # Bonus for having results in each source
        result_quality = 0
        for source in available_sources:
            results = result_data[source].get("results", [])
            if len(results) > 0:
                result_quality += 0.2
            if len(results) >= 5:
                result_quality += 0.1

        return min(1.0, coverage_score * 0.6 + result_quality * 0.4)

    def _score_recency(self, citations: list[Citation]) -> float:
        """Score based on recency of results."""
        if not citations:
            return 0.0

        current_year = datetime.now().year
        recent_count = 0
        very_recent_count = 0

        for citation in citations:
            if citation.year:
                age = current_year - citation.year
                if age <= 2:  # Within last 2 years
                    very_recent_count += 1
                    recent_count += 1
                elif age <= 5:  # Within last 5 years
                    recent_count += 1

        recent_ratio = recent_count / len(citations)
        very_recent_ratio = very_recent_count / len(citations)

        return recent_ratio * 0.6 + very_recent_ratio * 0.4

    def _score_authority(self, citations: list[Citation]) -> float:
        """Score based on authority of sources."""
        if not citations:
            return 0.0

        authority_score = 0

        for citation in citations:
            # High-impact journals
            if citation.journal and any(
                journal in citation.journal.lower()
                for journal in self.high_impact_journals
            ):
                authority_score += 0.3

            # Systematic reviews
            if any(
                keyword in citation.title.lower()
                for keyword in self.systematic_review_keywords
            ):
                authority_score += 0.4

            # Clinical trials (inherently authoritative)
            if citation.source == "clinicaltrials":
                authority_score += 0.2

            # Base authority for peer-reviewed sources
            if citation.source == "pubmed":
                authority_score += 0.1

        return min(1.0, authority_score / len(citations))

    def _score_diversity(
        self, result_data: dict[str, dict[str, Any]], citations: list[Citation]
    ) -> float:
        """Score based on diversity of sources and perspectives."""
        source_diversity = len(result_data) / 3.0  # Max 3 main sources

        # Check for diverse publication types
        pub_types = set()
        for citation in citations:
            if citation.source == "pubmed":
                # Could extract publication types from metadata
                pub_types.add("research_article")
            elif citation.source == "clinicaltrials":
                pub_types.add("clinical_trial")
            elif citation.source == "rag":
                pub_types.add("document")

        type_diversity = len(pub_types) / 3.0

        return (source_diversity + type_diversity) / 2.0

    def _score_relevance(self, citations: list[Citation]) -> float:
        """Score based on relevance scores of citations."""
        if not citations:
            return 0.0

        avg_relevance = sum(c.relevance_score for c in citations) / len(citations)
        return avg_relevance

    def _count_primary_sources(self, citations: list[Citation]) -> int:
        """Count high-quality primary sources."""
        count = 0
        for citation in citations:
            if citation.journal and any(
                j in citation.journal.lower() for j in self.high_impact_journals
            ):
                count += 1
            elif citation.source == "clinicaltrials":
                count += 1
        return count

    def _count_recent_results(self, citations: list[Citation]) -> int:
        """Count results from last 2 years."""
        current_year = datetime.now().year
        return sum(1 for c in citations if c.year and (current_year - c.year) <= 2)

    def _count_high_impact(self, citations: list[Citation]) -> int:
        """Count high-impact publications."""
        return sum(
            1
            for c in citations
            if c.journal
            and any(j in c.journal.lower() for j in self.high_impact_journals)
        )

    def _has_systematic_reviews(self, citations: list[Citation]) -> bool:
        """Check if results include systematic reviews."""
        return any(
            any(
                keyword in c.title.lower()
                for keyword in self.systematic_review_keywords
            )
            for c in citations
        )

    def _has_recent_trials(self, result_data: dict[str, dict[str, Any]]) -> bool:
        """Check if results include recent clinical trials."""
        ctgov_data = result_data.get("clinicaltrials")
        if not ctgov_data:
            return False

        trials = ctgov_data.get("results", [])
        current_year = datetime.now().year

        for trial in trials:
            if trial.get("start_date"):
                try:
                    start_year = datetime.fromisoformat(trial["start_date"]).year
                    if (current_year - start_year) <= 3:
                        return True
                except (ValueError, TypeError):
                    pass

        return False

    def _has_multiple_perspectives(
        self, result_data: dict[str, dict[str, Any]]
    ) -> bool:
        """Check if results represent multiple perspectives."""
        # Simple check: do we have results from at least 2 different sources?
        sources_with_results = sum(
            1
            for data in result_data.values()
            if data.get("results") and len(data["results"]) > 0
        )
        return sources_with_results >= 2

    def _detect_conflicts(
        self, result_data: dict[str, dict[str, Any]], citations: list[Citation]
    ) -> list[str]:
        """Detect potential conflicts or limitations."""
        conflicts = []

        # Check for very old results
        if citations:
            valid_years = [c.year for c in citations if c.year is not None]
            if valid_years:
                avg_age = sum(datetime.now().year - year for year in valid_years) / len(
                    valid_years
                )

                if avg_age > 10:
                    conflicts.append("Results may be outdated (average age > 10 years)")

        # Check for limited source diversity
        if len(result_data) < 2:
            conflicts.append("Limited source diversity")

        # Check for small result sets
        total_results = sum(
            len(data.get("results", [])) for data in result_data.values()
        )
        if total_results < 5:
            conflicts.append("Limited number of results found")

        return conflicts
