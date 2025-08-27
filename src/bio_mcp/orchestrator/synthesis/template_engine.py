"""Template engine for generating formatted answers."""

from datetime import datetime
from typing import Any

from bio_mcp.config.logging_config import get_logger

logger = get_logger(__name__)


class TemplateEngine:
    """Generates formatted answers using templates."""

    def __init__(self):
        self.templates = {
            "answer_comprehensive": self._comprehensive_template,
            "answer_partial": self._partial_template,
            "answer_minimal": self._minimal_template,
            "answer_empty": self._empty_template,
        }

    async def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render template with context."""
        template_func = self.templates.get(template_name, self._comprehensive_template)
        return template_func(context)

    def _comprehensive_template(self, context: dict[str, Any]) -> str:
        """Template for comprehensive answers."""
        parts = []

        # Header with query analysis
        parts.append(self._render_header(context))

        # Quality summary
        parts.append(self._render_quality_summary(context))

        # Results by source
        parts.append(self._render_results_by_source(context))

        # Key findings
        parts.append(self._render_key_findings(context))

        # Citations
        parts.append(self._render_citations(context))

        # Footer with metadata
        parts.append(self._render_footer(context))

        return "\n".join(parts)

    def _partial_template(self, context: dict[str, Any]) -> str:
        """Template for partial answers."""
        parts = []

        parts.append("# Research Results (Partial)")
        parts.append(f"**Query:** {context['query']}")
        parts.append(
            "\n⚠️ *Note: This is a partial response due to some data sources being unavailable.*\n"
        )

        parts.append(self._render_results_by_source(context))
        parts.append(self._render_citations(context))
        parts.append(self._render_footer(context))

        return "\n".join(parts)

    def _minimal_template(self, context: dict[str, Any]) -> str:
        """Template for minimal answers."""
        parts = []

        parts.append("# Research Results (Limited)")
        parts.append(f"**Query:** {context['query']}")
        parts.append(
            "\n⚠️ *Note: Limited results found. Consider refining your search terms.*\n"
        )

        parts.append(self._render_results_by_source(context))

        return "\n".join(parts)

    def _empty_template(self, context: dict[str, Any]) -> str:
        """Template for empty results."""
        return f"""# No Results Found

**Query:** {context["query"]}

❌ No relevant results were found for your query.

## Suggestions:
- Try broader search terms
- Check spelling and terminology
- Consider alternative keywords or synonyms
- Reduce the number of filters if any were applied

*Searched sources: PubMed, ClinicalTrials.gov, and internal documents*
"""

    def _render_header(self, context: dict[str, Any]) -> str:
        """Render answer header."""
        frame = context.get("frame", {})
        intent = frame.get("intent", "unknown").replace("_", " ").title()

        header = f"""# Biomedical Research Results

**Query:** {context["query"]}
**Analysis Intent:** {intent}
**Generated:** {datetime.fromisoformat(context["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")} UTC
"""

        # Add entity information if available
        entities = frame.get("entities", {})
        if entities:
            entity_lines = []
            for key, value in entities.items():
                if value:
                    entity_lines.append(f"- **{key.title()}:** {value}")

            if entity_lines:
                header += (
                    "\n**Entities Identified:**\n" + "\n".join(entity_lines) + "\n"
                )

        return header

    def _render_quality_summary(self, context: dict[str, Any]) -> str:
        """Render quality metrics summary."""
        quality = context.get("quality", {})
        if not quality:
            return ""

        overall_score = quality.get("overall_score", 0)
        score_emoji = (
            "🟢" if overall_score >= 0.8 else "🟡" if overall_score >= 0.6 else "🔴"
        )

        summary = f"""## Quality Assessment {score_emoji}

**Overall Quality Score:** {overall_score:.2f}/1.00

- **Completeness:** {quality.get("completeness_score", 0):.2f} (Source coverage)
- **Recency:** {quality.get("recency_score", 0):.2f} (Recent publications)
- **Authority:** {quality.get("authority_score", 0):.2f} (High-impact sources)
- **Diversity:** {quality.get("diversity_score", 0):.2f} (Multiple perspectives)
"""

        # Add quality flags
        flags = []
        if quality.get("has_systematic_reviews"):
            flags.append("✅ Includes systematic reviews")
        if quality.get("has_recent_trials"):
            flags.append("✅ Includes recent clinical trials")
        if quality.get("has_multiple_perspectives"):
            flags.append("✅ Multiple perspectives represented")

        if flags:
            summary += "\n**Quality Indicators:**\n" + "\n".join(flags) + "\n"

        # Add warnings if any
        conflicts = quality.get("potential_conflicts", [])
        if conflicts:
            summary += (
                "\n**Limitations:**\n" + "\n".join(f"⚠️ {c}" for c in conflicts) + "\n"
            )

        return summary

    def _render_results_by_source(self, context: dict[str, Any]) -> str:
        """Render results organized by source."""
        results = context.get("results", {})
        if not results:
            return "## Results\n\nNo results found.\n"

        parts = ["## Results Summary\n"]

        source_names = {
            "pubmed": "📚 PubMed Publications",
            "clinicaltrials": "🧪 Clinical Trials",
            "rag": "📄 Related Documents",
        }

        for source, data in results.items():
            source_results = data.get("results", [])
            if not source_results:
                continue

            source_name = source_names.get(source, source.title())
            parts.append(f"### {source_name} ({len(source_results)} found)\n")

            # Show top 5 results
            for i, result in enumerate(source_results[:5], 1):
                if source == "pubmed":
                    parts.append(self._format_pubmed_result(i, result))
                elif source == "clinicaltrials":
                    parts.append(self._format_trial_result(i, result))
                elif source == "rag":
                    parts.append(self._format_rag_result(i, result))

            if len(source_results) > 5:
                parts.append(
                    f"*... and {len(source_results) - 5} additional results*\n"
                )

            parts.append("")  # Empty line between sources

        return "\n".join(parts)

    def _format_pubmed_result(self, index: int, result: dict[str, Any]) -> str:
        """Format PubMed result."""
        title = result.get("title", "Untitled")
        authors = result.get("authors", [])
        journal = result.get("journal", "Unknown Journal")
        year = result.get("year", "Unknown Year")
        pmid = result.get("pmid")

        # Format authors
        if isinstance(authors, list):
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += " et al."
        else:
            author_str = str(authors) if authors else "Unknown Authors"

        formatted = f"{index}. **{title}**\n"
        formatted += f"   - Authors: {author_str}\n"
        formatted += f"   - Journal: {journal} ({year})\n"
        if pmid:
            formatted += (
                f"   - PMID: [{pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid})\n"
            )

        return formatted

    def _format_trial_result(self, index: int, result: dict[str, Any]) -> str:
        """Format clinical trial result."""
        title = result.get("title", "Untitled Trial")
        nct_id = result.get("nct_id")
        phase = result.get("phase", "Unknown Phase")
        status = result.get("status", "Unknown Status")
        sponsor = result.get("sponsor", "Unknown Sponsor")

        formatted = f"{index}. **{title}**\n"
        formatted += f"   - Phase: {phase}\n"
        formatted += f"   - Status: {status}\n"
        formatted += f"   - Sponsor: {sponsor}\n"
        if nct_id:
            formatted += f"   - ClinicalTrials.gov: [{nct_id}](https://clinicaltrials.gov/ct2/show/{nct_id})\n"

        return formatted

    def _format_rag_result(self, index: int, result: dict[str, Any]) -> str:
        """Format RAG result."""
        title = result.get("title", "Document")
        score = result.get("score", 0)
        snippet = result.get("snippet", "No description available")

        formatted = f"{index}. **{title}**\n"
        formatted += f"   - Relevance Score: {score:.3f}\n"
        formatted += f"   - {snippet[:200]}...\n"

        return formatted

    def _render_key_findings(self, context: dict[str, Any]) -> str:
        """Render key findings section."""
        # This is a simplified version - could be enhanced with NLP summarization
        results = context.get("results", {})
        if not results:
            return ""

        findings = ["## Key Findings\n"]

        total_results = sum(len(data.get("results", [])) for data in results.values())
        findings.append(f"- **{total_results} total results** found across all sources")

        # Source-specific findings
        for source, data in results.items():
            source_results = data.get("results", [])
            if source_results:
                source_name = source.replace("_", " ").title()
                findings.append(
                    f"- **{len(source_results)} {source_name} results** identified"
                )

        return "\n".join(findings) + "\n"

    def _render_citations(self, context: dict[str, Any]) -> str:
        """Render citations section."""
        citations = context.get("citations", [])
        if not citations:
            return ""

        parts = ["## References\n"]

        for i, citation in enumerate(citations[:20], 1):  # Limit to top 20
            formatted_citation = f"{i}. "

            # Authors
            if citation.get("authors"):
                authors = citation["authors"]
                if len(authors) > 3:
                    formatted_citation += f"{', '.join(authors[:3])} et al. "
                else:
                    formatted_citation += f"{', '.join(authors)}. "

            # Title
            formatted_citation += f"{citation.get('title', 'Untitled')}. "

            # Journal/Source specific formatting
            if citation.get("journal"):
                formatted_citation += f"*{citation['journal']}*. "

            # Year
            if citation.get("year"):
                formatted_citation += f"{citation['year']}. "

            # Identifiers and URLs
            if citation.get("pmid"):
                formatted_citation += f"PMID: [{citation['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{citation['pmid']})"
            elif citation.get("nct_id"):
                formatted_citation += f"ClinicalTrials.gov: [{citation['nct_id']}](https://clinicaltrials.gov/ct2/show/{citation['nct_id']})"
            elif citation.get("url"):
                formatted_citation += f"[Link]({citation['url']})"

            parts.append(formatted_citation + "\n")

        if len(citations) > 20:
            parts.append(f"*... and {len(citations) - 20} additional references*\n")

        return "\n".join(parts)

    def _render_footer(self, context: dict[str, Any]) -> str:
        """Render footer with metadata."""
        metrics = context.get("metrics", {})

        footer = f"""---

**Execution Summary:**
- Total execution time: {metrics.get("execution_time", 0):.1f}ms
- Cache hit rate: {metrics.get("cache_hit_rate", 0):.1%}
- Sources queried: {metrics.get("source_count", 0)}

*Generated by Bio-MCP Orchestrator*
"""

        return footer
