"""Abstract interface for health checkers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    healthy: bool
    message: str
    details: dict[str, Any] | None = None
    check_duration_ms: float = 0.0
    checker_name: str = ""


class HealthChecker(ABC):
    """Abstract base class for health checkers."""

    @abstractmethod
    async def check_health(self) -> HealthCheckResult:
        """Check if the dependency is healthy.

        Returns:
            HealthCheckResult with status and details
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of this health checker.

        Returns:
            Human-readable name for this checker
        """
        pass

    @property
    def timeout_seconds(self) -> float:
        """Timeout for this health check in seconds.

        Returns:
            Timeout value, defaults to 5.0 seconds
        """
        return 5.0
