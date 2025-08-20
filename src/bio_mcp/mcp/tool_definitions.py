"""
Tool definitions for Bio-MCP server.
Centralized location for all MCP tool schemas and metadata.
"""

from mcp.types import Tool

from ..config.search_config import SEARCH_CONFIG


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
                        "default": SEARCH_CONFIG.PUBMED_DEFAULT_LIMIT,
                        "minimum": SEARCH_CONFIG.PUBMED_MIN_LIMIT,
                        "maximum": SEARCH_CONFIG.PUBMED_MAX_LIMIT,
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
                        "default": SEARCH_CONFIG.PUBMED_DEFAULT_LIMIT,
                        "minimum": SEARCH_CONFIG.PUBMED_MIN_LIMIT,
                        "maximum": SEARCH_CONFIG.PUBMED_MAX_LIMIT,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="pubmed.sync.incremental",
            description="Search PubMed and sync documents incrementally using EDAT watermarks for efficient updates",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for PubMed documents to sync incrementally",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of new documents to sync in this batch",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 500,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
    ]


def get_rag_tool_definitions() -> list[Tool]:
    """Get RAG tool definitions for hybrid search and document retrieval."""
    return [
        Tool(
            name="rag.search",
            description="Advanced hybrid search combining BM25 keyword search with vector similarity, optimized for biotech investment research",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for biomedical literature"},
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": SEARCH_CONFIG.DEFAULT_TOP_K,
                        "minimum": SEARCH_CONFIG.MIN_TOP_K,
                        "maximum": SEARCH_CONFIG.MAX_TOP_K,
                    },
                    "search_mode": {
                        "type": "string", 
                        "enum": ["hybrid", "semantic", "bm25"],
                        "description": "Search strategy: 'hybrid' (BM25+vector), 'semantic' (vector only), 'bm25' (keyword only)",
                        "default": "hybrid"
                    },
                    "alpha": {
                        "type": "number",
                        "description": "Hybrid search weighting: 0.0=pure BM25 keyword, 1.0=pure vector semantic, 0.5=balanced",
                        "default": 0.5,
                        "minimum": 0.0,
                        "maximum": 1.0
                    },
                    "rerank_by_quality": {
                        "type": "boolean",
                        "description": "Boost results by PubMed quality metrics, journal impact, and investment relevance",
                        "default": True
                    },
                    "filters": {
                        "type": "object",
                        "description": "Metadata filters for date ranges, journals, etc.",
                        "properties": {
                            "date_from": {"type": "string", "description": "Filter results from this date (YYYY-MM-DD)"},
                            "date_to": {"type": "string", "description": "Filter results to this date (YYYY-MM-DD)"},
                            "journals": {"type": "array", "items": {"type": "string"}, "description": "Filter by specific journals"}
                        },
                        "additionalProperties": False
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
    """Get corpus management tool definitions for checkpoint management."""
    return [
        Tool(
            name="corpus.checkpoint.create",
            description="Create a new corpus checkpoint capturing current corpus state for reproducible research",
            inputSchema={
                "type": "object",
                "properties": {
                    "checkpoint_id": {
                        "type": "string",
                        "description": "Unique identifier for the checkpoint",
                    },
                    "name": {
                        "type": "string",
                        "description": "Human-readable name for the checkpoint",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of the checkpoint purpose",
                    },
                    "primary_queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of primary queries used to build this corpus",
                    },
                    "parent_checkpoint_id": {
                        "type": "string",
                        "description": "Optional parent checkpoint ID for lineage tracking",
                    },
                },
                "required": ["checkpoint_id", "name"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="corpus.checkpoint.get",
            description="Get corpus checkpoint details by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "checkpoint_id": {
                        "type": "string",
                        "description": "Checkpoint ID to retrieve",
                    }
                },
                "required": ["checkpoint_id"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="corpus.checkpoint.list",
            description="List all available corpus checkpoints with pagination",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of checkpoints to return",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of checkpoints to skip for pagination",
                        "default": 0,
                        "minimum": 0,
                    },
                },
                "additionalProperties": False,
            },
        ),
        Tool(
            name="corpus.checkpoint.delete",
            description="Delete a corpus checkpoint permanently",
            inputSchema={
                "type": "object",
                "properties": {
                    "checkpoint_id": {
                        "type": "string",
                        "description": "Checkpoint ID to delete",
                    }
                },
                "required": ["checkpoint_id"],
                "additionalProperties": False,
            },
        ),
    ]


def get_all_tool_definitions() -> list[Tool]:
    """Get all available tool definitions."""
    tools = [get_ping_tool_definition()]
    tools.extend(get_pubmed_tool_definitions())
    tools.extend(get_rag_tool_definitions())
    tools.extend(get_corpus_tool_definitions())
    return tools
