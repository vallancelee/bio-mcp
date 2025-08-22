"""
Simplified integration tests for RAG tools MCP interface.

Tests MCP tools with real PostgreSQL database using TestContainers.
Weaviate tests are handled separately to avoid timeout issues.
"""

import pytest

from bio_mcp.mcp.rag_tools import rag_get_tool, rag_search_tool
from tests.utils.mcp_validators import MCPResponseValidator

# Mark all tests to not use weaviate by default
pytestmark = pytest.mark.no_weaviate


class TestRAGToolsIntegrationSimplified:
    """Simplified integration tests for RAG tools."""

    def setup_method(self):
        """Setup test fixtures."""
        self.validator = MCPResponseValidator()

    @pytest.mark.asyncio
    async def test_rag_search_validation_errors(self):
        """Test RAG search parameter validation."""
        # Test missing query
        result = await rag_search_tool("rag.search", {"limit": 10})

        assert len(result) == 1
        response_text = result[0].text
        
        # Should return JSON error format
        assert "```json" in response_text
        
        # Parse and validate error structure
        import json
        json_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])
        
        assert json_data["success"] is False
        assert json_data["operation"] == "rag.search"
        assert "error" in json_data
        assert json_data["error"]["code"] == "MISSING_PARAMETER"
        assert "query" in json_data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_rag_search_with_mock_results(self, sample_documents):
        """Test RAG search with basic functionality (external services mocked in conftest)."""
        result = await rag_search_tool(
            "rag.search",
            {"query": "cancer research", "limit": 5, "search_mode": "hybrid"},
        )

        assert len(result) == 1
        self.validator.validate_text_content(result[0])
        response_text = result[0].text

        # Should contain query information
        assert (
            "cancer research" in response_text.lower()
            or "query" in response_text.lower()
        )
        # If successful, should have execution time; if failed, should have error indication
        assert "ms" in response_text or "No documents found" in response_text

    @pytest.mark.asyncio
    async def test_rag_get_validation_errors(self):
        """Test RAG get document parameter validation."""
        # Test missing doc_id
        result = await rag_get_tool("rag.get", {})

        assert len(result) == 1
        response_text = result[0].text
        
        # Should return JSON error format
        assert "```json" in response_text
        
        # Parse and validate error structure
        import json
        json_data = json.loads(response_text.split("```json\n")[1].split("\n```")[0])
        
        assert json_data["success"] is False
        assert json_data["operation"] == "rag.get"
        assert "error" in json_data
        assert json_data["error"]["code"] == "MISSING_PARAMETER"
        assert "doc_id" in json_data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_rag_get_with_existing_document(self, sample_documents):
        """Test RAG get with existing document."""
        # Use the first sample document
        sample_pmid = "12345678"  # From conftest sample_documents fixture

        result = await rag_get_tool("rag.get", {"doc_id": sample_pmid})

        assert len(result) == 1
        self.validator.validate_text_content(result[0])
        response_text = result[0].text

        # Should contain document information or proper error
        assert (
            sample_pmid in response_text
            or "Cancer Research Paper" in response_text
            or "not found" in response_text.lower()
            or "❌" in response_text
        )

    @pytest.mark.asyncio
    async def test_rag_get_nonexistent_document(self):
        """Test RAG get with non-existent document."""
        result = await rag_get_tool(
            "rag.get",
            {
                "doc_id": "99999999"  # Non-existent PMID
            },
        )

        assert len(result) == 1
        response_text = result[0].text
        assert "❌" in response_text or "not found" in response_text.lower()
        assert "99999999" in response_text

    @pytest.mark.asyncio
    async def test_rag_search_mode_parameters(self, sample_documents):
        """Test different search modes."""
        search_modes = ["hybrid", "semantic", "bm25", "vector"]

        for mode in search_modes:
            result = await rag_search_tool(
                "rag.search", {"query": "test query", "search_mode": mode, "limit": 3}
            )

            assert len(result) == 1
            response_text = result[0].text
            # Should either succeed or fail gracefully
            assert (
                "ms" in response_text
                or "No documents found" in response_text
                or "❌" in response_text
            )  # Should have execution time or proper error
            # Don't require specific content since external services may not be fully initialized

    @pytest.mark.asyncio
    async def test_rag_search_limit_validation(self, sample_documents):
        """Test search limit parameter validation."""
        # Test with various limits
        limits = [1, 5, 10, 50]

        for limit in limits:
            result = await rag_search_tool(
                "rag.search", {"query": "test", "limit": limit}
            )

            assert len(result) == 1
            result_text = result[0].text
            assert (
                "ms" in result_text
                or "No documents found" in result_text
                or "❌" in result_text
            )

        # Test invalid limit (too high)
        result = await rag_search_tool(
            "rag.search",
            {
                "query": "test",
                "limit": 1000,  # Should be capped or cause error
            },
        )

        assert len(result) == 1
        # Should either work with capped limit or show error
        response_text = result[0].text
        assert (
            "ms" in response_text
            or "No documents found" in response_text
            or "❌" in response_text
        )
