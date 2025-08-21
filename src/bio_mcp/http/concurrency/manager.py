"""Central concurrency coordinator."""

import asyncio
import heapq
from contextlib import asynccontextmanager
from typing import Any

from .circuit import CircuitBreaker
from .exceptions import RateLimitExceededError


class PriorityQueue:
    """Priority queue for request scheduling."""
    
    def __init__(self):
        self._queue = []
        self._index = 0
        self._lock = asyncio.Lock()
    
    async def put(self, priority: int, item: Any):
        """Add item with priority."""
        async with self._lock:
            heapq.heappush(self._queue, (priority, self._index, item))
            self._index += 1
    
    async def get(self):
        """Get highest priority item."""
        async with self._lock:
            if not self._queue:
                raise asyncio.QueueEmpty()
            _, _, item = heapq.heappop(self._queue)
            return item
    
    def qsize(self) -> int:
        """Get queue size."""
        return len(self._queue)


class ConcurrencyManager:
    """Manage concurrency limits and back-pressure."""
    
    def __init__(
        self,
        max_concurrent_total: int = 100,
        max_queue_depth: int = 500,
        tool_limits: dict[str, dict[str, Any]] | None = None,
        circuit_breaker_enabled: bool = False,
        circuit_breaker_threshold: float = 0.5
    ):
        self.max_concurrent_total = max_concurrent_total
        self.max_queue_depth = max_queue_depth
        self.tool_limits = tool_limits or {}
        self.circuit_breaker_enabled = circuit_breaker_enabled
        self.circuit_breaker_threshold = circuit_breaker_threshold
        
        # Global semaphore and queue
        self.global_semaphore = asyncio.Semaphore(max_concurrent_total)
        self.global_queue = PriorityQueue()
        self.global_active = 0
        self.queued_count = 0  # Track queued requests
        
        # Per-tool semaphores and circuit breakers
        self.tool_semaphores = {}
        self.tool_circuit_breakers = {}
        self.tool_failure_counts = {}
        
        # Initialize tool semaphores
        for tool, config in self.tool_limits.items():
            max_concurrent = config.get("max_concurrent", 10)
            self.tool_semaphores[tool] = asyncio.Semaphore(max_concurrent)
            
            if circuit_breaker_enabled:
                self.tool_circuit_breakers[tool] = CircuitBreaker(
                    failure_threshold=circuit_breaker_threshold
                )
            self.tool_failure_counts[tool] = 0
    
    @asynccontextmanager
    async def acquire_global(self):
        """Acquire global concurrency slot."""
        # Track requests that would be queued
        if self.global_semaphore._value == 0:
            if hasattr(self, '_current_queue_size'):
                self._current_queue_size += 1
            else:
                self._current_queue_size = 1
                
            try:
                if self._current_queue_size > self.max_queue_depth:
                    raise RateLimitExceededError(
                        "Queue full - request rejected",
                        retry_after=1,
                        queue_depth=self._current_queue_size - 1
                    )
                else:
                    raise RateLimitExceededError(
                        f"Global concurrent request limit ({self.max_concurrent_total}) exceeded",
                        retry_after=1,
                        queue_depth=self._current_queue_size
                    )
            finally:
                self._current_queue_size -= 1
        
        # Use standard semaphore context manager
        async with self.global_semaphore:
            yield
    
    @asynccontextmanager 
    async def acquire_tool(self, tool_name: str):
        """Acquire per-tool concurrency slot."""
        # Check circuit breaker first
        if self.circuit_breaker_enabled:
            # Create circuit breaker if it doesn't exist
            if tool_name not in self.tool_circuit_breakers:
                self.tool_circuit_breakers[tool_name] = CircuitBreaker(
                    failure_threshold=self.circuit_breaker_threshold
                )
            
            circuit = self.tool_circuit_breakers[tool_name]
            if circuit.state in ["open", "half_open"]:
                raise Exception(f"Circuit breaker {circuit.state} for tool {tool_name}")
        
        # Get or create semaphore for this tool
        if tool_name not in self.tool_semaphores:
            # Use default limits for unknown tools
            tool_config = {"max_concurrent": 10, "timeout_ms": 30000}
            self.tool_semaphores[tool_name] = asyncio.Semaphore(10)
        else:
            tool_config = self.tool_limits.get(tool_name, {"max_concurrent": 10, "timeout_ms": 30000})
        
        semaphore = self.tool_semaphores[tool_name]
        timeout_ms = tool_config.get("timeout_ms", 30000)
        timeout_s = timeout_ms / 1000
        
        try:
            # Try to acquire with timeout - this will wait if semaphore is busy
            await asyncio.wait_for(semaphore.acquire(), timeout=timeout_s)
            try:
                yield
            finally:
                semaphore.release()
        except TimeoutError:
            raise TimeoutError(f"Tool {tool_name} acquisition timed out")
    
    def record_tool_failure(self, tool_name: str, error_code: str):
        """Record tool failure for circuit breaker."""
        self.tool_failure_counts[tool_name] = self.tool_failure_counts.get(tool_name, 0) + 1
        
        if self.circuit_breaker_enabled:
            # Create circuit breaker if it doesn't exist
            if tool_name not in self.tool_circuit_breakers:
                self.tool_circuit_breakers[tool_name] = CircuitBreaker(
                    failure_threshold=self.circuit_breaker_threshold
                )
            
            circuit = self.tool_circuit_breakers[tool_name]
            # Record the failure with the circuit breaker properly
            import asyncio
            _task = asyncio.create_task(circuit.record_failure())
            
            # Simple additional check - trip after 5 failures
            if self.tool_failure_counts[tool_name] >= 5:
                from .circuit import CircuitState
                circuit._state = CircuitState.OPEN