"""
Basic metrics collection for Bio-MCP server.
Phase 1B: Simple metrics tracking for monitoring and observability.
"""

import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from ..config.config import config


@dataclass
class ToolMetrics:
    """Metrics for individual tool usage."""
    name: str
    call_count: int
    success_count: int
    error_count: int
    total_duration_ms: float
    avg_duration_ms: float
    min_duration_ms: float | None
    max_duration_ms: float | None
    last_called: str | None


@dataclass
class ServerMetrics:
    """Overall server metrics."""
    start_time: str
    uptime_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    tools: list[ToolMetrics]


class MetricsCollector:
    """Thread-safe metrics collection for MCP server."""
    
    def __init__(self, max_recent_calls: int = 1000):
        self.start_time = time.time()
        self.max_recent_calls = max_recent_calls
        self._lock = Lock()
        
        # Tool-specific metrics
        self._tool_calls: dict[str, int] = defaultdict(int)
        self._tool_successes: dict[str, int] = defaultdict(int)
        self._tool_errors: dict[str, int] = defaultdict(int)
        self._tool_durations: dict[str, list[float]] = defaultdict(list)
        self._tool_last_called: dict[str, datetime | None] = defaultdict(lambda: None)
        
        # Recent calls for detailed analysis
        self._recent_calls: deque = deque(maxlen=max_recent_calls)
    
    def record_tool_call(
        self, 
        tool_name: str, 
        duration_ms: float, 
        success: bool = True,
        error_type: str | None = None
    ):
        """Record a tool call with timing and result."""
        with self._lock:
            now = datetime.now(UTC)
            
            # Update counters
            self._tool_calls[tool_name] += 1
            if success:
                self._tool_successes[tool_name] += 1
            else:
                self._tool_errors[tool_name] += 1
            
            # Update timing
            self._tool_durations[tool_name].append(duration_ms)
            self._tool_last_called[tool_name] = now
            
            # Record detailed call info
            call_record = {
                "timestamp": now.isoformat(),
                "tool": tool_name,
                "duration_ms": duration_ms,
                "success": success,
                "error_type": error_type
            }
            self._recent_calls.append(call_record)
    
    def get_tool_metrics(self, tool_name: str) -> ToolMetrics | None:
        """Get metrics for a specific tool."""
        with self._lock:
            if tool_name not in self._tool_calls:
                return None
            
            durations = self._tool_durations[tool_name]
            
            return ToolMetrics(
                name=tool_name,
                call_count=self._tool_calls[tool_name],
                success_count=self._tool_successes[tool_name],
                error_count=self._tool_errors[tool_name],
                total_duration_ms=sum(durations),
                avg_duration_ms=sum(durations) / len(durations) if durations else 0,
                min_duration_ms=min(durations) if durations else None,
                max_duration_ms=max(durations) if durations else None,
                last_called=self._tool_last_called[tool_name].isoformat() if self._tool_last_called[tool_name] else None
            )
    
    def get_all_metrics(self) -> ServerMetrics:
        """Get comprehensive server metrics."""
        with self._lock:
            uptime = time.time() - self.start_time
            
            # Collect tool metrics
            tool_metrics = []
            for tool_name in self._tool_calls:
                tool_metric = self.get_tool_metrics(tool_name)
                if tool_metric:
                    tool_metrics.append(tool_metric)
            
            # Calculate totals
            total_requests = sum(self._tool_calls.values())
            successful_requests = sum(self._tool_successes.values())
            failed_requests = sum(self._tool_errors.values())
            
            return ServerMetrics(
                start_time=datetime.fromtimestamp(self.start_time, tz=UTC).isoformat(),
                uptime_seconds=uptime,
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                tools=tool_metrics
            )
    
    def get_recent_calls(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get recent tool calls for analysis."""
        with self._lock:
            calls = list(self._recent_calls)
            if limit:
                calls = calls[-limit:]
            return calls
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._tool_calls.clear()
            self._tool_successes.clear()
            self._tool_errors.clear()
            self._tool_durations.clear()
            self._tool_last_called.clear()
            self._recent_calls.clear()
            self.start_time = time.time()


# Global metrics collector instance
metrics_collector = MetricsCollector()


def record_tool_call(tool_name: str, duration_ms: float, success: bool = True, error_type: str | None = None):
    """Convenience function to record tool calls."""
    metrics_collector.record_tool_call(tool_name, duration_ms, success, error_type)


def get_metrics_dict() -> dict[str, Any]:
    """Get all metrics as a dictionary for JSON serialization."""
    metrics = metrics_collector.get_all_metrics()
    return {
        "server": {
            "start_time": metrics.start_time,
            "uptime_seconds": metrics.uptime_seconds,
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "success_rate": (
                metrics.successful_requests / metrics.total_requests 
                if metrics.total_requests > 0 else 0
            )
        },
        "tools": [asdict(tool) for tool in metrics.tools],
        "version": config.version
    }