"""Concurrency control exceptions."""

from typing import Any


class ConcurrencyError(Exception):
    """Base exception for concurrency control errors."""
    pass


class RateLimitExceeded(ConcurrencyError):
    """Exception raised when rate limits are exceeded."""
    
    def __init__(
        self,
        message: str,
        tool: str | None = None,
        retry_after: int = 0,
        queue_depth: int = 0,
        queue_position: int | None = None,
        estimated_wait_ms: int = 0
    ):
        super().__init__(message)
        self.tool = tool
        self.retry_after = retry_after
        self.queue_depth = queue_depth
        self.queue_position = queue_position
        self.estimated_wait_ms = estimated_wait_ms
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for HTTP response."""
        return {
            "ok": False,
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": str(self),
            "tool": self.tool,
            "retry_after": self.retry_after,
            "queue_depth": self.queue_depth,
            "queue_position": self.queue_position,
            "estimated_wait_ms": self.estimated_wait_ms
        }