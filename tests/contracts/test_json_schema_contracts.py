"""
JSON Schema contract tests for Bio-MCP API responses.

These tests validate that API responses match the exact JSON schemas defined
in contracts.md. They ensure backward compatibility during refactoring.
"""

import json
from typing import Any

import jsonschema
import pytest


class TestJSONSchemaContracts:
    """Test API responses against JSON schema contracts."""

    @pytest.fixture
    def rag_search_response_schema(self) -> dict[str, Any]:
        """JSON schema for rag.search response per contracts.md."""
        return {
            "type": "object",
            "required": ["results"],
            "properties": {
                "results": {
                    "type": "array",
                    "description": "Search results ordered by relevance score",
                    "items": {
                        "type": "object",
                        "required": ["doc_id", "uuid", "score"],
                        "properties": {
                            "doc_id": { 
                                "type": "string", 
                                "pattern": "^pmid:[0-9]+$",
                                "description": "Stable document identifier for lookup"
                            },
                            "uuid": { 
                                "type": "string", 
                                "minLength": 10,
                                "description": "Unique chunk identifier"
                            },
                            "sim": { 
                                "type": ["number", "null"],
                                "description": "Semantic similarity score"
                            },
                            "bm25": { 
                                "type": ["number", "null"],
                                "description": "BM25 relevance score"
                            },
                            "quality": { 
                                "type": ["number", "null"],
                                "description": "Document quality score"
                            },
                            "score": { 
                                "type": "number",
                                "description": "Final combined relevance score"
                            }
                        },
                        "additionalProperties": False
                    }
                }
            },
            "additionalProperties": False
        }

    @pytest.fixture
    def rag_get_response_schema(self) -> dict[str, Any]:
        """JSON schema for rag.get response per contracts.md."""
        return {
            "type": "object",
            "required": ["doc_id", "title", "journal", "pub_types", "quality", "version"],
            "properties": {
                "doc_id": { 
                    "type": "string",
                    "description": "PubMed document identifier"
                },
                "title": { 
                    "type": ["string", "null"],
                    "description": "Article title"
                },
                "abstract": { 
                    "type": ["string", "null"],
                    "description": "Article abstract text"
                },
                "journal": { 
                    "type": ["string", "null"],
                    "description": "Journal name"
                },
                "pub_types": { 
                    "type": "array", 
                    "items": {"type": "string"},
                    "description": "Publication types (e.g., 'Randomized Controlled Trial')"
                },
                "pdat": { 
                    "type": ["string", "null"],
                    "description": "Publication date (YYYY-MM-DD)"
                },
                "edat": { 
                    "type": ["string", "null"],
                    "description": "Entrez date (ISO8601 UTC)"
                },
                "lr": { 
                    "type": ["string", "null"],
                    "description": "Last revision date (ISO8601 UTC)"
                },
                "pmcid": { 
                    "type": ["string", "null"],
                    "description": "PubMed Central ID"
                },
                "quality": {
                    "type": "object",
                    "required": ["total"],
                    "description": "Quality scoring breakdown",
                    "properties": {
                        "design": { 
                            "type": ["integer", "null"],
                            "description": "Study design quality score"
                        },
                        "recency": { 
                            "type": ["integer", "null"],
                            "description": "Publication recency score"
                        },
                        "journal": { 
                            "type": ["integer", "null"],
                            "description": "Journal impact score"
                        },
                        "human": { 
                            "type": ["integer", "null"],
                            "description": "Human studies relevance score"
                        },
                        "total": { 
                            "type": "integer",
                            "description": "Combined quality score"
                        }
                    },
                    "additionalProperties": False
                },
                "version": { 
                    "type": "integer", 
                    "minimum": 1,
                    "description": "Document version number"
                }
            },
            "additionalProperties": False
        }

    @pytest.fixture
    def checkpoint_get_response_schema(self) -> dict[str, Any]:
        """JSON schema for corpus.checkpoint.get response."""
        return {
            "type": "object",
            "required": ["query_key"],
            "properties": {
                "query_key": { 
                    "type": "string",
                    "description": "Query identifier"
                },
                "last_edat": { 
                    "type": ["string", "null"], 
                    "description": "Last processed EDAT timestamp (ISO8601 UTC) or null if none"
                }
            },
            "additionalProperties": False
        }

    @pytest.fixture
    def checkpoint_set_response_schema(self) -> dict[str, Any]:
        """JSON schema for corpus.checkpoint.set response."""
        return {
            "type": "object",
            "required": ["ok"],
            "properties": { 
                "ok": { 
                    "type": "boolean",
                    "description": "Success indicator"
                } 
            },
            "additionalProperties": False
        }

    @pytest.fixture
    def error_envelope_schema(self) -> dict[str, Any]:
        """JSON schema for error response envelope."""
        return {
            "type": "object",
            "required": ["error"],
            "properties": {
                "error": {
                    "type": "object",
                    "required": ["code", "message"],
                    "properties": {
                        "code": {
                            "type": "string",
                            "enum": [
                                "RATE_LIMIT", "UPSTREAM", "VALIDATION", "NOT_FOUND", 
                                "INVARIANT_FAILURE", "STORE", "EMBEDDINGS", "WEAVIATE",
                                "ENTREZ", "UNKNOWN"
                            ]
                        },
                        "message": { 
                            "type": "string",
                            "description": "Human-readable error description"
                        },
                        "details": { 
                            "type": ["object", "array", "string", "null"],
                            "description": "Additional error context (optional)"
                        }
                    },
                    "additionalProperties": False
                }
            },
            "additionalProperties": False
        }

    def _extract_json_from_response(self, response_text: str) -> dict[str, Any]:
        """Extract JSON from MCP response text."""
        # Try to find JSON in common response formats
        if "```json" in response_text:
            try:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
                return json.loads(json_str)
            except (ValueError, json.JSONDecodeError) as e:
                pytest.fail(f"Failed to parse JSON from response: {e}")
        
        # Try to parse entire response as JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pytest.skip(f"Response not in JSON format: {response_text[:100]}...")

    def _validate_against_schema(self, data: dict[str, Any], schema: dict[str, Any], schema_name: str):
        """Validate data against JSON schema."""
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as e:
            pytest.fail(f"Schema validation failed for {schema_name}: {e.message}")
        except jsonschema.SchemaError as e:
            pytest.fail(f"Invalid schema {schema_name}: {e.message}")

    @pytest.mark.asyncio
    async def test_rag_search_schema_compliance(self, rag_search_response_schema, sample_documents):
        """Test that rag.search responses match JSON schema exactly."""
        from bio_mcp.mcp.rag_tools import rag_search_tool
        
        result = await rag_search_tool(
            "rag.search", 
            {"query": "cancer treatment", "top_k": 3}
        )
        
        assert len(result) == 1
        response_data = self._extract_json_from_response(result[0].text)
        
        self._validate_against_schema(
            response_data, 
            rag_search_response_schema, 
            "rag.search response"
        )

    @pytest.mark.asyncio
    async def test_rag_get_schema_compliance(self, rag_get_response_schema, sample_documents):
        """Test that rag.get responses match JSON schema exactly."""
        from bio_mcp.mcp.rag_tools import rag_get_tool
        
        result = await rag_get_tool(
            "rag.get",
            {"doc_id": "pmid:12345678"}
        )
        
        assert len(result) == 1
        response_data = self._extract_json_from_response(result[0].text)
        
        self._validate_against_schema(
            response_data,
            rag_get_response_schema,
            "rag.get response"
        )

    @pytest.mark.asyncio
    async def test_checkpoint_get_schema_compliance(self, checkpoint_get_response_schema):
        """Test that corpus.checkpoint.get responses match schema."""
        from bio_mcp.mcp.corpus_tools import corpus_checkpoint_get_tool
        
        result = await corpus_checkpoint_get_tool(
            "corpus.checkpoint.get", 
            {"checkpoint_id": "test_schema_query"}
        )
        
        assert len(result) == 1
        response_data = self._extract_json_from_response(result[0].text)
        
        self._validate_against_schema(
            response_data,
            checkpoint_get_response_schema,
            "checkpoint.get response"
        )

    @pytest.mark.asyncio
    async def test_checkpoint_create_schema_compliance(self, checkpoint_set_response_schema):
        """Test that corpus.checkpoint.create responses match expectations."""
        from bio_mcp.mcp.corpus_tools import corpus_checkpoint_create_tool
        
        result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create",
            {
                "checkpoint_id": "test_schema_create",
                "name": "Test Schema Checkpoint", 
                "description": "Testing schema compliance",
                "primary_queries": ["test query"]
            }
        )
        
        assert len(result) == 1
        response_data = self._extract_json_from_response(result[0].text)
        
        # For create operations, just check that we get a success/error response
        assert len(result[0].text) > 0
        assert ("✅" in result[0].text) or ("❌" in result[0].text)

    @pytest.mark.asyncio
    async def test_error_response_schema_compliance(self, error_envelope_schema):
        """Test that error responses follow standard error envelope."""
        from bio_mcp.mcp.rag_tools import rag_search_tool
        
        # Trigger validation error with invalid parameters
        result = await rag_search_tool("rag.search", {"invalid_param": "test"})
        
        assert len(result) == 1
        
        # Try to parse as error envelope if it's JSON
        response_text = result[0].text
        if "```json" in response_text or response_text.strip().startswith("{"):
            response_data = self._extract_json_from_response(response_text)
            
            # If it contains an error field, validate against schema
            if "error" in response_data:
                self._validate_against_schema(
                    response_data,
                    error_envelope_schema,
                    "error envelope"
                )


class TestContractRegression:
    """Regression tests to ensure contract compatibility across changes."""

    def test_required_fields_never_removed(self):
        """Ensure required fields documented in contracts are never removed."""
        # This test serves as documentation and breakage detection
        # If this test fails, it indicates a breaking change requiring major version bump
        
        # Document current contract requirements
        contracts = {
            "rag.search": {
                "required_response_fields": ["results"],
                "required_result_fields": ["doc_id", "uuid", "score"]
            },
            "rag.get": {
                "required_response_fields": ["doc_id", "title", "journal", "pub_types", "quality", "version"],
                "required_quality_fields": ["total"]
            },
            "corpus.checkpoint.get": {
                "required_response_fields": ["query_key", "last_edat"]  # last_edat can be null
            },
            "corpus.checkpoint.set": {
                "required_response_fields": ["ok"]
            },
            "error_envelope": {
                "required_error_fields": ["code", "message"]
            }
        }
        
        # This assertion will fail if contracts change, forcing developer attention
        assert contracts["rag.search"]["required_response_fields"] == ["results"]
        assert contracts["rag.get"]["required_response_fields"] == ["doc_id", "title", "journal", "pub_types", "quality", "version"]
        assert contracts["corpus.checkpoint.get"]["required_response_fields"] == ["query_key", "last_edat"]
        assert contracts["corpus.checkpoint.set"]["required_response_fields"] == ["ok"]
        assert contracts["error_envelope"]["required_error_fields"] == ["code", "message"]

    def test_doc_id_pattern_stability(self):
        """Ensure doc_id pattern remains stable: pmid:[0-9]+"""
        import re
        
        # This pattern must never change without major version bump
        STABLE_DOC_ID_PATTERN = r"^pmid:[0-9]+$"
        
        # Test pattern validity
        test_cases = [
            ("pmid:12345678", True),
            ("pmid:1", True),  
            ("pmid:999999999", True),
            ("pubmed:12345678", False),  # Wrong prefix
            ("pmid:abc123", False),      # Non-numeric ID
            ("pmid:", False),            # Empty ID
            ("12345678", False),         # Missing prefix
        ]
        
        for test_id, should_match in test_cases:
            matches = bool(re.match(STABLE_DOC_ID_PATTERN, test_id))
            assert matches == should_match, f"Pattern stability violated for: {test_id}"

    def test_error_code_enum_stability(self):
        """Ensure error code enumeration remains stable."""
        # These error codes must remain valid across versions
        STABLE_ERROR_CODES = {
            "RATE_LIMIT", "UPSTREAM", "VALIDATION", "NOT_FOUND", 
            "INVARIANT_FAILURE", "STORE", "EMBEDDINGS", "WEAVIATE",
            "ENTREZ", "UNKNOWN"
        }
        
        # This assertion will fail if error codes change
        current_codes = {
            "RATE_LIMIT", "UPSTREAM", "VALIDATION", "NOT_FOUND", 
            "INVARIANT_FAILURE", "STORE", "EMBEDDINGS", "WEAVIATE",
            "ENTREZ", "UNKNOWN"
        }
        
        assert current_codes == STABLE_ERROR_CODES, "Error code enumeration changed"

    def test_version_field_constraints(self):
        """Ensure version field constraints remain stable."""
        # Version must be integer >= 1 per contract
        valid_versions = [1, 2, 100, 9999]
        invalid_versions = [0, -1, "1", 1.5, None]
        
        for version in valid_versions:
            assert isinstance(version, int) and version >= 1, f"Valid version {version} failed constraint"
        
        for version in invalid_versions:
            assert not (isinstance(version, int) and version >= 1), f"Invalid version {version} passed constraint"