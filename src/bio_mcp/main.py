#!/usr/bin/env python3
"""
Bio-MCP Server - Biomedical Model Context Protocol server
"""

import asyncio
import signal
import sys
import time
from collections.abc import Sequence
from typing import Any

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool

from .config.config import config
from .config.logging_config import auto_configure_logging, get_logger
from .core.error_handling import error_boundary, validate_tool_arguments
from .mcp.corpus_tools import (
    corpus_checkpoint_create_tool,
    corpus_checkpoint_delete_tool,
    corpus_checkpoint_get_tool,
    corpus_checkpoint_list_tool,
)
from .mcp.pubmed_tools import (
    pubmed_get_tool,
    pubmed_search_tool,
    pubmed_sync_incremental_tool,
    pubmed_sync_tool,
)
from .mcp.rag_tools import rag_get_tool, rag_search_tool
from .mcp.resources import list_resources, read_resource
from .mcp.tool_definitions import get_all_tool_definitions
from .monitoring.metrics import record_tool_call

# Configure structured logging
auto_configure_logging()
logger = get_logger(__name__)

# Create the MCP server instance
server = Server(config.server_name)

# Note: Tools are handled directly in call_tool function below


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return get_all_tool_definitions()


@server.list_resources()
async def list_mcp_resources() -> list[Resource]:
    """List available MCP resources."""
    return await list_resources()


@server.read_resource()
async def read_mcp_resource(uri: str) -> str:
    """Read a specific MCP resource by URI."""
    return await read_resource(uri)


@server.call_tool()
@error_boundary(fallback_message="Tool execution failed", return_error_response=True)
async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle tool calls with error boundaries and metrics."""
    start_time = time.time()
    tool_logger = logger.with_context(tool=name, arguments=arguments)

    try:
        # Get tool schema for validation
        tool_def = next(
            (tool for tool in get_all_tool_definitions() if tool.name == name), None
        )
        if tool_def:
            # Validate arguments against schema
            validate_tool_arguments(name, arguments, tool_def.inputSchema)

        # Route to appropriate tool implementation
        if name == "ping":
            message = arguments.get("message", "pong")
            tool_logger.info("Processing ping tool request", request_message=message)

            # Build version info
            version_info = f"v{config.version}"
            if config.build:
                version_info += f"-{config.build}"
            if config.commit:
                version_info += f" ({config.commit[:8]})"

            # Include basic server info in response
            response = f"""Bio-MCP Server Response: {message}

Server Info:
- Version: {version_info}
- Name: {config.server_name}
- Log Level: {config.log_level}
- Database: {config.database_url}
- Weaviate: {config.weaviate_url}
- PubMed API: {"configured" if config.pubmed_api_key else "not configured"}
- OpenAI API: {"configured" if config.openai_api_key else "not configured"}"""

            tool_logger.info(
                "Ping tool completed successfully", response_length=len(response)
            )

            # Record successful metrics
            duration_ms = (time.time() - start_time) * 1000
            record_tool_call(name, duration_ms, success=True)

            return [TextContent(type="text", text=response)]

        elif name == "pubmed.search":
            return await pubmed_search_tool(name, arguments)

        elif name == "pubmed.get":
            return await pubmed_get_tool(name, arguments)

        elif name == "pubmed.sync":
            return await pubmed_sync_tool(name, arguments)
        
        elif name == "pubmed.sync.incremental":
            return await pubmed_sync_incremental_tool(name, arguments)

        elif name == "rag.search":
            return await rag_search_tool(name, arguments)

        elif name == "rag.get":
            return await rag_get_tool(name, arguments)
        
        elif name == "corpus.checkpoint.create":
            return await corpus_checkpoint_create_tool(name, arguments)
        
        elif name == "corpus.checkpoint.get":
            return await corpus_checkpoint_get_tool(name, arguments)
        
        elif name == "corpus.checkpoint.list":
            return await corpus_checkpoint_list_tool(name, arguments)
        
        elif name == "corpus.checkpoint.delete":
            return await corpus_checkpoint_delete_tool(name, arguments)

        else:
            tool_logger.error("Unknown tool requested", tool=name)
            # Record error metrics
            duration_ms = (time.time() - start_time) * 1000
            record_tool_call(
                name, duration_ms, success=False, error_type="unknown_tool"
            )
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        # Record error metrics for any other exceptions
        duration_ms = (time.time() - start_time) * 1000
        record_tool_call(name, duration_ms, success=False, error_type=type(e).__name__)
        raise


# Global shutdown event
shutdown_event = asyncio.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting Bio-MCP server...")

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Import and run the server
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            # Create server task
            server_task = asyncio.create_task(
                server.run(
                    read_stream, write_stream, server.create_initialization_options()
                )
            )

            # Wait for either server completion or shutdown signal
            done, pending = await asyncio.wait(
                [server_task, asyncio.create_task(shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # If shutdown was requested, log it
            if shutdown_event.is_set():
                logger.info("Graceful shutdown completed")
            else:
                # Server completed normally, check for errors
                for task in done:
                    if task.exception():
                        logger.error(f"Server task failed: {task.exception()}")
                        raise task.exception()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        logger.info("Bio-MCP server stopped")


if __name__ == "__main__":
    asyncio.run(main())
