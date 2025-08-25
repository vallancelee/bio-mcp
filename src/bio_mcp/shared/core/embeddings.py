"""
Legacy embeddings module - redirects to new enhanced chunking system.

This module maintains backward compatibility by providing the old interface
but delegates all functionality to the new enhanced chunking system.
"""

from typing import Any
from uuid import UUID

from bio_mcp.config.logging_config import get_logger
from bio_mcp.models.document import Chunk, Document

# Use the new enhanced chunking system directly
from bio_mcp.services.chunking import AbstractChunker as NewChunker
from bio_mcp.services.chunking import ChunkingConfig as NewChunkingConfig

logger = get_logger(__name__)


class ChunkingConfig:
    """Legacy configuration - redirects to new system."""

    TARGET_TOKENS = 325  # Target tokens per chunk
    MAX_TOKENS = 450  # Hard maximum tokens per chunk
    MIN_TOKENS = 120  # Minimum tokens for merging sections
    OVERLAP_TOKENS = 50  # Overlap tokens when splitting
    TOKENIZER_MODEL = "gpt-4"  # Model to use for token counting
    NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # For stable UUIDs


class DocumentChunk:
    """Legacy DocumentChunk class - kept for backward compatibility."""

    def __init__(
        self,
        pmid: str,
        chunk_id: str,
        title: str,
        section: str,
        text: str,
        tokens: int,
        quality_total: float = 0.0,
        year: int | None = None,
        source_url: str = "",
        # Additional legacy attributes
        n_sentences: int = 0,
        edat: str | None = None,
        lr: str | None = None,
        token_count: int | None = None,  # Alias for tokens
    ):
        self.pmid = pmid
        self.chunk_id = chunk_id
        self.title = title
        self.section = section
        self.text = text
        self.tokens = token_count if token_count is not None else tokens
        self.token_count = self.tokens  # Backward compatibility alias
        self.quality_total = quality_total
        self.year = year
        self.source_url = source_url
        self.n_sentences = n_sentences
        self.edat = edat
        self.lr = lr

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Weaviate storage."""
        return {
            "pmid": self.pmid,
            "chunk_id": self.chunk_id,
            "title": self.title,
            "section": self.section,
            "text": self.text,
            "tokens": self.tokens,
            "token_count": self.token_count,  # Include alias
            "quality_total": self.quality_total,
            "year": self.year,
            "source_url": self.source_url,
            "n_sentences": self.n_sentences,
            "edat": self.edat,
            "lr": self.lr,
        }


class AbstractChunker:
    """
    Legacy chunker interface - now uses enhanced chunking system.
    """

    def __init__(self, model_name: str = ChunkingConfig.TOKENIZER_MODEL):
        # Always use the new enhanced chunker
        config = NewChunkingConfig(
            target_tokens=ChunkingConfig.TARGET_TOKENS,
            max_tokens=ChunkingConfig.MAX_TOKENS,
            min_tokens=ChunkingConfig.MIN_TOKENS,
            overlap_tokens=ChunkingConfig.OVERLAP_TOKENS,
        )
        self._chunker = NewChunker(config)
        logger.info("Using enhanced chunking system")

    def chunk_document(self, document: Document, **legacy_kwargs) -> list["Chunk"]:
        """
        Chunk a Document instance into Chunk instances.

        Args:
            document: Document instance to chunk
            **legacy_kwargs: Ignored, for compatibility

        Returns:
            List of Chunk objects
        """
        # Use enhanced chunker directly - it returns Chunk objects
        return self._chunker.chunk_document(document)

    # Legacy methods for backward compatibility
    def chunk_abstract(
        self,
        pmid: str,
        title: str,
        abstract: str,
        quality_total: float = 0.0,
        year: int | None = None,
        source_url: str = "",
    ) -> list[DocumentChunk]:
        """
        Legacy method: chunk abstract text into DocumentChunk objects.

        Converts to new Document format and back for compatibility.
        """
        # Convert to new Document format
        document = Document(
            uid=f"pubmed:{pmid}",
            source="pubmed",
            source_id=pmid,
            title=title,
            text=abstract,
            detail={
                "quality_total": quality_total,
                "year": year,
                "source_url": source_url,
            },
        )

        # Use enhanced chunker
        chunks = self._chunker.chunk_document(document)

        # Handle empty content - create a minimal chunk for backward compatibility
        if not chunks and not abstract.strip():
            legacy_chunks = [
                DocumentChunk(
                    pmid=pmid,
                    chunk_id="title",
                    title=title,
                    section="Title Only",
                    text="No content available",
                    tokens=0,
                    quality_total=quality_total,
                    year=year,
                    source_url=source_url,
                )
            ]
            return legacy_chunks

        # Convert back to legacy DocumentChunk format
        legacy_chunks = []
        for chunk in chunks:
            legacy_chunk = DocumentChunk(
                pmid=pmid,
                chunk_id=chunk.chunk_id,
                title=chunk.title or title,
                section=chunk.section or "Unstructured",
                text=chunk.text,
                tokens=chunk.tokens or 0,
                quality_total=quality_total,
                year=year,
                source_url=source_url,
            )
            legacy_chunks.append(legacy_chunk)

        return legacy_chunks


# Conversion functions for backward compatibility
def document_chunk_to_chunk(
    doc_chunk: DocumentChunk, parent_uid: str, chunk_idx: int
) -> "Chunk":
    """Convert legacy DocumentChunk to new Chunk format."""
    from bio_mcp.models.document import Chunk

    # Extract PMID from parent_uid if it's in pubmed:PMID format
    if parent_uid.startswith("pubmed:"):
        source = "pubmed"
    else:
        parts = parent_uid.split(":", 1)
        source = parts[0] if len(parts) > 1 else "unknown"

    # Create standardized chunk_id
    chunk_id = f"s{chunk_idx}"

    chunk = Chunk(
        chunk_id=chunk_id,
        uuid=Chunk.generate_uuid(parent_uid, chunk_id),
        parent_uid=parent_uid,
        source=source,
        chunk_idx=chunk_idx,
        text=doc_chunk.text,
        title=doc_chunk.title,
        section=doc_chunk.section,
        tokens=doc_chunk.tokens,
        meta={
            "n_sentences": getattr(doc_chunk, "n_sentences", 0),
            "quality_total": doc_chunk.quality_total,
            "year": doc_chunk.year,
            "edat": getattr(doc_chunk, "edat", None),
            "lr": getattr(doc_chunk, "lr", None),
            "source_url": doc_chunk.source_url,
            "chunker_version": "1.0_legacy",
            "legacy_chunk_id": doc_chunk.chunk_id,
        },
    )

    return chunk


def chunk_to_document_chunk(chunk: "Chunk") -> DocumentChunk:
    """Convert new Chunk to legacy DocumentChunk format."""

    # Extract PMID from parent_uid
    if chunk.parent_uid.startswith("pubmed:"):
        pmid = chunk.parent_uid.split(":", 1)[1]
    else:
        # For non-pubmed sources, use the source_id
        pmid = getattr(chunk, "source_id", chunk.parent_uid.split(":", 1)[-1])

    # Get legacy chunk_id from meta or generate one
    legacy_chunk_id = chunk.meta.get("legacy_chunk_id", chunk.chunk_id)

    doc_chunk = DocumentChunk(
        pmid=pmid,
        chunk_id=legacy_chunk_id,
        title=chunk.title or "",
        section=chunk.section or "Text",
        text=chunk.text,
        tokens=chunk.tokens or 0,
        quality_total=chunk.meta.get("quality_total", 0.0),
        year=chunk.meta.get("year"),
        source_url=chunk.meta.get("source_url", ""),
    )

    # Add optional attributes if they exist in meta
    if "n_sentences" in chunk.meta:
        doc_chunk.n_sentences = chunk.meta["n_sentences"]
    if "edat" in chunk.meta:
        doc_chunk.edat = chunk.meta["edat"]
    if "lr" in chunk.meta:
        doc_chunk.lr = chunk.meta["lr"]

    return doc_chunk


def create_chunker(model_name: str = ChunkingConfig.TOKENIZER_MODEL) -> AbstractChunker:
    """Factory function to create a chunker instance."""
    return AbstractChunker(model_name)
