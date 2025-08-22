"""Tests for back-pressure and concurrency control (T6)."""

import asyncio
import time

import pytest


class TestGlobalConcurrencyLimits:
    """Test global concurrency limit enforcement."""

    @pytest.mark.asyncio
    async def test_global_limit_enforcement(self):
        """Test global concurrent request limit."""
        from bio_mcp.http.concurrency.manager import ConcurrencyManager

        manager = ConcurrencyManager(max_concurrent_total=3)

        # Use a barrier to keep operations running concurrently
        barrier = asyncio.Event()

        async def mock_operation():
            async with manager.acquire_global():
                await barrier.wait()  # Wait for signal
                return "success"

        # Start 3 concurrent operations (should succeed)
        tasks = [asyncio.create_task(mock_operation()) for _ in range(3)]

        # Let them acquire their slots
        await asyncio.sleep(0.01)

        # The 4th operation should be rejected
        start_time = time.time()
        with pytest.raises(Exception) as exc_info:
            async with manager.acquire_global():
                pass

        # Should fail quickly (not wait)
        elapsed = time.time() - start_time
        assert elapsed < 0.05  # Should reject immediately
        assert "concurrent request limit" in str(exc_info.value)

        # Release the operations
        barrier.set()
        results = await asyncio.gather(*tasks)
        assert all(r == "success" for r in results)

    @pytest.mark.asyncio
    async def test_429_response_format(self):
        """Test 429 response includes Retry-After header."""
        from bio_mcp.http.concurrency.exceptions import RateLimitExceededError
        from bio_mcp.http.concurrency.manager import ConcurrencyManager

        manager = ConcurrencyManager(max_concurrent_total=1, max_queue_depth=0)

        # Fill the slot
        async with manager.acquire_global():
            # Try to acquire another (should fail with proper format)
            try:
                async with manager.acquire_global():
                    pass
                assert False, "Should have raised RateLimitExceeded"
            except RateLimitExceededError as e:
                error_data = e.to_dict()

                assert error_data["ok"] is False
                assert error_data["error_code"] == "RATE_LIMIT_EXCEEDED"
                assert "retry_after" in error_data
                assert "queue_depth" in error_data
                assert error_data["retry_after"] > 0

    @pytest.mark.asyncio
    async def test_queue_overflow_error_format(self):
        """Test queue overflow returns proper error format."""
        from bio_mcp.http.concurrency.exceptions import RateLimitExceededError

        # Simple test: create exception with queue full message
        exc = RateLimitExceededError(
            "Queue full - request rejected", retry_after=1, queue_depth=5
        )

        error_data = exc.to_dict()
        assert error_data["ok"] is False
        assert error_data["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert "queue full" in error_data["message"].lower()
        assert error_data["queue_depth"] == 5


class TestPerToolSemaphores:
    """Test per-tool semaphore behavior."""

    @pytest.mark.asyncio
    async def test_independent_tool_limits(self):
        """Test independent limits for different tools."""
        from bio_mcp.http.concurrency.manager import ConcurrencyManager

        tool_limits = {
            "rag.search": {"max_concurrent": 2, "timeout_ms": 100},
            "pubmed.sync": {"max_concurrent": 1, "timeout_ms": 100},
        }
        manager = ConcurrencyManager(tool_limits=tool_limits)

        # rag.search should allow 2 concurrent
        async def rag_operation():
            async with manager.acquire_tool("rag.search"):
                await asyncio.sleep(0.1)
                return "rag_success"

        tasks = [rag_operation() for _ in range(2)]
        results = await asyncio.gather(*tasks)
        assert all(r == "rag_success" for r in results)

        # pubmed.sync should allow only 1 concurrent
        barrier = asyncio.Event()

        async def pubmed_operation():
            async with manager.acquire_tool("pubmed.sync"):
                await barrier.wait()
                return "pubmed_success"

        # Start first pubmed operation
        task1 = asyncio.create_task(pubmed_operation())
        await asyncio.sleep(0.01)

        # Second should be rejected
        with pytest.raises(Exception):
            async with manager.acquire_tool("pubmed.sync"):
                pass

        # Cleanup
        barrier.set()
        await task1

    @pytest.mark.asyncio
    async def test_semaphore_release_on_success_and_failure(self):
        """Test semaphore release on success and failure."""
        from bio_mcp.http.concurrency.manager import ConcurrencyManager

        manager = ConcurrencyManager(
            tool_limits={"test.tool": {"max_concurrent": 1, "timeout_ms": 100}}
        )

        # Test successful release
        async with manager.acquire_tool("test.tool"):
            pass  # Should release properly

        # Should be able to acquire again
        async with manager.acquire_tool("test.tool"):
            pass

        # Test failure release
        try:
            async with manager.acquire_tool("test.tool"):
                raise ValueError("Simulated error")
        except ValueError:
            pass  # Expected

        # Should still be able to acquire again (semaphore released)
        async with manager.acquire_tool("test.tool"):
            pass

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling doesn't leak semaphore permits."""
        from bio_mcp.http.concurrency.manager import ConcurrencyManager

        manager = ConcurrencyManager(
            tool_limits={"test.tool": {"max_concurrent": 1, "timeout_ms": 100}}
        )

        barrier = asyncio.Event()

        # Fill the semaphore
        async def blocking_operation():
            async with manager.acquire_tool("test.tool"):
                await barrier.wait()

        task = asyncio.create_task(blocking_operation())
        await asyncio.sleep(0.01)

        # This should timeout
        with pytest.raises(asyncio.TimeoutError):
            async with manager.acquire_tool("test.tool"):
                pass

        # Release the blocker
        barrier.set()
        await task

        # Should be able to acquire now (no leak)
        async with manager.acquire_tool("test.tool"):
            pass


class TestCircuitBreaker:
    """Test circuit breaker behavior."""

    @pytest.mark.asyncio
    async def test_circuit_opens_on_errors(self):
        """Test circuit opens at error threshold."""
        from bio_mcp.http.concurrency.circuit import CircuitBreaker

        breaker = CircuitBreaker(
            failure_threshold=0.5,  # 50% error rate
            min_requests=4,
            timeout_ms=100,  # Short timeout for testing
        )

        # Generate failures to trip circuit
        for _ in range(2):
            await breaker.record_success()
        for _ in range(2):
            await breaker.record_failure()

        # Circuit should be open
        assert breaker.state == "open"

        # Should reject requests
        with pytest.raises(Exception) as exc_info:
            async with breaker:
                pass
        assert "circuit breaker is open" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_circuit_half_open_recovery(self):
        """Test gradual recovery in half-open state."""
        from bio_mcp.http.concurrency.circuit import CircuitBreaker

        breaker = CircuitBreaker(
            failure_threshold=0.5,
            min_requests=2,
            timeout_ms=10,  # Short timeout for testing
        )

        # Trip the circuit
        await breaker.record_failure()
        await breaker.record_failure()
        assert breaker.state == "open"

        # Wait for timeout
        await asyncio.sleep(0.02)

        # Should be half-open
        assert breaker.state == "half_open"

        # Success should close circuit
        async with breaker:
            await breaker.record_success()

        assert breaker.state == "closed"

    @pytest.mark.asyncio
    async def test_per_tool_circuit_isolation(self):
        """Test independent circuit breakers per tool."""
        from bio_mcp.http.concurrency.manager import ConcurrencyManager

        manager = ConcurrencyManager(
            circuit_breaker_enabled=True, circuit_breaker_threshold=0.5
        )

        # Trip circuit for one tool
        for _ in range(5):
            manager.record_tool_failure("failing.tool", "ERROR")

        # Should block failing tool (circuit may be open or half_open)
        with pytest.raises(Exception) as exc_info:
            async with manager.acquire_tool("failing.tool"):
                pass

        # Verify it's a circuit breaker error
        assert "circuit breaker" in str(exc_info.value).lower()

        # But allow other tools
        async with manager.acquire_tool("working.tool"):
            pass


class TestBackPressureIntegration:
    """Test complete back-pressure system."""

    @pytest.mark.asyncio
    async def test_mixed_tool_load(self):
        """Test system handles mixed tool load correctly."""
        from bio_mcp.http.concurrency.manager import ConcurrencyManager

        tool_limits = {
            "fast.tool": {"max_concurrent": 5, "priority": 1, "timeout_ms": 100},
            "slow.tool": {"max_concurrent": 2, "priority": 2, "timeout_ms": 100},
        }
        manager = ConcurrencyManager(max_concurrent_total=4, tool_limits=tool_limits)

        results = []

        async def fast_operation():
            async with manager.acquire_tool("fast.tool"):
                await asyncio.sleep(0.01)
                results.append("fast")

        async def slow_operation():
            async with manager.acquire_tool("slow.tool"):
                await asyncio.sleep(0.05)
                results.append("slow")

        # Mix of fast and slow operations
        tasks = []
        tasks.extend([fast_operation() for _ in range(3)])
        tasks.extend([slow_operation() for _ in range(2)])

        await asyncio.gather(*tasks)

        # Should have completed all operations
        assert len(results) == 5
        assert results.count("fast") == 3
        assert results.count("slow") == 2

    @pytest.mark.asyncio
    async def test_graceful_degradation_under_load(self):
        """Test system degrades gracefully under overload."""
        from bio_mcp.http.concurrency.manager import ConcurrencyManager

        manager = ConcurrencyManager(max_concurrent_total=2, max_queue_depth=3)

        successful_ops = 0
        rejected_ops = 0

        async def operation():
            nonlocal successful_ops
            try:
                async with manager.acquire_global():
                    await asyncio.sleep(0.01)
                    successful_ops += 1
            except Exception:
                nonlocal rejected_ops
                rejected_ops += 1

        # Generate heavy load
        tasks = [operation() for _ in range(10)]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Should have processed some and rejected some
        assert successful_ops > 0
        assert rejected_ops > 0
        assert successful_ops + rejected_ops == 10
