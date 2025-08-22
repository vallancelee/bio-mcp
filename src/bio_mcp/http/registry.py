"""Tool registry for HTTP adapter - maps MCP tools to HTTP endpoints."""

from collections.abc import Callable
from typing import Any

from mcp.types import Tool

from bio_mcp.mcp.corpus_tools import (
    corpus_checkpoint_create_tool,
    corpus_checkpoint_delete_tool,
    corpus_checkpoint_get_tool,
    corpus_checkpoint_list_tool,
)
from bio_mcp.mcp.rag_tools import rag_get_tool, rag_search_tool
from bio_mcp.mcp.tool_definitions import (
    get_corpus_tool_definitions,
    get_ping_tool_definition,
    get_pubmed_tool_definitions,
    get_rag_tool_definitions,
)
from bio_mcp.sources.pubmed.tools import (
    pubmed_get_tool,
    pubmed_search_tool,
    pubmed_sync_incremental_tool,
    pubmed_sync_tool,
)


class ToolRegistry:
    """Registry for mapping tool names to their callable implementations."""

    def __init__(self):
        """Initialize empty tool registry."""
        self.tools: dict[str, Callable] = {}
        self.tool_definitions: dict[str, Tool] = {}

    def register(
        self, name: str, tool_func: Callable, tool_definition: Tool | None = None
    ) -> None:
        """Register a tool function with the given name and optional definition."""
        self.tools[name] = tool_func
        if tool_definition:
            self.tool_definitions[name] = tool_definition

    def get_tool(self, name: str) -> Callable | None:
        """Get a tool function by name, or None if not found."""
        return self.tools.get(name)

    def list_tool_names(self) -> list[str]:
        """List all registered tool names."""
        return list(self.tools.keys())

    def get_tool_definition(self, name: str) -> Tool | None:
        """Get a tool definition by name, or None if not found."""
        return self.tool_definitions.get(name)

    def get_tool_schema(self, name: str) -> dict[str, Any] | None:
        """Get a tool's schema information, or None if not found."""
        definition = self.get_tool_definition(name)
        if definition:
            return {
                "name": definition.name,
                "description": definition.description,
                "inputSchema": definition.inputSchema,
            }
        return None


def _ping_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Simple ping tool implementation for HTTP adapter."""
    message = arguments.get("message", "pong")
    return {"message": f"HTTP adapter ping: {message}"}


def build_registry() -> ToolRegistry:
    """Build and populate the tool registry with all available MCP tools.

    This maps the tool names from the MCP server to their corresponding
    callable implementations and includes their schema definitions.
    """
    registry = ToolRegistry()

    # Register core tools with definitions
    ping_def = get_ping_tool_definition()
    registry.register("ping", _ping_tool, ping_def)

    # Register PubMed tools with definitions
    pubmed_defs = get_pubmed_tool_definitions()
    pubmed_def_map = {tool.name: tool for tool in pubmed_defs}

    registry.register(
        "pubmed.search", pubmed_search_tool, pubmed_def_map.get("pubmed.search")
    )
    registry.register("pubmed.get", pubmed_get_tool, pubmed_def_map.get("pubmed.get"))
    registry.register(
        "pubmed.sync", pubmed_sync_tool, pubmed_def_map.get("pubmed.sync")
    )
    registry.register(
        "pubmed.sync.incremental",
        pubmed_sync_incremental_tool,
        pubmed_def_map.get("pubmed.sync.incremental"),
    )

    # Register RAG tools with definitions
    rag_defs = get_rag_tool_definitions()
    rag_def_map = {tool.name: tool for tool in rag_defs}

    registry.register("rag.search", rag_search_tool, rag_def_map.get("rag.search"))
    registry.register("rag.get", rag_get_tool, rag_def_map.get("rag.get"))

    # Register corpus management tools with definitions
    corpus_defs = get_corpus_tool_definitions()
    corpus_def_map = {tool.name: tool for tool in corpus_defs}

    registry.register(
        "corpus.checkpoint.create",
        corpus_checkpoint_create_tool,
        corpus_def_map.get("corpus.checkpoint.create"),
    )
    registry.register(
        "corpus.checkpoint.get",
        corpus_checkpoint_get_tool,
        corpus_def_map.get("corpus.checkpoint.get"),
    )
    registry.register(
        "corpus.checkpoint.list",
        corpus_checkpoint_list_tool,
        corpus_def_map.get("corpus.checkpoint.list"),
    )
    registry.register(
        "corpus.checkpoint.delete",
        corpus_checkpoint_delete_tool,
        corpus_def_map.get("corpus.checkpoint.delete"),
    )

    return registry
