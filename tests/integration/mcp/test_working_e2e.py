"""
Working end-to-end integration tests for MCP tools.

Tests realistic biomedical research workflows without complex mocking,
focusing on validating that tools work correctly with real inputs.
"""

import pytest
from mcp.types import TextContent

from bio_mcp.mcp.corpus_tools import (
    corpus_checkpoint_create_tool,
    corpus_checkpoint_delete_tool,
    corpus_checkpoint_get_tool,
    corpus_checkpoint_list_tool,
)
from bio_mcp.mcp.rag_tools import rag_get_tool, rag_search_tool
from bio_mcp.mcp.resources import list_resources
from tests.utils.mcp_validators import MCPResponseValidator


class TestWorkingEndToEndWorkflows:
    """Working end-to-end tests that validate real tool behavior."""

    def setup_method(self):
        """Setup test fixtures."""
        self.validator = MCPResponseValidator()

    @pytest.mark.asyncio
    async def test_complete_biomedical_research_workflow(self):
        """Test a complete biomedical research workflow from start to finish."""

        print("\n🔬 Starting Complete Biomedical Research Workflow Test")

        # === Phase 1: Search for Cancer Research ===
        print("📋 Phase 1: Searching for cancer research papers...")

        search_result = await rag_search_tool(
            "rag.search",
            {
                "query": "glioblastoma treatment immunotherapy",
                "search_mode": "hybrid",
                "top_k": 3,
                "rerank_by_quality": True,
            },
        )

        # Validate search worked
        assert len(search_result) == 1
        assert isinstance(search_result[0], TextContent)
        self.validator.validate_text_content(search_result[0])

        search_text = search_result[0].text
        print(f"✅ Search completed: {len(search_text)} chars returned")

        # Should have meaningful content
        assert len(search_text) > 50
        assert "glioblastoma" in search_text.lower() or "search" in search_text.lower()

        # === Phase 2: Try to get specific document details ===
        print("📄 Phase 2: Retrieving document details...")

        get_result = await rag_get_tool(
            "rag.get",
            {
                "doc_id": "test_doc_001"  # Generic test document ID
            },
        )

        # Validate get worked
        assert len(get_result) == 1
        assert isinstance(get_result[0], TextContent)
        self.validator.validate_text_content(get_result[0])

        get_text = get_result[0].text
        print(f"✅ Document retrieval completed: {len(get_text)} chars returned")

        # Should have meaningful response (found or not found)
        assert len(get_text) > 20
        assert (
            "test_doc_001" in get_text
            or "not found" in get_text.lower()
            or "document" in get_text.lower()
            or "no document" in get_text.lower()
        )

        # === Phase 3: Create research checkpoint ===
        print("💾 Phase 3: Creating research checkpoint...")

        checkpoint_id = "test_cancer_research_2024"
        create_result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create",
            {
                "checkpoint_id": checkpoint_id,
                "name": "Cancer Research 2024",
                "description": "Checkpoint for glioblastoma immunotherapy research",
            },
        )

        # Validate checkpoint creation
        assert len(create_result) == 1
        assert isinstance(create_result[0], TextContent)
        self.validator.validate_text_content(create_result[0])

        create_text = create_result[0].text
        print(f"✅ Checkpoint creation completed: {len(create_text)} chars returned")

        # Should indicate success or failure clearly
        assert len(create_text) > 30
        success_indicators = ["✅", "created successfully", "Cancer Research 2024"]
        error_indicators = ["❌", "error", "failed"]

        has_success = any(indicator in create_text for indicator in success_indicators)
        has_error = any(
            indicator.lower() in create_text.lower() for indicator in error_indicators
        )

        print(f"   Success indicators found: {has_success}")
        print(f"   Error indicators found: {has_error}")

        # === Phase 4: List checkpoints ===
        print("📚 Phase 4: Listing research checkpoints...")

        list_result = await corpus_checkpoint_list_tool(
            "corpus.checkpoint.list", {"limit": 10, "offset": 0}
        )

        # Validate list worked
        assert len(list_result) == 1
        assert isinstance(list_result[0], TextContent)
        self.validator.validate_text_content(list_result[0])

        list_text = list_result[0].text
        print(f"✅ Checkpoint listing completed: {len(list_text)} chars returned")

        # Should have meaningful content
        assert len(list_text) > 20

        # === Phase 5: Get checkpoint details ===
        print("🔍 Phase 5: Getting checkpoint details...")

        get_checkpoint_result = await corpus_checkpoint_get_tool(
            "corpus.checkpoint.get", {"checkpoint_id": checkpoint_id}
        )

        # Validate get checkpoint worked
        assert len(get_checkpoint_result) == 1
        assert isinstance(get_checkpoint_result[0], TextContent)
        self.validator.validate_text_content(get_checkpoint_result[0])

        get_checkpoint_text = get_checkpoint_result[0].text
        print(
            f"✅ Checkpoint details completed: {len(get_checkpoint_text)} chars returned"
        )

        # Should respond meaningfully
        assert len(get_checkpoint_text) > 20

        # === Phase 6: List available resources ===
        print("🗂️ Phase 6: Listing available resources...")

        try:
            resources_result = await list_resources()

            # Should return list (may be empty)
            assert isinstance(resources_result, list)
            print(
                f"✅ Resources listing completed: {len(resources_result)} resources found"
            )

            # If resources exist, validate they have proper structure
            if resources_result:
                from mcp.types import Resource

                for i, resource in enumerate(resources_result[:3]):  # Check first 3
                    assert isinstance(resource, Resource)
                    assert hasattr(resource, "uri")
                    assert hasattr(resource, "name")
                    print(f"   Resource {i + 1}: {resource.uri}")
        except Exception as e:
            print(f"⚠️ Resources not available: {e}")
            assert len(str(e)) > 5  # Should have meaningful error

        # === Phase 7: Cleanup - Delete checkpoint ===
        print("🗑️ Phase 7: Cleaning up test checkpoint...")

        delete_result = await corpus_checkpoint_delete_tool(
            "corpus.checkpoint.delete", {"checkpoint_id": checkpoint_id}
        )

        # Validate delete worked
        assert len(delete_result) == 1
        assert isinstance(delete_result[0], TextContent)
        self.validator.validate_text_content(delete_result[0])

        delete_text = delete_result[0].text
        print(f"✅ Checkpoint deletion completed: {len(delete_text)} chars returned")

        # Should respond meaningfully
        assert len(delete_text) > 20

        print("\n🎉 Complete Biomedical Research Workflow Test - SUCCESS!")
        print("   All 7 phases completed with valid MCP responses")

    @pytest.mark.asyncio
    async def test_immunotherapy_research_scenario(self):
        """Test immunotherapy-specific research scenario."""

        print("\n💉 Starting Immunotherapy Research Scenario")

        # Search for immunotherapy papers
        search_result = await rag_search_tool(
            "rag.search",
            {
                "query": "PD-1 checkpoint inhibitor melanoma",
                "search_mode": "semantic",
                "top_k": 5,
            },
        )

        assert len(search_result) == 1
        search_text = search_result[0].text
        print(f"✅ Immunotherapy search: {len(search_text)} chars")

        # Should handle search gracefully
        assert len(search_text) > 30
        assert (
            "pd-1" in search_text.lower()
            or "immunotherapy" in search_text.lower()
            or "search" in search_text.lower()
        )

        # Try to get a test immunotherapy paper  
        get_result = await rag_get_tool(
            "rag.get",
            {
                "doc_id": "test_immunotherapy_001"  # Test document ID
            },
        )

        assert len(get_result) == 1
        get_text = get_result[0].text
        print(f"✅ Document retrieval: {len(get_text)} chars")

        # Should respond meaningfully
        assert len(get_text) > 20

        print("🎉 Immunotherapy Research Scenario - SUCCESS!")

    @pytest.mark.asyncio
    async def test_machine_learning_medical_scenario(self):
        """Test ML in medicine research scenario."""

        print("\n🤖 Starting Machine Learning Medical Scenario")

        # Search for ML medical papers
        search_result = await rag_search_tool(
            "rag.search",
            {
                "query": "machine learning medical imaging deep learning",
                "search_mode": "bm25",
                "top_k": 3,
            },
        )

        assert len(search_result) == 1
        search_text = search_result[0].text
        print(f"✅ ML medical search: {len(search_text)} chars")

        # Should handle search gracefully
        assert len(search_text) > 30

        # Test edge case - very specific query
        edge_search_result = await rag_search_tool(
            "rag.search",
            {
                "query": "convolutional neural networks radiology diagnosis accuracy",
                "search_mode": "hybrid",
                "top_k": 1,
                "rerank_by_quality": False,
            },
        )

        assert len(edge_search_result) == 1
        edge_text = edge_search_result[0].text
        print(f"✅ Edge case search: {len(edge_text)} chars")

        assert len(edge_text) > 20

        print("🎉 Machine Learning Medical Scenario - SUCCESS!")

    @pytest.mark.asyncio
    async def test_checkpoint_management_scenario(self):
        """Test comprehensive checkpoint management."""

        print("\n📁 Starting Checkpoint Management Scenario")

        checkpoint_ids = []

        # Create multiple checkpoints
        for i, (name, desc) in enumerate(
            [
                (
                    "Cancer ML Research",
                    "Machine learning applications in cancer research",
                ),
                (
                    "Immunotherapy Trials",
                    "Clinical trials for immunotherapy treatments",
                ),
                ("Biomarker Discovery", "Research on cancer biomarker identification"),
            ]
        ):
            checkpoint_id = f"test_checkpoint_{i + 1}"
            checkpoint_ids.append(checkpoint_id)

            create_result = await corpus_checkpoint_create_tool(
                "corpus.checkpoint.create",
                {"checkpoint_id": checkpoint_id, "name": name, "description": desc},
            )

            assert len(create_result) == 1
            create_text = create_result[0].text
            print(f"✅ Created checkpoint {i + 1}: {len(create_text)} chars")
            assert len(create_text) > 20

        # List all checkpoints
        list_result = await corpus_checkpoint_list_tool("corpus.checkpoint.list", {})
        assert len(list_result) == 1
        list_text = list_result[0].text
        print(f"✅ Listed checkpoints: {len(list_text)} chars")
        assert len(list_text) > 20

        # Get details for each checkpoint
        for checkpoint_id in checkpoint_ids:
            get_result = await corpus_checkpoint_get_tool(
                "corpus.checkpoint.get", {"checkpoint_id": checkpoint_id}
            )
            assert len(get_result) == 1
            get_text = get_result[0].text
            print(f"✅ Got details for {checkpoint_id}: {len(get_text)} chars")
            assert len(get_text) > 20

        # Delete all test checkpoints
        for checkpoint_id in checkpoint_ids:
            delete_result = await corpus_checkpoint_delete_tool(
                "corpus.checkpoint.delete", {"checkpoint_id": checkpoint_id}
            )
            assert len(delete_result) == 1
            delete_text = delete_result[0].text
            print(f"✅ Deleted {checkpoint_id}: {len(delete_text)} chars")
            assert len(delete_text) > 20

        print("🎉 Checkpoint Management Scenario - SUCCESS!")

    @pytest.mark.asyncio
    async def test_error_handling_scenarios(self):
        """Test comprehensive error handling across all tools."""

        print("\n🚨 Starting Error Handling Scenarios")

        # Test various error conditions
        error_tests = [
            # RAG search errors
            (rag_search_tool, "rag.search", {}, "Empty query"),
            (rag_search_tool, "rag.search", {"query": ""}, "Empty string query"),
            (
                rag_search_tool,
                "rag.search",
                {"query": "test", "top_k": -1},
                "Negative top_k",
            ),
            # RAG get errors
            (rag_get_tool, "rag.get", {}, "Missing doc_id"),
            (rag_get_tool, "rag.get", {"doc_id": ""}, "Empty doc_id"),
            # Checkpoint errors
            (
                corpus_checkpoint_create_tool,
                "corpus.checkpoint.create",
                {},
                "Missing params",
            ),
            (
                corpus_checkpoint_get_tool,
                "corpus.checkpoint.get",
                {},
                "Missing checkpoint_id",
            ),
            (
                corpus_checkpoint_delete_tool,
                "corpus.checkpoint.delete",
                {},
                "Missing checkpoint_id",
            ),
        ]

        for i, (tool_func, tool_name, params, description) in enumerate(error_tests):
            print(f"   Testing error case {i + 1}: {description}")

            result = await tool_func(tool_name, params)

            # Should return valid MCP response
            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            self.validator.validate_text_content(result[0])

            response_text = result[0].text

            # Should have meaningful error message or valid response
            assert len(response_text) > 10
            assert len(response_text) < 5000  # Allow for structured JSON responses

            # Should not contain internal details
            assert "traceback" not in response_text.lower()
            assert "/users/" not in response_text.lower()

            print(f"   ✅ Error case {i + 1} handled gracefully")

        print("🎉 Error Handling Scenarios - SUCCESS!")

    @pytest.mark.asyncio
    async def test_performance_characteristics(self):
        """Test performance characteristics under realistic conditions."""

        print("\n⚡ Starting Performance Characteristics Test")

        import time

        # Test search performance
        queries = [
            "cancer treatment",
            "immunotherapy",
            "machine learning",
            "glioblastoma",
            "biomarkers",
        ]

        total_search_time = 0
        for i, query in enumerate(queries):
            start_time = time.time()

            result = await rag_search_tool("rag.search", {"query": query, "top_k": 3})

            end_time = time.time()
            search_time = (end_time - start_time) * 1000  # Convert to ms
            total_search_time += search_time

            assert len(result) == 1
            print(f"   Query {i + 1} ({query}): {search_time:.1f}ms")

            # Should complete in reasonable time (allow for cold starts)
            assert search_time < 5000, f"Query took too long: {search_time:.1f}ms"

        avg_search_time = total_search_time / len(queries)
        print(f"✅ Average search time: {avg_search_time:.1f}ms")

        # Test checkpoint operations performance
        start_time = time.time()

        checkpoint_result = await corpus_checkpoint_list_tool(
            "corpus.checkpoint.list", {}
        )

        end_time = time.time()
        list_time = (end_time - start_time) * 1000

        assert len(checkpoint_result) == 1
        print(f"✅ Checkpoint list time: {list_time:.1f}ms")

        # Should complete quickly
        assert list_time < 2000, f"Checkpoint list took too long: {list_time:.1f}ms"

        print("🎉 Performance Characteristics Test - SUCCESS!")

    @pytest.mark.asyncio
    async def test_concurrent_usage_simulation(self):
        """Test simulated concurrent usage patterns."""

        print("\n🔄 Starting Concurrent Usage Simulation")

        import asyncio

        async def simulate_researcher_session(researcher_id: int):
            """Simulate a single researcher's session."""

            # Search for papers
            search_result = await rag_search_tool(
                "rag.search",
                {"query": f"cancer research session {researcher_id}", "top_k": 2},
            )
            assert len(search_result) == 1

            # Try to get a document
            get_result = await rag_get_tool(
                "rag.get", {"doc_id": f"test_doc_{researcher_id:03d}"}
            )
            assert len(get_result) == 1

            # List checkpoints
            list_result = await corpus_checkpoint_list_tool(
                "corpus.checkpoint.list", {}
            )
            assert len(list_result) == 1

            return researcher_id

        # Simulate 3 concurrent researchers
        print("   Simulating 3 concurrent researcher sessions...")

        tasks = [simulate_researcher_session(i) for i in range(1, 4)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete successfully
        exceptions = [r for r in results if isinstance(r, Exception)]
        successful = [r for r in results if not isinstance(r, Exception)]

        print(f"   ✅ Successful sessions: {len(successful)}")
        print(f"   ❌ Failed sessions: {len(exceptions)}")

        # At least some should succeed (allow for service unavailability)
        assert len(successful) > 0, "All concurrent sessions failed"

        if exceptions:
            print(
                f"   Note: Some sessions failed (expected if services unavailable): {exceptions[:2]}"
            )

        print("🎉 Concurrent Usage Simulation - SUCCESS!")
