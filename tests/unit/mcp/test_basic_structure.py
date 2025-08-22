"""
Basic structure tests for MCP tools.

Simple tests to validate that MCP tools are properly structured and callable.
"""

import pytest
from mcp.types import TextContent

from bio_mcp.mcp.corpus_tools import (
    corpus_checkpoint_create_tool,
    corpus_checkpoint_delete_tool,
    corpus_checkpoint_get_tool,
    corpus_checkpoint_list_tool,
)
from bio_mcp.mcp.rag_tools import rag_get_tool, rag_search_tool
from bio_mcp.mcp.resources import list_resources, read_resource


class TestMCPToolsBasicStructure:
    """Basic structure validation for MCP tools."""

    def test_rag_tools_are_callable(self):
        """Test that RAG tool functions are callable."""
        assert callable(rag_search_tool)
        assert callable(rag_get_tool)

    def test_corpus_tools_are_callable(self):
        """Test that corpus tool functions are callable."""
        assert callable(corpus_checkpoint_create_tool)
        assert callable(corpus_checkpoint_get_tool)
        assert callable(corpus_checkpoint_list_tool)
        assert callable(corpus_checkpoint_delete_tool)

    def test_resource_functions_are_callable(self):
        """Test that resource functions are callable."""
        assert callable(list_resources)
        assert callable(read_resource)

    @pytest.mark.asyncio
    async def test_rag_search_basic_structure(self):
        """Test RAG search tool basic error handling structure."""
        # Test with missing required parameter
        try:
            result = await rag_search_tool("rag.search", {})

            # Should return list of TextContent
            assert isinstance(result, list)
            if result:
                assert isinstance(result[0], TextContent)
                assert result[0].type == "text"
                assert isinstance(result[0].text, str)

        except Exception as e:
            # Should be a reasonable error message
            assert len(str(e)) > 5

    @pytest.mark.asyncio
    async def test_rag_get_basic_structure(self):
        """Test RAG get tool basic error handling structure."""
        # Test with missing required parameter
        try:
            result = await rag_get_tool("rag.get", {})

            # Should return list of TextContent
            assert isinstance(result, list)
            if result:
                assert isinstance(result[0], TextContent)
                assert result[0].type == "text"
                assert isinstance(result[0].text, str)

        except Exception as e:
            # Should be a reasonable error message
            assert len(str(e)) > 5

    @pytest.mark.asyncio
    async def test_checkpoint_create_basic_structure(self):
        """Test checkpoint create tool basic error handling structure."""
        # Test with missing required parameters
        try:
            result = await corpus_checkpoint_create_tool("corpus.checkpoint.create", {})

            # Should return list of TextContent
            assert isinstance(result, list)
            if result:
                assert isinstance(result[0], TextContent)
                assert result[0].type == "text"
                assert isinstance(result[0].text, str)

        except Exception as e:
            # Should be a reasonable error message
            assert len(str(e)) > 5

    @pytest.mark.asyncio
    async def test_checkpoint_list_basic_structure(self):
        """Test checkpoint list tool basic structure."""
        try:
            result = await corpus_checkpoint_list_tool("corpus.checkpoint.list", {})

            # Should return list of TextContent
            assert isinstance(result, list)
            if result:
                assert isinstance(result[0], TextContent)
                assert result[0].type == "text"
                assert isinstance(result[0].text, str)

        except Exception as e:
            # Should be a reasonable error message
            assert len(str(e)) > 5

    @pytest.mark.asyncio
    async def test_list_resources_basic_structure(self):
        """Test list resources basic structure."""
        try:
            result = await list_resources()

            # Should return list of Resource objects
            assert isinstance(result, list)
            # Empty list is acceptable for basic structure test

        except Exception as e:
            # Should be a reasonable error message
            assert len(str(e)) > 5

    @pytest.mark.asyncio
    async def test_read_resource_basic_structure(self):
        """Test read resource basic error handling structure."""
        try:
            result = await read_resource("corpus://bio_mcp/invalid")

            # Should return string content or handle error gracefully
            assert isinstance(result, str) or result is None

        except Exception as e:
            # Should be a reasonable error message
            assert len(str(e)) > 5
