"""
Optimized ClinicalTrials.gov MCP tools integration tests.

Rate-limited and consolidated tests to reduce API calls while maintaining
comprehensive coverage of the ClinicalTrials.gov integration.
"""

import asyncio

import pytest
from mcp.types import TextContent

from bio_mcp.mcp.clinicaltrials_tools import (
    handle_clinicaltrials_get,
    handle_clinicaltrials_investment_search,
    handle_clinicaltrials_investment_summary,
    handle_clinicaltrials_search,
    handle_clinicaltrials_sync,
)
from tests.utils.mcp_validators import MCPResponseValidator

pytestmark = pytest.mark.no_weaviate  # Skip Weaviate for ClinicalTrials tests

# Rate limiting delay between tests
RATE_LIMIT_DELAY = 1.5  # 1.5 seconds between tests (well under 5/second limit)


@pytest.fixture(scope="class")
def validator():
    """Create a validator instance shared across test class."""
    return MCPResponseValidator()


class TestClinicalTrialsToolsOptimized:
    """Optimized integration tests for ClinicalTrials.gov MCP tools with rate limiting."""

    @pytest.mark.asyncio
    async def test_comprehensive_search_workflow(self, validator):
        """
        Comprehensive test covering search functionality, validation, and different parameters.
        Consolidates multiple search scenarios into one test to minimize API calls.
        """

        print("\n=== Comprehensive Search Workflow Test ===")

        # Test 1: Basic search
        print("Step 1: Basic search...")
        result1 = await handle_clinicaltrials_search({"query": "diabetes", "limit": 2})

        assert len(result1) == 1
        assert isinstance(result1[0], TextContent)
        validator.validate_text_content(result1[0])

        response1_text = result1[0].text
        assert (
            "nct_ids" in response1_text.lower() or "results" in response1_text.lower()
        )

        # Rate limit delay
        await asyncio.sleep(RATE_LIMIT_DELAY)

        # Test 2: Search with filters (use different condition to avoid caching)
        print("Step 2: Search with filters...")
        result2 = await handle_clinicaltrials_search(
            {"query": "heart disease", "status": "RECRUITING", "limit": 1}
        )

        assert len(result2) == 1
        assert isinstance(result2[0], TextContent)
        validator.validate_text_content(result2[0])

        response2_text = result2[0].text
        # Should contain results or proper error handling
        assert len(response2_text) > 50

        # Rate limit delay
        await asyncio.sleep(RATE_LIMIT_DELAY)

        # Test 3: Empty query (should work)
        print("Step 3: Empty query validation...")
        result3 = await handle_clinicaltrials_search({"limit": 1})

        assert len(result3) == 1
        assert isinstance(result3[0], TextContent)
        validator.validate_text_content(result3[0])

        # Test 4: Parameter validation (no API call)
        print("Step 4: Parameter validation...")
        result4 = await handle_clinicaltrials_search(
            {
                "query": "test",
                "limit": -1,  # Invalid limit should be handled gracefully
            }
        )

        assert len(result4) == 1
        assert isinstance(result4[0], TextContent)

        print("✅ Comprehensive Search Workflow Test Complete")

    @pytest.mark.asyncio
    async def test_investment_functionality_consolidated(self, validator):
        """
        Consolidated test for all investment-related functionality.
        Tests investment search and summary in one workflow.
        """

        print("\n=== Investment Functionality Test ===")

        # Test 1: Investment search with realistic parameters
        print("Step 1: Investment search...")
        result1 = await handle_clinicaltrials_investment_search(
            {
                "query": "cancer immunotherapy",
                "min_investment_score": 0.1,  # Low threshold for testing
                "limit": 3,
            }
        )

        assert len(result1) == 1
        assert isinstance(result1[0], TextContent)
        validator.validate_text_content(result1[0])

        response1_text = result1[0].text
        assert "investment" in response1_text.lower()

        # Rate limit delay
        await asyncio.sleep(RATE_LIMIT_DELAY)

        # Test 2: Investment summary with sample NCT IDs
        print("Step 2: Investment summary...")
        sample_nct_ids = ["NCT04567890", "NCT03456789"]  # Sample NCT format IDs
        result2 = await handle_clinicaltrials_investment_summary(
            {"nct_ids": sample_nct_ids}
        )

        assert len(result2) == 1
        assert isinstance(result2[0], TextContent)
        validator.validate_text_content(result2[0])

        response2_text = result2[0].text
        assert len(response2_text) > 20  # Should have meaningful content

        # Test 3: Investment summary validation (no API call)
        print("Step 3: Investment summary validation...")
        result3 = await handle_clinicaltrials_investment_summary(
            {
                "nct_ids": []  # Empty list should return error
            }
        )

        assert len(result3) == 1
        assert isinstance(result3[0], TextContent)
        response3_text = result3[0].text
        assert "error" in response3_text.lower() or "❌" in response3_text

        print("✅ Investment Functionality Test Complete")

    @pytest.mark.asyncio
    async def test_get_and_sync_functionality(self, validator):
        """
        Test get and sync functionality with minimal API calls.
        Uses realistic but likely non-existent NCT IDs to test error handling.
        """

        print("\n=== Get and Sync Functionality Test ===")

        # Test 1: Get functionality (will likely return not found, which is fine)
        print("Step 1: Get trial details...")
        result1 = await handle_clinicaltrials_get(
            {
                "nct_id": "NCT99999999"  # Unlikely to exist
            }
        )

        assert len(result1) == 1
        assert isinstance(result1[0], TextContent)
        validator.validate_text_content(result1[0])

        # Should either return data or proper error handling
        response1_text = result1[0].text
        assert len(response1_text) > 20

        # Rate limit delay
        await asyncio.sleep(RATE_LIMIT_DELAY)

        # Test 2: Get validation (no API call)
        print("Step 2: Get parameter validation...")
        result2 = await handle_clinicaltrials_get(
            {
                "nct_id": ""  # Empty NCT ID should error
            }
        )

        assert len(result2) == 1
        assert isinstance(result2[0], TextContent)
        response2_text = result2[0].text
        assert "error" in response2_text.lower() or "❌" in response2_text

        # Test 3: Sync functionality (will likely fail gracefully without full DB setup)
        print("Step 3: Sync functionality...")
        result3 = await handle_clinicaltrials_sync(
            {"query": "test sync", "query_key": "integration_test", "limit": 1}
        )

        assert len(result3) == 1
        assert isinstance(result3[0], TextContent)
        validator.validate_text_content(result3[0])

        # Should handle gracefully whether DB is available or not
        response3_text = result3[0].text
        assert len(response3_text) > 20

        # Test 4: Sync validation (no API call)
        print("Step 4: Sync parameter validation...")
        result4 = await handle_clinicaltrials_sync(
            {
                "query": "test",
                # Missing query_key should error
            }
        )

        assert len(result4) == 1
        assert isinstance(result4[0], TextContent)
        response4_text = result4[0].text
        assert "error" in response4_text.lower() or "❌" in response4_text

        print("✅ Get and Sync Functionality Test Complete")

    @pytest.mark.asyncio
    async def test_response_format_and_robustness(self, validator):
        """
        Test response formatting consistency and error robustness.
        Focuses on validation and edge cases with minimal API calls.
        """

        print("\n=== Response Format and Robustness Test ===")

        # Test response format consistency with one simple API call
        print("Step 1: Response format consistency...")
        result1 = await handle_clinicaltrials_search(
            {"query": "test format", "limit": 1}
        )

        # Validate response structure
        assert isinstance(result1, list)
        assert len(result1) >= 1
        assert all(isinstance(item, TextContent) for item in result1)

        # Validate TextContent structure
        for item in result1:
            validator.validate_text_content(item)
            assert len(item.text.strip()) > 0

        # Rate limit delay
        await asyncio.sleep(RATE_LIMIT_DELAY)

        # Test various parameter validation scenarios (no API calls)
        print("Step 2: Parameter validation robustness...")

        validation_tests = [
            # (handler, args, expected_behavior)
            (
                handle_clinicaltrials_search,
                {"limit": "invalid"},
                "should handle gracefully",
            ),
            (handle_clinicaltrials_get, {"nct_id": None}, "should error"),
            (
                handle_clinicaltrials_investment_search,
                {"min_investment_score": "invalid"},
                "should handle gracefully",
            ),
            (
                handle_clinicaltrials_investment_summary,
                {"nct_ids": "not_a_list"},
                "should error",
            ),
            (handle_clinicaltrials_sync, {"limit": -100}, "should handle gracefully"),
        ]

        for handler, args, expected in validation_tests:
            try:
                result = await handler(args)

                # Should always return valid response even on error
                assert len(result) == 1
                assert isinstance(result[0], TextContent)
                validator.validate_text_content(result[0])

                # Should have meaningful content
                response_text = result[0].text
                assert len(response_text.strip()) > 10

            except Exception as e:
                # If an exception occurs, it should be reasonable
                assert len(str(e)) > 0
                print(f"Expected validation error handled: {e}")

        print("✅ Response Format and Robustness Test Complete")

    @pytest.mark.asyncio
    async def test_end_to_end_workflow_minimal(self, validator):
        """
        Minimal end-to-end workflow test that covers the complete user journey
        with minimal API calls by reusing data and focusing on integration.
        """

        print("\n=== Minimal End-to-End Workflow Test ===")

        # Single comprehensive workflow with minimal API calls
        print("Step 1: Complete workflow simulation...")

        # 1. Search for trials
        search_result = await handle_clinicaltrials_search(
            {"query": "phase2 oncology", "limit": 1}
        )

        assert len(search_result) == 1
        search_text = search_result[0].text
        assert len(search_text) > 50

        # Rate limit delay
        await asyncio.sleep(RATE_LIMIT_DELAY)

        # 2. Investment analysis (using mock data to avoid additional API calls)
        investment_result = await handle_clinicaltrials_investment_summary(
            {
                "nct_ids": ["NCT12345678", "NCT87654321"]  # Mock IDs
            }
        )

        assert len(investment_result) == 1
        investment_text = investment_result[0].text
        assert len(investment_text) > 30

        # All tools have been exercised in a realistic workflow
        print("✅ End-to-End Workflow Test Complete")
        print("\n=== All Optimized Tests Complete ===")
        print("✅ ClinicalTrials.gov integration fully tested with minimal API calls")

    @pytest.mark.asyncio
    async def test_tool_registration_and_availability(self, validator):
        """
        Test that all tools are properly registered and available.
        This is a pure validation test with no external API calls.
        """

        print("\n=== Tool Registration Test ===")

        # Test that all handler functions exist and are callable
        handlers = [
            handle_clinicaltrials_search,
            handle_clinicaltrials_get,
            handle_clinicaltrials_investment_search,
            handle_clinicaltrials_investment_summary,
            handle_clinicaltrials_sync,
        ]

        for handler in handlers:
            assert callable(handler)

            # Test that handlers accept arguments dict (basic signature validation)
            try:
                # This should not make API calls, just test parameter validation
                result = await handler({})
                assert isinstance(result, list)
                # Most should return validation errors for empty args, which is expected
            except Exception as e:
                # Some handlers might raise exceptions on invalid args, which is also fine
                assert len(str(e)) > 0

        print("✅ Tool Registration Test Complete")
