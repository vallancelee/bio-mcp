#!/usr/bin/env python3
"""
Bio-MCP Server - Biomedical Model Context Protocol server
"""

import asyncio
import logging
from typing import Any, Sequence

from mcp.server import Server
from mcp.types import Tool, TextContent

from .config import config


# Configure logging from config
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle tool calls."""
    if name == "ping":
        message = arguments.get("message", "pong")
        logger.info(f"Ping tool called with message: {message}")
        
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
        
        return [
            TextContent(
                type="text",
                text=response
            )
        ]
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting Bio-MCP server...")
    
    # Import and run the server
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())