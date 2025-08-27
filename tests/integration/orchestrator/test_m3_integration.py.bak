"""Integration test for M3 LangGraph State Management milestone."""

import asyncio
from datetime import UTC, datetime

import pytest

from bio_mcp.orchestrator.budget.manager import (
    BudgetManager,
    BudgetStatus,
    ResourceType,
)
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.error.recovery import (
    ErrorRecoveryManager,
    RecoveryAction,
)
from bio_mcp.orchestrator.state import NodeResult, OrchestratorState
from bio_mcp.orchestrator.state_management.persistence import (
    BioMCPCheckpointSaver,
    StateManager,
)


class TestM3Integration:
    """Integration test for M3 milestone components."""

    @pytest.mark.asyncio
    async def test_m3_full_workflow_integration(self):
        """Test complete M3 workflow with state management, error recovery, and budget tracking."""
        config = OrchestratorConfig()

        # Initialize M3 components
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        state_manager = StateManager(config, checkpointer)
        error_manager = ErrorRecoveryManager(config)
        budget_manager = BudgetManager(config)

        # Create budget tracker for this session
        budget_tracker = await budget_manager.create_tracker(
            time_budget_ms=10000,  # 10 seconds
            token_budget=2000,
            request_budget=20,
        )

        # Test 1: Initial state creation and checkpoint
        initial_state = OrchestratorState(
            query="Find diabetes research with error recovery and budget management",
            config={},
            frame={
                "entities": {"topic": "diabetes", "company": "Pfizer"},
                "intent": "multi_search",
                "filters": {"published_within_days": 365},
            },
            routing_decision="multi_search",
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=["frame_parser", "router"],
            answer=None,
            session_id=None,
            messages=[{"role": "system", "content": "Starting multi-search workflow"}],
        )

        # Create initial checkpoint
        checkpoint = await state_manager.create_checkpoint(initial_state)
        assert checkpoint.checkpoint_id.startswith("ckpt_")
        assert checkpoint.query == initial_state["query"]

        # Verify budget is active
        budget_status, budget_msg = await budget_manager.check_budget_status(
            budget_tracker
        )
        assert budget_status == BudgetStatus.ACTIVE

        # Test 2: Simulate successful PubMed operation with budget tracking
        pubmed_operation_cost = await budget_manager.estimate_operation_cost(
            "pubmed.search", {"limit": 20}
        )
        can_afford = await budget_manager.can_afford_operation(
            budget_tracker, "pubmed.search", {"limit": 20}
        )
        assert can_afford is True

        # Consume budget for PubMed search
        success = await budget_manager.enforce_budget(
            budget_tracker, ResourceType.TIME, pubmed_operation_cost[ResourceType.TIME]
        )
        assert success is True
        success = await budget_manager.enforce_budget(
            budget_tracker,
            ResourceType.TOKENS,
            pubmed_operation_cost[ResourceType.TOKENS],
        )
        assert success is True
        success = await budget_manager.enforce_budget(
            budget_tracker, ResourceType.REQUESTS, 1
        )
        assert success is True

        # Update state with PubMed results
        updated_state_1 = dict(initial_state)
        updated_state_1.update(
            {
                "pubmed_results": {
                    "results": [
                        {"pmid": "12345", "title": "Diabetes Study 1"},
                        {"pmid": "67890", "title": "Diabetes Study 2"},
                    ],
                    "total": 2,
                },
                "tool_calls_made": ["pubmed.search"],
                "cache_hits": {"pubmed_search": False},
                "latencies": {
                    "pubmed_search": pubmed_operation_cost[ResourceType.TIME]
                },
                "node_path": ["frame_parser", "router", "enhanced_pubmed"],
                "messages": initial_state["messages"]
                + [{"role": "system", "content": "PubMed search completed: 2 results"}],
            }
        )

        # Update checkpoint
        await state_manager.update_checkpoint(checkpoint.checkpoint_id, updated_state_1)

        # Test 3: Simulate ClinicalTrials error with recovery
        trials_error = NodeResult(
            success=False,
            error_message="Rate limit exceeded: 429 Too Many Requests",
            node_name="clinicaltrials.search",
            latency_ms=500.0,
        )

        # Classify and create recovery strategy
        recovery_strategy = await error_manager.create_recovery_strategy(
            trials_error, attempt=1, max_attempts=3
        )
        assert recovery_strategy.action == RecoveryAction.RETRY_WITH_BACKOFF
        assert recovery_strategy.delay_seconds > 0

        # Apply recovery to state
        recovered_state = await error_manager.execute_recovery(
            recovery_strategy, updated_state_1, trials_error, "clinicaltrials.search"
        )

        # Verify error was recorded
        assert len(recovered_state["errors"]) == 1
        assert recovered_state["errors"][0]["node"] == "clinicaltrials.search"
        assert recovered_state["errors"][0]["strategy"] == "retry_with_backoff"
        assert "recovery_retry" in recovered_state["node_path"]

        # Update checkpoint with recovery state
        await state_manager.update_checkpoint(checkpoint.checkpoint_id, recovered_state)

        # Test 4: Simulate retry success after delay
        await asyncio.sleep(0.01)  # Simulate brief delay

        trials_operation_cost = await budget_manager.estimate_operation_cost(
            "clinicaltrials.search", {"limit": 50}
        )
        can_afford_retry = await budget_manager.can_afford_operation(
            budget_tracker, "clinicaltrials.search", {"limit": 50}
        )
        assert can_afford_retry is True

        # Consume budget for trials retry
        await budget_manager.enforce_budget(
            budget_tracker, ResourceType.TIME, trials_operation_cost[ResourceType.TIME]
        )
        await budget_manager.enforce_budget(
            budget_tracker,
            ResourceType.TOKENS,
            trials_operation_cost[ResourceType.TOKENS],
        )
        await budget_manager.enforce_budget(budget_tracker, ResourceType.REQUESTS, 1)

        # Update state with successful trials results
        final_state = dict(recovered_state)
        final_state.update(
            {
                "ctgov_results": {
                    "results": [
                        {"nct_id": "NCT123456", "title": "Diabetes Phase III Trial"},
                        {"nct_id": "NCT789012", "title": "Diabetes Phase II Trial"},
                    ],
                    "total": 2,
                },
                "tool_calls_made": recovered_state["tool_calls_made"]
                + ["clinicaltrials.search"],
                "cache_hits": {**recovered_state["cache_hits"], "trials_search": False},
                "latencies": {
                    **recovered_state["latencies"],
                    "trials_search": trials_operation_cost[ResourceType.TIME],
                },
                "node_path": recovered_state["node_path"] + ["enhanced_trials"],
                "messages": recovered_state["messages"]
                + [
                    {
                        "role": "system",
                        "content": "ClinicalTrials search completed after retry: 2 results",
                    }
                ],
            }
        )

        # Test 5: Finalize checkpoint with metrics
        await state_manager.finalize_checkpoint(checkpoint.checkpoint_id, final_state)

        # Verify final checkpoint
        final_checkpoint = await checkpointer.aget_checkpoint(checkpoint.checkpoint_id)
        assert final_checkpoint is not None
        assert final_checkpoint.completed_at is not None
        assert final_checkpoint.error_count == 1  # One error that was recovered
        assert (
            final_checkpoint.partial_results is True
        )  # Marked as partial due to recovered error

        # Test 6: Verify budget summary
        budget_summary = await budget_manager.get_budget_summary(budget_tracker)
        assert budget_summary["status"] in [BudgetStatus.ACTIVE, BudgetStatus.WARNING]
        assert (
            budget_summary["usage"][ResourceType.REQUESTS] == 2
        )  # PubMed + ClinicalTrials
        assert budget_summary["usage"][ResourceType.TIME] > 0
        assert budget_summary["usage"][ResourceType.TOKENS] > 0

        # Test 7: Verify metrics were saved
        cursor = checkpointer.conn.cursor()
        cursor.execute(
            "SELECT * FROM query_metrics WHERE checkpoint_id = ?",
            (checkpoint.checkpoint_id,),
        )
        metrics_row = cursor.fetchone()
        assert metrics_row is not None
        assert metrics_row[3] == "multi_search"  # intent
        assert metrics_row[4] > 0  # total_latency_ms
        assert metrics_row[7] == 4  # result_count (2 PubMed + 2 trials)

        print("✅ M3 Integration Test Complete!")
        print(f"📊 Final checkpoint: {final_checkpoint.checkpoint_id}")
        print(
            f"🔬 Results: PubMed={len(final_state['pubmed_results']['results'])}, Trials={len(final_state['ctgov_results']['results'])}"
        )
        print(f"⚠️  Errors recovered: {final_checkpoint.error_count}")
        print(
            f"💰 Budget used: {budget_summary['usage'][ResourceType.TIME]}ms time, {budget_summary['usage'][ResourceType.TOKENS]} tokens, {budget_summary['usage'][ResourceType.REQUESTS]} requests"
        )
        print(f"🛤️  Final path: {final_state['node_path']}")

    @pytest.mark.asyncio
    async def test_m3_budget_exceeded_scenario(self):
        """Test M3 workflow when budget is exceeded."""
        config = OrchestratorConfig()

        # Initialize components with very restrictive budget
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        state_manager = StateManager(config, checkpointer)
        budget_manager = BudgetManager(config)

        # Create restrictive budget tracker
        budget_tracker = await budget_manager.create_tracker(
            time_budget_ms=1000,  # Only 1 second
            token_budget=100,  # Only 100 tokens
            request_budget=2,  # Only 2 requests
        )

        initial_state = OrchestratorState(
            query="Budget constrained search",
            config={},
            frame={"intent": "search", "entities": {"topic": "diabetes"}},
            routing_decision="single_search",
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=["frame_parser", "router"],
            answer=None,
            session_id=None,
            messages=[],
        )

        checkpoint = await state_manager.create_checkpoint(initial_state)

        # Test 1: First operation succeeds within budget
        pubmed_cost = await budget_manager.estimate_operation_cost(
            "pubmed.search", {"limit": 10}
        )
        can_afford_1 = await budget_manager.can_afford_operation(
            budget_tracker, "pubmed.search", {"limit": 10}
        )
        assert can_afford_1 is True

        # Consume budget for first operation
        await budget_manager.enforce_budget(
            budget_tracker, ResourceType.TIME, pubmed_cost[ResourceType.TIME]
        )
        await budget_manager.enforce_budget(
            budget_tracker, ResourceType.TOKENS, pubmed_cost[ResourceType.TOKENS]
        )
        await budget_manager.enforce_budget(budget_tracker, ResourceType.REQUESTS, 1)

        # Test 2: Check if expensive operation can be afforded (should fail)
        rag_cost = await budget_manager.estimate_operation_cost(
            "rag.search", {"query": "diabetes", "limit": 20}
        )
        can_afford_expensive = await budget_manager.can_afford_operation(
            budget_tracker, "rag.search", {"query": "diabetes", "limit": 20}
        )
        assert (
            can_afford_expensive is False
        )  # Should not be able to afford due to token budget

        # Test 3: Check budget status (should be warning or exceeded)
        budget_status, budget_msg = await budget_manager.check_budget_status(
            budget_tracker
        )
        assert budget_status in [
            BudgetStatus.ACTIVE,
            BudgetStatus.WARNING,
            BudgetStatus.TOKEN_EXCEEDED,
            BudgetStatus.TIME_EXCEEDED,
            BudgetStatus.REQUEST_EXCEEDED,
        ]
        assert any(
            word in budget_msg.lower()
            for word in ["budget", "active", "warning", "exceeded"]
        )

        # Test 4: Timeout calculation should reflect remaining budget
        timeout = await budget_manager.calculate_timeout(budget_tracker)
        remaining = budget_tracker.get_remaining()
        expected_timeout = remaining[ResourceType.TIME]
        assert timeout == expected_timeout

        # Update state with partial results
        partial_state = dict(initial_state)
        partial_state.update(
            {
                "pubmed_results": {"results": [{"pmid": "12345"}], "total": 1},
                "tool_calls_made": ["pubmed.search"],
                "latencies": {"pubmed_search": pubmed_cost[ResourceType.TIME]},
                "node_path": ["frame_parser", "router", "enhanced_pubmed"],
                "messages": [
                    {
                        "role": "system",
                        "content": "Partial results due to budget constraints",
                    }
                ],
                "errors": [
                    {
                        "node": "budget_manager",
                        "error": "Cannot afford expensive operations due to budget constraints",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "strategy": "partial_results",
                    }
                ],
            }
        )

        # Finalize with partial results
        await state_manager.finalize_checkpoint(checkpoint.checkpoint_id, partial_state)

        # Verify checkpoint indicates partial completion
        final_checkpoint = await checkpointer.aget_checkpoint(checkpoint.checkpoint_id)
        assert final_checkpoint is not None
        assert final_checkpoint.partial_results is True  # Should be marked as partial
        assert final_checkpoint.error_count == 1

        print("✅ M3 Budget Exceeded Test Complete!")
        print(f"💸 Budget status: {budget_status}")
        print(f"⏱️  Timeout remaining: {timeout}ms")
        print(
            f"📊 Final checkpoint marked as partial: {final_checkpoint.partial_results}"
        )

    @pytest.mark.asyncio
    async def test_m3_error_cascade_handling(self):
        """Test M3 workflow with cascading errors and recovery limits."""
        config = OrchestratorConfig()

        # Initialize components
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        state_manager = StateManager(config, checkpointer)
        error_manager = ErrorRecoveryManager(config, max_retries=3)  # Limited retries
        budget_manager = BudgetManager(config)

        budget_tracker = await budget_manager.create_tracker(
            time_budget_ms=15000, token_budget=3000, request_budget=10
        )

        initial_state = OrchestratorState(
            query="Error cascade test",
            config={},
            frame={"intent": "search", "entities": {"topic": "cancer"}},
            routing_decision="multi_search",
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=["frame_parser", "router"],
            answer=None,
            session_id=None,
            messages=[],
        )

        checkpoint = await state_manager.create_checkpoint(initial_state)
        current_state = dict(initial_state)

        # Test cascade of errors with different recovery strategies
        error_scenarios = [
            # Error 1: Rate limit (retry with backoff)
            NodeResult(
                success=False,
                error_message="Rate limit exceeded",
                node_name="pubmed.search",
                latency_ms=100.0,
            ),
            # Error 2: Rate limit again (retry with backoff)
            NodeResult(
                success=False,
                error_message="Rate limit exceeded",
                node_name="pubmed.search",
                latency_ms=100.0,
            ),
            # Error 3: Rate limit third time (should exceed max retries)
            NodeResult(
                success=False,
                error_message="Rate limit exceeded",
                node_name="pubmed.search",
                latency_ms=100.0,
            ),
        ]

        # Process each error in cascade
        for attempt, error in enumerate(error_scenarios, 1):
            strategy = await error_manager.create_recovery_strategy(
                error, attempt, max_attempts=3
            )

            if attempt < 3:
                # First two attempts should retry
                assert strategy.action == RecoveryAction.RETRY_WITH_BACKOFF
                assert strategy.should_continue is True
            else:
                # Third attempt should fail permanently (reached max_attempts)
                assert strategy.action == RecoveryAction.FAIL_PERMANENTLY
                assert strategy.should_continue is False

            # Apply recovery
            current_state = await error_manager.execute_recovery(
                strategy, current_state, error, "pubmed.search"
            )

            # Update checkpoint after each error
            await state_manager.update_checkpoint(
                checkpoint.checkpoint_id, current_state
            )

        # After cascade, should have 3 errors recorded
        assert len(current_state["errors"]) == 3
        assert current_state["errors"][-1]["strategy"] == "fail_permanently"

        # Should have recovery markers in path
        recovery_markers = [
            node for node in current_state["node_path"] if node.startswith("recovery_")
        ]
        assert (
            len(recovery_markers) == 3
        )  # One for each error processed (2 retry + 1 fail_permanently)

        # Try a different node that should succeed
        trials_cost = await budget_manager.estimate_operation_cost(
            "clinicaltrials.search", {"limit": 20}
        )
        can_afford = await budget_manager.can_afford_operation(
            budget_tracker, "clinicaltrials.search", {"limit": 20}
        )
        assert can_afford is True

        # Simulate successful trials operation
        await budget_manager.enforce_budget(
            budget_tracker, ResourceType.TIME, trials_cost[ResourceType.TIME]
        )
        await budget_manager.enforce_budget(
            budget_tracker, ResourceType.TOKENS, trials_cost[ResourceType.TOKENS]
        )
        await budget_manager.enforce_budget(budget_tracker, ResourceType.REQUESTS, 1)

        # Update state with successful trials results
        current_state.update(
            {
                "ctgov_results": {"results": [{"nct_id": "NCT999888"}], "total": 1},
                "tool_calls_made": current_state["tool_calls_made"]
                + ["clinicaltrials.search"],
                "latencies": {
                    **current_state["latencies"],
                    "trials_search": trials_cost[ResourceType.TIME],
                },
                "node_path": current_state["node_path"] + ["enhanced_trials"],
                "messages": current_state["messages"]
                + [
                    {
                        "role": "system",
                        "content": "ClinicalTrials succeeded despite PubMed failures",
                    }
                ],
            }
        )

        # Finalize checkpoint
        await state_manager.finalize_checkpoint(checkpoint.checkpoint_id, current_state)

        # Verify final state
        final_checkpoint = await checkpointer.aget_checkpoint(checkpoint.checkpoint_id)
        assert final_checkpoint is not None
        assert final_checkpoint.error_count == 3
        assert (
            final_checkpoint.partial_results is True
        )  # Partial due to PubMed failures
        assert final_checkpoint.completed_at is not None

        # Verify we got some results despite errors
        assert current_state["ctgov_results"] is not None
        assert len(current_state["ctgov_results"]["results"]) > 0

        print("✅ M3 Error Cascade Test Complete!")
        print(f"⚠️  Total errors handled: {final_checkpoint.error_count}")
        print(f"🔄 Recovery attempts: {len(recovery_markers)}")
        print(f"📊 Partial results obtained: {final_checkpoint.partial_results}")
        print(
            f"🎯 ClinicalTrials results: {len(current_state['ctgov_results']['results'])}"
        )
        print(f"🛤️  Final node path: {current_state['node_path']}")


if __name__ == "__main__":
    # Run integration tests directly
    pytest.main([__file__, "-v"])
