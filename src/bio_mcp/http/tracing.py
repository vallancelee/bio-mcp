"""Trace context and correlation for HTTP adapter."""

import time
import uuid
from contextvars import ContextVar
from typing import Any, Optional

from bio_mcp.config.logging_config import get_logger

logger = get_logger(__name__)

# Context variable for current trace
_current_trace: ContextVar[Optional['TraceContext']] = ContextVar('current_trace', default=None)


def generate_trace_id() -> str:
    """Generate a unique trace ID using UUID4.
    
    Returns:
        A string trace ID in UUID4 format
    """
    return str(uuid.uuid4())


def get_current_trace() -> Optional['TraceContext']:
    """Get the current trace context if one exists.
    
    Returns:
        Current TraceContext or None
    """
    return _current_trace.get()


class TraceContext:
    """Context for tracing request lifecycle with correlation data."""
    
    def __init__(self, trace_id: str, tool_name: str):
        """Initialize trace context.
        
        Args:
            trace_id: Unique identifier for this trace
            tool_name: Name of the tool being executed
        """
        self.trace_id = trace_id
        self.tool_name = tool_name
        self.start_time = time.time()
        self.metadata: dict[str, Any] = {}
        self._error: Exception | None = None
        self._result: Any = None
        self._status = "pending"
    
    def get_duration_ms(self) -> float:
        """Get elapsed time since trace start in milliseconds.
        
        Returns:
            Duration in milliseconds
        """
        return (time.time() - self.start_time) * 1000
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the trace context.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
    
    def set_error(self, error: Exception) -> None:
        """Mark trace as failed with error.
        
        Args:
            error: Exception that caused the failure
        """
        self._error = error
        self._status = "error"
    
    def set_success(self, result: Any = None) -> None:
        """Mark trace as successful.
        
        Args:
            result: Optional result data
        """
        self._result = result
        self._status = "success"
    
    def get_structured_log_data(self) -> dict[str, Any]:
        """Get structured data for logging.
        
        Returns:
            Dictionary with trace data for structured logging
        """
        data = {
            "trace_id": self.trace_id,
            "tool": self.tool_name,
            "latency_ms": self.get_duration_ms(),
            "status": self._status,
            "metadata": self.metadata.copy()
        }
        
        if self._error:
            data["error_type"] = type(self._error).__name__
            data["error_message"] = str(self._error)
        
        return data
    
    def get_correlation_data(self) -> dict[str, Any]:
        """Get correlation data for request tracing.
        
        Returns:
            Dictionary with correlation fields
        """
        correlation = {
            "trace_id": self.trace_id,
            "tool": self.tool_name
        }
        
        # Include relevant metadata for correlation
        for key, value in self.metadata.items():
            if key in ["user_id", "request_id", "session_id", "tenant_id"]:
                correlation[key] = value
        
        return correlation
    
    def __enter__(self) -> 'TraceContext':
        """Enter context manager - set as current trace."""
        self._token = _current_trace.set(self)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager - log completion and reset current trace."""
        # Handle any exception that occurred
        if exc_type is not None:
            self.set_error(exc_val)
        elif self._status == "pending":
            # Set success if not explicitly set
            self.set_success()
        
        # Log trace completion
        log_data = self.get_structured_log_data()
        
        if self._status == "error":
            logger.error(
                f"Tool execution failed: {self.tool_name}",
                **log_data
            )
        else:
            logger.info(
                f"Tool execution completed: {self.tool_name}",
                **log_data
            )
        
        # Reset current trace
        _current_trace.reset(self._token)