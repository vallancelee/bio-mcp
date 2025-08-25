#!/usr/bin/env python3
"""
Bio-MCP CLI Client

A command-line client for testing the Bio-MCP server using JSON-RPC calls.
Connects to a running MCP server via stdio and sends tool calls.

Usage:
    python clients/cli.py rag.search --query "weight loss vs placebo" --top-k 5
    python clients/cli.py rag.get --doc-id pmid:1001
    python clients/cli.py corpus.checkpoint.get --query-key demo
    python clients/cli.py ping --message "hello world"
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(help="Bio-MCP CLI Client - Test MCP server tools")
console = Console()


def find_project_root() -> Path:
    """Find the project root directory by looking for pyproject.toml."""
    current = Path(__file__).resolve()

    # Look up the directory tree for pyproject.toml
    for parent in [current.parent, *list(current.parents)]:
        if (parent / "pyproject.toml").exists():
            return parent

    # Fallback to parent of clients directory
    return current.parent.parent


class MCPClient:
    """Simple MCP client for testing tool calls."""

    def __init__(
        self, server_command: str | None = None, working_dir: Path | None = None
    ):
        if working_dir is None:
            self.working_dir = find_project_root()
        else:
            self.working_dir = working_dir

        if server_command is None:
            self.server_command = "uv run python -m src.bio_mcp.main"
        else:
            self.server_command = server_command

        self.process = None
        self.request_id = 1

    async def __aenter__(self):
        """Start the MCP server process."""
        console.print(f"[blue]Working directory: {self.working_dir}[/blue]")
        console.print(f"[blue]Starting MCP server: {self.server_command}[/blue]")

        self.process = await asyncio.create_subprocess_shell(
            self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.working_dir),
        )

        # Initialize the MCP connection
        await self._send_initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the MCP server process."""
        if self.process:
            console.print("[blue]Shutting down MCP server...[/blue]")

            # Close stdin to signal the server to shutdown
            if self.process.stdin:
                self.process.stdin.close()

            try:
                await asyncio.wait_for(self.process.wait(), timeout=3.0)
            except TimeoutError:
                console.print(
                    "[yellow]Server taking too long, sending SIGTERM...[/yellow]"
                )
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except TimeoutError:
                    console.print(
                        "[red]Server didn't respond to SIGTERM, killing...[/red]"
                    )
                    self.process.kill()
                    await self.process.wait()

    async def _send_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC message to the server and get response."""
        if not self.process:
            raise RuntimeError("MCP server not started")

        # Send message
        message_json = json.dumps(message) + "\n"
        self.process.stdin.write(message_json.encode())
        await self.process.stdin.drain()

        # Read response
        response_line = await self.process.stdout.readline()
        if not response_line:
            stderr = await self.process.stderr.read()
            raise RuntimeError(f"No response from server. stderr: {stderr.decode()}")

        return json.loads(response_line.decode())

    async def _send_initialize(self):
        """Send initialize message to set up the MCP connection."""
        init_message = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "bio-mcp-cli", "version": "1.0.0"},
            },
        }
        self.request_id += 1

        response = await self._send_message(init_message)

        if "error" in response:
            raise RuntimeError(f"Initialize failed: {response['error']}")

        console.print("[green]✓ MCP connection initialized[/green]")

        # Send initialized notification
        initialized_message = {"jsonrpc": "2.0", "method": "notifications/initialized"}

        # For notifications, we don't expect a response
        message_json = json.dumps(initialized_message) + "\n"
        self.process.stdin.write(message_json.encode())
        await self.process.stdin.drain()

    async def list_tools(self) -> dict[str, Any]:
        """List available tools."""
        message = {"jsonrpc": "2.0", "id": self.request_id, "method": "tools/list"}
        self.request_id += 1

        return await self._send_message(message)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool with the given arguments."""
        message = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        self.request_id += 1

        return await self._send_message(message)


def display_response(response: dict[str, Any], tool_name: str):
    """Display the tool response in a formatted way."""

    if "error" in response:
        console.print(
            Panel(
                f"[red]Error: {response['error']['message']}[/red]\n"
                f"Code: {response['error']['code']}",
                title=f"❌ Tool Call Failed: {tool_name}",
                border_style="red",
            )
        )
        return

    if "result" not in response:
        console.print(
            Panel(
                "[yellow]No result in response[/yellow]",
                title=f"⚠️ Tool Call: {tool_name}",
                border_style="yellow",
            )
        )
        return

    result = response["result"]

    # Handle different result formats
    if isinstance(result, dict) and "content" in result:
        # MCP tool response format
        content = result["content"]
        if isinstance(content, list) and len(content) > 0:
            # Display each content item
            for i, item in enumerate(content):
                if isinstance(item, dict) and "text" in item:
                    console.print(
                        Panel(
                            item["text"],
                            title=f"✅ {tool_name} - Response {i + 1}",
                            border_style="green",
                        )
                    )
                else:
                    console.print(
                        Panel(
                            JSON(json.dumps(item, indent=2)),
                            title=f"✅ {tool_name} - Response {i + 1}",
                            border_style="green",
                        )
                    )
        else:
            console.print(
                Panel(
                    JSON(json.dumps(content, indent=2)),
                    title=f"✅ {tool_name}",
                    border_style="green",
                )
            )
    else:
        # Raw result
        console.print(
            Panel(
                JSON(json.dumps(result, indent=2)),
                title=f"✅ {tool_name}",
                border_style="green",
            )
        )


# Global options
@app.callback()
def main(
    server_cmd: str = typer.Option(
        None,
        "--server-cmd",
        "-s",
        help="Command to start the MCP server (default: 'python src/bio_mcp/main.py')",
    ),
    working_dir: str = typer.Option(
        None,
        "--working-dir",
        "-w",
        help="Working directory for the server (default: auto-detect project root)",
    ),
):
    """Bio-MCP CLI Client - Test MCP server tools"""
    # Store global options in the app context
    app.info.context = {
        "server_cmd": server_cmd,
        "working_dir": Path(working_dir) if working_dir else None,
    }


def get_client() -> MCPClient:
    """Get an MCP client with the configured options."""
    context = getattr(app.info, "context", {})
    return MCPClient(
        server_command=context.get("server_cmd"), working_dir=context.get("working_dir")
    )


@app.command()
def ping(
    message: str = typer.Option("pong", "--message", "-m", help="Message to echo back"),
):
    """Test server connectivity with ping tool."""

    async def run_ping():
        async with get_client() as client:
            console.print(f"[blue]Calling ping tool with message: '{message}'[/blue]")

            response = await client.call_tool("ping", {"message": message})
            display_response(response, "ping")

    asyncio.run(run_ping())


@app.command("rag.search")
def rag_search(
    query: str = typer.Option(..., "--query", "-q", help="Search query"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to return"),
):
    """Search the RAG corpus for relevant documents."""

    async def run_search():
        async with get_client() as client:
            console.print(
                f"[blue]Searching RAG corpus: '{query}' (top_k={top_k})[/blue]"
            )

            response = await client.call_tool(
                "rag.search", {"query": query, "top_k": top_k}
            )
            display_response(response, "rag.search")

    asyncio.run(run_search())


@app.command("rag.get")
def rag_get(
    doc_id: str = typer.Option(..., "--doc-id", "-d", help="Document ID to retrieve"),
):
    """Get a specific document from the RAG corpus."""

    async def run_get():
        async with get_client() as client:
            console.print(f"[blue]Getting document: '{doc_id}'[/blue]")

            response = await client.call_tool("rag.get", {"doc_id": doc_id})
            display_response(response, "rag.get")

    asyncio.run(run_get())


@app.command("corpus.checkpoint.get")
def corpus_checkpoint_get(
    query_key: str = typer.Option(
        ..., "--query-key", "-k", help="Query key for checkpoint"
    ),
):
    """Get corpus checkpoint for a query key."""

    async def run_checkpoint():
        async with get_client() as client:
            console.print(f"[blue]Getting corpus checkpoint: '{query_key}'[/blue]")

            response = await client.call_tool(
                "corpus.checkpoint.get", {"query_key": query_key}
            )
            display_response(response, "corpus.checkpoint.get")

    asyncio.run(run_checkpoint())


@app.command("list-tools")
def list_tools_cmd():
    """List all available tools on the server."""

    async def run_list():
        async with get_client() as client:
            console.print("[blue]Listing available tools...[/blue]")

            response = await client.list_tools()

            if "error" in response:
                console.print(
                    Panel(
                        f"[red]Error: {response['error']['message']}[/red]",
                        title="❌ Failed to list tools",
                        border_style="red",
                    )
                )
                return

            if "result" in response:
                tools = response["result"].get("tools", [])

                if not tools:
                    console.print("[yellow]No tools available[/yellow]")
                    return

                table = Table(title="Available Tools")
                table.add_column("Name", style="cyan", no_wrap=True)
                table.add_column("Description", style="white")
                table.add_column("Input Schema", style="dim")

                for tool in tools:
                    name = tool.get("name", "Unknown")
                    description = tool.get("description", "No description")
                    schema = json.dumps(tool.get("inputSchema", {}), indent=2)
                    table.add_row(name, description, schema)

                console.print(table)
            else:
                console.print("[yellow]No tools found in response[/yellow]")

    asyncio.run(run_list())


@app.command("pubmed.search")
def pubmed_search(
    term: str = typer.Option(..., "--term", "-t", help="Search term"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of results to return"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
):
    """Search PubMed for documents."""

    async def run_search():
        async with get_client() as client:
            console.print(
                f"[blue]Searching PubMed: '{term}' (limit={limit}, offset={offset})[/blue]"
            )

            response = await client.call_tool(
                "pubmed.search", {"term": term, "limit": limit, "offset": offset}
            )
            display_response(response, "pubmed.search")

    asyncio.run(run_search())


@app.command("pubmed.get")
def pubmed_get(
    pmid: str = typer.Option(..., "--pmid", "-p", help="PubMed ID to retrieve"),
):
    """Get a specific PubMed document."""

    async def run_get():
        async with get_client() as client:
            console.print(f"[blue]Getting PubMed document: '{pmid}'[/blue]")

            response = await client.call_tool("pubmed.get", {"pmid": pmid})
            display_response(response, "pubmed.get")

    asyncio.run(run_get())


@app.command("pubmed.sync")
def pubmed_sync(
    query: str = typer.Option(..., "--query", "-q", help="Search query to sync"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of documents to sync"),
):
    """Search PubMed and sync documents to database."""

    async def run_sync():
        async with get_client() as client:
            console.print(
                f"[blue]Syncing PubMed documents: '{query}' (limit={limit})[/blue]"
            )

            response = await client.call_tool(
                "pubmed.sync", {"query": query, "limit": limit}
            )
            display_response(response, "pubmed.sync")

    asyncio.run(run_sync())


@app.command("pubmed.sync.incremental")
def pubmed_sync_incremental(
    query: str = typer.Option(
        ..., "--query", "-q", help="Search query for incremental sync"
    ),
    limit: int = typer.Option(
        100, "--limit", "-l", help="Maximum number of new documents to sync"
    ),
):
    """Search PubMed and sync documents incrementally using EDAT watermarks."""

    async def run_incremental_sync():
        async with get_client() as client:
            console.print(
                f"[blue]Incremental sync PubMed documents: '{query}' (limit={limit})[/blue]"
            )

            response = await client.call_tool(
                "pubmed.sync.incremental", {"query": query, "limit": limit}
            )
            display_response(response, "pubmed.sync.incremental")

    asyncio.run(run_incremental_sync())


@app.command("corpus.checkpoint.create")
def corpus_checkpoint_create(
    checkpoint_id: str = typer.Option(
        ..., "--checkpoint-id", "-id", help="Unique checkpoint identifier"
    ),
    name: str = typer.Option(
        ..., "--name", "-n", help="Human-readable checkpoint name"
    ),
    description: str = typer.Option(
        "", "--description", "-d", help="Optional checkpoint description"
    ),
    primary_queries: str = typer.Option(
        "", "--queries", "-q", help="Comma-separated list of primary queries"
    ),
    parent_checkpoint_id: str = typer.Option(
        "", "--parent", "-p", help="Optional parent checkpoint ID"
    ),
):
    """Create a new corpus checkpoint capturing current corpus state."""

    async def run_create():
        async with get_client() as client:
            console.print(
                f"[blue]Creating corpus checkpoint: '{checkpoint_id}' - {name}[/blue]"
            )

            # Prepare arguments
            args = {
                "checkpoint_id": checkpoint_id,
                "name": name,
            }

            if description:
                args["description"] = description
            if primary_queries:
                args["primary_queries"] = [
                    q.strip() for q in primary_queries.split(",")
                ]
            if parent_checkpoint_id:
                args["parent_checkpoint_id"] = parent_checkpoint_id

            response = await client.call_tool("corpus.checkpoint.create", args)
            display_response(response, "corpus.checkpoint.create")

    asyncio.run(run_create())


@app.command("corpus.checkpoint.list")
def corpus_checkpoint_list(
    limit: int = typer.Option(
        20, "--limit", "-l", help="Maximum number of checkpoints to return"
    ),
    offset: int = typer.Option(
        0, "--offset", "-o", help="Number of checkpoints to skip"
    ),
):
    """List all available corpus checkpoints with pagination."""

    async def run_list():
        async with get_client() as client:
            console.print(
                f"[blue]Listing corpus checkpoints (limit={limit}, offset={offset})[/blue]"
            )

            response = await client.call_tool(
                "corpus.checkpoint.list", {"limit": limit, "offset": offset}
            )
            display_response(response, "corpus.checkpoint.list")

    asyncio.run(run_list())


@app.command("corpus.checkpoint.delete")
def corpus_checkpoint_delete(
    checkpoint_id: str = typer.Option(
        ..., "--checkpoint-id", "-id", help="Checkpoint ID to delete"
    ),
):
    """Delete a corpus checkpoint permanently."""

    async def run_delete():
        async with get_client() as client:
            console.print(f"[blue]Deleting corpus checkpoint: '{checkpoint_id}'[/blue]")

            response = await client.call_tool(
                "corpus.checkpoint.delete", {"checkpoint_id": checkpoint_id}
            )
            display_response(response, "corpus.checkpoint.delete")

    asyncio.run(run_delete())


@app.command("clinicaltrials.search")
def clinicaltrials_search(
    query: str = typer.Option(..., "--query", "-q", help="Search query for clinical trials"),
    condition: str = typer.Option(None, "--condition", help="Medical condition or disease"),
    intervention: str = typer.Option(None, "--intervention", help="Drug, device, or treatment"),
    phase: str = typer.Option(None, "--phase", help="Clinical trial phase (PHASE1, PHASE2, PHASE3, etc.)"),
    status: str = typer.Option(None, "--status", help="Trial status (RECRUITING, COMPLETED, etc.)"),
    sponsor_class: str = typer.Option(None, "--sponsor-class", help="Sponsor type (INDUSTRY, NIH, ACADEMIC, etc.)"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results"),
):
    """Search ClinicalTrials.gov for clinical trials."""
    
    async def run_search():
        async with get_client() as client:
            console.print(f"[blue]Searching clinical trials: '{query}'[/blue]")
            
            args = {"query": query, "limit": limit}
            if condition:
                args["condition"] = condition
            if intervention:
                args["intervention"] = intervention
            if phase:
                args["phase"] = phase
            if status:
                args["status"] = status
            if sponsor_class:
                args["sponsor_class"] = sponsor_class
            
            response = await client.call_tool("clinicaltrials.search", args)
            display_response(response, "clinicaltrials.search")

    asyncio.run(run_search())


@app.command("clinicaltrials.get")
def clinicaltrials_get(
    nct_id: str = typer.Option(..., "--nct-id", help="ClinicalTrials.gov NCT ID"),
):
    """Get detailed information for a specific clinical trial."""
    
    async def run_get():
        async with get_client() as client:
            console.print(f"[blue]Retrieving clinical trial: {nct_id}[/blue]")
            
            response = await client.call_tool("clinicaltrials.get", {"nct_id": nct_id})
            display_response(response, "clinicaltrials.get")

    asyncio.run(run_get())


@app.command("clinicaltrials.investment_search")
def clinicaltrials_investment_search(
    query: str = typer.Option("", "--query", "-q", help="Search query for therapeutic areas"),
    min_score: float = typer.Option(0.5, "--min-score", help="Minimum investment relevance score (0.0-1.0)"),
    limit: int = typer.Option(25, "--limit", "-l", help="Maximum number of results"),
):
    """Search for investment-relevant clinical trials."""
    
    async def run_investment_search():
        async with get_client() as client:
            console.print(f"[blue]Investment search: '{query}' (min score: {min_score})[/blue]")
            
            response = await client.call_tool("clinicaltrials.investment_search", {
                "query": query,
                "min_investment_score": min_score,
                "limit": limit
            })
            display_response(response, "clinicaltrials.investment_search")

    asyncio.run(run_investment_search())


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[red]Interrupted by user[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
