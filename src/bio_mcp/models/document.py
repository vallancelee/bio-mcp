"""
Core document models for multi-source biomedical data.

This module provides the shared Document and Chunk models that enable processing
of documents from multiple sources (PubMed, ClinicalTrials.gov, etc.) through
a common pipeline while preserving source-specific richness.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Document(BaseModel):
    """
    Minimal, shared document model for multi-source biomedical data.
    
    This model provides a stable base for cross-source operations like chunking,
    embedding, and indexing, while preserving source-specific details in the
    `detail` field.
    
    Examples:
        >>> doc = Document(
        ...     uid="pubmed:12345678",
        ...     source="pubmed", 
        ...     source_id="12345678",
        ...     title="Cancer Research Study",
        ...     text="This study investigates...",
        ...     detail={"journal": "Nature", "mesh_terms": ["cancer", "treatment"]}
        ... )
    """
    
    # Core identity
    uid: str = Field(..., description="Universal document ID, e.g. 'pubmed:12345678'")
    source: str = Field(..., description="Source identifier: 'pubmed', 'clinicaltrials', etc.")
    source_id: str = Field(..., description="Source-specific ID (PMID, NCT number, etc.)")
    
    # Minimal content (required for chunking/embedding)
    title: str | None = Field(None, description="Document title")
    text: str = Field(..., description="Main text content to chunk and embed")
    
    # Temporal metadata
    published_at: datetime | None = Field(None, description="Original publication date")
    fetched_at: datetime | None = Field(None, description="When we retrieved this document")
    
    # Common cross-source metadata
    authors: list[str] | None = Field(None, description="List of author names")
    labels: list[str] | None = Field(None, description="User-assigned or computed labels")
    identifiers: dict[str, str] = Field(
        default_factory=dict, 
        description="Cross-references like DOI, PMCID, etc."
    )
    language: str | None = Field(None, description="Document language code")
    
    # Provenance and extensions
    provenance: dict[str, Any] = Field(
        default_factory=dict,
        description="Audit info: s3_raw_uri, content_hash, etc."
    )
    detail: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific fields (journal, MeSH terms, etc.)"
    )
    
    # Schema versioning for future migrations
    schema_version: int = Field(default=1, description="Schema version for migrations")
    
    @field_validator('uid')
    @classmethod
    def validate_uid_format(cls, v: str) -> str:
        """Ensure UID follows 'source:source_id' format."""
        if ':' not in v:
            raise ValueError("UID must follow format 'source:source_id'")
        return v
    
    @field_validator('source')
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Ensure source is lowercase and alphanumeric."""
        if not v.isalnum():
            raise ValueError("Source must be alphanumeric")
        return v.lower()
    
    def model_post_init(self, __context: Any) -> None:
        """Validate UID consistency with source and source_id."""
        expected_uid = f"{self.source}:{self.source_id}"
        if self.uid != expected_uid:
            raise ValueError(
                f"UID '{self.uid}' doesn't match source:source_id '{expected_uid}'"
            )
    
    def get_searchable_text(self) -> str:
        """
        Get the full searchable text content for this document.
        
        Returns:
            Combined text from title and main content, suitable for search.
        """
        parts = []
        if self.title:
            parts.append(self.title)
        if self.text:
            parts.append(self.text)
        return " ".join(parts).strip()
    
    def get_content_hash(self) -> str:
        """
        Generate a stable hash of the document content.
        
        Returns:
            SHA-256 hash of the searchable text content.
        """
        import hashlib
        content = self.get_searchable_text()
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


class Chunk(BaseModel):
    """
    Document chunk model for embedding and vector search.
    
    Represents a portion of a document that has been chunked for embedding,
    maintaining links back to the parent document and carrying forward
    relevant metadata.
    
    Examples:
        >>> chunk = Chunk(
        ...     chunk_id="pubmed:12345678:0",
        ...     parent_uid="pubmed:12345678",
        ...     source="pubmed",
        ...     chunk_idx=0,
        ...     text="This is the first chunk of text...",
        ...     title="Cancer Research Study"
        ... )
    """
    
    # Core identity and relationships
    chunk_id: str = Field(..., description="Unique chunk ID: parent_uid:chunk_idx")
    parent_uid: str = Field(..., description="UID of parent Document")
    source: str = Field(..., description="Source identifier (inherited from parent)")
    chunk_idx: int = Field(..., description="0-based index within parent document")
    
    # Content
    text: str = Field(..., description="Chunk text content")
    
    # Inherited metadata from parent document
    title: str | None = Field(None, description="Parent document title")
    published_at: datetime | None = Field(None, description="Parent publication date")
    
    # Chunking metadata
    tokens: int | None = Field(None, description="Token count (if computed)")
    section: str | None = Field(None, description="Document section (abstract, intro, etc.)")
    
    # Additional metadata
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional chunk-specific metadata"
    )
    
    @field_validator('chunk_id')
    @classmethod
    def validate_chunk_id_format(cls, v: str) -> str:
        """Ensure chunk_id follows 'parent_uid:chunk_idx' format."""
        parts = v.split(':')
        if len(parts) < 3:  # source:source_id:chunk_idx
            raise ValueError("chunk_id must follow format 'parent_uid:chunk_idx'")
        return v
    
    def model_post_init(self, __context: Any) -> None:
        """Validate chunk_id consistency with parent_uid and chunk_idx."""
        expected_chunk_id = f"{self.parent_uid}:{self.chunk_idx}"
        if self.chunk_id != expected_chunk_id:
            raise ValueError(
                f"chunk_id '{self.chunk_id}' doesn't match expected '{expected_chunk_id}'"
            )
    
    def get_embedding_text(self) -> str:
        """
        Get the text to be embedded for this chunk.
        
        Returns:
            The chunk text, optionally prefixed with title context.
        """
        if self.title and self.title.lower() not in self.text.lower():
            return f"{self.title}: {self.text}"
        return self.text
    
    def get_display_context(self) -> str:
        """
        Get a human-readable context string for this chunk.
        
        Returns:
            A string describing the chunk's position and context.
        """
        context_parts = []
        
        if self.title:
            context_parts.append(f"'{self.title}'")
        
        if self.section:
            context_parts.append(f"section: {self.section}")
        
        context_parts.append(f"chunk {self.chunk_idx + 1}")
        
        if self.published_at:
            pub_year = self.published_at.year
            context_parts.append(f"published {pub_year}")
        
        return f"From {', '.join(context_parts)}"


# Type aliases for convenience
DocumentDict = dict[str, Any]
ChunkDict = dict[str, Any]