"""MCP tool adapter for orchestrator integration."""
import asyncio
from datetime import UTC, datetime
from typing import Any

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import NodeResult


class MCPToolAdapter:
    """Adapter for MCP tool integration with caching and fallback patterns."""
    
    def __init__(self, config: OrchestratorConfig, db_manager: Any):
        """Initialize the MCP tool adapter.
        
        Args:
            config: Orchestrator configuration
            db_manager: Database manager for tool data access
        """
        self.config = config
        self.db_manager = db_manager
        self._tools: dict[str, Any] = {}
        self.cache: Any | None = None
    
    async def execute_tool(
        self, 
        tool_name: str, 
        args: dict[str, Any], 
        cache_policy: str = "cache_then_network"
    ) -> NodeResult:
        """Execute a single MCP tool with caching support.
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments to pass to the tool
            cache_policy: Caching policy ("cache_then_network", "cache_only", "network_only")
            
        Returns:
            NodeResult with execution results
        """
        start_time = datetime.now(UTC)
        
        # TODO: Implement caching when cache backend is available
        # For now, cache policies are ignored and we always execute directly
        
        # Check if tool exists (after cache checks)
        if tool_name not in self._tools:
            return NodeResult(
                success=False,
                error_code="TOOL_NOT_FOUND",
                error_message=f"Tool {tool_name} not available",
                latency_ms=int((datetime.now(UTC) - start_time).total_seconds() * 1000),
                cache_hit=False,
                node_name=tool_name
            )
        
        # Execute tool directly
        tool = self._tools[tool_name]
        try:
            result = await tool.execute(args)
            
            return NodeResult(
                success=True,
                data=result,
                latency_ms=int((datetime.now(UTC) - start_time).total_seconds() * 1000),
                cache_hit=False,
                node_name=tool_name
            )
            
        except Exception as e:
            return NodeResult(
                success=False,
                error_code="EXECUTION_ERROR",
                error_message=str(e),
                latency_ms=int((datetime.now(UTC) - start_time).total_seconds() * 1000),
                cache_hit=False,
                node_name=tool_name
            )
    
    async def batch_execute(
        self, 
        tool_calls: list[dict[str, Any]], 
        max_concurrency: int = 5
    ) -> list[NodeResult]:
        """Execute multiple MCP tools concurrently.
        
        Args:
            tool_calls: List of tool call specifications
            max_concurrency: Maximum concurrent executions
            
        Returns:
            List of NodeResult objects
        """
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def execute_with_semaphore(tool_call: dict[str, Any]) -> NodeResult:
            async with semaphore:
                return await self.execute_tool(
                    tool_call["tool"], 
                    tool_call["args"]
                )
        
        tasks = [execute_with_semaphore(call) for call in tool_calls]
        return await asyncio.gather(*tasks)
    
