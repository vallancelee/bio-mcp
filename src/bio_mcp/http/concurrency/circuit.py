"""Circuit breaker implementation."""

import time
from contextlib import asynccontextmanager
from enum import Enum


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for failure isolation."""
    
    def __init__(
        self,
        failure_threshold: float = 0.5,
        min_requests: int = 10,
        timeout_ms: int = 60000
    ):
        self.failure_threshold = failure_threshold
        self.min_requests = min_requests
        self.timeout_s = timeout_ms / 1000
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
    
    @property
    def state(self) -> str:
        """Get current state as string."""
        return self._state.value
    
    @state.setter
    def state(self, value: str | CircuitState):
        """Set circuit state."""
        if isinstance(value, str):
            self._state = CircuitState(value)
        else:
            self._state = value
    
    async def record_success(self):
        """Record successful operation."""
        self.success_count += 1
        
        if self._state == CircuitState.HALF_OPEN:
            # Successful operation in half-open, close circuit
            self._state = CircuitState.CLOSED
            self.failure_count = 0
    
    async def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        # Check if we should trip
        total_requests = self.success_count + self.failure_count
        if total_requests >= self.min_requests:
            failure_rate = self.failure_count / total_requests
            if failure_rate >= self.failure_threshold:
                self._state = CircuitState.OPEN
    
    def _should_allow_request(self) -> bool:
        """Check if request should be allowed."""
        if self._state == CircuitState.CLOSED:
            return True
        elif self._state == CircuitState.OPEN:
            # Check if timeout has passed
            if time.time() - self.last_failure_time >= self.timeout_s:
                self._state = CircuitState.HALF_OPEN
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not self._should_allow_request():
            raise Exception("Circuit breaker is open")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
    
    @asynccontextmanager
    async def context(self):
        """Provide context manager interface."""
        async with self:
            yield