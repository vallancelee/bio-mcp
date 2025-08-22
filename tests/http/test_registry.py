"""Tests for HTTP tool registry discovery and mapping."""

from unittest.mock import Mock

from bio_mcp.http.registry import ToolRegistry, build_registry


class TestToolRegistry:
    """Test cases for the ToolRegistry class."""

    def test_registry_initialization(self):
        """Test registry can be initialized with tools."""
        mock_tool = Mock()
        mock_tool.name = "test.tool"

        registry = ToolRegistry()
        registry.register("test.tool", mock_tool)

        assert "test.tool" in registry.tools
        assert registry.get_tool("test.tool") == mock_tool

    def test_registry_get_nonexistent_tool(self):
        """Test registry returns None for non-existent tools."""
        registry = ToolRegistry()

        assert registry.get_tool("nonexistent.tool") is None

    def test_registry_list_tools(self):
        """Test registry can list all tool names."""
        mock_tool1 = Mock()
        mock_tool1.name = "tool.one"
        mock_tool2 = Mock()
        mock_tool2.name = "tool.two"

        registry = ToolRegistry()
        registry.register("tool.one", mock_tool1)
        registry.register("tool.two", mock_tool2)

        tool_names = registry.list_tool_names()
        assert set(tool_names) == {"tool.one", "tool.two"}


class TestBuildRegistry:
    """Test cases for the build_registry function."""

    def test_build_registry_discovers_expected_tools(self):
        """Test that build_registry discovers all expected MCP tools."""
        registry = build_registry()

        # Check that we discover the expected tool categories
        expected_tools = [
            "ping",
            "pubmed.search",
            "pubmed.get",
            "pubmed.sync",
            "pubmed.sync.incremental",
            "rag.search",
            "rag.get",
            "corpus.checkpoint.create",
            "corpus.checkpoint.get",
            "corpus.checkpoint.list",
            "corpus.checkpoint.delete",
        ]

        discovered_tools = registry.list_tool_names()

        for tool_name in expected_tools:
            assert tool_name in discovered_tools, (
                f"Expected tool {tool_name} not found in registry"
            )

    def test_build_registry_maps_tools_to_callables(self):
        """Test that tools are mapped to callable functions."""
        registry = build_registry()

        # Test a few key tools
        ping_tool = registry.get_tool("ping")
        assert ping_tool is not None
        assert callable(ping_tool)

        pubmed_search_tool = registry.get_tool("pubmed.search")
        assert pubmed_search_tool is not None
        assert callable(pubmed_search_tool)

        rag_search_tool = registry.get_tool("rag.search")
        assert rag_search_tool is not None
        assert callable(rag_search_tool)

    def test_registry_tool_metadata(self):
        """Test that registry preserves tool metadata."""
        registry = build_registry()

        # Check that we can access tool definitions
        tool_names = registry.list_tool_names()
        assert len(tool_names) > 0

        # Verify tools are properly categorized
        pubmed_tools = [name for name in tool_names if name.startswith("pubmed.")]
        rag_tools = [name for name in tool_names if name.startswith("rag.")]
        corpus_tools = [name for name in tool_names if name.startswith("corpus.")]

        assert len(pubmed_tools) >= 4  # search, get, sync, sync.incremental
        assert len(rag_tools) >= 2  # search, get
        assert len(corpus_tools) >= 4  # checkpoint.create, get, list, delete
