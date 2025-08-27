"""Parallel execution coordinator with rate limiting."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from bio_mcp.orchestrator.middleware.rate_limiter import TokenBucketRateLimiter
from bio_mcp.orchestrator.state import NodeResult


class ParallelExecutor:
    """Coordinator for parallel task execution with rate limiting and concurrency control."""

    def __init__(self, rate_limiter: TokenBucketRateLimiter, max_concurrency: int = 5):
        """Initialize the parallel executor.

        Args:
            rate_limiter: Token bucket rate limiter for throttling
            max_concurrency: Maximum number of concurrent tasks
        """
        self.rate_limiter = rate_limiter
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def execute_parallel(
        self, tasks: list[dict[str, Any]], timeout: float | None = None
    ) -> list[NodeResult]:
        """Execute multiple tasks in parallel with rate limiting.

        Args:
            tasks: List of task specifications with 'func', 'args', 'kwargs', and optional 'token_cost'
            timeout: Optional timeout for individual tasks (in seconds)

        Returns:
            List of NodeResult objects from task execution
        """
        if not tasks:
            return []

        # Create coroutines for all tasks
        task_coroutines = [self._execute_single_task(task, timeout) for task in tasks]

        # Execute all tasks concurrently
        results = await asyncio.gather(*task_coroutines, return_exceptions=True)

        # Convert any exceptions to NodeResult errors
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    NodeResult(
                        success=False,
                        error_code="EXECUTION_ERROR",
                        error_message=str(result),
                        node_name=f"task_{i}",
                        latency_ms=0.0,
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    async def _execute_single_task(
        self, task: dict[str, Any], timeout: float | None = None
    ) -> NodeResult:
        """Execute a single task with rate limiting and concurrency control.

        Args:
            task: Task specification with 'func', 'args', 'kwargs', and optional 'token_cost'
            timeout: Optional timeout for the task

        Returns:
            NodeResult from task execution
        """
        start_time = datetime.now(UTC)

        try:
            # Extract task parameters
            func: Callable = task["func"]
            args: tuple = task.get("args", ())
            kwargs: dict = task.get("kwargs", {})
            token_cost: int = task.get("token_cost", 1)

            # Acquire rate limiting tokens
            await self.rate_limiter.acquire(token_cost)

            # Acquire concurrency semaphore
            async with self._semaphore:
                # Execute the task with optional timeout
                if timeout:
                    try:
                        result = await asyncio.wait_for(
                            func(*args, **kwargs), timeout=timeout
                        )
                    except TimeoutError:
                        return NodeResult(
                            success=False,
                            error_code="TIMEOUT",
                            error_message=f"Task timed out after {timeout} seconds",
                            node_name=getattr(func, "__name__", "unknown"),
                            latency_ms=int(
                                (datetime.now(UTC) - start_time).total_seconds() * 1000
                            ),
                        )
                else:
                    result = await func(*args, **kwargs)

                # Update latency if result doesn't have it set
                if hasattr(result, "latency_ms") and result.latency_ms == 0.0:
                    result.latency_ms = int(
                        (datetime.now(UTC) - start_time).total_seconds() * 1000
                    )

                return result

        except Exception as e:
            return NodeResult(
                success=False,
                error_code="EXECUTION_ERROR",
                error_message=str(e),
                node_name=getattr(task.get("func"), "__name__", "unknown"),
                latency_ms=int((datetime.now(UTC) - start_time).total_seconds() * 1000),
            )
