"""Tests for async/sync tool adapter."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from bio_mcp.http.adapters import invoke_tool_safely, is_async_callable


class TestAsyncDetection:
    """Test async vs sync callable detection."""
    
    def test_detects_sync_function(self):
        """Test that sync functions are correctly identified."""
        def sync_func(name: str, args: dict) -> str:
            return "sync result"
        
        assert not is_async_callable(sync_func)
    
    def test_detects_async_function(self):
        """Test that async functions are correctly identified."""
        async def async_func(name: str, args: dict) -> str:
            return "async result"
        
        assert is_async_callable(async_func)
    
    def test_detects_sync_lambda(self):
        """Test that sync lambdas are correctly identified."""
        def sync_lambda(name, args):
            return "lambda result"
        
        assert not is_async_callable(sync_lambda)
    
    def test_detects_async_mock(self):
        """Test that async mocks are correctly identified."""
        async_mock = AsyncMock()
        
        assert is_async_callable(async_mock)
    
    def test_detects_sync_mock(self):
        """Test that sync mocks are correctly identified."""
        sync_mock = Mock()
        
        assert not is_async_callable(sync_mock)


class TestToolInvocation:
    """Test safe tool invocation with async/sync handling."""
    
    @pytest.mark.asyncio
    async def test_invoke_sync_tool_safely(self):
        """Test that sync tools are wrapped with anyio.to_thread."""
        def sync_tool(name: str, args: dict) -> dict:
            return {"message": f"sync tool {name}", "args": args}
        
        result = await invoke_tool_safely(
            tool_func=sync_tool,
            tool_name="test.sync",
            params={"param1": "value1"},
            trace_id="test-trace-123"
        )
        
        assert result["message"] == "sync tool test.sync"
        assert result["args"]["param1"] == "value1"
    
    @pytest.mark.asyncio
    async def test_invoke_async_tool_safely(self):
        """Test that async tools are awaited directly."""
        async def async_tool(name: str, args: dict) -> dict:
            return {"message": f"async tool {name}", "args": args}
        
        result = await invoke_tool_safely(
            tool_func=async_tool,
            tool_name="test.async", 
            params={"param1": "value1"},
            trace_id="test-trace-456"
        )
        
        assert result["message"] == "async tool test.async"
        assert result["args"]["param1"] == "value1"
    
    @pytest.mark.asyncio
    async def test_invoke_sync_tool_with_exception(self):
        """Test that sync tool exceptions are properly handled."""
        def failing_sync_tool(name: str, args: dict) -> dict:
            raise ValueError("Sync tool failed")
        
        with pytest.raises(ValueError, match="Sync tool failed"):
            await invoke_tool_safely(
                tool_func=failing_sync_tool,
                tool_name="test.failing.sync",
                params={},
                trace_id="test-trace-error"
            )
    
    @pytest.mark.asyncio  
    async def test_invoke_async_tool_with_exception(self):
        """Test that async tool exceptions are properly handled."""
        async def failing_async_tool(name: str, args: dict) -> dict:
            raise ValueError("Async tool failed")
        
        with pytest.raises(ValueError, match="Async tool failed"):
            await invoke_tool_safely(
                tool_func=failing_async_tool,
                tool_name="test.failing.async",
                params={},
                trace_id="test-trace-error"
            )
    
    @pytest.mark.asyncio
    async def test_invoke_with_mock_tools(self):
        """Test invocation with mock tools for different scenarios."""
        # Sync mock
        sync_mock = Mock(return_value={"sync": "response"})
        result = await invoke_tool_safely(sync_mock, "mock.sync", {}, "trace-1")
        assert result == {"sync": "response"}
        sync_mock.assert_called_once_with("mock.sync", {})
        
        # Async mock
        async_mock = AsyncMock(return_value={"async": "response"})
        result = await invoke_tool_safely(async_mock, "mock.async", {}, "trace-2")
        assert result == {"async": "response"}
        async_mock.assert_called_once_with("mock.async", {})


class TestConcurrentInvocation:
    """Test concurrent tool invocation scenarios."""
    
    @pytest.mark.asyncio
    async def test_concurrent_sync_tools(self):
        """Test multiple sync tools can be invoked concurrently."""
        def slow_sync_tool(name: str, args: dict) -> dict:
            import time
            time.sleep(0.1)  # Simulate work
            return {"tool": name, "result": "completed"}
        
        # Invoke multiple sync tools concurrently
        tasks = [
            invoke_tool_safely(slow_sync_tool, f"tool.{i}", {}, f"trace-{i}")
            for i in range(3)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["tool"] == f"tool.{i}"
            assert result["result"] == "completed"
    
    @pytest.mark.asyncio
    async def test_concurrent_mixed_tools(self):
        """Test mixing sync and async tools in concurrent execution."""
        def sync_tool(name: str, args: dict) -> dict:
            return {"type": "sync", "name": name}
        
        async def async_tool(name: str, args: dict) -> dict:
            await asyncio.sleep(0.01)  # Simulate async work
            return {"type": "async", "name": name}
        
        # Mix sync and async tools
        tasks = [
            invoke_tool_safely(sync_tool, "sync.tool", {}, "trace-sync"),
            invoke_tool_safely(async_tool, "async.tool", {}, "trace-async"),
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 2
        sync_result = next(r for r in results if r["type"] == "sync")
        async_result = next(r for r in results if r["type"] == "async")
        
        assert sync_result["name"] == "sync.tool"
        assert async_result["name"] == "async.tool"