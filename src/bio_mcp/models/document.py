"""
Core document models for multi-source biomedical data.

This module provides the shared Document and Chunk models that enable processing
of documents from multiple sources (PubMed, ClinicalTrials.gov, etc.) through
a common pipeline while preserving source-specific richness.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# UUID namespace for deterministic chunk IDs (fix once, never change)
CHUNK_UUID_NAMESPACE = uuid.UUID("1b2c3d4e-0000-0000-0000-000000000000")


class Document(BaseModel):
    """Minimal shared document model for multi-source biomedical data."""

    # Core identity
    uid: str = Field(..., description="Universal document ID, e.g. 'pubmed:12345678'")
    source: str = Field(..., description="Source identifier: 'pubmed', 'ctgov', etc.")
    source_id: str = Field(
        ..., description="Source-specific ID (PMID, NCT number, etc.)"
    )

    # Content (minimal for cross-source operations)
    title: str | None = Field(None, description="Document title")
    text: str = Field(..., description="Main text content to chunk (abstract/summary)")

    # Temporal metadata
    published_at: datetime | None = Field(None, description="Original publication date")
    fetched_at: datetime | None = Field(
        None, description="When we retrieved this document"
    )
    language: str | None = Field(None, description="Document language code")

    # Common cross-source metadata
    authors: list[str] | None = Field(None, description="List of author names")
    labels: list[str] | None = Field(
        None, description="User-assigned or computed labels"
    )
    identifiers: dict[str, str] = Field(
        default_factory=dict, description="Cross-references like DOI, PMCID, etc."
    )

    # Provenance and extensions
    provenance: dict[str, Any] = Field(
        default_factory=dict, description="Audit info: s3_raw_uri, content_hash, etc."
    )
    detail: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific fields (journal, MeSH terms, etc.)",
    )
    license: str | None = Field(None, description="License information")

    # Schema versioning
    schema_version: int = Field(default=1, description="Schema version for migrations")

    @field_validator("uid")
    @classmethod
    def validate_uid_format(cls, v: str) -> str:
        """Ensure UID follows 'source:source_id' format."""
        if ":" not in v:
            raise ValueError("UID must follow format 'source:source_id'")
        parts = v.split(":", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("UID must have non-empty source and source_id")
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Ensure source is lowercase and valid identifier."""
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
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class Chunk(BaseModel):
    """Document chunk model for embedding and vector search."""

    # Core identity and relationships
    chunk_id: str = Field(
        ..., description="Stable short ID within doc, e.g. 's0', 'w1'"
    )
    uuid: str = Field(..., description="UUIDv5 computed from parent_uid + chunk_id")
    parent_uid: str = Field(..., description="UID of parent Document")
    source: str = Field(..., description="Source identifier (inherited from parent)")

    # Position and content
    chunk_idx: int = Field(..., description="0-based index within parent document")
    text: str = Field(..., description="Chunk text content")

    # Inherited metadata from parent document
    title: str | None = Field(None, description="Parent document title")
    section: str | None = Field(
        None,
        description="Document section (Background/Methods/Results/Conclusions/Other)",
    )
    published_at: datetime | None = Field(None, description="Parent publication date")

    # Chunking metadata
    tokens: int | None = Field(None, description="Token count (if computed)")
    n_sentences: int | None = Field(None, description="Number of sentences in chunk")

    # Additional metadata
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata including chunker info and source-specific data",
    )

    @field_validator("chunk_id")
    @classmethod
    def validate_chunk_id_format(cls, v: str) -> str:
        """Ensure chunk_id follows expected format (s0, w1, etc.)."""
        import re

        if not re.match(r"^[sw]\d+$", v):
            raise ValueError(
                "chunk_id must follow format 's0', 'w1', etc. (s=section, w=window)"
            )
        return v

    @field_validator("uuid")
    @classmethod
    def validate_uuid_format(cls, v: str) -> str:
        """Ensure uuid is valid UUID format."""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("uuid must be valid UUID format")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Validate relationships and generate UUID if needed."""
        # Validate that UUID matches expected UUIDv5 generation
        expected_uuid = str(
            uuid.uuid5(CHUNK_UUID_NAMESPACE, f"{self.parent_uid}:{self.chunk_id}")
        )
        if self.uuid != expected_uuid:
            raise ValueError(
                f"UUID '{self.uuid}' doesn't match expected UUIDv5 '{expected_uuid}'"
            )

    @classmethod
    def generate_uuid(cls, parent_uid: str, chunk_id: str) -> str:
        """Generate deterministic UUIDv5 for a chunk."""
        return str(uuid.uuid5(CHUNK_UUID_NAMESPACE, f"{parent_uid}:{chunk_id}"))

    def get_embedding_text(self) -> str:
        """Get the text to be embedded for this chunk."""
        # Return the text as-is since formatting is handled during chunking
        return self.text

    def get_display_context(self) -> str:
        """Get a human-readable context string for this chunk."""
        context_parts = []

        if self.title:
            context_parts.append(f"'{self.title}'")

        if self.section and self.section != "Unstructured":
            context_parts.append(f"section: {self.section}")

        context_parts.append(f"chunk {self.chunk_idx + 1}")

        if self.published_at:
            pub_year = self.published_at.year
            context_parts.append(f"published {pub_year}")

        return f"From {', '.join(context_parts)}"


# Type aliases for convenience
DocumentDict = dict[str, Any]
ChunkDict = dict[str, Any]


class MetadataBuilder:
    """Helper class for building multi-source metadata."""

    @staticmethod
    def build_chunk_metadata(
        chunker_version: str,
        tokenizer: str,
        source_specific: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        """Build standardized chunk metadata."""
        return {
            "chunker_version": chunker_version,
            "tokenizer": tokenizer,
            "src": {source: source_specific},
        }

    @staticmethod
    def extract_top_level_fields(document: Document) -> dict[str, Any]:
        """Extract fields commonly used for filtering/ranking."""
        return {
            "parent_uid": document.uid,
            "source": document.source,
            "title": document.title,
            "published_at": document.published_at,
            "year": document.published_at.year if document.published_at else None,
        }
