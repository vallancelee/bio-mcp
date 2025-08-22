"""
Unit tests for PubMed document normalizer.

Tests cover:
- Normalization from various PubMed data formats
- Edge cases and error handling
- Field mapping and validation
- Date parsing and author extraction
- Detail field construction
"""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest

from bio_mcp.models.document import Document
from bio_mcp.services.normalization.pubmed import PubMedNormalizer, to_document


class TestPubMedNormalizer:
    """Test the PubMedNormalizer class."""

    def test_minimal_document_normalization(self):
        """Test normalizing a document with minimal required fields."""
        raw_data = {
            "pmid": "12345678",
            "title": "Minimal Test Document",
            "abstract": "This is a test abstract.",
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data,
            s3_raw_uri="s3://bucket/pubmed/12345678.json",
            content_hash="abc123",
        )

        assert doc.uid == "pubmed:12345678"
        assert doc.source == "pubmed"
        assert doc.source_id == "12345678"
        assert doc.title == "Minimal Test Document"
        assert doc.text == "This is a test abstract."
        assert doc.authors is None
        assert doc.identifiers == {}
        assert doc.provenance["s3_raw_uri"] == "s3://bucket/pubmed/12345678.json"
        assert doc.provenance["content_hash"] == "abc123"
        assert doc.detail == {}

    def test_full_document_normalization(self):
        """Test normalizing a document with all fields populated."""
        raw_data = {
            "pmid": "98765432",
            "title": "CRISPR-Cas9 Gene Editing in Cancer Research",
            "abstract": "This comprehensive study investigates the application of CRISPR-Cas9 gene editing technology in cancer treatment approaches.",
            "authors": ["Smith, John A", "Johnson, Mary K", "Williams, Robert"],
            "journal": "Nature Biotechnology",
            "publication_date": "2023-06-15",
            "doi": "10.1038/nbt.2023.001",
            "keywords": ["CRISPR", "gene editing", "cancer", "therapy"],
            "mesh_terms": [
                "Gene Editing",
                "CRISPR-Cas Systems",
                "Neoplasms",
                "Gene Therapy",
            ],
            "language": "eng",
            "impact_factor": 54.908,
            "citation_count": 127,
            "affiliations": ["Harvard Medical School", "Stanford University"],
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data,
            s3_raw_uri="s3://bucket/pubmed/98765432.json",
            content_hash="def456",
        )

        assert doc.uid == "pubmed:98765432"
        assert doc.title == "CRISPR-Cas9 Gene Editing in Cancer Research"
        assert "CRISPR-Cas9 gene editing technology" in doc.text
        assert doc.authors == ["Smith, John A", "Johnson, Mary K", "Williams, Robert"]
        assert doc.identifiers["doi"] == "10.1038/nbt.2023.001"
        assert doc.language == "en"

        # Check detail fields
        assert doc.detail["journal"] == "Nature Biotechnology"
        assert "CRISPR" in doc.detail["keywords"]
        assert "Gene Editing" in doc.detail["mesh_terms"]
        assert doc.detail["impact_factor"] == 54.908
        assert doc.detail["citation_count"] == 127
        assert "Harvard Medical School" in doc.detail["affiliations"]

        # Check provenance
        assert doc.provenance["s3_raw_uri"] == "s3://bucket/pubmed/98765432.json"
        assert doc.provenance["content_hash"] == "def456"
        assert "normalized_at" in doc.provenance
        assert doc.provenance["normalizer_version"] == "1.0"

    def test_missing_pmid_error(self):
        """Test that missing PMID raises ValueError."""
        raw_data = {
            "title": "Document without PMID",
            "abstract": "This document is missing PMID.",
        }

        with pytest.raises(ValueError, match="PMID is required"):
            PubMedNormalizer.from_raw_dict(
                raw_data, s3_raw_uri="s3://bucket/test.json", content_hash="test123"
            )

    def test_empty_pmid_error(self):
        """Test that empty PMID raises ValueError."""
        raw_data = {
            "pmid": "",
            "title": "Document with empty PMID",
            "abstract": "This document has empty PMID.",
        }

        with pytest.raises(ValueError, match="PMID is required"):
            PubMedNormalizer.from_raw_dict(
                raw_data, s3_raw_uri="s3://bucket/test.json", content_hash="test123"
            )

    def test_no_abstract_uses_title_as_text(self):
        """Test that documents without abstract use title as text."""
        raw_data = {
            "pmid": "11111111",
            "title": "Title Only Document",
            # No abstract field
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data, s3_raw_uri="s3://bucket/11111111.json", content_hash="title123"
        )

        assert doc.title == "Title Only Document"
        assert doc.text == "Title Only Document"

    def test_no_title_or_abstract(self):
        """Test document with neither title nor abstract."""
        raw_data = {
            "pmid": "22222222"
            # No title or abstract
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data, s3_raw_uri="s3://bucket/22222222.json", content_hash="empty123"
        )

        assert doc.title is None
        assert doc.text == ""

    def test_case_insensitive_field_mapping(self):
        """Test that field mapping works with different case conventions."""
        raw_data = {
            "PMID": "33333333",  # Uppercase
            "Title": "Case Test Document",  # Title case
            "Abstract": "Testing case insensitive mapping.",  # Title case
            "DOI": "10.1000/test.case.001",  # Uppercase
            "Authors": ["Test, Author"],  # Title case
            "Language": "English",  # Full word
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data, s3_raw_uri="s3://bucket/33333333.json", content_hash="case123"
        )

        assert doc.uid == "pubmed:33333333"
        assert doc.title == "Case Test Document"
        assert doc.text == "Testing case insensitive mapping."
        assert doc.identifiers["doi"] == "10.1000/test.case.001"
        assert doc.authors == ["Test, Author"]
        assert doc.language == "en"  # Normalized to ISO code

    def test_publication_date_parsing(self):
        """Test various publication date formats."""
        test_cases = [
            # (input, expected_year, expected_month, expected_day)
            ("2023-06-15", 2023, 6, 15),
            ("2023-06", 2023, 6, 1),
            ("2023", 2023, 1, 1),
            ("2023/06/15", 2023, 6, 15),
            ("06/15/2023", 2023, 6, 15),
            ("15/06/2023", 2023, 6, 15),
            (date(2023, 6, 15), 2023, 6, 15),
            (datetime(2023, 6, 15, 12, 30, 45), 2023, 6, 15),
        ]

        for date_input, exp_year, exp_month, exp_day in test_cases:
            raw_data = {
                "pmid": "44444444",
                "title": "Date Test",
                "abstract": "Testing date parsing",
                "publication_date": date_input,
            }

            doc = PubMedNormalizer.from_raw_dict(
                raw_data, s3_raw_uri="s3://bucket/44444444.json", content_hash="date123"
            )

            assert doc.published_at is not None
            assert doc.published_at.year == exp_year
            assert doc.published_at.month == exp_month
            assert doc.published_at.day == exp_day
            assert doc.published_at.tzinfo == UTC

    def test_invalid_publication_date(self):
        """Test handling of invalid publication dates."""
        raw_data = {
            "pmid": "55555555",
            "title": "Invalid Date Test",
            "abstract": "Testing invalid date handling",
            "publication_date": "not-a-date",
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data, s3_raw_uri="s3://bucket/55555555.json", content_hash="invalid123"
        )

        assert doc.published_at is None

    def test_author_list_parsing(self):
        """Test various author list formats."""
        # Test list of strings
        raw_data1 = {
            "pmid": "66666666",
            "title": "Author Test 1",
            "abstract": "Testing author parsing",
            "authors": ["Smith, John A", "Johnson, Mary", "Williams, Robert B"],
        }

        doc1 = PubMedNormalizer.from_raw_dict(
            raw_data1, s3_raw_uri="s3://bucket/66666666.json", content_hash="auth123"
        )

        assert doc1.authors == ["Smith, John A", "Johnson, Mary", "Williams, Robert B"]

        # Test comma-separated string
        raw_data2 = {
            "pmid": "77777777",
            "title": "Author Test 2",
            "abstract": "Testing author parsing",
            "authors": "Smith, John A, Johnson, Mary, Williams, Robert B",
        }

        doc2 = PubMedNormalizer.from_raw_dict(
            raw_data2, s3_raw_uri="s3://bucket/77777777.json", content_hash="auth456"
        )

        assert doc2.authors == ["Smith, John A", "Johnson, Mary", "Williams, Robert B"]

        # Test structured author data
        raw_data3 = {
            "pmid": "88888888",
            "title": "Author Test 3",
            "abstract": "Testing structured authors",
            "authors": [
                {"LastName": "Smith", "ForeName": "John", "Initials": "JA"},
                {"LastName": "Johnson", "Initials": "M"},
                {"LastName": "Williams", "ForeName": "Robert"},
            ],
        }

        doc3 = PubMedNormalizer.from_raw_dict(
            raw_data3, s3_raw_uri="s3://bucket/88888888.json", content_hash="auth789"
        )

        expected_authors = ["Smith John", "Johnson M", "Williams Robert"]
        assert doc3.authors == expected_authors

    def test_identifier_extraction(self):
        """Test extraction of various identifiers."""
        raw_data = {
            "pmid": "99999999",
            "title": "Identifier Test",
            "abstract": "Testing identifier extraction",
            "doi": "10.1038/nature.2023.001",
            "pmc_id": "PMC8765432",
            "PMC": "8765433",  # Alternative PMC format
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data, s3_raw_uri="s3://bucket/99999999.json", content_hash="id123"
        )

        assert doc.identifiers["doi"] == "10.1038/nature.2023.001"
        assert doc.identifiers["pmc"] == "PMC8765432"

    def test_pmc_id_normalization(self):
        """Test PMC ID normalization (adding PMC prefix if missing)."""
        raw_data = {
            "pmid": "10101010",
            "title": "PMC Test",
            "abstract": "Testing PMC normalization",
            "pmc_id": "1234567",  # Missing PMC prefix
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data, s3_raw_uri="s3://bucket/10101010.json", content_hash="pmc123"
        )

        assert doc.identifiers["pmc"] == "PMC1234567"

    def test_detail_fields_construction(self):
        """Test construction of PubMed-specific detail fields."""
        raw_data = {
            "pmid": "11223344",
            "title": "Detail Fields Test",
            "abstract": "Testing detail field construction",
            "journal": "Nature Medicine",
            "mesh_terms": ["Gene Therapy", "CRISPR Systems"],
            "keywords": "gene editing, crispr, cancer",  # String format
            "publication_types": ["Journal Article", "Research Support"],
            "impact_factor": "54.908",  # String that should convert to float
            "citation_count": "127",  # String that should convert to int
            "abstract_sections": {
                "Background": "Background text here",
                "Methods": "Methods text here",
            },
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data, s3_raw_uri="s3://bucket/11223344.json", content_hash="detail123"
        )

        assert doc.detail["journal"] == "Nature Medicine"
        assert doc.detail["mesh_terms"] == ["Gene Therapy", "CRISPR Systems"]
        assert doc.detail["keywords"] == ["gene editing", "crispr", "cancer"]
        assert doc.detail["publication_types"] == [
            "Journal Article",
            "Research Support",
        ]
        assert doc.detail["impact_factor"] == 54.908
        assert doc.detail["citation_count"] == 127
        assert doc.detail["abstract_sections"]["Background"] == "Background text here"

    def test_from_dataclass_conversion(self):
        """Test conversion from PubMedDocument dataclass."""
        # Create a mock dataclass object
        mock_pubmed_doc = MagicMock()
        mock_pubmed_doc.pmid = "12121212"
        mock_pubmed_doc.title = "Dataclass Test"
        mock_pubmed_doc.abstract = "Testing dataclass conversion"
        mock_pubmed_doc.authors = ["Test, Author"]
        mock_pubmed_doc.journal = "Test Journal"
        mock_pubmed_doc.doi = "10.1000/test.dataclass"
        mock_pubmed_doc.keywords = ["test", "dataclass"]
        mock_pubmed_doc.mesh_terms = ["Testing"]

        doc = PubMedNormalizer.from_dataclass(
            mock_pubmed_doc,
            s3_raw_uri="s3://bucket/12121212.json",
            content_hash="dataclass123",
        )

        assert doc.uid == "pubmed:12121212"
        assert doc.title == "Dataclass Test"
        assert doc.text == "Testing dataclass conversion"
        assert doc.authors == ["Test, Author"]
        assert doc.identifiers["doi"] == "10.1000/test.dataclass"
        assert doc.detail["journal"] == "Test Journal"

    def test_convenience_function(self):
        """Test the to_document convenience function."""
        raw_data = {
            "pmid": "13131313",
            "title": "Convenience Function Test",
            "abstract": "Testing the convenience function",
        }

        doc = to_document(
            raw_data, s3_raw_uri="s3://bucket/13131313.json", content_hash="conv123"
        )

        assert isinstance(doc, Document)
        assert doc.uid == "pubmed:13131313"
        assert doc.title == "Convenience Function Test"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_unicode_content(self):
        """Test handling of Unicode content."""
        raw_data = {
            "pmid": "unicode123",
            "title": "研究论文: Gene Expression in 中文 🧬",
            "abstract": "This study examines ΔFosB protein μg/ml concentrations.",
            "authors": ["José García-López", "李明", "Müller, Hans"],
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data,
            s3_raw_uri="s3://bucket/unicode123.json",
            content_hash="unicode456",
        )

        assert "研究论文" in doc.title
        assert "🧬" in doc.title
        assert "ΔFosB" in doc.text
        assert "José García-López" in doc.authors

    def test_very_long_content(self):
        """Test handling of very long content."""
        long_abstract = "A" * 100000  # 100k character abstract

        raw_data = {
            "pmid": "long123",
            "title": "Very Long Document",
            "abstract": long_abstract,
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data, s3_raw_uri="s3://bucket/long123.json", content_hash="long456"
        )

        assert len(doc.text) == 100000
        assert doc.text == long_abstract

    def test_empty_string_fields(self):
        """Test handling of empty string fields."""
        raw_data = {
            "pmid": "empty123",
            "title": "",  # Empty title
            "abstract": "   ",  # Whitespace-only abstract
            "authors": ["", "  ", "Valid Author"],  # Mixed empty/valid authors
            "doi": "  ",  # Whitespace-only DOI
            "journal": "",  # Empty journal
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data, s3_raw_uri="s3://bucket/empty123.json", content_hash="empty456"
        )

        assert doc.title is None  # Empty string becomes None
        assert doc.text == ""  # Whitespace-only becomes empty
        assert doc.authors == ["Valid Author"]  # Empty authors filtered out
        assert "doi" not in doc.identifiers  # Empty DOI not included
        assert "journal" not in doc.detail  # Empty journal not included

    def test_null_and_none_values(self):
        """Test handling of null/None values."""
        raw_data = {
            "pmid": "null123",
            "title": "Null Test",
            "abstract": "Testing null handling",
            "authors": None,
            "journal": None,
            "doi": None,
            "keywords": None,
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data, s3_raw_uri="s3://bucket/null123.json", content_hash="null456"
        )

        assert doc.authors is None
        assert "journal" not in doc.detail
        assert "doi" not in doc.identifiers
        assert "keywords" not in doc.detail

    def test_malformed_data_types(self):
        """Test handling of malformed data types."""
        raw_data = {
            "pmid": 123456,  # Integer instead of string
            "title": "Type Test",
            "abstract": "Testing type handling",
            "authors": "Single Author String",  # String instead of list
            "keywords": 12345,  # Invalid type for keywords
            "impact_factor": "not-a-number",  # Invalid number
        }

        doc = PubMedNormalizer.from_raw_dict(
            raw_data, s3_raw_uri="s3://bucket/123456.json", content_hash="type456"
        )

        assert doc.source_id == "123456"  # Integer converted to string
        assert doc.authors == ["Single Author String"]  # String converted to list
        assert "keywords" not in doc.detail  # Invalid keywords ignored
        assert "impact_factor" not in doc.detail  # Invalid number ignored
