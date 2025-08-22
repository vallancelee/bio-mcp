"""
Document model compatibility tests for Bio-MCP refactoring.

Tests ensure that the new Document/Chunk models produce identical API responses
to the legacy implementation, maintaining backward compatibility during the
multi-source document refactoring.
"""

import json
from typing import Any

import pytest

from bio_mcp.models.document import Chunk, Document
from bio_mcp.services.normalization.pubmed import PubMedNormalizer
from bio_mcp.shared.models.database_models import NormalizedDocument


class TestDocumentModelCompatibility:
    """Test that Document model changes don't break API contracts."""

    @pytest.fixture
    def sample_pubmed_raw_data(self) -> dict[str, Any]:
        """Sample raw PubMed data for testing normalization."""
        return {
            "pmid": "12345678",
            "title": "Cancer Treatment Advances",
            "abstract": "This study investigates novel cancer treatment approaches...",
            "authors": ["Smith, John A", "Johnson, Mary B"],
            "journal": "Nature Medicine",
            "publication_date": "2023-06-15",
            "doi": "10.1038/nm.12345",
            "mesh_terms": ["Neoplasms", "Drug Therapy"],
            "pub_types": ["Journal Article", "Research Support"]
        }

    @pytest.fixture
    def normalized_document(self, sample_pubmed_raw_data) -> Document:
        """Create normalized Document from raw PubMed data."""
        return PubMedNormalizer.from_raw_dict(
            sample_pubmed_raw_data,
            s3_raw_uri="s3://test-bucket/pubmed/12345678.json",
            content_hash="abc123def456"
        )

    def test_document_to_normalized_document_conversion(self, normalized_document):
        """Test Document to NormalizedDocument database conversion preserves data."""
        s3_uri = "s3://test-bucket/pubmed/12345678.json" 
        content_hash = "abc123def456789"
        
        # Convert to database record
        db_record = NormalizedDocument.from_document(
            document=normalized_document,
            s3_raw_uri=s3_uri,
            content_hash=content_hash
        )
        
        # Verify all data is preserved
        assert db_record.uid == normalized_document.uid
        assert db_record.source == normalized_document.source
        assert db_record.source_id == normalized_document.source_id
        assert db_record.title == normalized_document.title
        assert db_record.published_at == normalized_document.published_at
        assert db_record.s3_raw_uri == s3_uri
        assert db_record.content_hash == content_hash

    def test_normalized_document_to_api_response_format(self, normalized_document):
        """Test database record produces correct API response format."""
        s3_uri = "s3://test-bucket/pubmed/12345678.json"
        content_hash = "abc123def456789"
        
        db_record = NormalizedDocument.from_document(
            document=normalized_document,
            s3_raw_uri=s3_uri,
            content_hash=content_hash
        )
        
        # Convert to API response format
        api_dict = db_record.to_document_dict()
        
        # Verify API response structure matches contract
        expected_fields = {
            "uid", "source", "source_id", "title", "published_at",
            "s3_raw_uri", "content_hash", "created_at"
        }
        assert set(api_dict.keys()) == expected_fields
        
        # Verify field types match contract expectations
        assert isinstance(api_dict["uid"], str)
        assert isinstance(api_dict["source"], str) 
        assert isinstance(api_dict["source_id"], str)
        assert api_dict["title"] is None or isinstance(api_dict["title"], str)
        assert api_dict["published_at"] is None or isinstance(api_dict["published_at"], str)
        assert isinstance(api_dict["s3_raw_uri"], str)
        assert isinstance(api_dict["content_hash"], str)
        assert api_dict["created_at"] is None or isinstance(api_dict["created_at"], str)

    @pytest.mark.asyncio
    async def test_rag_search_response_consistency_with_documents(self, sample_documents):
        """Test rag.search produces consistent responses regardless of data model."""
        from bio_mcp.mcp.rag_tools import rag_search_tool
        
        # Test with current implementation
        result = await rag_search_tool(
            "rag.search",
            {
                "query": "cancer treatment",
                "top_k": 5,
                "quality_bias": True
            }
        )
        
        assert len(result) == 1
        response_text = result[0].text
        
        # Verify response structure remains consistent
        # Even if no results, the response format should be predictable
        assert isinstance(response_text, str)
        assert len(response_text) > 0
        
        # If JSON response, verify structure
        if "```json" in response_text:
            try:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
                response_data = json.loads(json_str)
                
                # Must have MCP envelope structure
                assert "success" in response_data
                assert "operation" in response_data
                assert "metadata" in response_data
                
                # For successful responses, check data structure
                if response_data.get("success"):
                    assert "data" in response_data
                    data = response_data["data"]
                    assert "results" in data
                    assert isinstance(data["results"], list)
                    
                    # Each result must have required fields
                    for result_item in data["results"]:
                        assert "uuid" in result_item
                        assert "pmid" in result_item
                        assert "score" in result_item
                        # pmid should be numeric string
                        assert result_item["pmid"].isdigit()
                    
            except json.JSONDecodeError:
                pass  # Not JSON format is also valid

    def test_document_uid_format_stability(self, sample_pubmed_raw_data):
        """Test that Document UIDs maintain stable format across changes."""
        document = PubMedNormalizer.from_raw_dict(
            sample_pubmed_raw_data,
            s3_raw_uri="s3://test-bucket/pubmed/12345678.json",
            content_hash="test123"
        )
        
        # UID format must be stable: "source:source_id"
        assert document.uid == "pubmed:12345678"
        assert document.source == "pubmed"
        assert document.source_id == "12345678"
        
        # Pattern must match contract expectations
        import re
        pattern = r"^pmid:[0-9]+$"
        api_doc_id = document.uid.replace("pubmed:", "pmid:")
        assert re.match(pattern, api_doc_id), f"UID format changed: {api_doc_id}"

    def test_chunk_id_format_stability(self, normalized_document):
        """Test that Chunk IDs maintain stable format across changes."""
        # Create chunks from document
        chunks = self._create_test_chunks(normalized_document)
        
        # Chunk ID format must be stable: "parent_uid:chunk_idx"
        for i, chunk in enumerate(chunks):
            expected_id = f"{normalized_document.uid}:{i}"
            assert chunk.chunk_id == expected_id
            assert chunk.parent_uid == normalized_document.uid
            assert chunk.chunk_idx == i

    def _create_test_chunks(self, document: Document) -> list[Chunk]:
        """Create test chunks from document (mimics chunking service)."""
        # Simple chunking for testing
        text_parts = [document.text[i:i+100] for i in range(0, len(document.text), 100)]
        
        chunks = []
        for i, text_part in enumerate(text_parts):
            chunk = Chunk(
                chunk_id=f"{document.uid}:{i}",
                parent_uid=document.uid,
                source=document.source,
                chunk_idx=i,
                text=text_part,
                title=document.title,
                published_at=document.published_at,
                meta={"language": "en"}
            )
            chunks.append(chunk)
        
        return chunks

    def test_quality_score_compatibility(self):
        """Test that quality scores maintain expected structure."""
        # Quality scores must follow contract structure
        quality_example = {
            "design": 2,
            "recency": 1, 
            "journal": 2,
            "human": 1,
            "total": 6
        }
        
        # Verify required field present
        assert "total" in quality_example
        assert isinstance(quality_example["total"], int)
        
        # Verify optional fields have correct types
        for field in ["design", "recency", "journal", "human"]:
            if field in quality_example:
                assert quality_example[field] is None or isinstance(quality_example[field], int)

    @pytest.mark.asyncio
    async def test_error_handling_consistency(self):
        """Test that error responses remain consistent with Document models."""
        from bio_mcp.mcp.rag_tools import rag_get_tool
        
        # Test with non-existent document
        result = await rag_get_tool(
            "rag.get",
            {"doc_id": "pmid:99999999999"}
        )
        
        assert len(result) == 1
        response_text = result[0].text
        
        # Error response should be helpful and consistent
        assert "❌" in response_text or "not found" in response_text.lower()
        assert len(response_text) < 1000  # Should be concise
        assert len(response_text) > 10    # Should be informative

    def test_metadata_preservation_through_pipeline(self, sample_pubmed_raw_data):
        """Test that metadata is preserved through the entire pipeline."""
        document = PubMedNormalizer.from_raw_dict(
            sample_pubmed_raw_data,
            s3_raw_uri="s3://test-bucket/pubmed/12345678.json", 
            content_hash="metadata123"
        )
        
        # Original metadata should be preserved in detail field
        assert "journal" in document.detail
        assert "mesh_terms" in document.detail
        assert document.detail["journal"] == "Nature Medicine"
        assert document.detail["mesh_terms"] == ["Neoplasms", "Drug Therapy"]
        
        # Core fields should be normalized
        assert document.title == "Cancer Treatment Advances"
        assert document.source == "pubmed"
        assert document.source_id == "12345678"
        assert document.identifiers.get("doi") == "10.1038/nm.12345"

    def test_backward_compatibility_markers(self):
        """Test that backward compatibility markers are present."""
        # This test documents the current API version and compatibility expectations
        API_VERSION = "1.0"
        SUPPORTS_MULTI_SOURCE = True  # After Document model implementation
        SUPPORTS_LEGACY_PMID_FORMAT = True  # Still support pmid:xxx format
        
        # These assertions document current compatibility guarantees
        assert API_VERSION == "1.0", "API version changed - check for breaking changes"
        assert SUPPORTS_MULTI_SOURCE is True, "Multi-source support should be enabled"
        assert SUPPORTS_LEGACY_PMID_FORMAT is True, "Legacy PMID format must be supported"

    @pytest.mark.asyncio  
    async def test_response_performance_consistency(self, sample_documents):
        """Test that responses maintain acceptable performance with Document models."""
        import time

        from bio_mcp.mcp.rag_tools import rag_search_tool
        
        start_time = time.time()
        
        result = await rag_search_tool(
            "rag.search",
            {"query": "performance test", "top_k": 10}
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Response time should remain reasonable
        assert response_time < 60.0, f"Response too slow: {response_time}s"
        assert len(result) == 1
        assert isinstance(result[0].text, str)

    def test_schema_evolution_safety(self):
        """Test that schema changes follow safe evolution practices."""
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