"""
Quality scoring for biomedical documents.
Implements domain logic for calculating document quality boosts based on journal impact and recency.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class QualityConfig:
    """Configuration for quality scoring parameters."""

    # Journal impact boost
    JOURNAL_BOOST_FACTOR: float = 0.10  # 10% boost for high-impact journals

    # Recency boost
    RECENCY_BOOST_FACTOR: float = 0.05  # 5% boost for recent publications
    RECENT_YEARS_THRESHOLD: int = 2  # Papers from last 2 years get boost

    # Legacy quality score integration
    LEGACY_QUALITY_DIVISOR: int = 20  # Normalize legacy quality_total scores

    # High-impact journal lists (could be made configurable in future)
    TIER_1_JOURNALS: frozenset[str] = frozenset(
        [
            "nature",
            "science",
            "cell",
            "lancet",
            "nejm",
            "new england journal of medicine",
        ]
    )

    # Investment relevance keywords for biotech research
    INVESTMENT_KEYWORDS: frozenset[str] = frozenset(
        [
            "clinical trial",
            "phase i",
            "phase ii",
            "phase iii",
            "fda approval",
            "market",
            "commercial",
            "therapeutic",
            "drug development",
            "pipeline",
            "biotech",
            "pharma",
            "revenue",
            "patent",
            "intellectual property",
            "regulatory",
            "approval",
            "indication",
            "companion diagnostic",
            "personalized medicine",
            "precision medicine",
            "biomarker",
        ]
    )

    # Investment relevance boost
    INVESTMENT_BOOST_FACTOR: float = 0.08  # 8% boost for investment-relevant content


class JournalQualityScorer:
    """Domain service for calculating document quality scores."""

    def __init__(self, config: QualityConfig | None = None):
        self.config = config or QualityConfig()

    def calculate_quality_boost(self, document: dict[str, Any]) -> float:
        """
        Calculate the total quality boost for a document.

        Args:
            document: Document metadata containing journal, publication_date, etc.

        Returns:
            Total quality boost factor (e.g., 0.15 = 15% boost)
        """
        quality_factors = []

        # Journal impact boost
        journal_boost = self._calculate_journal_boost(document.get("journal", ""))
        if journal_boost > 0:
            quality_factors.append(journal_boost)

        # Publication recency boost
        recency_boost = self._calculate_recency_boost(document.get("publication_date"))
        if recency_boost > 0:
            quality_factors.append(recency_boost)

        # Legacy quality score integration
        legacy_boost = self._calculate_legacy_boost(document.get("quality_total", 0))
        if legacy_boost > 0:
            quality_factors.append(legacy_boost)

        # Investment relevance boost for biotech research
        investment_boost = self._calculate_investment_boost(document)
        if investment_boost > 0:
            quality_factors.append(investment_boost)

        return sum(quality_factors)

    def _calculate_journal_boost(self, journal: str) -> float:
        """Calculate boost based on journal impact factor."""
        if not journal:
            return 0.0

        journal_lower = journal.lower()

        # Check if any high-impact journal name appears in the journal string
        if any(
            tier1_journal in journal_lower
            for tier1_journal in self.config.TIER_1_JOURNALS
        ):
            return self.config.JOURNAL_BOOST_FACTOR

        return 0.0

    def _calculate_recency_boost(self, publication_date: Any) -> float:
        """Calculate boost based on publication recency."""
        if not publication_date:
            return 0.0

        current_year = datetime.now(UTC).year
        recent_threshold = current_year - self.config.RECENT_YEARS_THRESHOLD + 1

        # Handle both string and datetime objects
        if hasattr(publication_date, "year"):
            # datetime object
            if publication_date.year >= recent_threshold:
                return self.config.RECENCY_BOOST_FACTOR
        elif isinstance(publication_date, str):
            # string format - extract year if possible
            try:
                year_str = publication_date[:4]
                if year_str.isdigit() and int(year_str) >= recent_threshold:
                    return self.config.RECENCY_BOOST_FACTOR
            except (ValueError, IndexError):
                pass  # Skip if can't parse year

        return 0.0

    def _calculate_legacy_boost(self, quality_total: int | None) -> float:
        """Calculate boost from legacy quality_total scores."""
        if not quality_total or quality_total <= 0:
            return 0.0

        return quality_total / self.config.LEGACY_QUALITY_DIVISOR

    def _calculate_investment_boost(self, document: dict[str, Any]) -> float:
        """Calculate boost based on investment relevance for biotech research."""
        # Combine searchable text fields
        searchable_text = " ".join(
            [
                document.get("title", ""),
                document.get("abstract", ""),
                " ".join(document.get("keywords", [])),
                " ".join(document.get("mesh_terms", [])),
            ]
        ).lower()

        if not searchable_text:
            return 0.0

        # Count investment-relevant keywords
        keyword_matches = sum(
            1
            for keyword in self.config.INVESTMENT_KEYWORDS
            if keyword in searchable_text
        )

        # Apply boost if investment-relevant content found
        if keyword_matches > 0:
            # Scale boost by number of matches (up to 3x boost)
            boost_multiplier = min(keyword_matches / 3.0, 1.0)
            return self.config.INVESTMENT_BOOST_FACTOR * boost_multiplier

        return 0.0

    def apply_quality_boost(
        self, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Apply quality boosting to search results and sort by boosted score.

        Args:
            results: List of search result dictionaries

        Returns:
            Results with quality boost applied, sorted by boosted_score descending
        """
        for result in results:
            original_score = result.get("score", 0.0)
            quality_boost = self.calculate_quality_boost(result)

            if original_score and original_score > 0:
                boosted_score = original_score * (1 + quality_boost)
                result["boosted_score"] = boosted_score
                result["quality_boost"] = quality_boost
            else:
                result["boosted_score"] = original_score
                result["quality_boost"] = 0

        # Sort by boosted score (highest first), handling None values
        def sort_key(x):
            score = x.get("boosted_score")
            if score is None:
                score = x.get("score", 0)
            return score if score is not None else 0

        results.sort(key=sort_key, reverse=True)
        return results
