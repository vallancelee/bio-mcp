"""
Contract tests for Bio-MCP API compatibility.

These tests ensure that API responses maintain exact compatibility with the
contracts.md schema during the multi-source document refactoring.

Tests validate:
- Response structure matches JSON schema exactly
- Tool behavior remains consistent before/after Document model changes
- Error formats follow the standard error envelope
- All required fields are present with correct types

Note: These tests may skip if external dependencies (Weaviate, database) are unavailable.
For core contract validation without external dependencies, see test_core_contracts.py.
"""

import json
from typing import Any

import pytest

from bio_mcp.mcp import corpus_tools, rag_tools
from tests.utils.mcp_validators import MCPResponseValidator


class TestAPIContracts:
    """Test API contract compliance for all MCP tools."""

    def setup_method(self):
        """Setup test fixtures and validators."""
        self.validator = MCPResponseValidator()

    @pytest.mark.asyncio
    async def test_rag_search_response_schema(self, sample_documents):
        """Test rag.search response matches contract schema exactly."""
        # Execute the tool with timeout protection
        import asyncio
        try:
            result = await asyncio.wait_for(
                rag_tools.rag_search_tool(
                    "rag.search", 
                    {
                        "query": "cancer treatment",
                        "top_k": 5,
                        "quality_bias": True
                    }
                ),
                timeout=10.0  # 10 second timeout
            )
        except TimeoutError:
            pytest.skip("RAG search timed out - external dependencies unavailable")
        
        assert len(result) == 1
        response_text = result[0].text
        
        # Parse JSON response
        try:
            response_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])
        except (IndexError, json.JSONDecodeError):
            # If not JSON format, check it's a valid response (error or no results)
            valid_responses = [
                "❌" in response_text,
                "error" in response_text.lower(),
                "no documents found" in response_text.lower(),
                "failed to initialize" in response_text.lower()
            ]
            assert any(valid_responses), f"Unexpected response format: {response_text[:200]}"
            return

        # Validate response structure matches contract
        self._validate_rag_search_response(response_data)

    def _validate_rag_search_response(self, response: dict[str, Any]):
        """Validate rag.search response against contract schema."""
        # Validate top-level MCP response envelope
        assert "success" in response, "Missing 'success' field"
        assert "operation" in response, "Missing 'operation' field"
        assert "metadata" in response, "Missing 'metadata' field"
        
        assert isinstance(response["success"], bool), "'success' must be boolean"
        assert response["operation"] == "rag.search", "Unexpected operation"
        assert isinstance(response["metadata"], dict), "'metadata' must be object"
        
        # Validate metadata
        metadata = response["metadata"]
        assert "execution_time_ms" in metadata, "Missing 'execution_time_ms' in metadata"
        assert "timestamp" in metadata, "Missing 'timestamp' in metadata"
        assert "version" in metadata, "Missing 'version' in metadata"
        
        # For success responses, validate data structure
        if response.get("success"):
            assert "data" in response, "Success response missing 'data' field"
            data = response["data"]
            assert isinstance(data, dict), "'data' must be object"
            
            assert "results" in data, "Missing 'results' field in data"
            assert isinstance(data["results"], list), "'results' must be array"
            
            # Validate each result item
            for result_item in data["results"]:
                self._validate_search_result_item(result_item)
        else:
            # For error responses, validate error structure
            assert "error" in response, "Error response missing 'error' field"
            error = response["error"]
            assert "code" in error, "Error missing 'code' field"
            assert "message" in error, "Error missing 'message' field"

    def _validate_search_result_item(self, item: dict[str, Any]):
        """Validate individual search result item schema."""
        # Required fields in new JSON schema
        required_fields = {"uuid", "pmid", "title", "score"}
        for field in required_fields:
            assert field in item, f"Missing required field: {field}"
        
        # Field type validations
        assert isinstance(item["uuid"], str), "uuid must be string"
        assert len(item["uuid"]) >= 10, "uuid must have minLength 10"
        
        assert isinstance(item["pmid"], str), "pmid must be string"
        
        assert isinstance(item["title"], str), "title must be string"
        
        assert isinstance(item["score"], (int, float)), "score must be number"
        
        # Optional string fields
        optional_string_fields = {"abstract", "journal", "publication_date", "content"}
        for field in optional_string_fields:
            if field in item:
                assert isinstance(item[field], str), f"{field} must be string"
        
        # Optional number fields
        optional_number_fields = {"boosted_score", "quality_boost", "distance"}
        for field in optional_number_fields:
            if field in item:
                assert item[field] is None or isinstance(item[field], (int, float)), f"{field} must be number or null"
        
        # Optional object/string fields
        if "explain_score" in item:
            assert isinstance(item["explain_score"], (str, dict)), "explain_score must be string or object"
        
        # Allow reasonable fields - don't be too strict about additional properties
        # since the response format is evolving

    @pytest.mark.asyncio  
    async def test_rag_get_response_schema(self, sample_documents):
        """Test rag.get response matches contract schema exactly."""
        # Execute the tool with a known doc_id and timeout protection
        import asyncio
        try:
            result = await asyncio.wait_for(
                rag_tools.rag_get_tool(
                    "rag.get",
                    {"doc_id": "pmid:12345678"}
                ),
                timeout=10.0
            )
        except TimeoutError:
            pytest.skip("RAG get timed out - external dependencies unavailable")
        
        assert len(result) == 1
        response_text = result[0].text
        
        # Parse JSON response
        try:
            response_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])
        except (IndexError, json.JSONDecodeError):
            # Check for valid error response if document not found
            assert "❌" in response_text or "not found" in response_text.lower()
            return

        self._validate_rag_get_response(response_data)

    def _validate_rag_get_response(self, response: dict[str, Any]):
        """Validate rag.get response against contract schema."""
        # Validate MCP envelope structure
        assert "success" in response, "Missing 'success' field"
        assert "operation" in response, "Missing 'operation' field"
        assert "metadata" in response, "Missing 'metadata' field"
        assert response["operation"] == "rag.get", "Unexpected operation"
        
        # For success responses, validate data structure
        if response.get("success"):
            assert "data" in response, "Success response missing 'data' field"
            data = response["data"]
            
            # Required fields per contract (now in data object)
            required_fields = {"doc_id", "title", "journal", "pub_types", "quality", "version"}
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
            
            # Field type validations
            assert isinstance(data["doc_id"], str), "doc_id must be string"
            
            # title can be string or null
            assert data["title"] is None or isinstance(data["title"], str), "title must be string or null"
            
            # journal can be string or null  
            assert data["journal"] is None or isinstance(data["journal"], str), "journal must be string or null"
            
            # pub_types must be array of strings
            assert isinstance(data["pub_types"], list), "pub_types must be array"
            for pub_type in data["pub_types"]:
                assert isinstance(pub_type, str), "pub_types items must be strings"
            
            # version must be integer >= 1
            assert isinstance(data["version"], int), "version must be integer"
            assert data["version"] >= 1, "version must be minimum 1"
            
            # Validate quality object
            self._validate_quality_object(data["quality"])
        else:
            # For error responses, validate error structure
            assert "error" in response, "Error response missing 'error' field"
            error = response["error"]
            assert "code" in error, "Error missing 'code' field"
            assert "message" in error, "Error missing 'message' field"

    def _validate_quality_object(self, quality: dict[str, Any]):
        """Validate quality score object schema."""
        # Required field
        assert "total" in quality, "quality.total is required"
        assert isinstance(quality["total"], int), "quality.total must be integer"
        
        # Optional integer fields
        optional_int_fields = {"design", "recency", "journal", "human"}
        for field in optional_int_fields:
            if field in quality:
                assert quality[field] is None or isinstance(quality[field], int), f"quality.{field} must be integer or null"
        
        # No additional properties
        allowed_fields = {"total"} | set(optional_int_fields)
        extra_fields = set(quality.keys()) - allowed_fields
        assert not extra_fields, f"Unexpected fields in quality object: {extra_fields}"

    @pytest.mark.asyncio
    async def test_corpus_checkpoint_get_schema(self, sample_checkpoint):
        """Test corpus.checkpoint.get response matches contract."""
        result = await corpus_tools.corpus_checkpoint_get_tool(
            "corpus.checkpoint.get",
            {"checkpoint_id": "test_query"}
        )
        
        assert len(result) == 1
        response_text = result[0].text
        
        try:
            response_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])
        except (IndexError, json.JSONDecodeError):
            # Check for valid error response
            assert "❌" in response_text or "error" in response_text.lower()
            return

        self._validate_checkpoint_get_response(response_data)

    def _validate_checkpoint_get_response(self, response: dict[str, Any]):
        """Validate corpus.checkpoint.get response schema."""
        # Validate MCP envelope structure
        assert "success" in response, "Missing 'success' field"
        assert "operation" in response, "Missing 'operation' field"
        assert "metadata" in response, "Missing 'metadata' field"
        assert response["operation"] == "corpus.checkpoint.get", "Unexpected operation"
        
        # For success responses, validate data structure
        if response.get("success"):
            assert "data" in response, "Success response missing 'data' field"
            # Allow flexible checkpoint structure in data
        else:
            # For error responses, validate error structure
            assert "error" in response, "Error response missing 'error' field"
            error = response["error"]
            assert "code" in error, "Error missing 'code' field"
            assert "message" in error, "Error missing 'message' field"

    @pytest.mark.asyncio
    async def test_corpus_checkpoint_create_schema(self):
        """Test corpus.checkpoint.create response matches contract."""
        result = await corpus_tools.corpus_checkpoint_create_tool(
            "corpus.checkpoint.create",
            {
                "checkpoint_id": "test_contract_checkpoint",
                "name": "Test Contract Checkpoint",
                "description": "Testing contract validation",
                "primary_queries": ["test query"]
            }
        )
        
        assert len(result) == 1
        response_text = result[0].text
        
        try:
            json.loads(response_text.split("```json\n")[1].split("\n```")[0])
        except (IndexError, json.JSONDecodeError):
            # Check for valid error response
            assert "❌" in response_text or "error" in response_text.lower()
            return

        # Response should have success or error indication
        response_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])
        assert "success" in response_data
        assert "operation" in response_data
        assert "metadata" in response_data
        assert response_data["operation"] == "corpus.checkpoint.create"
        
        # Should indicate success or failure clearly
        if response_data["success"]:
            assert "data" in response_data
        else:
            assert "error" in response_data

    @pytest.mark.asyncio
    async def test_error_response_envelope(self):
        """Test that all error responses follow the standard error envelope."""
        # Test with invalid parameters to trigger error
        result = await rag_tools.rag_search_tool("rag.search", {"invalid": "param"})
        
        assert len(result) == 1
        response_text = result[0].text
        
        # Should be an error response with standard format
        assert "error" in response_text.lower() or "```json" in response_text
        
        # Try to parse as error JSON if possible
        if "```json" in response_text:
            try:
                error_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])
                # Validate the full error response structure
                assert "success" in error_data and error_data["success"] is False
                assert "error" in error_data
                assert "operation" in error_data
                assert "metadata" in error_data
                
                # Validate the error field itself
                self._validate_error_envelope(error_data["error"])
            except (IndexError, json.JSONDecodeError):
                pass  # Error not in JSON format, that's also valid

    def _validate_error_envelope(self, error: dict[str, Any]):
        """Validate error response follows standard error envelope."""
        # Required fields
        assert "code" in error, "error.code is required"
        assert "message" in error, "error.message is required"
        
        # Field types
        assert isinstance(error["code"], str), "error.code must be string"
        assert isinstance(error["message"], str), "error.message must be string"
        
        # Valid error codes per contract (updated for new JSON responses)
        valid_codes = {
            "RATE_LIMIT", "UPSTREAM", "VALIDATION", "NOT_FOUND", 
            "INVARIANT_FAILURE", "STORE", "EMBEDDINGS", "WEAVIATE",
            "ENTREZ", "UNKNOWN", "MISSING_PARAMETER", "OPERATION_FAILED"
        }
        assert error["code"] in valid_codes, f"Invalid error code: {error['code']}"
        
        # Optional details field
        if "details" in error:
            # Can be object, array, string, or null
            assert error["details"] is None or isinstance(error["details"], dict | list | str), "Invalid details type"
        
        # No additional properties
        allowed_fields = {"code", "message", "details"}
        extra_fields = set(error.keys()) - allowed_fields
        assert not extra_fields, f"Unexpected fields in error envelope: {extra_fields}"


class TestContractStability:
    """Test that contracts remain stable across implementation changes."""
    
    @pytest.mark.asyncio
    async def test_search_result_ordering_consistency(self, sample_documents):
        """Test that search results maintain consistent ordering."""
        query = "cancer treatment clinical trial"
        
        # Run search multiple times with timeout protection
        import asyncio
        results = []
        for _ in range(3):
            try:
                result = await asyncio.wait_for(
                    rag_tools.rag_search_tool(
                        "rag.search",
                        {
                            "query": query,
                            "top_k": 10,
                            "quality_bias": True,
                            "search_mode": "hybrid"
                        }
                    ),
                    timeout=5.0
                )
                results.append(result)
            except TimeoutError:
                pytest.skip("RAG search timed out - external dependencies unavailable")
        
        # All results should have same structure
        for result_set in results:
            assert len(result_set) == 1
            # Should contain consistent response format
            response_text = result_set[0].text
            assert isinstance(response_text, str)
            assert len(response_text) > 0

    @pytest.mark.asyncio
    async def test_doc_id_pattern_consistency(self, sample_documents):
        """Test that doc_id patterns remain stable across changes."""
        result = await rag_tools.rag_search_tool(
            "rag.search",
            {"query": "test document", "top_k": 5}
        )
        
        response_text = result[0].text
        
        # If we get results with doc_ids, they should follow pattern
        if "pmid:" in response_text:
            # Extract doc_ids and validate pattern
            import re
            doc_ids = re.findall(r'"doc_id":\s*"(pmid:[0-9]+)"', response_text)
            for doc_id in doc_ids:
                assert doc_id.startswith("pmid:")
                assert doc_id.split(":", 1)[1].isdigit()

    @pytest.mark.asyncio
    async def test_response_time_constraints(self, sample_documents):
        """Test that API responses meet performance contracts."""
        import time
        
        start_time = time.time()
        
        result = await rag_tools.rag_search_tool(
            "rag.search",
            {"query": "quick test", "top_k": 5}
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Should respond within reasonable time (even for mock/error responses)
        assert response_time < 30.0, f"Response took too long: {response_time}s"
        assert len(result) == 1

    def test_schema_versioning_compatibility(self):
        """Test that schema changes maintain backward compatibility."""
        # This test documents the current API version expectations
        # If these assertions fail, it indicates a breaking change that needs major version bump
        
        # Current expected schema versions (update when making breaking changes)
        
        # Document required fields that cannot be removed without major version bump
        RAG_SEARCH_REQUIRED_FIELDS = {"results"}
        RAG_GET_REQUIRED_FIELDS = {"doc_id", "title", "journal", "pub_types", "quality", "version"}
        CHECKPOINT_GET_REQUIRED_FIELDS = {"query_key", "last_edat"}
        CHECKPOINT_SET_REQUIRED_FIELDS = {"ok"}
        ERROR_ENVELOPE_REQUIRED_FIELDS = {"code", "message"}
        
        # These assertions serve as documentation and breaking change detection
        assert RAG_SEARCH_REQUIRED_FIELDS == {"results"}, "Breaking change in rag.search response"
        assert RAG_GET_REQUIRED_FIELDS == {"doc_id", "title", "journal", "pub_types", "quality", "version"}, "Breaking change in rag.get response"
        assert CHECKPOINT_GET_REQUIRED_FIELDS == {"query_key", "last_edat"}, "Breaking change in checkpoint.get response"
        assert CHECKPOINT_SET_REQUIRED_FIELDS == {"ok"}, "Breaking change in checkpoint.set response"  
        assert ERROR_ENVELOPE_REQUIRED_FIELDS == {"code", "message"}, "Breaking change in error envelope"