"""Tool registry for HTTP adapter - maps MCP tools to HTTP endpoints."""

from collections.abc import Callable
from typing import Any

from bio_mcp.mcp.corpus_tools import (
    corpus_checkpoint_create_tool,
    corpus_checkpoint_delete_tool,
    corpus_checkpoint_get_tool,
    corpus_checkpoint_list_tool,
)
from bio_mcp.mcp.rag_tools import rag_get_tool, rag_search_tool
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
    
    def register(self, name: str, tool_func: Callable) -> None:
        """Register a tool function with the given name."""
        self.tools[name] = tool_func
    
    def get_tool(self, name: str) -> Callable | None:
        """Get a tool function by name, or None if not found."""
        return self.tools.get(name)
    
    def list_tool_names(self) -> list[str]:
        """List all registered tool names."""
        return list(self.tools.keys())


def _ping_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Simple ping tool implementation for HTTP adapter."""
    message = arguments.get("message", "pong")
    return {"message": f"HTTP adapter ping: {message}"}


def build_registry() -> ToolRegistry:
    """Build and populate the tool registry with all available MCP tools.
    
    This maps the tool names from the MCP server to their corresponding
    callable implementations.
    """
    registry = ToolRegistry()
    
    # Register core tools
    registry.register("ping", _ping_tool)
    
    # Register PubMed tools
    registry.register("pubmed.search", pubmed_search_tool)
    registry.register("pubmed.get", pubmed_get_tool)
    registry.register("pubmed.sync", pubmed_sync_tool)
    registry.register("pubmed.sync.incremental", pubmed_sync_incremental_tool)
    
    # Register RAG tools
    registry.register("rag.search", rag_search_tool)
    registry.register("rag.get", rag_get_tool)
    
    # Register corpus management tools
    registry.register("corpus.checkpoint.create", corpus_checkpoint_create_tool)
    registry.register("corpus.checkpoint.get", corpus_checkpoint_get_tool)
    registry.register("corpus.checkpoint.list", corpus_checkpoint_list_tool)
    registry.register("corpus.checkpoint.delete", corpus_checkpoint_delete_tool)
    
    return registry