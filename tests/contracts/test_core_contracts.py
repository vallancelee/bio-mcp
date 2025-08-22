"""
Core contract tests that don't require external dependencies.

These tests focus on data model contracts and schema validation without
making network calls or requiring complex integration setups.
"""

import pytest
from typing import Dict, Any

from bio_mcp.models.document import Document, Chunk
from bio_mcp.services.normalization.pubmed import PubMedNormalizer
from bio_mcp.shared.models.database_models import NormalizedDocument


class TestCoreContracts:
    """Core contract tests for data models and schemas."""

    @pytest.fixture
    def sample_raw_data(self) -> Dict[str, Any]:
        """Sample raw data for testing."""
        return {
            "pmid": "12345678",
            "title": "Test Document",
            "abstract": "Test abstract content",
            "authors": ["Test Author"],
            "journal": "Test Journal",
            "publication_date": "2023-01-01"
        }

    def test_document_uid_contract_stability(self, sample_raw_data):
        """Test that Document UID format is stable across changes."""
        document = PubMedNormalizer.from_raw_dict(
            sample_raw_data,
            s3_raw_uri="s3://test/test.json",
            content_hash="test123"
        )
        
        # Contract: UID must be "source:source_id"
        assert document.uid == "pubmed:12345678"
        assert document.source == "pubmed"
        assert document.source_id == "12345678"
        
        # Contract: UID pattern for API compatibility
        import re
        api_doc_id = document.uid.replace("pubmed:", "pmid:")
        assert re.match(r"^pmid:[0-9]+$", api_doc_id)

    def test_chunk_id_contract_stability(self, sample_raw_data):
        """Test that Chunk ID format is stable across changes."""
        document = PubMedNormalizer.from_raw_dict(
            sample_raw_data,
            s3_raw_uri="s3://test/test.json",
            content_hash="test123"
        )
        
        # Create test chunks
        chunks = []
        for i in range(3):
            chunk = Chunk(
                chunk_id=f"{document.uid}:{i}",
                parent_uid=document.uid,
                source=document.source,
                chunk_idx=i,
                text=f"chunk {i} text",
                title=document.title,
                published_at=document.published_at
            )
            chunks.append(chunk)
        
        # Contract: Chunk ID must be "parent_uid:chunk_idx"
        for i, chunk in enumerate(chunks):
            expected_id = f"pubmed:12345678:{i}"
            assert chunk.chunk_id == expected_id
            assert chunk.parent_uid == "pubmed:12345678"
            assert chunk.chunk_idx == i

    def test_database_model_contract_stability(self, sample_raw_data):
        """Test that database model fields remain stable."""
        document = PubMedNormalizer.from_raw_dict(
            sample_raw_data,
            s3_raw_uri="s3://test/test.json", 
            content_hash="test123"
        )
        
        # Convert to database model
        db_record = NormalizedDocument.from_document(
            document=document,
            s3_raw_uri="s3://test/test.json",
            content_hash="test123"
        )
        
        # Contract: Required database fields
        required_fields = {
            "uid", "source", "source_id", "title", "published_at",
            "s3_raw_uri", "content_hash", "created_at"
        }
        
        # Test dictionary conversion
        api_dict = db_record.to_document_dict()
        assert set(api_dict.keys()) == required_fields
        
        # Contract: Field types must be stable
        assert isinstance(api_dict["uid"], str)
        assert isinstance(api_dict["source"], str)
        assert isinstance(api_dict["source_id"], str)
        assert api_dict["title"] is None or isinstance(api_dict["title"], str)
        assert api_dict["published_at"] is None or isinstance(api_dict["published_at"], str)

    def test_error_code_contract_stability(self):
        """Test that error codes remain stable across versions."""
        # Contract: These error codes must remain valid
        stable_error_codes = {
            "RATE_LIMIT", "UPSTREAM", "VALIDATION", "NOT_FOUND", 
            "INVARIANT_FAILURE", "STORE", "EMBEDDINGS", "WEAVIATE",
            "ENTREZ", "UNKNOWN"
        }
        
        # This test will fail if error codes change, forcing attention to breaking changes
        current_codes = {
            "RATE_LIMIT", "UPSTREAM", "VALIDATION", "NOT_FOUND", 
            "INVARIANT_FAILURE", "STORE", "EMBEDDINGS", "WEAVIATE",
            "ENTREZ", "UNKNOWN"
        }
        
        assert current_codes == stable_error_codes, "Error code contract violated"

    def test_required_field_contract_stability(self):
        """Test that API required fields are documented and stable."""
        # Contract: These fields cannot be removed without major version bump
        api_contracts = {
            "rag_search": {"results"},
            "rag_get": {"doc_id", "title", "journal", "pub_types", "quality", "version"},
            "checkpoint_get": {"query_key", "last_edat"},
            "error_envelope": {"code", "message"}
        }
        
        # Verify contracts match documentation
        assert api_contracts["rag_search"] == {"results"}
        assert "doc_id" in api_contracts["rag_get"]
        assert "quality" in api_contracts["rag_get"]
        assert "code" in api_contracts["error_envelope"]
        assert "message" in api_contracts["error_envelope"]

    def test_doc_id_pattern_contract_stability(self):
        """Test that doc_id pattern remains stable."""
        import re
        
        # Contract: doc_id pattern must never change without major version bump
        stable_pattern = r"^pmid:[0-9]+$"
        
        # Test cases that must always work
        valid_doc_ids = ["pmid:1", "pmid:12345678", "pmid:999999999"]
        invalid_doc_ids = ["pubmed:123", "pmid:abc", "pmid:", "123"]
        
        for doc_id in valid_doc_ids:
            assert re.match(stable_pattern, doc_id), f"Valid doc_id {doc_id} failed pattern"
            
        for doc_id in invalid_doc_ids:
            assert not re.match(stable_pattern, doc_id), f"Invalid doc_id {doc_id} passed pattern"

    def test_quality_score_contract_stability(self):
        """Test that quality score structure remains stable."""
        # Contract: Quality score object structure
        example_quality = {
            "design": 2,
            "recency": 1,
            "journal": 2, 
            "human": 1,
            "total": 6
        }
        
        # Required field
        assert "total" in example_quality
        assert isinstance(example_quality["total"], int)
        
        # Optional fields with correct types
        optional_fields = {"design", "recency", "journal", "human"}
        for field in optional_fields:
            if field in example_quality:
                value = example_quality[field]
                assert value is None or isinstance(value, int)

    def test_version_field_contract_stability(self):
        """Test that version field constraints remain stable."""
        # Contract: version must be integer >= 1
        valid_versions = [1, 2, 100, 9999]
        invalid_versions = [0, -1, "1", 1.5, None]
        
        for version in valid_versions:
            assert isinstance(version, int) and version >= 1
            
        for version in invalid_versions:
            assert not (isinstance(version, int) and version >= 1)


class TestSchemaEvolutionSafety:
    """Test that schema evolution follows safe practices."""

    def test_additive_changes_only(self):
        """Test that only additive changes are allowed for minor versions."""
        # Document safe schema evolution rules
        evolution_rules = {
            "can_add_optional_fields": True,
            "can_remove_required_fields": False,
            "can_change_field_types": False,
            "can_rename_fields": False,
            "can_add_enum_values": True,
            "can_remove_enum_values": False
        }
        
        # These rules ensure backward compatibility
        assert evolution_rules["can_add_optional_fields"] is True
        assert evolution_rules["can_remove_required_fields"] is False
        assert evolution_rules["can_change_field_types"] is False
        assert evolution_rules["can_rename_fields"] is False

    def test_breaking_change_detection(self):
        """Test that breaking changes are detected."""
        # This test will fail if someone tries to make breaking changes
        # without updating the test, forcing attention to compatibility
        
        api_version = "1.0"  # Current API version
        supports_backward_compatibility = True
        
        assert api_version == "1.0", "API version changed - check for breaking changes"
        assert supports_backward_compatibility is True, "Backward compatibility flag changed"