"""
PubMed-specific document models.
"""

from dataclasses import dataclass, field

from bio_mcp.shared.models.base_models import BaseDocument


@dataclass
class PubMedDocument(BaseDocument):
    """PubMed-specific document model."""
    # PubMed-specific fields (all with defaults to avoid dataclass issues)
    pmid: str = ""
    journal: str | None = None
    doi: str | None = None
    mesh_terms: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    impact_factor: float | None = None
    citation_count: int = 0
    
    def __post_init__(self):
        if self.pmid:  # Only set if pmid was provided
            self.source = "pubmed"
            self.source_id = self.pmid
            self.id = f"pubmed:{self.pmid}"
    
    def get_search_content(self) -> str:
        """Return text content optimized for search and embedding."""
        parts = [self.title]
        if self.abstract:
            parts.append(self.abstract)
        if self.mesh_terms:
            parts.append(" ".join(self.mesh_terms))
        if self.keywords:
            parts.append(" ".join(self.keywords))
        return " ".join(parts)
    
    def get_display_title(self) -> str:
        """Return formatted title for display with journal info."""
        journal_info = f" ({self.journal})" if self.journal else ""
        return f"{self.title}{journal_info}"