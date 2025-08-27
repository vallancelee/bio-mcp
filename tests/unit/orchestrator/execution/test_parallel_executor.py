"""Test parallel execution coordinator."""

import asyncio

import pytest

from bio_mcp.orchestrator.execution.parallel_executor import ParallelExecutor
from bio_mcp.orchestrator.middleware.rate_limiter import TokenBucketRateLimiter
from bio_mcp.orchestrator.state import NodeResult


class TestParallelExecutor:
    """Test ParallelExecutor implementation."""

    @pytest.mark.asyncio
    async def test_init_parallel_executor(self):
        """Test parallel executor initialization."""
        rate_limiter = TokenBucketRateLimiter(capacity=10, refill_rate=5.0)
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=5)

        assert executor.rate_limiter == rate_limiter
        assert executor.max_concurrency == 5

    @pytest.mark.asyncio
    async def test_execute_single_task(self):
        """Test executing a single task."""
        rate_limiter = TokenBucketRateLimiter(capacity=10, refill_rate=5.0)
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=5)

        async def test_task(arg: str) -> NodeResult:
            return NodeResult(
                success=True, data={"result": f"processed_{arg}"}, node_name="test_task"
            )

        tasks = [{"func": test_task, "args": ("input1",), "kwargs": {}}]
        results = await executor.execute_parallel(tasks)

        assert len(results) == 1
        assert results[0].success
        assert results[0].data["result"] == "processed_input1"

    @pytest.mark.asyncio
    async def test_execute_multiple_tasks_parallel(self):
        """Test executing multiple tasks in parallel."""
        rate_limiter = TokenBucketRateLimiter(capacity=10, refill_rate=10.0)
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=3)

        async def test_task(arg: str, delay: float = 0.01) -> NodeResult:
            await asyncio.sleep(delay)
            return NodeResult(
                success=True, data={"result": f"processed_{arg}"}, node_name="test_task"
            )

        tasks = [
            {"func": test_task, "args": ("task1",), "kwargs": {"delay": 0.05}},
            {"func": test_task, "args": ("task2",), "kwargs": {"delay": 0.05}},
            {"func": test_task, "args": ("task3",), "kwargs": {"delay": 0.05}},
        ]

        start_time = asyncio.get_event_loop().time()
        results = await executor.execute_parallel(tasks)
        end_time = asyncio.get_event_loop().time()

        # Should execute in parallel (not sequentially)
        execution_time = end_time - start_time
        assert execution_time < 0.1  # Much less than 0.15 (3 * 0.05) if sequential

        assert len(results) == 3
        assert all(result.success for result in results)
        assert {result.data["result"] for result in results} == {
            "processed_task1",
            "processed_task2",
            "processed_task3",
        }

    @pytest.mark.asyncio
    async def test_rate_limiting_applied(self):
        """Test that rate limiting is applied to task execution."""
        # Very restrictive rate limiter
        rate_limiter = TokenBucketRateLimiter(
            capacity=1, refill_rate=2.0
        )  # 2 tokens per second
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=5)

        async def test_task(arg: str) -> NodeResult:
            return NodeResult(success=True, data={"task": arg}, node_name="test_task")

        tasks = [
            {"func": test_task, "args": ("task1",), "kwargs": {}},
            {"func": test_task, "args": ("task2",), "kwargs": {}},
            {"func": test_task, "args": ("task3",), "kwargs": {}},
        ]

        start_time = asyncio.get_event_loop().time()
        results = await executor.execute_parallel(tasks)
        end_time = asyncio.get_event_loop().time()

        # Should be rate limited - expect some delay
        execution_time = end_time - start_time
        assert (
            execution_time >= 0.5
        )  # At least some significant delay due to rate limiting

        assert len(results) == 3
        assert all(result.success for result in results)

    @pytest.mark.asyncio
    async def test_concurrency_limiting(self):
        """Test that maximum concurrency is respected."""
        rate_limiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=20.0
        )  # Very permissive
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=2)

        concurrent_count = 0
        max_concurrent = 0

        async def test_task(arg: str) -> NodeResult:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)

            await asyncio.sleep(0.1)  # Hold concurrency slot

            concurrent_count -= 1
            return NodeResult(success=True, data={"task": arg}, node_name="test_task")

        tasks = [
            {"func": test_task, "args": (f"task{i}",), "kwargs": {}} for i in range(5)
        ]

        results = await executor.execute_parallel(tasks)

        # Should not have exceeded max concurrency
        assert max_concurrent <= 2
        assert len(results) == 5
        assert all(result.success for result in results)

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test handling of task errors."""
        rate_limiter = TokenBucketRateLimiter(capacity=10, refill_rate=10.0)
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=5)

        async def success_task() -> NodeResult:
            return NodeResult(
                success=True, data={"status": "ok"}, node_name="success_task"
            )

        async def error_task() -> NodeResult:
            raise ValueError("Task failed")

        tasks = [
            {"func": success_task, "args": (), "kwargs": {}},
            {"func": error_task, "args": (), "kwargs": {}},
            {"func": success_task, "args": (), "kwargs": {}},
        ]

        results = await executor.execute_parallel(tasks)

        assert len(results) == 3
        assert results[0].success
        assert not results[1].success  # Should capture error
        assert "Task failed" in results[1].error_message
        assert results[2].success

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """Test task execution with timeout."""
        rate_limiter = TokenBucketRateLimiter(capacity=10, refill_rate=10.0)
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=5)

        async def slow_task() -> NodeResult:
            await asyncio.sleep(0.2)  # Longer than timeout
            return NodeResult(
                success=True, data={"result": "slow"}, node_name="slow_task"
            )

        async def fast_task() -> NodeResult:
            await asyncio.sleep(0.01)
            return NodeResult(
                success=True, data={"result": "fast"}, node_name="fast_task"
            )

        tasks = [
            {"func": slow_task, "args": (), "kwargs": {}},
            {"func": fast_task, "args": (), "kwargs": {}},
        ]

        results = await executor.execute_parallel(tasks, timeout=0.1)

        assert len(results) == 2
        assert not results[0].success  # Should timeout
        assert "timed out" in results[0].error_message.lower()
        assert results[1].success  # Should complete in time

    @pytest.mark.asyncio
    async def test_custom_token_cost(self):
        """Test tasks with custom token costs."""
        rate_limiter = TokenBucketRateLimiter(capacity=5, refill_rate=10.0)
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=5)

        async def expensive_task() -> NodeResult:
            return NodeResult(
                success=True, data={"cost": "high"}, node_name="expensive_task"
            )

        async def cheap_task() -> NodeResult:
            return NodeResult(
                success=True, data={"cost": "low"}, node_name="cheap_task"
            )

        tasks = [
            {"func": expensive_task, "args": (), "kwargs": {}, "token_cost": 3},
            {"func": cheap_task, "args": (), "kwargs": {}, "token_cost": 1},
            {"func": expensive_task, "args": (), "kwargs": {}, "token_cost": 3},
        ]

        start_time = asyncio.get_event_loop().time()
        results = await executor.execute_parallel(tasks)
        end_time = asyncio.get_event_loop().time()

        # Should be rate limited due to high token costs
        execution_time = end_time - start_time
        assert execution_time >= 0.05  # Some delay expected

        assert len(results) == 3
        assert all(result.success for result in results)

    @pytest.mark.asyncio
    async def test_empty_task_list(self):
        """Test executing empty task list."""
        rate_limiter = TokenBucketRateLimiter(capacity=10, refill_rate=10.0)
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=5)

        results = await executor.execute_parallel([])

        assert results == []
