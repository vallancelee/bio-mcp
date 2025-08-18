"""
Tool definitions for Bio-MCP server.
Centralized location for all MCP tool schemas and metadata.
"""

from mcp.types import Tool


def get_ping_tool_definition() -> Tool:
    """Get ping tool definition."""
    return Tool(
        name="ping",
        description="Simple ping tool to test server connectivity",
        inputSchema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Optional message to echo back",
                    "default": "pong",
                }
            },
            "additionalProperties": False,
        },
    )


def get_pubmed_tool_definitions() -> list[Tool]:
    """Get PubMed tool definitions."""
    return [
        Tool(
            name="pubmed.search",
            description="Search PubMed for documents",
            inputSchema={
                "type": "object",
                "properties": {
                    "term": {"type": "string", "description": "Search term for PubMed"},
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination",
                        "default": 0,
                        "minimum": 0,
                    },
                },
                "required": ["term"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="pubmed.get",
            description="Get a PubMed document by PMID",
            inputSchema={
                "type": "object",
                "properties": {
                    "pmid": {
                        "type": "string",
                        "description": "PubMed ID of the document to retrieve",
                    }
                },
                "required": ["pmid"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="pubmed.sync",
            description="Search PubMed and sync documents to database",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for PubMed documents to sync",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of documents to sync",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
    ]


def get_rag_tool_definitions() -> list[Tool]:
    """Get RAG tool definitions (placeholder for future implementation)."""
    return [
        Tool(
            name="rag.search",
            description="Search the RAG corpus for relevant documents",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="rag.get",
            description="Get a specific document from the RAG corpus",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Document ID to retrieve",
                    }
                },
                "required": ["doc_id"],
                "additionalProperties": False,
            },
        ),
    ]


def get_corpus_tool_definitions() -> list[Tool]:
    """Get corpus management tool definitions (placeholder for future implementation)."""
    return [
        Tool(
            name="corpus.checkpoint.get",
            description="Get corpus checkpoint for a query key",
            inputSchema={
                "type": "object",
                "properties": {
                    "query_key": {
                        "type": "string",
                        "description": "Query key for checkpoint",
                    }
                },
                "required": ["query_key"],
                "additionalProperties": False,
            },
        )
    ]


def get_all_tool_definitions() -> list[Tool]:
    """Get all available tool definitions."""
    tools = [get_ping_tool_definition()]
    tools.extend(get_pubmed_tool_definitions())
    # Future tools - uncomment when implemented:
    # tools.extend(get_rag_tool_definitions())
    # tools.extend(get_corpus_tool_definitions())
    return tools
