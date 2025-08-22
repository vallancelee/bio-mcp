"""Decorators for observability instrumentation."""

import functools
import time
from collections.abc import Callable
from typing import Any

from .logging import get_structured_logger
from .metrics import get_global_collector


def observe_tool_invocation(func: Callable) -> Callable:
    """Decorator to observe tool invocations."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        tool_name = func.__name__
        collector = get_global_collector()
        logger = get_structured_logger("tool")

        # Start timing
        start_time = time.time()
        collector.increment_inflight(tool_name)

        try:
            # Execute function
            result = await func(*args, **kwargs)

            # Record success
            latency_ms = (time.time() - start_time) * 1000
            collector.increment_request(tool_name, "success")
            collector.record_latency(tool_name, latency_ms)

            logger.info(
                f"Tool {tool_name} completed successfully",
                tool=tool_name,
                status="success",
                latency_ms=latency_ms,
            )

            return result

        except Exception as e:
            # Record error
            latency_ms = (time.time() - start_time) * 1000
            error_type = type(e).__name__

            collector.increment_request(tool_name, "error")
            collector.increment_error(tool_name, error_type)
            collector.record_latency(tool_name, latency_ms)

            logger.error(
                f"Tool {tool_name} failed with {error_type}",
                tool=tool_name,
                status="error",
                error_type=error_type,
                latency_ms=latency_ms,
                error_message=str(e),
            )

            raise

        finally:
            collector.decrement_inflight(tool_name)

    return wrapper
