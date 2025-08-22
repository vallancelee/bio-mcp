"""
Unit tests for NormalizedDocument database model.

Tests the new normalized documents table for multi-source metadata storage.
"""

from datetime import UTC, datetime

import pytest  # noqa: F401 - may be used by test framework

from bio_mcp.models.document import Document
from bio_mcp.shared.models.database_models import NormalizedDocument


class TestNormalizedDocument:
    """Test the NormalizedDocument database model."""

    def test_from_document_conversion(self):
        """Test creating NormalizedDocument from Document model."""
        # Create a Document instance
        doc = Document(
            uid="pubmed:12345678",
            source="pubmed",
            source_id="12345678",
            title="Test Document for Database Storage",
            text="This is the abstract content for testing.",
            published_at=datetime(2023, 6, 15, tzinfo=UTC),
            authors=["Smith, John A", "Johnson, Mary"],
            identifiers={"doi": "10.1000/test.doi"},
            provenance={"test": True},
            detail={"journal": "Test Journal"}
        )

        # Convert to database record
        s3_uri = "s3://bucket/test/12345678.json"
        content_hash = "abc123def456"
        
        normalized_doc = NormalizedDocument.from_document(
            document=doc,
            s3_raw_uri=s3_uri,
            content_hash=content_hash
        )

        # Verify conversion
        assert normalized_doc.uid == "pubmed:12345678"
        assert normalized_doc.source == "pubmed"
        assert normalized_doc.source_id == "12345678"
        assert normalized_doc.title == "Test Document for Database Storage"
        assert normalized_doc.published_at == datetime(2023, 6, 15, tzinfo=UTC)
        assert normalized_doc.s3_raw_uri == s3_uri
        assert normalized_doc.content_hash == content_hash

    def test_to_document_dict_conversion(self):
        """Test converting database record to dictionary."""
        # Create a NormalizedDocument instance
        normalized_doc = NormalizedDocument(
            uid="pubmed:87654321",
            source="pubmed",
            source_id="87654321",
            title="Database Record Test",
            published_at=datetime(2023, 8, 22, tzinfo=UTC),
            s3_raw_uri="s3://bucket/test/87654321.json",
            content_hash="xyz789uvw012",
        )

        # Convert to dictionary
        doc_dict = normalized_doc.to_document_dict()

        # Verify dictionary structure
        assert doc_dict["uid"] == "pubmed:87654321"
        assert doc_dict["source"] == "pubmed"
        assert doc_dict["source_id"] == "87654321"
        assert doc_dict["title"] == "Database Record Test"
        assert doc_dict["published_at"] == "2023-08-22T00:00:00+00:00"
        assert doc_dict["s3_raw_uri"] == "s3://bucket/test/87654321.json"
        assert doc_dict["content_hash"] == "xyz789uvw012"
        assert "created_at" in doc_dict

    def test_none_published_at_handling(self):
        """Test handling of None published_at field."""
        normalized_doc = NormalizedDocument(
            uid="pubmed:99999999",
            source="pubmed",
            source_id="99999999",
            title="No Publication Date",
            published_at=None,  # No publication date
            s3_raw_uri="s3://bucket/test/99999999.json",
            content_hash="nodate123",
        )

        doc_dict = normalized_doc.to_document_dict()
        assert doc_dict["published_at"] is None

    def test_none_title_handling(self):
        """Test handling of None title field."""
        normalized_doc = NormalizedDocument(
            uid="pubmed:88888888",
            source="pubmed",
            source_id="88888888",
            title=None,  # No title
            published_at=datetime(2023, 1, 1, tzinfo=UTC),
            s3_raw_uri="s3://bucket/test/88888888.json",
            content_hash="notitle456",
        )

        doc_dict = normalized_doc.to_document_dict()
        assert doc_dict["title"] is None

    def test_multi_source_support(self):
        """Test that the model supports different sources."""
        # Test with a different source (not PubMed)
        doc = Document(
            uid="clinicaltrials:NCT01234567",
            source="clinicaltrials",
            source_id="NCT01234567",
            title="Clinical Trial Study",
            text="This is a clinical trial description.",
            published_at=datetime(2022, 12, 1, tzinfo=UTC),
            authors=["Research Team"],
            identifiers={"nct_id": "NCT01234567"},
            provenance={"clinical_trials_gov": True},
            detail={"phase": "Phase III"}
        )

        normalized_doc = NormalizedDocument.from_document(
            document=doc,
            s3_raw_uri="s3://bucket/clinical/NCT01234567.json",
            content_hash="clinical123"
        )

        # Verify multi-source support
        assert normalized_doc.uid == "clinicaltrials:NCT01234567"
        assert normalized_doc.source == "clinicaltrials"
        assert normalized_doc.source_id == "NCT01234567"
        assert normalized_doc.title == "Clinical Trial Study"

        doc_dict = normalized_doc.to_document_dict()
        assert doc_dict["source"] == "clinicaltrials"
        assert doc_dict["uid"] == "clinicaltrials:NCT01234567"