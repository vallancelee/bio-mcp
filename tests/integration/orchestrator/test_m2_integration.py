"""Integration test for M2 LangGraph Tool Integration milestone."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock

import pytest

from bio_mcp.orchestrator.adapters.mcp_adapter import MCPToolAdapter
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.execution.parallel_executor import ParallelExecutor
from bio_mcp.orchestrator.middleware.rate_limiter import TokenBucketRateLimiter
from bio_mcp.orchestrator.nodes.enhanced_tool_nodes import (
    EnhancedPubMedNode,
    EnhancedTrialsNode,
)
from bio_mcp.orchestrator.types import NodeResult, OrchestratorState


class TestM2Integration:
    """Integration test for M2 milestone components."""

    @pytest.mark.asyncio
    async def test_m2_full_workflow_integration(self):
        """Test complete M2 workflow with all components integrated."""
        config = OrchestratorConfig()
        db_manager = Mock()

        # Test 1: MCPToolAdapter with rate limiting
        rate_limiter = TokenBucketRateLimiter(capacity=10, refill_rate=5.0)
        adapter = MCPToolAdapter(config, db_manager)

        # Mock a real tool
        mock_pubmed_tool = Mock()
        mock_pubmed_tool.execute = AsyncMock(
            return_value={
                "results": [{"pmid": "12345", "title": "Diabetes Research"}],
                "total": 1,
            }
        )
        adapter._tools = {"pubmed.search": mock_pubmed_tool}

        # Test direct tool execution
        result = await adapter.execute_tool("pubmed.search", {"term": "diabetes"})
        assert result.success
        assert result.data["total"] == 1

        # Test 2: Parallel execution with rate limiting
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=3)

        async def mock_search_task(term: str) -> NodeResult:
            return NodeResult(
                success=True,
                data={
                    "results": [
                        {"pmid": f"pmid_{term}", "title": f"Article about {term}"}
                    ],
                    "total": 1,
                },
                node_name="mock_search",
            )

        parallel_tasks = [
            {
                "func": mock_search_task,
                "args": ("diabetes",),
                "kwargs": {},
                "token_cost": 1,
            },
            {
                "func": mock_search_task,
                "args": ("cancer",),
                "kwargs": {},
                "token_cost": 1,
            },
        ]

        parallel_results = await executor.execute_parallel(parallel_tasks)
        assert len(parallel_results) == 2
        assert all(r.success for r in parallel_results)

        # Test 3: Enhanced PubMed Node with full integration
        pubmed_node = EnhancedPubMedNode(config, db_manager)

        # Mock the node's adapter to return realistic results
        pubmed_node.adapter.execute_tool = AsyncMock(
            return_value=NodeResult(
                success=True,
                data={
                    "results": [
                        {"pmid": "11111", "title": "Diabetes Type 1 Study"},
                        {"pmid": "22222", "title": "Pharma Company Research"},
                    ],
                    "total": 2,
                },
                cache_hit=False,
                latency_ms=150.0,
                node_name="pubmed.search",
            )
        )

        pubmed_state = OrchestratorState(
            query="diabetes research from pharma companies",
            config={},
            frame={
                "entities": {"topic": "diabetes", "company": "Pfizer"},
                "filters": {"published_within_days": 90},
            },
            routing_decision=None,
            pubmed_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=[],
            messages=[],
        )

        pubmed_result = await pubmed_node(pubmed_state)

        assert "pubmed_results" in pubmed_result
        assert pubmed_result["pubmed_results"]["total_results"] == 2
        assert "diabetes" in pubmed_result["pubmed_results"]["search_terms"]
        assert "Pfizer[AD]" in pubmed_result["pubmed_results"]["search_terms"]
        assert "enhanced_pubmed" in pubmed_result["node_path"]

        # Test 4: Enhanced Trials Node with quality filtering
        trials_node = EnhancedTrialsNode(config, db_manager)

        # Mock trials search with quality filtering scenarios
        trials_node.adapter.execute_tool = AsyncMock(
            return_value=NodeResult(
                success=True,
                data={
                    "results": [
                        {
                            "nct_id": "NCT123456",
                            "title": "Diabetes Phase III Trial",
                            "status": "recruiting",
                            "phase": "Phase III",
                            "start_date": "2023-01-01",
                        },
                        {
                            "nct_id": "NCT789012",
                            "title": "Withdrawn Trial",
                            "status": "withdrawn",
                            "phase": "Phase I",
                        },
                        {
                            "nct_id": "NCT345678",
                            "title": "Active Diabetes Study",
                            "status": "active, not recruiting",
                            "phase": "Phase II",
                            "start_date": "2022-06-01",
                            "enrollment": {"actual": 100, "target": 150},
                        },
                    ],
                    "total": 3,
                },
                cache_hit=False,
                latency_ms=200.0,
                node_name="clinicaltrials.search",
            )
        )

        trials_state = OrchestratorState(
            query="diabetes clinical trials",
            config={},
            frame={
                "entities": {"indication": "diabetes"},
                "filters": {"phase": "Phase III", "status": "recruiting"},
            },
            routing_decision=None,
            trials_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=[],
            messages=[],
        )

        trials_result = await trials_node(trials_state)

        assert "ctgov_results" in trials_result
        # Should filter out withdrawn trial, so 2 quality trials
        assert trials_result["ctgov_results"]["filtered_count"] == 2
        assert trials_result["ctgov_results"]["total_found"] == 3
        assert "enhanced_trials" in trials_result["node_path"]

        # Verify quality filtering worked
        processed_trials = trials_result["ctgov_results"]["trials"]
        nct_ids = {trial["nct_id"] for trial in processed_trials}
        assert "NCT123456" in nct_ids  # recruiting trial kept
        assert "NCT345678" in nct_ids  # active trial kept
        assert "NCT789012" not in nct_ids  # withdrawn trial filtered out

        # Verify relevance scoring and enhancement
        for trial in processed_trials:
            assert "relevance_score" in trial
            assert "enrollment_speed" in trial
            assert "completion_likelihood" in trial

        # Test 5: End-to-end workflow simulation
        # Simulate a complete orchestrator workflow using all M2 components

        workflow_state = OrchestratorState(
            query="Find recent diabetes research and related clinical trials from pharmaceutical companies",
            config={},
            frame={
                "entities": {
                    "topic": "diabetes",
                    "indication": "diabetes",
                    "company": "Novartis",
                },
                "filters": {
                    "published_within_days": 365,
                    "phase": "Phase III",
                    "status": "recruiting",
                },
            },
            routing_decision="multi_search",
            pubmed_results=None,
            trials_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=["frame_parser", "router"],
            messages=[
                {
                    "role": "system",
                    "content": "Multi-source search initiated for diabetes research",
                }
            ],
        )

        # Execute PubMed search
        pubmed_enhanced_result = await pubmed_node(workflow_state)

        # Merge pubmed result back into workflow state for trials search
        merged_state = {**workflow_state, **pubmed_enhanced_result}

        # Execute Trials search with updated state
        trials_enhanced_result = await trials_node(merged_state)

        # Verify final workflow state - merge all results
        final_state = {**merged_state, **trials_enhanced_result}

        assert (
            len(final_state["node_path"]) == 4
        )  # frame_parser, router, enhanced_pubmed, enhanced_trials
        assert "pubmed_results" in final_state
        assert "ctgov_results" in final_state
        assert (
            len(final_state["tool_calls_made"]) >= 2
        )  # At least pubmed.search and clinicaltrials.search

        # Verify performance tracking
        assert "pubmed_search" in final_state["latencies"]
        assert "ctgov_search" in final_state["latencies"]
        assert "pubmed_search" in final_state["cache_hits"]
        assert "ctgov_search" in final_state["cache_hits"]

        # Verify message flow
        assert len(final_state["messages"]) >= 3  # initial + pubmed + trials messages

        print("✅ M2 Integration Test Complete!")
        print(
            f"📊 Final state contains {final_state['pubmed_results']['total_results']} PubMed results"
        )
        print(
            f"🔬 Final state contains {final_state['ctgov_results']['filtered_count']} quality trials"
        )
        print(f"⚡ Tool calls made: {final_state['tool_calls_made']}")
        print(f"🛤️  Node path: {final_state['node_path']}")

    @pytest.mark.asyncio
    async def test_m2_error_handling_integration(self):
        """Test M2 components error handling and resilience."""
        config = OrchestratorConfig()
        db_manager = Mock()

        # Test rate limiter under stress
        rate_limiter = TokenBucketRateLimiter(
            capacity=2, refill_rate=1.0
        )  # Very restrictive
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=5)

        async def slow_failing_task(should_fail: bool = False) -> NodeResult:
            if should_fail:
                raise ValueError("Simulated task failure")
            await asyncio.sleep(0.01)  # Small delay to test rate limiting
            return NodeResult(
                success=True, data={"status": "ok"}, node_name="test_task"
            )

        # Mix of successful and failing tasks
        stress_tasks = [
            {
                "func": slow_failing_task,
                "args": (False,),
                "kwargs": {},
                "token_cost": 1,
            },
            {
                "func": slow_failing_task,
                "args": (True,),
                "kwargs": {},
                "token_cost": 1,
            },  # This will fail
            {
                "func": slow_failing_task,
                "args": (False,),
                "kwargs": {},
                "token_cost": 1,
            },
        ]

        stress_results = await executor.execute_parallel(stress_tasks, timeout=1.0)

        assert len(stress_results) == 3
        assert stress_results[0].success
        assert not stress_results[1].success  # The failing task
        assert "Simulated task failure" in stress_results[1].error_message
        assert stress_results[2].success

        # Test node error handling
        pubmed_node = EnhancedPubMedNode(config, db_manager)

        # Test with empty entities (should trigger error path)
        error_state = OrchestratorState(
            query="generic query",
            config={},
            frame={"entities": {}, "filters": {}},  # Empty entities
            routing_decision=None,
            pubmed_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=[],
            messages=[],
        )

        error_result = await pubmed_node(error_state)

        assert "error" in error_result
        assert "No search terms found" in error_result["error"]
        assert "errors" in error_result
        assert len(error_result["errors"]) == 1
        assert error_result["errors"][0]["node"] == "enhanced_pubmed"

    @pytest.mark.asyncio
    async def test_m2_performance_characteristics(self):
        """Test M2 components performance and concurrency behavior."""

        # Test rate limiter performance characteristics
        rate_limiter = TokenBucketRateLimiter(capacity=5, refill_rate=10.0)

        # Consume all tokens immediately
        await rate_limiter.acquire(5)
        assert rate_limiter.get_available_tokens() == 0

        # Next acquisition should wait for refill
        start_time = time.time()
        await rate_limiter.acquire(1)
        elapsed = time.time() - start_time

        # Should have waited approximately 0.1 seconds (1 token / 10 per second)
        assert 0.05 <= elapsed <= 0.2  # Allow some margin

        # Test parallel executor concurrency limits
        executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=2)

        concurrent_counter = {"value": 0, "max_seen": 0}

        async def concurrency_tracking_task(task_id: str) -> NodeResult:
            concurrent_counter["value"] += 1
            concurrent_counter["max_seen"] = max(
                concurrent_counter["max_seen"], concurrent_counter["value"]
            )

            await asyncio.sleep(0.05)  # Hold the concurrency slot briefly

            concurrent_counter["value"] -= 1
            return NodeResult(
                success=True, data={"task_id": task_id}, node_name="concurrency_test"
            )

        concurrency_tasks = [
            {
                "func": concurrency_tracking_task,
                "args": (f"task_{i}",),
                "kwargs": {},
                "token_cost": 1,
            }
            for i in range(4)
        ]

        concurrency_results = await executor.execute_parallel(concurrency_tasks)

        # Should not have exceeded max concurrency of 2
        assert concurrent_counter["max_seen"] <= 2
        assert len(concurrency_results) == 4
        assert all(r.success for r in concurrency_results)

        print("✅ M2 Performance Test Complete!")
        print(
            f"🎯 Max concurrency observed: {concurrent_counter['max_seen']} (limit: 2)"
        )
        print(f"⏱️  Rate limiter delay measured: {elapsed:.3f}s")
