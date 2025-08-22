import uuid
from datetime import datetime

import pytest

from bio_mcp.models.document import (
    CHUNK_UUID_NAMESPACE,
    Chunk,
    Document,
    MetadataBuilder,
)


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
            detail={"journal": "Nature", "mesh_terms": ["test", "paper"]},
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
            Document(
                uid="test-bad:123", source="test-bad", source_id="123", text="test"
            )


class TestChunkModel:
    """Test Chunk model validation and behavior."""

    def test_valid_chunk_creation(self):
        """Test creating a valid chunk."""
        parent_uid = "pubmed:12345678"
        chunk_id = "s0"
        expected_uuid = str(
            uuid.uuid5(CHUNK_UUID_NAMESPACE, f"{parent_uid}:{chunk_id}")
        )

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
            meta={"chunker_version": "v1.0.0"},
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
                chunk_id=cid,
                uuid=uuid_val,
                parent_uid=parent_uid,
                source="pubmed",
                chunk_idx=0,
                text="test",
            )

        # Invalid chunk IDs
        for cid in ["invalid", "s", "1", "x0"]:
            with pytest.raises(ValueError, match="chunk_id must follow format"):
                uuid_val = Chunk.generate_uuid(parent_uid, cid)
                Chunk(
                    chunk_id=cid,
                    uuid=uuid_val,
                    parent_uid=parent_uid,
                    source="pubmed",
                    chunk_idx=0,
                    text="test",
                )

    def test_uuid_consistency_validation(self):
        """Test UUID consistency validation."""
        parent_uid = "pubmed:123"
        chunk_id = "s0"
        wrong_uuid = "00000000-0000-0000-0000-000000000000"

        # Should fail with wrong UUID
        with pytest.raises(ValueError, match="UUID .* doesn't match expected"):
            Chunk(
                chunk_id=chunk_id,
                uuid=wrong_uuid,
                parent_uid=parent_uid,
                source="pubmed",
                chunk_idx=0,
                text="test",
            )


class TestMetadataBuilder:
    """Test metadata building utilities."""

    def test_build_chunk_metadata(self):
        """Test chunk metadata building."""
        metadata = MetadataBuilder.build_chunk_metadata(
            chunker_version="v1.2.0",
            tokenizer="hf:pritamdeka/BioBERT",
            source_specific={"mesh_terms": ["test"], "journal": "Nature"},
            source="pubmed",
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
            published_at=datetime(2024, 1, 15),
        )

        fields = MetadataBuilder.extract_top_level_fields(doc)

        assert fields["parent_uid"] == "pubmed:123"
        assert fields["source"] == "pubmed"
        assert fields["title"] == "Test"
        assert fields["year"] == 2024
