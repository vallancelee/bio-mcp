"""Async-safe tool adapter for HTTP endpoints."""

import inspect
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import anyio


def is_async_callable(func: Callable) -> bool:
    """Check if a callable is async (coroutine function or async mock).

    Args:
        func: The callable to check

    Returns:
        True if the callable is async, False otherwise
    """
    # Check for AsyncMock first (before inspect.iscoroutinefunction)
    if isinstance(func, AsyncMock):
        return True

    # Check if it's a coroutine function
    return inspect.iscoroutinefunction(func)


async def invoke_tool_safely(
    tool_func: Callable, tool_name: str, params: dict[str, Any], trace_id: str
) -> Any:
    """Safely invoke a tool with async/sync detection and proper execution.

    Args:
        tool_func: The tool function to invoke
        tool_name: Name of the tool being invoked
        params: Parameters to pass to the tool
        trace_id: Trace ID for request correlation

    Returns:
        The result of the tool execution

    Raises:
        Any exception raised by the tool function
    """
    if is_async_callable(tool_func):
        # Async tool - await directly
        return await tool_func(tool_name, params)
    else:
        # Sync tool - run in thread pool to avoid blocking
        return await anyio.to_thread.run_sync(tool_func, tool_name, params)
