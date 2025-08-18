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
from mcp.types import TextContent, Tool

from .config import config
from .error_handling import error_boundary, validate_tool_arguments
from .logging_config import auto_configure_logging, get_logger
from .metrics import record_tool_call
from .security import validate_request_security

# Configure structured logging
auto_configure_logging()
logger = get_logger(__name__)

# Create the MCP server instance
server = Server(config.server_name)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="ping",
            description="Simple ping tool to test server connectivity",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Optional message to echo back",
                        "default": "pong"
                    }
                },
                "additionalProperties": False
            }
        )
    ]


@server.call_tool()
@error_boundary(fallback_message="Tool execution failed", return_error_response=True)
async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle tool calls with error boundaries and metrics."""
    start_time = time.time()
    tool_logger = logger.with_context(tool=name, arguments=arguments)
    
    try:
        if name == "ping":
            # Get tool schema for validation
            tools = await list_tools()
            ping_tool = next((tool for tool in tools if tool.name == "ping"), None)
            
            if ping_tool:
                # Validate arguments against schema
                validate_tool_arguments(name, arguments, ping_tool.inputSchema)
            
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
- PubMed API: {'configured' if config.pubmed_api_key else 'not configured'}
- OpenAI API: {'configured' if config.openai_api_key else 'not configured'}"""
            
            tool_logger.info("Ping tool completed successfully", response_length=len(response))
            
            # Record successful metrics
            duration_ms = (time.time() - start_time) * 1000
            record_tool_call(name, duration_ms, success=True)
            
            return [
                TextContent(
                    type="text",
                    text=response
                )
            ]
        else:
            tool_logger.error("Unknown tool requested", tool=name)
            # Record error metrics
            duration_ms = (time.time() - start_time) * 1000
            record_tool_call(name, duration_ms, success=False, error_type="unknown_tool")
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
                    read_stream,
                    write_stream,
                    server.create_initialization_options()
                )
            )
            
            # Wait for either server completion or shutdown signal
            done, pending = await asyncio.wait(
                [server_task, asyncio.create_task(shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
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