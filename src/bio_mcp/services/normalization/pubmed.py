"""
PubMed document normalizer.

This module converts raw PubMed data (from API or database) into the standardized
Document model for use in the multi-source pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.models.document import Document

logger = get_logger(__name__)


class PubMedNormalizer:
    """
    Normalizes PubMed documents to the common Document model.
    
    This class handles the conversion from various PubMed data formats
    (API responses, database records, dataclass instances) into the
    standardized Document model that can be processed by the common pipeline.
    """
    
    @staticmethod
    def from_raw_dict(
        raw: dict[str, Any], 
        *,
        s3_raw_uri: str,
        content_hash: str
    ) -> Document:
        """
        Convert raw PubMed API data to normalized Document.
        
        Args:
            raw: Raw PubMed data from API or database
            s3_raw_uri: S3 URI where raw data is archived
            content_hash: Hash of the raw content for deduplication
            
        Returns:
            Normalized Document instance
            
        Raises:
            ValueError: If required fields (pmid) are missing
        """
        # Extract PMID (required)
        pmid = str(raw.get("pmid") or raw.get("PMID") or "").strip()
        if not pmid:
            raise ValueError("PMID is required but missing from raw data")
        
        # Extract core fields
        title = (raw.get("title") or raw.get("Title") or "").strip() or None
        abstract = (raw.get("abstract") or raw.get("Abstract") or "").strip() or ""
        
        # Use abstract as main text; fallback to title if no abstract
        if not abstract and title:
            text = title
        else:
            text = abstract
        
        if not text:
            logger.warning("Document has no abstract or title", pmid=pmid)
            text = ""  # Still create document but with empty text
        
        # Extract temporal metadata  
        published_at = PubMedNormalizer._parse_publication_date(raw)
        fetched_at = datetime.now(UTC)
        
        # Extract authors
        authors = PubMedNormalizer._extract_authors(raw)
        
        # Extract identifiers
        identifiers = {}
        doi = (raw.get("doi") or raw.get("DOI") or "").strip()
        if doi:
            identifiers["doi"] = doi
        
        # Handle PMC ID if present
        pmc_id = (raw.get("pmc_id") or raw.get("PMC") or "").strip()
        if pmc_id:
            if not pmc_id.startswith("PMC"):
                pmc_id = f"PMC{pmc_id}"
            identifiers["pmc"] = pmc_id
        
        # Extract language
        language = (raw.get("language") or raw.get("Language") or "").strip()
        if language and language.lower() in ("eng", "english"):
            language = "en"
        elif not language:
            language = None
        
        # Build PubMed-specific detail fields
        detail = PubMedNormalizer._build_detail_fields(raw)
        
        # Create the normalized document
        doc = Document(
            uid=f"pubmed:{pmid}",
            source="pubmed",
            source_id=pmid,
            title=title,
            text=text,
            published_at=published_at,
            fetched_at=fetched_at,
            authors=authors,
            identifiers=identifiers,
            language=language,
            provenance={
                "s3_raw_uri": s3_raw_uri,
                "content_hash": content_hash,
                "normalized_at": fetched_at.isoformat(),
                "normalizer_version": "1.0"
            },
            detail=detail
        )
        
        logger.debug(
            "Normalized PubMed document",
            pmid=pmid,
            has_title=bool(title),
            has_abstract=bool(abstract),
            text_length=len(text),
            author_count=len(authors) if authors else 0
        )
        
        return doc
    
    @staticmethod
    def from_dataclass(
        pubmed_doc: Any,  # PubMedDocument from client.py or models.py
        *,
        s3_raw_uri: str,
        content_hash: str
    ) -> Document:
        """
        Convert PubMedDocument dataclass to normalized Document.
        
        Args:
            pubmed_doc: PubMedDocument instance from existing code
            s3_raw_uri: S3 URI where raw data is archived  
            content_hash: Hash of the raw content
            
        Returns:
            Normalized Document instance
        """
        # Convert dataclass to dict for consistent processing
        if hasattr(pubmed_doc, '__dict__'):
            raw_dict = {
                "pmid": pubmed_doc.pmid,
                "title": pubmed_doc.title,
                "abstract": getattr(pubmed_doc, 'abstract', None),
                "authors": getattr(pubmed_doc, 'authors', None),
                "journal": getattr(pubmed_doc, 'journal', None),
                "publication_date": getattr(pubmed_doc, 'publication_date', None),
                "doi": getattr(pubmed_doc, 'doi', None),
                "keywords": getattr(pubmed_doc, 'keywords', None),
                "mesh_terms": getattr(pubmed_doc, 'mesh_terms', None)
            }
        elif hasattr(pubmed_doc, 'to_dict'):
            raw_dict = pubmed_doc.to_dict()
        else:
            raise ValueError(f"Unsupported PubMed document type: {type(pubmed_doc)}")
        
        return PubMedNormalizer.from_raw_dict(
            raw_dict,
            s3_raw_uri=s3_raw_uri,
            content_hash=content_hash
        )
    
    @staticmethod
    def _parse_publication_date(raw: dict[str, Any]) -> datetime | None:
        """Parse publication date from various PubMed formats."""
        # Try different date fields
        pub_date = (
            raw.get("publication_date") or 
            raw.get("PublicationDate") or 
            raw.get("pub_date") or
            raw.get("PubDate")
        )
        
        if not pub_date:
            return None
        
        # Handle datetime objects (already parsed)
        if isinstance(pub_date, datetime):
            # Ensure timezone is set to UTC
            if pub_date.tzinfo is None:
                return pub_date.replace(tzinfo=UTC)
            return pub_date
        
        # Handle date objects
        if hasattr(pub_date, 'year'):
            return datetime(pub_date.year, pub_date.month, pub_date.day, tzinfo=UTC)
        
        # Handle string dates
        if isinstance(pub_date, str):
            pub_date = pub_date.strip()
            if not pub_date:
                return None
            
            # Try various date formats
            date_formats = [
                "%Y-%m-%d",
                "%Y-%m",
                "%Y",
                "%Y/%m/%d",
                "%m/%d/%Y",
                "%d/%m/%Y"
            ]
            
            for fmt in date_formats:
                try:
                    parsed = datetime.strptime(pub_date, fmt)
                    return parsed.replace(tzinfo=UTC)
                except ValueError:
                    continue
            
            # Try to extract just the year if other formats fail
            try:
                year = int(pub_date[:4])
                if 1900 <= year <= 2100:  # Reasonable year range
                    return datetime(year, 1, 1, tzinfo=UTC)
            except (ValueError, TypeError):
                pass
        
        logger.warning("Could not parse publication date", date_value=pub_date)
        return None
    
    @staticmethod
    def _extract_authors(raw: dict[str, Any]) -> list[str] | None:
        """Extract and normalize author list."""
        authors_raw = (
            raw.get("authors") or 
            raw.get("Authors") or 
            raw.get("author_list") or
            raw.get("AuthorList")
        )
        
        if not authors_raw:
            return None
        
        # Handle different author formats
        if isinstance(authors_raw, str):
            # Parse author string - authors are typically separated by commas,
            # but names themselves contain commas (LastName, FirstName)
            authors_raw = authors_raw.strip()
            
            # Use regex to split on commas that separate authors, not those within names
            # Pattern: Look for comma followed by space and a capitalized word that 
            # looks like a last name (not a first name/initial)
            
            # Split on commas, then reconstruct author names
            # Heuristic: if after a comma we see "Lastname, Firstname" pattern,
            # we know that comma separates authors
            parts = [part.strip() for part in authors_raw.split(',')]
            
            if len(parts) <= 1:
                # No commas or just one part
                return [authors_raw] if authors_raw else None
            
            # Reconstruct authors by looking for lastname/firstname patterns
            authors = []
            i = 0
            while i < len(parts):
                current_name = parts[i]
                
                # Check if next part looks like a first name/initials (not a new last name)
                if (i + 1 < len(parts) and 
                    len(parts[i + 1].split()) <= 2 and  # First name + optional middle initial
                    not (i + 2 < len(parts) and parts[i + 2] and parts[i + 2][0].islower())):  # Next isn't lowercase continuation
                    # Combine lastname with firstname
                    current_name = f"{current_name}, {parts[i + 1]}"
                    i += 2
                else:
                    i += 1
                
                if current_name.strip():
                    authors.append(current_name.strip())
            
            return authors if authors else None
        
        elif isinstance(authors_raw, list):
            authors = []
            for author in authors_raw:
                if isinstance(author, str):
                    name = author.strip()
                    if name:
                        authors.append(name)
                elif isinstance(author, dict):
                    # Handle structured author data
                    last_name = author.get("LastName", "").strip()
                    fore_name = author.get("ForeName", "").strip()
                    initials = author.get("Initials", "").strip()
                    
                    if last_name:
                        name_parts = [last_name]
                        if fore_name:
                            name_parts.append(fore_name)
                        elif initials:
                            name_parts.append(initials)
                        authors.append(" ".join(name_parts))
            
            return authors if authors else None
        
        return None
    
    @staticmethod
    def _build_detail_fields(raw: dict[str, Any]) -> dict[str, Any]:
        """Build PubMed-specific detail fields."""
        detail = {}
        
        # Journal information
        journal = (raw.get("journal") or raw.get("Journal") or "").strip()
        if journal:
            detail["journal"] = journal
        
        # MeSH terms
        mesh_terms = raw.get("mesh_terms") or raw.get("MeshTerms") or raw.get("MeSH")
        if mesh_terms:
            if isinstance(mesh_terms, list):
                detail["mesh_terms"] = [term.strip() for term in mesh_terms if term.strip()]
            elif isinstance(mesh_terms, str):
                detail["mesh_terms"] = [term.strip() for term in mesh_terms.split(",") if term.strip()]
        
        # Keywords
        keywords = raw.get("keywords") or raw.get("Keywords")
        if keywords:
            if isinstance(keywords, list):
                detail["keywords"] = [kw.strip() for kw in keywords if kw.strip()]
            elif isinstance(keywords, str):
                detail["keywords"] = [kw.strip() for kw in keywords.split(",") if kw.strip()]
        
        # Author affiliations
        affiliations = raw.get("affiliations") or raw.get("Affiliations")
        if affiliations:
            detail["affiliations"] = affiliations
        
        # Publication type
        pub_types = raw.get("publication_types") or raw.get("PublicationTypes")
        if pub_types:
            detail["publication_types"] = pub_types
        
        # Impact factor (if available)
        impact_factor = raw.get("impact_factor")
        if impact_factor is not None:
            try:
                detail["impact_factor"] = float(impact_factor)
            except (ValueError, TypeError):
                pass
        
        # Citation count (if available)
        citation_count = raw.get("citation_count")
        if citation_count is not None:
            try:
                detail["citation_count"] = int(citation_count)
            except (ValueError, TypeError):
                pass
        
        # Abstract sections (structured abstracts)
        abstract_sections = raw.get("abstract_sections")
        if abstract_sections and isinstance(abstract_sections, dict):
            detail["abstract_sections"] = abstract_sections
        
        # Remove empty values
        return {k: v for k, v in detail.items() if v is not None}


# Helper function for backward compatibility
def to_document(
    raw: dict[str, Any], 
    *,
    s3_raw_uri: str, 
    content_hash: str
) -> Document:
    """
    Convert raw PubMed data to normalized Document.
    
    This is a convenience function that delegates to PubMedNormalizer.from_raw_dict().
    
    Args:
        raw: Raw PubMed data dictionary
        s3_raw_uri: S3 URI where raw data is archived
        content_hash: Hash of the raw content
        
    Returns:
        Normalized Document instance
    """
    return PubMedNormalizer.from_raw_dict(
        raw,
        s3_raw_uri=s3_raw_uri,
        content_hash=content_hash
    )