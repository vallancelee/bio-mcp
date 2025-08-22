"""
Document chunking for Bio-MCP server.
Implements the chunking strategy from CHUNKING_STRATEGY.md for PubMed abstracts:
- Section-aware chunking for structured abstracts
- 250-350 token target chunks with 450 token max
- Special handling for numeric claims
- Stable chunk IDs for idempotent upserts
"""

import re
import uuid
from datetime import UTC
from typing import Any
from uuid import UUID

import tiktoken

from bio_mcp.config.logging_config import get_logger
from bio_mcp.models.document import Chunk, Document

logger = get_logger(__name__)


class ChunkingConfig:
    """Configuration for abstract chunking."""

    TARGET_TOKENS = 325  # Target tokens per chunk
    MAX_TOKENS = 450  # Hard maximum tokens per chunk
    MIN_TOKENS = 120  # Minimum tokens for merging sections
    OVERLAP_TOKENS = 50  # Overlap tokens when splitting
    TOKENIZER_MODEL = "gpt-4"  # Model to use for token counting
    NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # For stable UUIDs


class DocumentChunk:
    """Represents a chunk of a PubMed document."""

    def __init__(
        self,
        pmid: str,
        chunk_id: str,
        title: str,
        section: str,
        text: str,
        token_count: int,
        n_sentences: int = 0,
        quality_total: int | None = None,
        year: int | None = None,
        edat: str | None = None,
        lr: str | None = None,
        source_url: str | None = None,
    ):
        self.pmid = pmid
        self.chunk_id = chunk_id
        self.title = title
        self.section = section
        self.text = text
        self.token_count = token_count
        self.n_sentences = n_sentences
        self.quality_total = quality_total
        self.year = year
        self.edat = edat
        self.lr = lr
        self.source_url = source_url or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        # Generate stable UUID for Weaviate
        self.uuid = uuid.uuid5(ChunkingConfig.NAMESPACE, f"{pmid}:{chunk_id}")

    def to_dict(self) -> dict[str, Any]:
        """Convert chunk to dictionary for storage."""
        return {
            "pmid": self.pmid,
            "chunk_id": self.chunk_id,
            "uuid": str(self.uuid),
            "title": self.title,
            "section": self.section,
            "text": self.text,
            "token_count": self.token_count,
            "n_sentences": self.n_sentences,
            "quality_total": self.quality_total,
            "year": self.year,
            "edat": self.edat,
            "lr": self.lr,
            "source_url": self.source_url,
        }


class AbstractChunker:
    """Chunks PubMed abstracts according to the defined strategy."""

    def __init__(self, model_name: str = ChunkingConfig.TOKENIZER_MODEL):
        self.tokenizer = tiktoken.encoding_for_model(model_name)

        # Section detection patterns (case-insensitive)
        self.section_patterns = [
            r"^\s*(Background|Objective|Purpose|Introduction)\s*[:\-]",
            r"^\s*(Methods?|Methodology|Materials and Methods|Study Design)\s*[:\-]",
            r"^\s*(Results?|Findings|Outcomes)\s*[:\-]",
            r"^\s*(Conclusions?|Discussion|Interpretation|Implications)\s*[:\-]",
            r"^\s*(Limitations|Future Work|Clinical Relevance)\s*[:\-]",
        ]

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using the model's tokenizer."""
        return len(self.tokenizer.encode(text))

    def normalize_text(self, text: str) -> str:
        """Normalize text according to Step 1 of chunking strategy."""
        if not text:
            return ""

        # Unicode NFKC normalize
        import unicodedata

        text = unicodedata.normalize("NFKC", text)

        # Join hyphenated line breaks first
        text = re.sub(r"-\s*\n\s*", "", text)

        # Collapse multiple whitespace within lines but preserve newlines for structure detection
        text = re.sub(r"[ \t]+", " ", text)  # Collapse spaces and tabs within lines
        text = re.sub(r"\n[ \t]*\n", "\n\n", text)  # Normalize paragraph breaks
        text = re.sub(r"\n{3,}", "\n\n", text)  # Max 2 consecutive newlines

        return text.strip()

    def detect_structure(self, abstract: str) -> list[tuple[str, str]] | None:
        """Detect if abstract is structured and extract sections."""
        if not abstract:
            return None

        sections = []
        current_section = None
        current_content = []

        for line in abstract.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Check if line starts a new section
            section_found = False
            for pattern in self.section_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    # Save previous section
                    if current_section:
                        content = " ".join(current_content).strip()
                        if content:
                            sections.append((current_section, content))

                    # Start new section
                    current_section = match.group(1).title()
                    # Remove the header from the content
                    remaining_text = re.sub(
                        pattern, "", line, flags=re.IGNORECASE
                    ).strip()
                    current_content = [remaining_text] if remaining_text else []
                    section_found = True
                    break

            if not section_found and current_section:
                current_content.append(line)

        # Add final section
        if current_section:
            content = " ".join(current_content).strip()
            if content:
                sections.append((current_section, content))

        # Return sections if we found at least 2, otherwise None (unstructured)
        return sections if len(sections) >= 2 else None

    def split_sentences(self, text: str) -> list[str]:
        """Split text into sentences using simple rules."""
        if not text:
            return []

        # Simple sentence splitting that avoids breaking numbers
        sentences = []
        current = ""

        for char in text:
            current += char
            # Split on period, exclamation, question mark
            if char in ".!?" and len(current.strip()) > 10:
                # Don't split if it looks like a number or abbreviation
                stripped = current.strip()
                # Check for common patterns that shouldn't end sentences
                if not re.search(r"\d+\.\d*$|[A-Z]\.$|vs\.$|et al\.$|p\s*=$", stripped):
                    sentences.append(stripped)
                    current = ""

        # Add remaining text
        if current.strip():
            sentences.append(current.strip())

        return [s for s in sentences if s]

    def expand_around_stats(
        self, text_blocks: list[tuple[str, str, str]]
    ) -> list[tuple[str, str, str]]:
        """Expand chunks to keep statistical claims with comparators."""
        # For now, implement a simple version - could be enhanced later
        return text_blocks

    def chunk_structured(
        self, sections: list[tuple[str, str]]
    ) -> list[tuple[str, str, str]]:
        """Chunk structured abstract by sections."""
        chunks = []

        for i, (section_name, section_text) in enumerate(sections):
            section_tokens = self.count_tokens(section_text)

            if section_tokens <= ChunkingConfig.MAX_TOKENS:
                # Section fits in one chunk
                chunks.append((f"s{i}", section_name, section_text))
            else:
                # Split section by sentences
                sentences = self.split_sentences(section_text)
                current_chunk = []
                current_tokens = 0
                chunk_idx = 0

                for sentence in sentences:
                    sentence_tokens = self.count_tokens(sentence)

                    if (
                        current_tokens + sentence_tokens > ChunkingConfig.MAX_TOKENS
                        and current_chunk
                    ):
                        # Save current chunk
                        chunk_text = " ".join(current_chunk)
                        chunks.append((f"s{i}_{chunk_idx}", section_name, chunk_text))
                        chunk_idx += 1

                        # Start new chunk with overlap
                        if ChunkingConfig.OVERLAP_TOKENS > 0 and len(current_chunk) > 1:
                            # Keep last sentence for overlap
                            overlap_text = current_chunk[-1]
                            current_chunk = [overlap_text, sentence]
                            current_tokens = (
                                self.count_tokens(overlap_text) + sentence_tokens
                            )
                        else:
                            current_chunk = [sentence]
                            current_tokens = sentence_tokens
                    else:
                        current_chunk.append(sentence)
                        current_tokens += sentence_tokens

                # Add remaining chunk
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append((f"s{i}_{chunk_idx}", section_name, chunk_text))

        return chunks

    def chunk_unstructured(self, abstract: str) -> list[tuple[str, str, str]]:
        """Chunk unstructured abstract by sliding windows."""
        abstract_tokens = self.count_tokens(abstract)

        if abstract_tokens <= ChunkingConfig.MAX_TOKENS:
            return [("w0", "Unstructured", abstract)]

        sentences = self.split_sentences(abstract)
        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_idx = 0

        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)

            if (
                current_tokens + sentence_tokens > ChunkingConfig.TARGET_TOKENS
                and current_chunk
            ):
                # Save current chunk
                chunk_text = " ".join(current_chunk)
                chunks.append((f"w{chunk_idx}", "Unstructured", chunk_text))
                chunk_idx += 1

                # Start new chunk with overlap
                if ChunkingConfig.OVERLAP_TOKENS > 0 and len(current_chunk) > 1:
                    overlap_text = current_chunk[-1]
                    current_chunk = [overlap_text, sentence]
                    current_tokens = self.count_tokens(overlap_text) + sentence_tokens
                else:
                    current_chunk = [sentence]
                    current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

        # Add remaining chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append((f"w{chunk_idx}", "Unstructured", chunk_text))

        return chunks

    def chunk_document(self, document: Document, **legacy_kwargs) -> list[Chunk]:
        """
        Chunk a Document instance into Chunk instances.

        This is the new method that works with the multi-source Document model.

        Args:
            document: Document instance to chunk
            **legacy_kwargs: Ignored, for compatibility

        Returns:
            List of Chunk objects
        """
        # Extract metadata from document
        title = document.title or f"Document {document.source_id}"
        text = document.text

        # Extract additional metadata from detail if available
        year = None
        quality_total = None
        edat = None
        lr = None

        if document.published_at:
            year = document.published_at.year

        # Extract legacy fields from detail if available (for PubMed compatibility)
        if document.detail:
            quality_total = document.detail.get("quality_total")
            edat = document.detail.get("edat")
            lr = document.detail.get("lr")

        if not text or len(text.strip()) < 50:
            # Very short or empty text
            if text:
                combined_text = f"{title}\n[Section] Text\n{text}".strip()
                token_count = self.count_tokens(combined_text)
                chunk_id = "s0"  # Section-based chunk
                return [
                    Chunk(
                        chunk_id=chunk_id,
                        uuid=Chunk.generate_uuid(document.uid, chunk_id),
                        parent_uid=document.uid,
                        source=document.source,
                        chunk_idx=0,
                        text=combined_text,
                        title=title,
                        section="Text",
                        tokens=token_count,
                        meta={
                            "chunker_version": "2.0",
                            "chunk_strategy": "minimal",
                            "n_sentences": 1,
                        },
                    )
                ]
            else:
                # No text - create metadata-only chunk
                combined_text = f"{title}\n[Section] Title Only\nNo content available."
                token_count = self.count_tokens(combined_text)
                chunk_id = "s0"  # Even title-only chunks use section format
                return [
                    Chunk(
                        chunk_id=chunk_id,
                        uuid=Chunk.generate_uuid(document.uid, chunk_id),
                        parent_uid=document.uid,
                        source=document.source,
                        chunk_idx=0,  # Use 0 instead of -1 for consistency
                        text=combined_text,
                        title=title,
                        section="Title Only",
                        tokens=token_count,
                        meta={
                            "chunker_version": "2.0",
                            "chunk_strategy": "title_only",
                            "n_sentences": 0,
                            "legacy_chunk_id": "title",
                        },
                    )
                ]

        # Normalize text
        normalized_text = self.normalize_text(text)
        normalized_title = self.normalize_text(title)

        # Detect structure
        sections = self.detect_structure(normalized_text)

        if sections:
            # Structured text
            logger.debug(
                f"Chunking structured text for {document.uid}", sections=len(sections)
            )
            text_blocks = self.chunk_structured(sections)
            strategy = "structured"
        else:
            # Unstructured text
            logger.debug(f"Chunking unstructured text for {document.uid}")
            text_blocks = self.chunk_unstructured(normalized_text)
            strategy = "unstructured"

        # Apply numeric safety rules
        text_blocks = self.expand_around_stats(text_blocks)

        # Create chunks with enriched headers
        chunks = []
        for k, (legacy_chunk_id, section, body) in enumerate(text_blocks):
            # Add title prefix only to first chunk
            if k == 0:
                enriched_text = f"[Title] {normalized_title} ({document.source}:{document.source_id})\n[Section] {section}\n[Text] {body}"
            else:
                enriched_text = f"[Section] {section}\n[Text] {body}"

            # Count sentences
            sentences = self.split_sentences(body)
            n_sentences = len(sentences)

            # Calculate final token count
            token_count = self.count_tokens(enriched_text)

            # Use section-based chunking format
            chunk_id = f"s{k}"
            chunk = Chunk(
                chunk_id=chunk_id,
                uuid=Chunk.generate_uuid(document.uid, chunk_id),
                parent_uid=document.uid,
                source=document.source,
                chunk_idx=k,
                text=enriched_text.strip(),
                title=normalized_title,
                published_at=document.published_at,
                section=section,
                tokens=token_count,
                meta={
                    "chunker_version": "2.0",
                    "chunk_strategy": strategy,
                    "n_sentences": n_sentences,
                    "legacy_chunk_id": legacy_chunk_id,
                    "quality_total": quality_total,
                    "year": year,
                    "edat": edat,
                    "lr": lr,
                },
            )

            chunks.append(chunk)

        logger.info(
            f"Created {len(chunks)} chunks for {document.uid}",
            total_tokens=sum(c.tokens or 0 for c in chunks),
        )

        return chunks

    def chunk_abstract(
        self,
        pmid: str,
        title: str,
        abstract: str,
        quality_total: int | None = None,
        year: int | None = None,
        edat: str | None = None,
        lr: str | None = None,
    ) -> list[DocumentChunk]:
        """
        Chunk a PubMed abstract according to the chunking strategy.

        DEPRECATED: Use chunk_document() with Document model instead.
        This method is maintained for backward compatibility.

        Args:
            pmid: PubMed ID
            title: Article title
            abstract: Article abstract
            quality_total: Quality score for the document
            year: Publication year
            edat: Entry date
            lr: Last revision date

        Returns:
            List of DocumentChunk objects (legacy format)
        """
        # Convert to Document model and use new chunking logic
        from datetime import datetime

        # Create a temporary Document for the new chunking logic
        published_at = None
        if year:
            published_at = datetime(year, 1, 1, tzinfo=UTC)

        temp_document = Document(
            uid=f"pubmed:{pmid}",
            source="pubmed",
            source_id=pmid,
            title=title,
            text=abstract or "",
            published_at=published_at,
            authors=None,
            identifiers={},
            provenance={},
            detail={"quality_total": quality_total, "edat": edat, "lr": lr},
        )

        # Use new chunking logic
        new_chunks = self.chunk_document(temp_document)

        # Convert back to legacy DocumentChunk format
        legacy_chunks = []
        for chunk in new_chunks:
            legacy_chunk = chunk_to_document_chunk(chunk)
            legacy_chunks.append(legacy_chunk)

        return legacy_chunks


# Convenience function for creating chunker with backward compatibility wrapper
def create_chunker(model_name: str = ChunkingConfig.TOKENIZER_MODEL) -> AbstractChunker:
    """Create an AbstractChunker instance with both new and legacy methods."""
    return AbstractChunker(model_name)


# Helper function to convert legacy DocumentChunk to new Chunk model
def document_chunk_to_chunk(
    doc_chunk: DocumentChunk, document_uid: str, chunk_idx: int = 0
) -> Chunk:
    """Convert legacy DocumentChunk to new Chunk model."""
    # Use section-based chunk ID format for legacy conversion
    chunk_id = f"s{chunk_idx}"
    return Chunk(
        chunk_id=chunk_id,
        uuid=Chunk.generate_uuid(document_uid, chunk_id),
        parent_uid=document_uid,
        source="pubmed",  # Assume PubMed for legacy chunks
        chunk_idx=chunk_idx,
        text=doc_chunk.text,
        title=doc_chunk.title,
        section=doc_chunk.section,
        tokens=doc_chunk.token_count,
        meta={
            "chunker_version": "1.0_legacy",
            "n_sentences": doc_chunk.n_sentences,
            "quality_total": doc_chunk.quality_total,
            "year": doc_chunk.year,
            "edat": doc_chunk.edat,
            "lr": doc_chunk.lr,
            "legacy_chunk_id": doc_chunk.chunk_id,
        },
    )


# Helper function to convert new Chunk to legacy DocumentChunk
def chunk_to_document_chunk(chunk: Chunk) -> DocumentChunk:
    """Convert new Chunk model to legacy DocumentChunk."""
    # Extract PMID from parent_uid (assumes format "pubmed:12345678")
    pmid = (
        chunk.parent_uid.split(":")[-1] if ":" in chunk.parent_uid else chunk.parent_uid
    )

    # Use legacy chunk ID from meta if available, otherwise use chunk_idx
    legacy_chunk_id = chunk.meta.get("legacy_chunk_id", str(chunk.chunk_idx))

    return DocumentChunk(
        pmid=pmid,
        chunk_id=legacy_chunk_id,
        title=chunk.title,
        section=chunk.section,
        text=chunk.text,
        token_count=chunk.tokens or 0,
        n_sentences=chunk.meta.get("n_sentences", 0),
        quality_total=chunk.meta.get("quality_total"),
        year=chunk.meta.get("year"),
        edat=chunk.meta.get("edat"),
        lr=chunk.meta.get("lr"),
    )
