"""Budget management functionality for orchestrator."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from bio_mcp.orchestrator.config import OrchestratorConfig


class ResourceType(Enum):
    """Types of resources to track."""

    TIME = "time"
    TOKENS = "tokens"
    REQUESTS = "requests"


class BudgetStatus(Enum):
    """Status of budget consumption."""

    ACTIVE = "active"
    WARNING = "warning"
    TIME_EXCEEDED = "time_exceeded"
    TOKEN_EXCEEDED = "token_exceeded"
    REQUEST_EXCEEDED = "request_exceeded"


@dataclass
class BudgetTracker:
    """Tracks budget consumption across resources."""

    time_budget_ms: int
    token_budget: int
    request_budget: int
    time_spent_ms: int = 0
    tokens_used: int = 0
    requests_made: int = 0
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: BudgetStatus = BudgetStatus.ACTIVE

    def consume(self, resource_type: ResourceType, amount: int | float) -> bool:
        """Consume budget for a resource type.

        Args:
            resource_type: Type of resource to consume
            amount: Amount to consume

        Returns:
            True if consumption was successful, False if budget exceeded
        """
        # Don't allow consumption if already exceeded
        if self.status != BudgetStatus.ACTIVE and self.status != BudgetStatus.WARNING:
            return False

        # Check if consumption would exceed budget
        if resource_type == ResourceType.TIME:
            if self.time_spent_ms + amount > self.time_budget_ms:
                self.status = BudgetStatus.TIME_EXCEEDED
                return False
            self.time_spent_ms += int(amount)
        elif resource_type == ResourceType.TOKENS:
            if self.tokens_used + amount > self.token_budget:
                self.status = BudgetStatus.TOKEN_EXCEEDED
                return False
            self.tokens_used += int(amount)
        elif resource_type == ResourceType.REQUESTS:
            if self.requests_made + amount > self.request_budget:
                self.status = BudgetStatus.REQUEST_EXCEEDED
                return False
            self.requests_made += int(amount)

        # Update status based on usage
        self._update_status()
        return True

    def get_remaining(self) -> dict[ResourceType, int | float]:
        """Get remaining budget for all resources.

        Returns:
            Dictionary of remaining budget per resource type
        """
        return {
            ResourceType.TIME: max(0, self.time_budget_ms - self.time_spent_ms),
            ResourceType.TOKENS: max(0, self.token_budget - self.tokens_used),
            ResourceType.REQUESTS: max(0, self.request_budget - self.requests_made),
        }

    def get_usage_percentages(self) -> dict[ResourceType, float]:
        """Get usage percentages for all resources.

        Returns:
            Dictionary of usage percentages (0.0 to 1.0)
        """
        return {
            ResourceType.TIME: self.time_spent_ms / self.time_budget_ms
            if self.time_budget_ms > 0
            else 1.0,
            ResourceType.TOKENS: self.tokens_used / self.token_budget
            if self.token_budget > 0
            else 1.0,
            ResourceType.REQUESTS: self.requests_made / self.request_budget
            if self.request_budget > 0
            else 1.0,
        }

    def _update_status(self) -> None:
        """Update status based on current usage."""
        percentages = self.get_usage_percentages()

        # Check if any resource is above warning threshold (75%)
        warning_threshold = 0.75
        if any(pct >= warning_threshold for pct in percentages.values()):
            if self.status == BudgetStatus.ACTIVE:
                self.status = BudgetStatus.WARNING


class BudgetManager:
    """Manages budget tracking and enforcement for orchestrator."""

    def __init__(self, config: OrchestratorConfig):
        """Initialize budget manager.

        Args:
            config: Orchestrator configuration
        """
        self.config = config
        self.default_time_budget_ms = 30000  # 30 seconds
        self.default_token_budget = 10000
        self.default_request_budget = 100

    async def create_tracker(
        self,
        time_budget_ms: int | None = None,
        token_budget: int | None = None,
        request_budget: int | None = None,
    ) -> BudgetTracker:
        """Create a new budget tracker.

        Args:
            time_budget_ms: Time budget in milliseconds (uses default if None)
            token_budget: Token budget (uses default if None)
            request_budget: Request budget (uses default if None)

        Returns:
            New budget tracker instance
        """
        return BudgetTracker(
            time_budget_ms=time_budget_ms or self.default_time_budget_ms,
            token_budget=token_budget or self.default_token_budget,
            request_budget=request_budget or self.default_request_budget,
        )

    async def enforce_budget(
        self, tracker: BudgetTracker, resource_type: ResourceType, amount: int | float
    ) -> bool:
        """Enforce budget consumption.

        Args:
            tracker: Budget tracker instance
            resource_type: Type of resource to consume
            amount: Amount to consume

        Returns:
            True if consumption was allowed, False if budget exceeded
        """
        return tracker.consume(resource_type, amount)

    async def check_budget_status(
        self, tracker: BudgetTracker
    ) -> tuple[BudgetStatus, str]:
        """Check current budget status.

        Args:
            tracker: Budget tracker instance

        Returns:
            Tuple of (status, description message)
        """
        if tracker.status == BudgetStatus.ACTIVE:
            return tracker.status, "Budget is active and within limits"

        elif tracker.status == BudgetStatus.WARNING:
            percentages = tracker.get_usage_percentages()
            max_usage = max(percentages.values())
            return (
                tracker.status,
                f"Budget warning: {max_usage * 100:.0f}% of resources consumed",
            )

        elif tracker.status == BudgetStatus.TIME_EXCEEDED:
            return tracker.status, "Time budget exceeded - operations may timeout"

        elif tracker.status == BudgetStatus.TOKEN_EXCEEDED:
            return (
                tracker.status,
                "Token budget exceeded - cannot make more expensive operations",
            )

        elif tracker.status == BudgetStatus.REQUEST_EXCEEDED:
            return (
                tracker.status,
                "Request budget exceeded - cannot make more API calls",
            )

        return tracker.status, "Unknown budget status"

    async def calculate_timeout(self, tracker: BudgetTracker) -> int:
        """Calculate appropriate timeout based on remaining budget.

        Args:
            tracker: Budget tracker instance

        Returns:
            Timeout in milliseconds
        """
        if tracker.status in [
            BudgetStatus.TIME_EXCEEDED,
            BudgetStatus.TOKEN_EXCEEDED,
            BudgetStatus.REQUEST_EXCEEDED,
        ]:
            return 0

        remaining = tracker.get_remaining()
        return int(remaining[ResourceType.TIME])

    async def get_budget_summary(self, tracker: BudgetTracker) -> dict[str, Any]:
        """Get comprehensive budget summary.

        Args:
            tracker: Budget tracker instance

        Returns:
            Dictionary with detailed budget information
        """
        return {
            "status": tracker.status,
            "usage": {
                ResourceType.TIME: tracker.time_spent_ms,
                ResourceType.TOKENS: tracker.tokens_used,
                ResourceType.REQUESTS: tracker.requests_made,
            },
            "remaining": tracker.get_remaining(),
            "percentages": tracker.get_usage_percentages(),
            "start_time": tracker.start_time,
            "current_time": datetime.now(UTC),
        }

    async def estimate_operation_cost(
        self, operation: str, args: dict[str, Any]
    ) -> dict[ResourceType, int | float]:
        """Estimate resource cost for an operation.

        Args:
            operation: Operation name (e.g., "pubmed.search")
            args: Operation arguments

        Returns:
            Dictionary of estimated resource costs
        """
        # Base estimates for different operations
        operation_costs = {
            "pubmed.search": {
                ResourceType.TIME: 1000,  # 1 second base
                ResourceType.TOKENS: 50,  # Minimal tokens
                ResourceType.REQUESTS: 1,
            },
            "clinicaltrials.search": {
                ResourceType.TIME: 2000,  # 2 seconds base
                ResourceType.TOKENS: 100,  # More complex responses
                ResourceType.REQUESTS: 1,
            },
            "rag.search": {
                ResourceType.TIME: 3000,  # 3 seconds base (vector search + LLM)
                ResourceType.TOKENS: 1000,  # Vector embeddings + LLM tokens
                ResourceType.REQUESTS: 1,
            },
        }

        base_costs = operation_costs.get(
            operation,
            {
                ResourceType.TIME: 2000,
                ResourceType.TOKENS: 200,
                ResourceType.REQUESTS: 1,
            },
        )

        # Adjust based on arguments
        estimated_costs = dict(base_costs)

        # Scale by limit/results requested
        if "limit" in args:
            limit = int(args["limit"])
            # Scale time and tokens based on result count
            scale_factor = min(limit / 20, 3.0)  # Cap at 3x scaling
            estimated_costs[ResourceType.TIME] = int(
                estimated_costs[ResourceType.TIME] * scale_factor
            )
            estimated_costs[ResourceType.TOKENS] = int(
                estimated_costs[ResourceType.TOKENS] * scale_factor
            )

        return estimated_costs

    async def can_afford_operation(
        self, tracker: BudgetTracker, operation: str, args: dict[str, Any]
    ) -> bool:
        """Check if an operation can be afforded within budget.

        Args:
            tracker: Budget tracker instance
            operation: Operation name
            args: Operation arguments

        Returns:
            True if operation can be afforded
        """
        if tracker.status in [
            BudgetStatus.TIME_EXCEEDED,
            BudgetStatus.TOKEN_EXCEEDED,
            BudgetStatus.REQUEST_EXCEEDED,
        ]:
            return False

        estimated_costs = await self.estimate_operation_cost(operation, args)
        remaining = tracker.get_remaining()

        # Check if we have enough budget for each resource type
        for resource_type, cost in estimated_costs.items():
            if remaining[resource_type] < cost:
                return False

        return True
