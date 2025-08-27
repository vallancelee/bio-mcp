"""Test token bucket rate limiter."""

import asyncio
from unittest.mock import patch

import pytest

from bio_mcp.orchestrator.middleware.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    """Test TokenBucketRateLimiter implementation."""

    @pytest.mark.asyncio
    async def test_init_rate_limiter(self):
        """Test rate limiter initialization."""
        limiter = TokenBucketRateLimiter(capacity=10, refill_rate=5.0)

        assert limiter.capacity == 10
        assert limiter.refill_rate == 5.0
        assert limiter.tokens == 10  # starts full

    @pytest.mark.asyncio
    async def test_acquire_tokens_success(self):
        """Test successful token acquisition."""
        limiter = TokenBucketRateLimiter(capacity=10, refill_rate=5.0)

        # Should be able to acquire tokens immediately
        start_time = asyncio.get_event_loop().time()
        await limiter.acquire(3)
        end_time = asyncio.get_event_loop().time()

        # Should not have blocked
        assert end_time - start_time < 0.1
        assert limiter.tokens == 7

    @pytest.mark.asyncio
    async def test_acquire_tokens_with_waiting(self):
        """Test token acquisition with rate limiting delay."""
        limiter = TokenBucketRateLimiter(
            capacity=5, refill_rate=10.0
        )  # 10 tokens per second

        # Consume all tokens
        await limiter.acquire(5)
        assert limiter.tokens == 0

        # Next acquisition should wait for refill
        start_time = asyncio.get_event_loop().time()
        await limiter.acquire(1)
        end_time = asyncio.get_event_loop().time()

        # Should have waited approximately 0.1 seconds (1 token / 10 per second)
        wait_time = end_time - start_time
        assert wait_time >= 0.05  # allow some margin
        assert wait_time <= 0.2  # but not too long

    @pytest.mark.asyncio
    async def test_acquire_more_than_capacity(self):
        """Test acquiring more tokens than bucket capacity."""
        limiter = TokenBucketRateLimiter(capacity=5, refill_rate=10.0)

        with pytest.raises(
            ValueError, match="Cannot acquire more tokens than bucket capacity"
        ):
            await limiter.acquire(10)

    @pytest.mark.asyncio
    async def test_acquire_zero_tokens(self):
        """Test acquiring zero tokens."""
        limiter = TokenBucketRateLimiter(capacity=5, refill_rate=10.0)
        initial_tokens = limiter.tokens

        await limiter.acquire(0)

        # Should not change token count
        assert limiter.tokens == initial_tokens

    @pytest.mark.asyncio
    async def test_refill_tokens(self):
        """Test token refill over time."""
        limiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=20.0
        )  # 20 tokens per second

        # Consume 5 tokens
        await limiter.acquire(5)
        assert limiter.tokens == 5

        # Mock time to simulate passage
        with patch("asyncio.get_event_loop") as mock_loop:
            # Simulate 0.25 seconds passing (should add 5 tokens: 20 * 0.25)
            mock_loop.return_value.time.return_value = limiter._last_refill + 0.25

            # Trigger refill by acquiring 0 tokens
            await limiter.acquire(0)

            # Should have refilled to capacity (5 + 5 = 10)
            assert limiter.tokens == 10

    @pytest.mark.asyncio
    async def test_refill_does_not_exceed_capacity(self):
        """Test that refill doesn't exceed bucket capacity."""
        limiter = TokenBucketRateLimiter(capacity=5, refill_rate=10.0)

        # Start with full bucket, wait long time
        assert limiter.tokens == 5

        with patch("asyncio.get_event_loop") as mock_loop:
            # Simulate 1 second passing (would add 10 tokens, but capacity is 5)
            mock_loop.return_value.time.return_value = limiter._last_refill + 1.0

            await limiter.acquire(0)

            # Should still be at capacity
            assert limiter.tokens == 5

    @pytest.mark.asyncio
    async def test_concurrent_acquisitions(self):
        """Test concurrent token acquisitions."""
        limiter = TokenBucketRateLimiter(capacity=10, refill_rate=20.0)

        async def acquire_task(tokens: int) -> float:
            start = asyncio.get_event_loop().time()
            await limiter.acquire(tokens)
            return asyncio.get_event_loop().time() - start

        # Launch concurrent acquisitions that together exceed capacity
        tasks = [
            acquire_task(3),  # immediate
            acquire_task(3),  # immediate
            acquire_task(3),  # immediate
            acquire_task(2),  # should wait (total would be 11 > 10 capacity)
        ]

        wait_times = await asyncio.gather(*tasks)

        # First 3 should be immediate, last one should wait
        assert all(t < 0.1 for t in wait_times[:3])  # immediate
        assert wait_times[3] >= 0.05  # had to wait

    @pytest.mark.asyncio
    async def test_rate_limiter_context_manager(self):
        """Test rate limiter as async context manager."""
        limiter = TokenBucketRateLimiter(capacity=5, refill_rate=10.0)

        async with limiter.acquire_tokens(2):
            # Tokens should be consumed
            assert limiter.tokens == 3

        # Should still have consumed tokens after exiting context
        assert limiter.tokens == 3

    @pytest.mark.asyncio
    async def test_get_available_tokens(self):
        """Test getting current available token count."""
        limiter = TokenBucketRateLimiter(capacity=8, refill_rate=4.0)

        assert limiter.get_available_tokens() == 8

        await limiter.acquire(3)
        assert limiter.get_available_tokens() == 5
