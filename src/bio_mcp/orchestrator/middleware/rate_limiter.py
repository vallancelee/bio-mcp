"""Token bucket rate limiter for API request throttling."""
import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


class TokenBucketRateLimiter:
    """Token bucket rate limiter for controlling request rates."""
    
    def __init__(self, capacity: int, refill_rate: float):
        """Initialize the token bucket rate limiter.
        
        Args:
            capacity: Maximum number of tokens the bucket can hold
            refill_rate: Rate at which tokens are added (tokens per second)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)  # Start with full bucket
        self._last_refill = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()
        
    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens from the bucket, waiting if necessary.
        
        Args:
            tokens: Number of tokens to acquire
            
        Raises:
            ValueError: If requesting more tokens than bucket capacity
        """
        if tokens > self.capacity:
            raise ValueError("Cannot acquire more tokens than bucket capacity")
            
        if tokens == 0:
            # Still need to potentially refill
            await self._refill()
            return
            
        async with self._lock:
            while True:
                await self._refill()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                
                # Calculate how long to wait for enough tokens
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.refill_rate
                
                # Wait for tokens to refill
                await asyncio.sleep(wait_time)
    
    async def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_refill
        
        if elapsed > 0:
            # Add tokens based on elapsed time
            tokens_to_add = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self._last_refill = now
    
    @asynccontextmanager
    async def acquire_tokens(self, tokens: int = 1) -> AsyncGenerator[None, None]:
        """Async context manager for token acquisition.
        
        Args:
            tokens: Number of tokens to acquire
            
        Yields:
            None
        """
        await self.acquire(tokens)
        try:
            yield
        finally:
            # Tokens are consumed - no cleanup needed
            pass
    
    def get_available_tokens(self) -> int:
        """Get the current number of available tokens (without refilling).
        
        Returns:
            Number of tokens currently available
        """
        return int(self.tokens)