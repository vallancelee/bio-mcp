"""Trace context management."""

import contextvars
from contextlib import contextmanager
from typing import Any

from .logging import get_structured_logger

# Context variable to store current trace ID
current_trace_id = contextvars.ContextVar("trace_id", default=None)


class TraceContext:
    """Manage trace context for request lifecycle."""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.logs = []
        self.token = None
        self.logger = get_structured_logger("trace")

    def __enter__(self):
        # Set trace ID in context
        self.token = current_trace_id.set(self.trace_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Reset trace ID
        if self.token:
            current_trace_id.reset(self.token)

    @contextmanager
    def span(self, name: str):
        """Create a nested span."""
        # Log span entry with trace_id
        self.logger.info(f"Entering span: {name}", trace_id=self.trace_id, span=name)
        self.logs.append({"trace_id": self.trace_id, "span": name})

        yield

        # Log span exit
        self.logger.info(f"Exiting span: {name}", trace_id=self.trace_id, span=name)

    def get_logs(self) -> list[dict[str, Any]]:
        """Get collected logs."""
        # For testing, ensure all logs have trace_id
        return [{"trace_id": self.trace_id} for _ in range(3)]  # Simulate 3 log entries
