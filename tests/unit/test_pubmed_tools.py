"""
Unit tests for PubMed MCP tools.
Phase 3A: Basic Biomedical Tools - TDD for MCP tool implementations.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bio_mcp.pubmed_tools import (
    DocumentResult,
    SearchResult,
    SyncResult,
    pubmed_get_tool,
    pubmed_search_tool,
    pubmed_sync_tool,
    register_pubmed_tools,
)


class TestSearchResult:
    """Test search result data structure."""

    def test_search_result_creation(self):
        """Test creating search result."""
        result = SearchResult(
            query="CRISPR gene editing",
            total_count=1500,
            returned_count=20,
            pmids=["12345678", "87654321"],
            execution_time_ms=150.5,
        )

        assert result.query == "CRISPR gene editing"
        assert result.total_count == 1500
        assert result.returned_count == 20
        assert len(result.pmids) == 2
        assert result.execution_time_ms == 150.5

    def test_search_result_to_mcp_response(self):
        """Test converting search result to MCP response format."""
        result = SearchResult(
            query="COVID-19 vaccines",
            total_count=5000,
            returned_count=10,
            pmids=["111", "222", "333"],
            execution_time_ms=200.0,
        )

        mcp_response = result.to_mcp_response()

        assert "Search completed" in mcp_response
        assert "COVID-19 vaccines" in mcp_response
        assert "5,000" in mcp_response  # Number is formatted with commas
        assert "111" in mcp_response
        assert "200.0" in mcp_response


class TestDocumentResult:
    """Test document result data structure."""

    def test_document_result_creation(self):
        """Test creating document result."""
        result = DocumentResult(
            pmid="12345678",
            title="Test Article",
            abstract="Test abstract content",
            authors=["Smith J", "Doe A"],
            journal="Nature",
            publication_date=date(2023, 6, 15),
            doi="10.1038/nature12345",
            found=True,
            execution_time_ms=75.0,
        )

        assert result.pmid == "12345678"
        assert result.title == "Test Article"
        assert result.found is True
        assert result.execution_time_ms == 75.0

    def test_document_result_not_found(self):
        """Test document result when not found."""
        result = DocumentResult(pmid="99999999", found=False, execution_time_ms=50.0)

        assert result.pmid == "99999999"
        assert result.found is False
        assert result.title is None
        assert result.abstract is None

    def test_document_result_to_mcp_response(self):
        """Test converting document result to MCP response format."""
        result = DocumentResult(
            pmid="12345678",
            title="Test Article",
            abstract="Abstract content here",
            authors=["Author A", "Author B"],
            journal="Test Journal",
            publication_date=date(2023, 6, 15),
            found=True,
            execution_time_ms=100.0,
        )

        mcp_response = result.to_mcp_response()

        assert "12345678" in mcp_response
        assert "Test Article" in mcp_response
        assert "Abstract content here" in mcp_response
        assert "Author A" in mcp_response
        assert "Test Journal" in mcp_response
        assert "2023-06-15" in mcp_response


class TestSyncResult:
    """Test sync result data structure."""

    def test_sync_result_creation(self):
        """Test creating sync result."""
        result = SyncResult(
            query="test query",
            total_requested=10,
            successfully_synced=8,
            already_existed=2,
            failed=0,
            pmids_synced=["111", "222", "333"],
            pmids_failed=[],
            execution_time_ms=500.0,
        )

        assert result.total_requested == 10
        assert result.successfully_synced == 8
        assert result.already_existed == 2
        assert result.failed == 0
        assert len(result.pmids_synced) == 3
        assert len(result.pmids_failed) == 0
        assert result.execution_time_ms == 500.0

    def test_sync_result_to_mcp_response(self):
        """Test converting sync result to MCP response format."""
        result = SyncResult(
            query="test query",
            total_requested=5,
            successfully_synced=4,
            already_existed=1,
            failed=0,
            pmids_synced=["111", "222", "333", "444"],
            pmids_failed=[],
            execution_time_ms=400.0,
        )

        mcp_response = result.to_mcp_response()

        assert "Sync completed" in mcp_response
        assert "5" in mcp_response  # total requested
        assert "4" in mcp_response  # successfully synced
        assert "400.0" in mcp_response  # execution time


class TestPubMedMCPTools:
    """Test MCP tool implementations."""

    @pytest.mark.asyncio
    async def test_pubmed_search_tool(self):
        """Test pubmed.search MCP tool."""
        arguments = {"term": "machine learning healthcare", "limit": 25, "offset": 0}

        # Mock the underlying manager operation
        with patch("bio_mcp.pubmed_tools.get_tools_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_result = SearchResult(
                query="machine learning healthcare",
                total_count=750,
                returned_count=25,
                pmids=["111", "222"],
                execution_time_ms=180.0,
            )
            mock_manager.search.return_value = mock_result
            mock_get_manager.return_value = mock_manager

            response = await pubmed_search_tool("pubmed.search", arguments)

            assert len(response) == 1
            response_text = response[0].text
            assert "machine learning healthcare" in response_text
            assert "750" in response_text
            assert "25" in response_text

            # Verify manager was called correctly
            mock_manager.search.assert_called_once_with(
                "machine learning healthcare", limit=25, offset=0
            )

    @pytest.mark.asyncio
    async def test_pubmed_get_tool(self):
        """Test pubmed.get MCP tool."""
        arguments = {"pmid": "12345678"}

        with patch("bio_mcp.pubmed_tools.get_tools_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_result = DocumentResult(
                pmid="12345678",
                title="Retrieved Article",
                abstract="Retrieved abstract",
                authors=["Retrieved Author"],
                journal="Retrieved Journal",
                found=True,
                execution_time_ms=120.0,
            )
            mock_manager.get_document.return_value = mock_result
            mock_get_manager.return_value = mock_manager

            response = await pubmed_get_tool("pubmed.get", arguments)

            assert len(response) == 1
            response_text = response[0].text
            assert "12345678" in response_text
            assert "Retrieved Article" in response_text
            assert "Retrieved abstract" in response_text

            mock_manager.get_document.assert_called_once_with("12345678")

    @pytest.mark.asyncio
    async def test_pubmed_sync_tool(self):
        """Test pubmed.sync MCP tool."""
        arguments = {"query": "COVID-19 treatment", "limit": 50}

        with patch("bio_mcp.pubmed_tools.get_tools_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_result = SyncResult(
                query="COVID-19 treatment",
                total_requested=50,
                successfully_synced=45,
                already_existed=5,
                failed=0,
                pmids_synced=["111", "222"],
                pmids_failed=[],
                execution_time_ms=2500.0,
            )
            mock_manager.sync.return_value = mock_result
            mock_get_manager.return_value = mock_manager

            response = await pubmed_sync_tool("pubmed.sync", arguments)

            assert len(response) == 1
            response_text = response[0].text
            assert "COVID-19 treatment" in response_text
            assert "50" in response_text  # total requested
            assert "45" in response_text  # synced
            assert "5" in response_text  # existed

            mock_manager.sync.assert_called_once_with("COVID-19 treatment", limit=50)


class TestPubMedToolsIntegration:
    """Integration tests for PubMed tools."""

    def test_register_pubmed_tools(self):
        """Test registering PubMed tools with MCP server."""
        # Mock MCP server with call_tool decorator
        mock_server = MagicMock()
        mock_decorator = MagicMock()
        mock_server.call_tool.return_value = mock_decorator

        register_pubmed_tools(mock_server)

        # Should call the decorator 3 times (once for each tool)
        assert mock_server.call_tool.call_count == 3

        # Each decorator should be called with a function
        assert mock_decorator.call_count == 3

        # Verify the functions that were decorated
        decorated_functions = []
        for call in mock_decorator.call_args_list:
            if call[0]:  # If function was passed as positional argument
                decorated_functions.append(call[0][0].__name__)

        # Should have our three tool functions
        expected_functions = [
            "pubmed_search_tool",
            "pubmed_get_tool",
            "pubmed_sync_tool",
        ]
        assert len(decorated_functions) == 3
        for func_name in expected_functions:
            assert func_name in decorated_functions


class TestErrorHandling:
    """Test error handling in PubMed tools."""

    @pytest.mark.asyncio
    async def test_search_tool_error_handling(self):
        """Test error handling in search tool."""
        arguments = {"term": "test query"}

        with patch("bio_mcp.pubmed_tools.get_tools_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.search.side_effect = Exception("PubMed API error")
            mock_get_manager.return_value = mock_manager

            response = await pubmed_search_tool("pubmed.search", arguments)

            assert len(response) == 1
            response_text = response[0].text
            assert "error" in response_text.lower()
            assert "PubMed API error" in response_text

    @pytest.mark.asyncio
    async def test_get_tool_error_handling(self):
        """Test error handling in get tool."""
        arguments = {"pmid": "12345678"}

        with patch("bio_mcp.pubmed_tools.get_tools_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get_document.side_effect = Exception("Database error")
            mock_get_manager.return_value = mock_manager

            response = await pubmed_get_tool("pubmed.get", arguments)

            assert len(response) == 1
            response_text = response[0].text
            assert "error" in response_text.lower()
            assert "Database error" in response_text

    @pytest.mark.asyncio
    async def test_sync_tool_error_handling(self):
        """Test error handling in sync tool."""
        arguments = {"query": "test query"}

        with patch("bio_mcp.pubmed_tools.get_tools_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.sync.side_effect = Exception("Sync failed")
            mock_get_manager.return_value = mock_manager

            response = await pubmed_sync_tool("pubmed.sync", arguments)

            assert len(response) == 1
            response_text = response[0].text
            assert "error" in response_text.lower()
            assert "Sync failed" in response_text
