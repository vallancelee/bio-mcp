"""
Unit tests for Document and Chunk models.

Tests cover:
- Model validation and constraints
- Field validation and edge cases  
- Helper methods and computed properties
- Serialization and deserialization
- Error handling for invalid data
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from bio_mcp.models.document import Chunk, Document


class TestDocumentModel:
    """Test the Document Pydantic model."""
    
    def test_minimal_document_creation(self):
        """Test creating a document with minimal required fields."""
        doc = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            text="This is the abstract content."
        )
        
        assert doc.uid == "pubmed:12345678"
        assert doc.source == "pubmed"
        assert doc.source_id == "12345678"
        assert doc.text == "This is the abstract content."
        assert doc.title is None
        assert doc.published_at is None
        assert doc.authors is None
        assert doc.identifiers == {}
        assert doc.provenance == {}
        assert doc.detail == {}
        assert doc.schema_version == 1
    
    def test_full_document_creation(self):
        """Test creating a document with all fields populated."""
        published_date = datetime(2023, 6, 15, tzinfo=UTC)
        fetched_date = datetime(2023, 12, 1, tzinfo=UTC)
        
        doc = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="CRISPR-Cas9 Gene Editing",
            text="This study demonstrates gene editing applications...",
            published_at=published_date,
            fetched_at=fetched_date,
            authors=["Smith, J.", "Johnson, K."],
            labels=["gene-editing", "crispr"],
            identifiers={"doi": "10.1038/example.2023.001"},
            language="en",
            provenance={
                "s3_raw_uri": "s3://bucket/pubmed/12345678.json",
                "content_hash": "abc123def456"
            },
            detail={
                "journal": "Nature Biotechnology",
                "mesh_terms": ["Gene Editing", "CRISPR-Cas Systems"],
                "keywords": ["CRISPR", "gene therapy"]
            }
        )
        
        assert doc.uid == "pubmed:12345678"
        assert doc.title == "CRISPR-Cas9 Gene Editing"
        assert doc.published_at == published_date
        assert doc.authors == ["Smith, J.", "Johnson, K."]
        assert doc.identifiers["doi"] == "10.1038/example.2023.001"
        assert doc.provenance["s3_raw_uri"] == "s3://bucket/pubmed/12345678.json"
        assert doc.detail["journal"] == "Nature Biotechnology"
    
    def test_uid_validation(self):
        """Test UID format validation."""
        # Valid UID
        doc = Document(
            uid="pubmed:12345678",
            source="pubmed", 
            source_id="12345678",
            text="content"
        )
        assert doc.uid == "pubmed:12345678"
        
        # Invalid UID format (no colon)
        with pytest.raises(ValidationError, match="UID must follow format"):
            Document(
                uid="pubmed12345678",
                source="pubmed",
                source_id="12345678", 
                text="content"
            )
    
    def test_source_validation(self):
        """Test source field validation."""
        # Valid lowercase source
        doc = Document(
            uid="pubmed:12345",
            source="pubmed",
            source_id="12345",
            text="content"
        )
        assert doc.source == "pubmed"
        
        # Source gets lowercased
        doc = Document(
            uid="clinicaltrials:nct001",
            source="ClinicalTrials",
            source_id="nct001",
            text="content"
        )
        assert doc.source == "clinicaltrials"
        
        # Invalid source with special characters
        with pytest.raises(ValidationError, match="Source must be alphanumeric"):
            Document(
                uid="pub-med:12345",
                source="pub-med",
                source_id="12345",
                text="content"
            )
    
    def test_uid_consistency_validation(self):
        """Test that UID matches source:source_id format."""
        # Valid consistent UID
        doc = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            text="content"
        )
        assert doc.uid == "pubmed:12345678"
        
        # Inconsistent UID
        with pytest.raises(ValidationError, match="UID.*doesn't match"):
            Document(
                uid="pubmed:12345678",
                source="pubmed",
                source_id="87654321",  # Doesn't match UID
                text="content"
            )
    
    def test_get_searchable_text(self):
        """Test get_searchable_text method."""
        # Document with title and text
        doc = Document(
            uid="pubmed:12345",
            source="pubmed",
            source_id="12345",
            title="Cancer Research Study",
            text="This study investigates cancer treatments."
        )
        expected = "Cancer Research Study This study investigates cancer treatments."
        assert doc.get_searchable_text() == expected
        
        # Document with only text
        doc_no_title = Document(
            uid="pubmed:12346",
            source="pubmed", 
            source_id="12346",
            text="This study investigates cancer treatments."
        )
        assert doc_no_title.get_searchable_text() == "This study investigates cancer treatments."
        
        # Document with empty text
        doc_empty = Document(
            uid="pubmed:12347",
            source="pubmed",
            source_id="12347", 
            title="Just Title",
            text=""
        )
        assert doc_empty.get_searchable_text() == "Just Title"
    
    def test_get_content_hash(self):
        """Test content hash generation."""
        doc1 = Document(
            uid="pubmed:12345",
            source="pubmed",
            source_id="12345",
            title="Title",
            text="Same content"
        )
        
        doc2 = Document(
            uid="pubmed:12346",
            source="pubmed", 
            source_id="12346",
            title="Title",
            text="Same content"
        )
        
        doc3 = Document(
            uid="pubmed:12347",
            source="pubmed",
            source_id="12347",
            title="Title", 
            text="Different content"
        )
        
        # Same content should produce same hash
        assert doc1.get_content_hash() == doc2.get_content_hash()
        
        # Different content should produce different hash
        assert doc1.get_content_hash() != doc3.get_content_hash()
        
        # Hash should be SHA-256 (64 hex chars)
        hash_value = doc1.get_content_hash()
        assert len(hash_value) == 64
        assert all(c in '0123456789abcdef' for c in hash_value)
    
    def test_model_serialization(self):
        """Test JSON serialization and deserialization."""
        original = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678", 
            title="Test Document",
            text="This is test content.",
            published_at=datetime(2023, 1, 1, tzinfo=UTC),
            authors=["Author One", "Author Two"],
            identifiers={"doi": "10.1000/test"},
            provenance={"source": "api"},
            detail={"journal": "Test Journal"}
        )
        
        # Serialize to dict
        doc_dict = original.model_dump()
        assert doc_dict["uid"] == "pubmed:12345678"
        assert doc_dict["title"] == "Test Document"
        
        # Deserialize from dict
        reconstructed = Document(**doc_dict)
        assert reconstructed.uid == original.uid
        assert reconstructed.title == original.title
        assert reconstructed.published_at == original.published_at
        assert reconstructed.authors == original.authors
        assert reconstructed.identifiers == original.identifiers
        
        # Test JSON serialization
        json_str = original.model_dump_json()
        assert "pubmed:12345678" in json_str
        
        # Deserialize from JSON
        from_json = Document.model_validate_json(json_str)
        assert from_json.uid == original.uid


class TestChunkModel:
    """Test the Chunk Pydantic model."""
    
    def test_minimal_chunk_creation(self):
        """Test creating a chunk with minimal required fields."""
        chunk = Chunk(
            chunk_id="pubmed:12345678:0",
            parent_uid="pubmed:12345678",
            source="pubmed",
            chunk_idx=0,
            text="This is the first chunk of text."
        )
        
        assert chunk.chunk_id == "pubmed:12345678:0"
        assert chunk.parent_uid == "pubmed:12345678"
        assert chunk.source == "pubmed"
        assert chunk.chunk_idx == 0
        assert chunk.text == "This is the first chunk of text."
        assert chunk.title is None
        assert chunk.published_at is None
        assert chunk.tokens is None
        assert chunk.section is None
        assert chunk.meta == {}
    
    def test_full_chunk_creation(self):
        """Test creating a chunk with all fields populated."""
        published_date = datetime(2023, 6, 15, tzinfo=UTC)
        
        chunk = Chunk(
            chunk_id="pubmed:12345678:2",
            parent_uid="pubmed:12345678",
            source="pubmed",
            chunk_idx=2,
            text="This is the third chunk containing methodology details.",
            title="CRISPR-Cas9 Gene Editing Study",
            published_at=published_date,
            tokens=150,
            section="methods",
            meta={"language": "en", "confidence": 0.95}
        )
        
        assert chunk.chunk_id == "pubmed:12345678:2"
        assert chunk.chunk_idx == 2
        assert chunk.title == "CRISPR-Cas9 Gene Editing Study"
        assert chunk.published_at == published_date
        assert chunk.tokens == 150
        assert chunk.section == "methods"
        assert chunk.meta["language"] == "en"
        assert chunk.meta["confidence"] == 0.95
    
    def test_chunk_id_validation(self):
        """Test chunk_id format validation."""
        # Valid chunk_id
        chunk = Chunk(
            chunk_id="pubmed:12345678:0",
            parent_uid="pubmed:12345678",
            source="pubmed",
            chunk_idx=0,
            text="content"
        )
        assert chunk.chunk_id == "pubmed:12345678:0"
        
        # Invalid chunk_id format (too few parts)
        with pytest.raises(ValidationError, match="chunk_id must follow format"):
            Chunk(
                chunk_id="pubmed:12345678", 
                parent_uid="pubmed:12345678",
                source="pubmed",
                chunk_idx=0,
                text="content"
            )
    
    def test_chunk_id_consistency_validation(self):
        """Test that chunk_id matches parent_uid:chunk_idx format."""
        # Valid consistent chunk_id
        chunk = Chunk(
            chunk_id="pubmed:12345678:5",
            parent_uid="pubmed:12345678", 
            source="pubmed",
            chunk_idx=5,
            text="content"
        )
        assert chunk.chunk_id == "pubmed:12345678:5"
        
        # Inconsistent chunk_id
        with pytest.raises(ValidationError, match="chunk_id.*doesn't match"):
            Chunk(
                chunk_id="pubmed:12345678:5",
                parent_uid="pubmed:12345678",
                source="pubmed", 
                chunk_idx=3,  # Doesn't match chunk_id
                text="content"
            )
    
    def test_get_embedding_text(self):
        """Test get_embedding_text method."""
        # Chunk without title
        chunk_no_title = Chunk(
            chunk_id="pubmed:12345:0",
            parent_uid="pubmed:12345",
            source="pubmed",
            chunk_idx=0,
            text="This is the chunk content."
        )
        assert chunk_no_title.get_embedding_text() == "This is the chunk content."
        
        # Chunk with title (title not in text)
        chunk_with_title = Chunk(
            chunk_id="pubmed:12345:0",
            parent_uid="pubmed:12345",
            source="pubmed",
            chunk_idx=0,
            text="This is the chunk content.",
            title="Cancer Study"
        )
        expected = "Cancer Study: This is the chunk content."
        assert chunk_with_title.get_embedding_text() == expected
        
        # Chunk where title is already in text
        chunk_title_in_text = Chunk(
            chunk_id="pubmed:12345:0", 
            parent_uid="pubmed:12345",
            source="pubmed",
            chunk_idx=0,
            text="Cancer Study methodology shows that...",
            title="Cancer Study"
        )
        # Should not duplicate title
        assert chunk_title_in_text.get_embedding_text() == "Cancer Study methodology shows that..."
    
    def test_get_display_context(self):
        """Test get_display_context method."""
        # Basic chunk with title
        chunk1 = Chunk(
            chunk_id="pubmed:12345:0",
            parent_uid="pubmed:12345",
            source="pubmed",
            chunk_idx=0,
            text="content",
            title="Gene Editing Study"
        )
        context = chunk1.get_display_context()
        assert "'Gene Editing Study'" in context
        assert "chunk 1" in context
        
        # Chunk with section and publication date
        chunk2 = Chunk(
            chunk_id="pubmed:12345:2",
            parent_uid="pubmed:12345", 
            source="pubmed",
            chunk_idx=2,
            text="content",
            title="Gene Editing Study",
            section="methods",
            published_at=datetime(2023, 6, 15)
        )
        context = chunk2.get_display_context()
        assert "'Gene Editing Study'" in context
        assert "section: methods" in context
        assert "chunk 3" in context  # 1-based display
        assert "published 2023" in context
        
        # Chunk without title
        chunk3 = Chunk(
            chunk_id="pubmed:12345:0",
            parent_uid="pubmed:12345",
            source="pubmed", 
            chunk_idx=0,
            text="content"
        )
        context = chunk3.get_display_context()
        assert "chunk 1" in context
        assert "From" in context
    
    def test_chunk_model_serialization(self):
        """Test JSON serialization and deserialization."""
        original = Chunk(
            chunk_id="pubmed:12345678:1",
            parent_uid="pubmed:12345678",
            source="pubmed",
            chunk_idx=1,
            text="This is chunk content for testing serialization.",
            title="Test Document",
            published_at=datetime(2023, 1, 1, tzinfo=UTC),
            tokens=120,
            section="abstract",
            meta={"language": "en", "quality": "high"}
        )
        
        # Serialize to dict
        chunk_dict = original.model_dump()
        assert chunk_dict["chunk_id"] == "pubmed:12345678:1"
        assert chunk_dict["chunk_idx"] == 1
        
        # Deserialize from dict  
        reconstructed = Chunk(**chunk_dict)
        assert reconstructed.chunk_id == original.chunk_id
        assert reconstructed.text == original.text
        assert reconstructed.meta == original.meta
        
        # Test JSON serialization
        json_str = original.model_dump_json()
        assert "pubmed:12345678:1" in json_str
        
        # Deserialize from JSON
        from_json = Chunk.model_validate_json(json_str)
        assert from_json.chunk_id == original.chunk_id


class TestModelRelationships:
    """Test relationships between Document and Chunk models."""
    
    def test_document_chunk_relationship(self):
        """Test that chunks properly reference their parent document."""
        # Create a document
        doc = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Multi-chunk Document",
            text="This document will be split into multiple chunks."
        )
        
        # Create chunks that reference the document
        chunk1 = Chunk(
            chunk_id="pubmed:12345678:0",
            parent_uid=doc.uid,
            source=doc.source,
            chunk_idx=0,
            text="First chunk content",
            title=doc.title
        )
        
        chunk2 = Chunk(
            chunk_id="pubmed:12345678:1", 
            parent_uid=doc.uid,
            source=doc.source,
            chunk_idx=1,
            text="Second chunk content",
            title=doc.title
        )
        
        # Verify relationships
        assert chunk1.parent_uid == doc.uid
        assert chunk2.parent_uid == doc.uid
        assert chunk1.source == doc.source
        assert chunk2.source == doc.source
        assert chunk1.title == doc.title
        assert chunk2.title == doc.title
        
        # Verify unique chunk IDs
        assert chunk1.chunk_id != chunk2.chunk_id
        assert chunk1.chunk_idx == 0
        assert chunk2.chunk_idx == 1


class TestModelEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_text_document(self):
        """Test document with empty text (edge case)."""
        doc = Document(
            uid="pubmed:12345",
            source="pubmed",
            source_id="12345",
            text=""  # Empty text
        )
        assert doc.text == ""
        assert doc.get_searchable_text() == ""
    
    def test_very_long_text(self):
        """Test document with very long text."""
        long_text = "A" * 100000  # 100k characters
        
        doc = Document(
            uid="pubmed:12345",
            source="pubmed", 
            source_id="12345",
            text=long_text
        )
        
        assert len(doc.text) == 100000
        assert len(doc.get_content_hash()) == 64  # SHA-256 always 64 chars
    
    def test_unicode_content(self):
        """Test documents with Unicode content."""
        doc = Document(
            uid="pubmed:12345",
            source="pubmed",
            source_id="12345",
            title="研究论文 🧬",  # Chinese title with emoji
            text="This study examines ΔFosB protein expression μg/ml concentrations.",
            authors=["José García-López", "李明", "Müller, Hans"]
        )
        
        assert "研究论文 🧬" in doc.title
        assert "ΔFosB" in doc.text
        assert "José García-López" in doc.authors
        
        # Unicode content should hash consistently  
        hash1 = doc.get_content_hash()
        hash2 = doc.get_content_hash()
        assert hash1 == hash2
    
    def test_negative_chunk_index(self):
        """Test chunk with negative index (should work but unusual)."""
        # This is technically valid but unusual
        chunk = Chunk(
            chunk_id="pubmed:12345:-1",
            parent_uid="pubmed:12345",
            source="pubmed",
            chunk_idx=-1,
            text="Negative index chunk"
        )
        assert chunk.chunk_idx == -1
    
    def test_missing_required_fields(self):
        """Test model validation with missing required fields."""
        # Document missing required fields
        with pytest.raises(ValidationError):
            Document()  # Missing all required fields
        
        with pytest.raises(ValidationError): 
            Document(uid="pubmed:12345")  # Missing source, source_id, text
        
        # Chunk missing required fields
        with pytest.raises(ValidationError):
            Chunk()  # Missing all required fields
            
        with pytest.raises(ValidationError):
            Chunk(chunk_id="pubmed:12345:0")  # Missing other required fields