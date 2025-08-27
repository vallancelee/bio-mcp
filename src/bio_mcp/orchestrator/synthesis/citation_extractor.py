"""Citation extraction and formatting."""

from datetime import datetime
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.synthesis.synthesizer import Citation

logger = get_logger(__name__)


class CitationExtractor:
    """Extracts and formats citations from various sources."""

    def __init__(self):
        self.citation_counter = 0

    async def extract_citations(
        self, result_data: dict[str, dict[str, Any]]
    ) -> list[Citation]:
        """Extract citations from all result sources."""
        all_citations = []

        for source, data in result_data.items():
            results = data.get("results", [])
            source_citations = await self._extract_source_citations(source, results)
            all_citations.extend(source_citations)

        # Sort by relevance score
        all_citations.sort(key=lambda c: c.relevance_score, reverse=True)

        return all_citations

    async def _extract_source_citations(
        self, source: str, results: list[dict[str, Any]]
    ) -> list[Citation]:
        """Extract citations from specific source."""
        citations = []

        if source == "pubmed":
            citations = self._extract_pubmed_citations(results)
        elif source == "clinicaltrials":
            citations = self._extract_clinical_trial_citations(results)
        elif source == "rag":
            citations = self._extract_rag_citations(results)

        return citations

    def _extract_pubmed_citations(
        self, results: list[dict[str, Any]]
    ) -> list[Citation]:
        """Extract citations from PubMed results."""
        citations = []

        for result in results:
            self.citation_counter += 1

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

            # Calculate relevance score (placeholder - could be enhanced)
            relevance_score = self._calculate_pubmed_relevance(result)

            citation = Citation(
                id=str(self.citation_counter),
                source="pubmed",
                title=result.get("title", "Untitled"),
                authors=authors[:3],  # Limit to first 3 authors
                journal=result.get("journal"),
                year=year,
                pmid=result.get("pmid"),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{result.get('pmid')}"
                if result.get("pmid")
                else None,
                relevance_score=relevance_score,
            )

            citations.append(citation)

        return citations

    def _extract_clinical_trial_citations(
        self, results: list[dict[str, Any]]
    ) -> list[Citation]:
        """Extract citations from ClinicalTrials results."""
        citations = []

        for result in results:
            self.citation_counter += 1

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

            relevance_score = self._calculate_trial_relevance(result)

            citation = Citation(
                id=str(self.citation_counter),
                source="clinicaltrials",
                title=result.get("title", "Untitled Trial"),
                authors=sponsors,
                year=year,
                nct_id=result.get("nct_id"),
                url=f"https://clinicaltrials.gov/ct2/show/{result.get('nct_id')}"
                if result.get("nct_id")
                else None,
                relevance_score=relevance_score,
            )

            citations.append(citation)

        return citations

    def _extract_rag_citations(self, results: list[dict[str, Any]]) -> list[Citation]:
        """Extract citations from RAG results."""
        citations = []

        for result in results:
            self.citation_counter += 1

            relevance_score = result.get("score", 0.0)

            citation = Citation(
                id=str(self.citation_counter),
                source="rag",
                title=result.get("title", "Document"),
                authors=[],  # RAG typically doesn't have author info
                relevance_score=relevance_score,
                url=result.get("url"),
            )

            citations.append(citation)

        return citations

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
