"""Abstract interfaces for orchestrator components (no circular dependencies)."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Protocol

from bio_mcp.orchestrator.types import ConfigDict, NodeResult, OrchestratorState


class BaseNode(Protocol):
    """Protocol for LangGraph node implementations."""

    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Execute the node logic and return state updates."""
        ...


class BaseToolNode(ABC):
    """Abstract base class for tool execution nodes."""

    def __init__(self, config: ConfigDict, node_name: str):
        self.config = config
        self.node_name = node_name

    @abstractmethod
    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Execute the tool node logic."""
        pass

    def _error_response(
        self, state: OrchestratorState, error_msg: str
    ) -> dict[str, Any]:
        """Generate standardized error response."""
        return {
            "errors": state["errors"]
            + [
                {
                    "node": self.node_name,
                    "error": error_msg,
                    "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
                }
            ],
            "node_path": state["node_path"] + [self.node_name],
        }


class BaseAdapter(Protocol):
    """Protocol for adapter implementations."""

    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        cache_policy: str = "cache_then_network",
    ) -> NodeResult:
        """Execute a tool with given arguments and cache policy."""
        ...


class BaseRateLimiter(Protocol):
    """Protocol for rate limiting implementations."""

    async def acquire(self) -> None:
        """Acquire a rate limit token."""
        ...

    def get_current_rate(self) -> float:
        """Get current rate limit."""
        ...


class BaseCacheManager(Protocol):
    """Protocol for cache management implementations."""

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache with optional TTL."""
        ...


class BaseMetricsCollector(Protocol):
    """Protocol for metrics collection implementations."""

    def record_latency(self, operation: str, latency_ms: float) -> None:
        """Record operation latency."""
        ...

    def record_cache_hit(self, operation: str, hit: bool) -> None:
        """Record cache hit/miss."""
        ...


# Factory function protocol
NodeFactory = Callable[[ConfigDict], BaseNode]


class NodeRegistration:
    """Registration data for a node."""

    def __init__(
        self,
        name: str,
        factory: NodeFactory,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.name = name
        self.factory = factory
        self.dependencies = dependencies or []
        self.metadata = metadata or {}


class BaseNodeRegistry(Protocol):
    """Protocol for node registry implementations."""

    def register(self, registration: NodeRegistration) -> None:
        """Register a node with the registry."""
        ...

    def get_factory(self, name: str) -> NodeFactory:
        """Get factory function for a node."""
        ...

    def list_nodes(self) -> list[str]:
        """List all registered node names."""
        ...
