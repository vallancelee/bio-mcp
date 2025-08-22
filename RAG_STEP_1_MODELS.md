# RAG Step 1: Document and Chunk Models

**Objective:** Create shared Document and Chunk Pydantic models with UUIDv5 generation, multi-source metadata support, and comprehensive validation.

**Success Criteria:**
- Document and Chunk models with proper validation
- UUIDv5 deterministic ID generation 
- Multi-source metadata pattern implemented
- 100% test coverage for model validation
- Backward compatibility maintained

---

## 1. Core Models Implementation

### 1.1 Update Document Model 
**File:** `src/bio_mcp/models/document.py`

```python
from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, computed_field

# UUID namespace for deterministic chunk IDs (fix once, never change)
CHUNK_UUID_NAMESPACE = uuid.UUID("1b2c3d4e-0000-0000-0000-000000000000")

class Document(BaseModel):
    """Minimal shared document model for multi-source biomedical data."""
    
    # Core identity
    uid: str = Field(..., description="Universal document ID, e.g. 'pubmed:12345678'")
    source: str = Field(..., description="Source identifier: 'pubmed', 'ctgov', etc.")
    source_id: str = Field(..., description="Source-specific ID (PMID, NCT number, etc.)")

    # Content (minimal for cross-source operations)
    title: Optional[str] = Field(None, description="Document title")
    text: str = Field(..., description="Main text content to chunk (abstract/summary)")

    # Temporal metadata
    published_at: Optional[datetime] = Field(None, description="Original publication date")
    fetched_at: Optional[datetime] = Field(None, description="When we retrieved this document")
    language: Optional[str] = Field(None, description="Document language code")

    # Common cross-source metadata
    authors: Optional[List[str]] = Field(None, description="List of author names")
    labels: Optional[List[str]] = Field(None, description="User-assigned or computed labels")
    identifiers: Dict[str, str] = Field(
        default_factory=dict, 
        description="Cross-references like DOI, PMCID, etc."
    )

    # Provenance and extensions
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Audit info: s3_raw_uri, content_hash, etc."
    )
    detail: Dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific fields (journal, MeSH terms, etc.)"
    )
    license: Optional[str] = Field(None, description="License information")
    
    # Schema versioning
    schema_version: int = Field(default=1, description="Schema version for migrations")

    @field_validator('uid')
    @classmethod
    def validate_uid_format(cls, v: str) -> str:
        """Ensure UID follows 'source:source_id' format."""
        if ':' not in v:
            raise ValueError("UID must follow format 'source:source_id'")
        parts = v.split(':', 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("UID must have non-empty source and source_id")
        return v
    
    @field_validator('source')
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
        """Get the full searchable text content for this document."""
        parts = []
        if self.title:
            parts.append(self.title)
        if self.text:
            parts.append(self.text)
        return " ".join(parts).strip()
    
    def get_content_hash(self) -> str:
        """Generate a stable hash of the document content."""
        import hashlib
        content = self.get_searchable_text()
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

class Chunk(BaseModel):
    """Document chunk model for embedding and vector search."""
    
    # Core identity and relationships
    chunk_id: str = Field(..., description="Stable short ID within doc, e.g. 's0', 'w1'")
    uuid: str = Field(..., description="UUIDv5 computed from parent_uid + chunk_id")
    parent_uid: str = Field(..., description="UID of parent Document")
    source: str = Field(..., description="Source identifier (inherited from parent)")
    
    # Position and content
    chunk_idx: int = Field(..., description="0-based index within parent document")
    text: str = Field(..., description="Chunk text content")
    
    # Inherited metadata from parent document
    title: Optional[str] = Field(None, description="Parent document title")
    section: Optional[str] = Field(None, description="Document section (Background/Methods/Results/Conclusions/Other)")
    published_at: Optional[datetime] = Field(None, description="Parent publication date")
    
    # Chunking metadata
    tokens: Optional[int] = Field(None, description="Token count (if computed)")
    n_sentences: Optional[int] = Field(None, description="Number of sentences in chunk")
    
    # Additional metadata
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata including chunker info and source-specific data"
    )
    
    @field_validator('chunk_id')
    @classmethod
    def validate_chunk_id_format(cls, v: str) -> str:
        """Ensure chunk_id follows expected format (s0, w1, etc.)."""
        import re
        if not re.match(r'^[sw]\d+$', v):
            raise ValueError("chunk_id must follow format 's0', 'w1', etc. (s=section, w=window)")
        return v
    
    @field_validator('uuid')
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
        expected_uuid = str(uuid.uuid5(CHUNK_UUID_NAMESPACE, f"{self.parent_uid}:{self.chunk_id}"))
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
```

### 1.2 Multi-Source Metadata Pattern

Add metadata utilities:

```python
class MetadataBuilder:
    """Helper class for building multi-source metadata."""
    
    @staticmethod
    def build_chunk_metadata(
        chunker_version: str,
        tokenizer: str,
        source_specific: Dict[str, Any],
        source: str
    ) -> Dict[str, Any]:
        """Build standardized chunk metadata."""
        return {
            "chunker_version": chunker_version,
            "tokenizer": tokenizer,
            "src": {
                source: source_specific
            }
        }
    
    @staticmethod
    def extract_top_level_fields(document: Document) -> Dict[str, Any]:
        """Extract fields commonly used for filtering/ranking."""
        return {
            "parent_uid": document.uid,
            "source": document.source,
            "title": document.title,
            "published_at": document.published_at,
            "year": document.published_at.year if document.published_at else None,
        }
```

---

## 2. Testing Implementation

### 2.1 Unit Tests
**File:** `tests/unit/models/test_document_models.py`

```python
import pytest
import uuid
from datetime import datetime
from bio_mcp.models.document import Document, Chunk, MetadataBuilder, CHUNK_UUID_NAMESPACE

class TestDocumentModel:
    """Test Document model validation and behavior."""
    
    def test_valid_document_creation(self):
        """Test creating a valid document."""
        doc = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Test Paper",
            text="This is a test abstract.",
            published_at=datetime(2024, 1, 15),
            authors=["Smith, J.", "Doe, J."],
            identifiers={"doi": "10.1234/test"},
            detail={"journal": "Nature", "mesh_terms": ["test", "paper"]}
        )
        
        assert doc.uid == "pubmed:12345678"
        assert doc.source == "pubmed"
        assert doc.get_searchable_text() == "Test Paper This is a test abstract."
        assert len(doc.get_content_hash()) == 64  # SHA-256
    
    def test_uid_validation(self):
        """Test UID format validation."""
        # Valid UIDs
        Document(uid="pubmed:123", source="pubmed", source_id="123", text="test")
        Document(uid="ctgov:NCT123", source="ctgov", source_id="NCT123", text="test")
        
        # Invalid UIDs
        with pytest.raises(ValueError, match="UID must follow format"):
            Document(uid="invalid", source="pubmed", source_id="123", text="test")
        
        with pytest.raises(ValueError, match="doesn't match source:source_id"):
            Document(uid="pubmed:999", source="pubmed", source_id="123", text="test")
    
    def test_source_validation(self):
        """Test source validation."""
        # Valid sources
        Document(uid="test:123", source="test", source_id="123", text="test")
        
        # Invalid sources
        with pytest.raises(ValueError, match="Source must be alphanumeric"):
            Document(uid="test-bad:123", source="test-bad", source_id="123", text="test")

class TestChunkModel:
    """Test Chunk model validation and behavior."""
    
    def test_valid_chunk_creation(self):
        """Test creating a valid chunk."""
        parent_uid = "pubmed:12345678"
        chunk_id = "s0"
        expected_uuid = str(uuid.uuid5(CHUNK_UUID_NAMESPACE, f"{parent_uid}:{chunk_id}"))
        
        chunk = Chunk(
            chunk_id=chunk_id,
            uuid=expected_uuid,
            parent_uid=parent_uid,
            source="pubmed",
            chunk_idx=0,
            text="This is chunk text.",
            title="Test Paper",
            section="Background",
            tokens=10,
            n_sentences=1,
            meta={"chunker_version": "v1.0.0"}
        )
        
        assert chunk.chunk_id == "s0"
        assert chunk.uuid == expected_uuid
        assert chunk.get_embedding_text() == "This is chunk text."
        assert "Background" in chunk.get_display_context()
    
    def test_uuid_generation(self):
        """Test deterministic UUID generation."""
        parent_uid = "pubmed:12345678"
        chunk_id = "s0"
        
        uuid1 = Chunk.generate_uuid(parent_uid, chunk_id)
        uuid2 = Chunk.generate_uuid(parent_uid, chunk_id)
        
        assert uuid1 == uuid2  # Deterministic
        assert len(uuid1) == 36  # UUID format
    
    def test_chunk_id_validation(self):
        """Test chunk_id format validation."""
        parent_uid = "pubmed:123"
        
        # Valid chunk IDs
        for cid in ["s0", "s1", "w0", "w10"]:
            uuid_val = Chunk.generate_uuid(parent_uid, cid)
            Chunk(
                chunk_id=cid, uuid=uuid_val, parent_uid=parent_uid,
                source="pubmed", chunk_idx=0, text="test"
            )
        
        # Invalid chunk IDs
        for cid in ["invalid", "s", "1", "x0"]:
            with pytest.raises(ValueError, match="chunk_id must follow format"):
                uuid_val = Chunk.generate_uuid(parent_uid, cid)
                Chunk(
                    chunk_id=cid, uuid=uuid_val, parent_uid=parent_uid,
                    source="pubmed", chunk_idx=0, text="test"
                )
    
    def test_uuid_consistency_validation(self):
        """Test UUID consistency validation."""
        parent_uid = "pubmed:123"
        chunk_id = "s0"
        correct_uuid = Chunk.generate_uuid(parent_uid, chunk_id)
        wrong_uuid = "00000000-0000-0000-0000-000000000000"
        
        # Should fail with wrong UUID
        with pytest.raises(ValueError, match="UUID .* doesn't match expected"):
            Chunk(
                chunk_id=chunk_id, uuid=wrong_uuid, parent_uid=parent_uid,
                source="pubmed", chunk_idx=0, text="test"
            )

class TestMetadataBuilder:
    """Test metadata building utilities."""
    
    def test_build_chunk_metadata(self):
        """Test chunk metadata building."""
        metadata = MetadataBuilder.build_chunk_metadata(
            chunker_version="v1.2.0",
            tokenizer="hf:pritamdeka/BioBERT",
            source_specific={"mesh_terms": ["test"], "journal": "Nature"},
            source="pubmed"
        )
        
        assert metadata["chunker_version"] == "v1.2.0"
        assert metadata["tokenizer"] == "hf:pritamdeka/BioBERT"
        assert metadata["src"]["pubmed"]["mesh_terms"] == ["test"]
        assert metadata["src"]["pubmed"]["journal"] == "Nature"
    
    def test_extract_top_level_fields(self):
        """Test top-level field extraction."""
        doc = Document(
            uid="pubmed:123",
            source="pubmed", 
            source_id="123",
            title="Test",
            text="test",
            published_at=datetime(2024, 1, 15)
        )
        
        fields = MetadataBuilder.extract_top_level_fields(doc)
        
        assert fields["parent_uid"] == "pubmed:123"
        assert fields["source"] == "pubmed"
        assert fields["title"] == "Test"
        assert fields["year"] == 2024
```

### 2.2 Integration Tests
**File:** `tests/integration/models/test_document_integration.py`

```python
import pytest
from datetime import datetime
from bio_mcp.models.document import Document, Chunk

class TestDocumentChunkIntegration:
    """Test Document and Chunk models working together."""
    
    def test_document_to_chunks_workflow(self):
        """Test typical document → chunks workflow."""
        # Create document
        doc = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678", 
            title="Biomedical Research Paper",
            text="Background: This study investigates... Methods: We conducted... Results: We found...",
            published_at=datetime(2024, 1, 15),
            authors=["Smith, J."],
            provenance={"s3_raw_uri": "s3://bucket/pubmed/12345678.json"},
            detail={"journal": "Nature Medicine", "mesh_terms": ["research", "biomedical"]}
        )
        
        # Simulate chunking process
        chunks = []
        sections = ["Background", "Methods", "Results"]
        texts = [
            "Background: This study investigates...",
            "Methods: We conducted...", 
            "Results: We found..."
        ]
        
        for i, (section, text) in enumerate(zip(sections, texts)):
            chunk_id = f"s{i}"
            chunk = Chunk(
                chunk_id=chunk_id,
                uuid=Chunk.generate_uuid(doc.uid, chunk_id),
                parent_uid=doc.uid,
                source=doc.source,
                chunk_idx=i,
                text=text,
                title=doc.title,
                section=section,
                published_at=doc.published_at,
                tokens=len(text.split()),  # Rough approximation
                n_sentences=1,
                meta={
                    "chunker_version": "v1.2.0",
                    "tokenizer": "hf:pritamdeka/BioBERT",
                    "src": {
                        "pubmed": doc.detail
                    }
                }
            )
            chunks.append(chunk)
        
        # Verify relationships
        assert len(chunks) == 3
        for chunk in chunks:
            assert chunk.parent_uid == doc.uid
            assert chunk.source == doc.source
            assert chunk.title == doc.title
            assert chunk.published_at == doc.published_at
            assert chunk.meta["src"]["pubmed"]["journal"] == "Nature Medicine"
        
        # Verify deterministic UUIDs
        chunk_uuids = [chunk.uuid for chunk in chunks]
        assert len(set(chunk_uuids)) == 3  # All unique
        
        # Re-generate same chunks should have same UUIDs
        new_chunks = []
        for i, (section, text) in enumerate(zip(sections, texts)):
            chunk_id = f"s{i}"
            new_chunk = Chunk(
                chunk_id=chunk_id,
                uuid=Chunk.generate_uuid(doc.uid, chunk_id),
                parent_uid=doc.uid,
                source=doc.source,
                chunk_idx=i,
                text=text,
                title=doc.title,
                section=section
            )
            new_chunks.append(new_chunk)
        
        for original, regenerated in zip(chunks, new_chunks):
            assert original.uuid == regenerated.uuid
```

---

## 3. Configuration Updates

### 3.1 Environment Configuration
**File:** `.env.example` (additions)

```bash
# UUID namespace for deterministic chunk IDs (set once, never change)
BIO_MCP_UUID_NAMESPACE=1b2c3d4e-0000-0000-0000-000000000000

# Model versioning
BIO_MCP_DOCUMENT_SCHEMA_VERSION=1
BIO_MCP_CHUNKER_VERSION=v1.2.0
```

### 3.2 Configuration Class
**File:** `src/bio_mcp/config/config.py` (additions)

```python
import uuid

class Config:
    # ... existing config ...
    
    # Model configuration
    uuid_namespace: uuid.UUID = uuid.UUID(
        os.getenv("BIO_MCP_UUID_NAMESPACE", "1b2c3d4e-0000-0000-0000-000000000000")
    )
    document_schema_version: int = int(os.getenv("BIO_MCP_DOCUMENT_SCHEMA_VERSION", "1"))
    chunker_version: str = os.getenv("BIO_MCP_CHUNKER_VERSION", "v1.2.0")
```

---

## 4. Migration Guide

### 4.1 Backward Compatibility
- Existing `Document` usage should be reviewed and updated
- Add adapters where needed to maintain API compatibility
- Ensure no breaking changes to existing MCP tools

### 4.2 Rollback Plan
- Keep existing models as `_legacy` variants
- Add feature flag to switch between implementations
- Document rollback procedure

---

## 5. Success Validation

### 5.1 Checklist
- [ ] Document model validates all required fields
- [ ] Chunk model generates deterministic UUIDs
- [ ] Multi-source metadata pattern works for PubMed data
- [ ] All unit tests pass (100% coverage)
- [ ] Integration tests verify document→chunk workflow
- [ ] No breaking changes to existing APIs
- [ ] Configuration properly loaded and validated

### 5.2 Performance Requirements
- Document creation: <1ms per document
- Chunk UUID generation: <0.1ms per chunk
- Metadata validation: <0.5ms per document

---

## Next Steps

After completing this step:
1. Proceed to **RAG_STEP_2_CHUNKING.md** for section-aware chunking
2. Update any existing normalizers to use new Document model
3. Verify integration with PubMed data pipeline

**Estimated Time:** 1-2 days
**Dependencies:** None
**Risk Level:** Low (new models, minimal changes to existing code)