"""Test budget management functionality."""


import pytest

from bio_mcp.orchestrator.budget.manager import (
    BudgetManager,
    BudgetStatus,
    BudgetTracker,
    ResourceType,
)
from bio_mcp.orchestrator.config import OrchestratorConfig


class TestBudgetTracker:
    """Test BudgetTracker implementation."""

    def test_init_budget_tracker(self):
        """Test BudgetTracker initialization."""
        tracker = BudgetTracker(
            time_budget_ms=5000, token_budget=1000, request_budget=50
        )

        assert tracker.time_budget_ms == 5000
        assert tracker.token_budget == 1000
        assert tracker.request_budget == 50
        assert tracker.time_spent_ms == 0
        assert tracker.tokens_used == 0
        assert tracker.requests_made == 0
        assert tracker.start_time is not None
        assert tracker.status == BudgetStatus.ACTIVE

    def test_consume_time_within_budget(self):
        """Test consuming time within budget."""
        tracker = BudgetTracker(
            time_budget_ms=5000, token_budget=1000, request_budget=50
        )

        result = tracker.consume(ResourceType.TIME, 1000)

        assert result is True
        assert tracker.time_spent_ms == 1000
        assert tracker.status == BudgetStatus.ACTIVE

    def test_consume_time_exceeds_budget(self):
        """Test consuming time that exceeds budget."""
        tracker = BudgetTracker(
            time_budget_ms=2000, token_budget=1000, request_budget=50
        )

        # First consumption should succeed
        result1 = tracker.consume(ResourceType.TIME, 1000)
        assert result1 is True

        # Second consumption should exceed budget
        result2 = tracker.consume(ResourceType.TIME, 1500)
        assert result2 is False
        assert tracker.status == BudgetStatus.TIME_EXCEEDED
        assert tracker.time_spent_ms == 1000  # Shouldn't be updated after exceeded

    def test_consume_tokens_within_budget(self):
        """Test consuming tokens within budget."""
        tracker = BudgetTracker(
            time_budget_ms=5000, token_budget=1000, request_budget=50
        )

        result = tracker.consume(ResourceType.TOKENS, 300)

        assert result is True
        assert tracker.tokens_used == 300
        assert tracker.status == BudgetStatus.ACTIVE

    def test_consume_tokens_exceeds_budget(self):
        """Test consuming tokens that exceeds budget."""
        tracker = BudgetTracker(
            time_budget_ms=5000, token_budget=500, request_budget=50
        )

        # First consumption should succeed
        result1 = tracker.consume(ResourceType.TOKENS, 300)
        assert result1 is True

        # Second consumption should exceed budget
        result2 = tracker.consume(ResourceType.TOKENS, 300)
        assert result2 is False
        assert tracker.status == BudgetStatus.TOKEN_EXCEEDED
        assert tracker.tokens_used == 300  # Shouldn't be updated after exceeded

    def test_consume_requests_within_budget(self):
        """Test consuming requests within budget."""
        tracker = BudgetTracker(
            time_budget_ms=5000, token_budget=1000, request_budget=10
        )

        result = tracker.consume(ResourceType.REQUESTS, 5)

        assert result is True
        assert tracker.requests_made == 5
        assert tracker.status == BudgetStatus.ACTIVE

    def test_consume_requests_exceeds_budget(self):
        """Test consuming requests that exceeds budget."""
        tracker = BudgetTracker(
            time_budget_ms=5000, token_budget=1000, request_budget=5
        )

        # First consumption should succeed
        result1 = tracker.consume(ResourceType.REQUESTS, 3)
        assert result1 is True

        # Second consumption should exceed budget
        result2 = tracker.consume(ResourceType.REQUESTS, 4)
        assert result2 is False
        assert tracker.status == BudgetStatus.REQUEST_EXCEEDED
        assert tracker.requests_made == 3  # Shouldn't be updated after exceeded

    def test_get_remaining_budget(self):
        """Test getting remaining budget amounts."""
        tracker = BudgetTracker(
            time_budget_ms=5000, token_budget=1000, request_budget=50
        )

        tracker.consume(ResourceType.TIME, 1000)
        tracker.consume(ResourceType.TOKENS, 300)
        tracker.consume(ResourceType.REQUESTS, 10)

        remaining = tracker.get_remaining()

        assert remaining[ResourceType.TIME] == 4000
        assert remaining[ResourceType.TOKENS] == 700
        assert remaining[ResourceType.REQUESTS] == 40

    def test_get_usage_percentages(self):
        """Test getting usage percentages."""
        tracker = BudgetTracker(
            time_budget_ms=5000, token_budget=1000, request_budget=50
        )

        tracker.consume(ResourceType.TIME, 2500)
        tracker.consume(ResourceType.TOKENS, 250)
        tracker.consume(ResourceType.REQUESTS, 25)

        usage = tracker.get_usage_percentages()

        assert usage[ResourceType.TIME] == 0.5  # 50%
        assert usage[ResourceType.TOKENS] == 0.25  # 25%
        assert usage[ResourceType.REQUESTS] == 0.5  # 50%


class TestBudgetManager:
    """Test BudgetManager implementation."""

    def test_init_budget_manager(self):
        """Test BudgetManager initialization."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)

        assert manager.config == config
        assert manager.default_time_budget_ms == 30000  # 30 seconds
        assert manager.default_token_budget == 10000
        assert manager.default_request_budget == 100

    @pytest.mark.asyncio
    async def test_create_budget_tracker_default(self):
        """Test creating budget tracker with default values."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)

        tracker = await manager.create_tracker()

        assert tracker.time_budget_ms == 30000
        assert tracker.token_budget == 10000
        assert tracker.request_budget == 100
        assert tracker.status == BudgetStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_create_budget_tracker_custom(self):
        """Test creating budget tracker with custom values."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)

        tracker = await manager.create_tracker(
            time_budget_ms=15000, token_budget=5000, request_budget=25
        )

        assert tracker.time_budget_ms == 15000
        assert tracker.token_budget == 5000
        assert tracker.request_budget == 25
        assert tracker.status == BudgetStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_enforce_budget_within_limits(self):
        """Test enforcing budget when within limits."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)
        tracker = await manager.create_tracker(
            time_budget_ms=5000, token_budget=1000, request_budget=50
        )

        # Should allow operation within budget
        result = await manager.enforce_budget(tracker, ResourceType.TIME, 1000)

        assert result is True
        assert tracker.time_spent_ms == 1000
        assert tracker.status == BudgetStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_enforce_budget_exceeds_limits(self):
        """Test enforcing budget when exceeding limits."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)
        tracker = await manager.create_tracker(
            time_budget_ms=2000, token_budget=1000, request_budget=50
        )

        # First operation should succeed
        result1 = await manager.enforce_budget(tracker, ResourceType.TIME, 1000)
        assert result1 is True

        # Second operation should fail due to budget exceeded
        result2 = await manager.enforce_budget(tracker, ResourceType.TIME, 1500)
        assert result2 is False
        assert tracker.status == BudgetStatus.TIME_EXCEEDED

    @pytest.mark.asyncio
    async def test_check_budget_status_active(self):
        """Test checking budget status when active."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)
        tracker = await manager.create_tracker(
            time_budget_ms=5000, token_budget=1000, request_budget=50
        )

        status, message = await manager.check_budget_status(tracker)

        assert status == BudgetStatus.ACTIVE
        assert "active" in message.lower()

    @pytest.mark.asyncio
    async def test_check_budget_status_warning(self):
        """Test checking budget status when in warning zone."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)
        tracker = await manager.create_tracker(
            time_budget_ms=1000, token_budget=1000, request_budget=50
        )

        # Consume 80% of time budget (should trigger warning)
        await manager.enforce_budget(tracker, ResourceType.TIME, 800)

        status, message = await manager.check_budget_status(tracker)

        assert status == BudgetStatus.WARNING
        assert "warning" in message.lower()
        assert "80%" in message  # Should mention the high usage

    @pytest.mark.asyncio
    async def test_check_budget_status_exceeded(self):
        """Test checking budget status when exceeded."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)
        tracker = await manager.create_tracker(
            time_budget_ms=1000, token_budget=1000, request_budget=50
        )

        # Try to consume more than budget
        await manager.enforce_budget(tracker, ResourceType.TIME, 1500)

        status, message = await manager.check_budget_status(tracker)

        assert status == BudgetStatus.TIME_EXCEEDED
        assert "exceeded" in message.lower()
        assert "time" in message.lower()

    @pytest.mark.asyncio
    async def test_calculate_timeout_remaining_budget(self):
        """Test calculating timeout based on remaining budget."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)
        tracker = await manager.create_tracker(
            time_budget_ms=5000, token_budget=1000, request_budget=50
        )

        # Consume some time
        await manager.enforce_budget(tracker, ResourceType.TIME, 2000)

        timeout = await manager.calculate_timeout(tracker)

        # Should return remaining time budget
        assert timeout == 3000  # 5000 - 2000

    @pytest.mark.asyncio
    async def test_calculate_timeout_exceeded_budget(self):
        """Test calculating timeout when budget exceeded."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)
        tracker = await manager.create_tracker(
            time_budget_ms=1000, token_budget=1000, request_budget=50
        )

        # Exceed budget
        await manager.enforce_budget(tracker, ResourceType.TIME, 1500)

        timeout = await manager.calculate_timeout(tracker)

        # Should return 0 or minimal timeout when exceeded
        assert timeout == 0

    @pytest.mark.asyncio
    async def test_get_budget_summary(self):
        """Test getting comprehensive budget summary."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)
        tracker = await manager.create_tracker(
            time_budget_ms=5000, token_budget=1000, request_budget=50
        )

        # Consume some resources
        await manager.enforce_budget(tracker, ResourceType.TIME, 2000)
        await manager.enforce_budget(tracker, ResourceType.TOKENS, 300)
        await manager.enforce_budget(tracker, ResourceType.REQUESTS, 15)

        summary = await manager.get_budget_summary(tracker)

        # Check summary structure
        assert "status" in summary
        assert "usage" in summary
        assert "remaining" in summary
        assert "percentages" in summary

        # Check specific values
        assert summary["status"] == BudgetStatus.ACTIVE
        assert summary["usage"][ResourceType.TIME] == 2000
        assert summary["usage"][ResourceType.TOKENS] == 300
        assert summary["usage"][ResourceType.REQUESTS] == 15
        assert summary["remaining"][ResourceType.TIME] == 3000
        assert summary["remaining"][ResourceType.TOKENS] == 700
        assert summary["remaining"][ResourceType.REQUESTS] == 35
        assert summary["percentages"][ResourceType.TIME] == 0.4  # 40%
        assert summary["percentages"][ResourceType.TOKENS] == 0.3  # 30%
        assert summary["percentages"][ResourceType.REQUESTS] == 0.3  # 30%

    @pytest.mark.asyncio
    async def test_estimate_operation_cost(self):
        """Test estimating operation cost."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)

        # Test different operation types (use same limit for fair comparison)
        pubmed_cost = await manager.estimate_operation_cost(
            "pubmed.search", {"limit": 20}
        )
        trials_cost = await manager.estimate_operation_cost(
            "clinicaltrials.search", {"limit": 20}
        )
        rag_cost = await manager.estimate_operation_cost(
            "rag.search", {"query": "diabetes", "limit": 20}
        )

        # PubMed should be relatively fast
        assert pubmed_cost[ResourceType.TIME] <= 2000
        assert pubmed_cost[ResourceType.TOKENS] <= 100
        assert pubmed_cost[ResourceType.REQUESTS] == 1

        # ClinicalTrials should be slower
        assert trials_cost[ResourceType.TIME] > pubmed_cost[ResourceType.TIME]
        assert trials_cost[ResourceType.TOKENS] <= 200  # Same scaling as PubMed
        assert trials_cost[ResourceType.REQUESTS] == 1

        # RAG should be most expensive
        assert rag_cost[ResourceType.TIME] >= trials_cost[ResourceType.TIME]
        assert rag_cost[ResourceType.TOKENS] >= 500  # Vector search + LLM tokens
        assert rag_cost[ResourceType.REQUESTS] == 1

    @pytest.mark.asyncio
    async def test_can_afford_operation(self):
        """Test checking if operation can be afforded."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)
        tracker = await manager.create_tracker(
            time_budget_ms=3000, token_budget=1000, request_budget=5
        )

        # Should be able to afford small operation
        can_afford_small = await manager.can_afford_operation(
            tracker, "pubmed.search", {"limit": 10}
        )
        assert can_afford_small is True

        # Consume most of the budget
        await manager.enforce_budget(tracker, ResourceType.TIME, 2500)
        await manager.enforce_budget(tracker, ResourceType.TOKENS, 800)
        await manager.enforce_budget(tracker, ResourceType.REQUESTS, 4)

        # Should not be able to afford expensive operation
        can_afford_expensive = await manager.can_afford_operation(
            tracker, "rag.search", {"query": "test", "limit": 50}
        )
        assert can_afford_expensive is False

    @pytest.mark.asyncio
    async def test_budget_aware_timeout(self):
        """Test budget-aware timeout calculation."""
        config = OrchestratorConfig()
        manager = BudgetManager(config)
        tracker = await manager.create_tracker(
            time_budget_ms=2000, token_budget=1000, request_budget=50
        )

        # Initially should return full budget as timeout
        timeout1 = await manager.calculate_timeout(tracker)
        assert timeout1 == 2000

        # After consuming budget, timeout should decrease
        await manager.enforce_budget(tracker, ResourceType.TIME, 500)
        timeout2 = await manager.calculate_timeout(tracker)
        assert timeout2 == 1500

        # When budget exceeded, timeout should be minimal/zero
        await manager.enforce_budget(
            tracker, ResourceType.TIME, 2000
        )  # This should exceed
        timeout3 = await manager.calculate_timeout(tracker)
        assert timeout3 == 0
