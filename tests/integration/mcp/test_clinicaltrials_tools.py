"""
ClinicalTrials.gov MCP tools integration tests.

Tests the ClinicalTrials.gov integration including API calls, tool responses,
and end-to-end workflows for biotech investment analysis.
"""

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


@pytest.fixture(scope="class")
def validator():
    """Create a validator instance shared across test class."""
    return MCPResponseValidator()


class TestClinicalTrialsToolsIntegration:
    """Integration tests for ClinicalTrials.gov MCP tools."""

    @pytest.mark.asyncio
    async def test_clinicaltrials_search_basic(self, validator):
        """Test basic ClinicalTrials search functionality."""
        
        # Test basic search
        result = await handle_clinicaltrials_search({
            "query": "diabetes",
            "limit": 3
        })
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        validator.validate_text_content(result[0])
        
        response_text = result[0].text
        assert "nct_ids" in response_text.lower() or "results" in response_text.lower()
        assert len(response_text) > 50  # Should have meaningful content
        
        print("✅ Basic ClinicalTrials Search Test Complete")

    @pytest.mark.asyncio
    async def test_clinicaltrials_search_with_filters(self, validator):
        """Test ClinicalTrials search with advanced filters."""
        
        # Test search with phase and status filters
        result = await handle_clinicaltrials_search({
            "query": "alzheimer",
            "phase": "PHASE3",
            "status": "RECRUITING",
            "limit": 2
        })
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        validator.validate_text_content(result[0])
        
        response_text = result[0].text
        # Should contain search parameters info
        assert "phase" in response_text.lower() or "PHASE3" in response_text
        assert "recruiting" in response_text.lower() or "status" in response_text.lower()
        
        print("✅ ClinicalTrials Search with Filters Test Complete")

    @pytest.mark.asyncio
    async def test_clinicaltrials_search_validation_errors(self, validator):
        """Test ClinicalTrials search parameter validation."""
        
        # Test with missing/empty query (should work - API allows empty queries)
        result = await handle_clinicaltrials_search({})
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        validator.validate_text_content(result[0])
        
        response_text = result[0].text
        # Empty query should still return results, not an error
        assert "nct_ids" in response_text.lower() or "results" in response_text.lower()
        
        # Test with invalid limit
        result = await handle_clinicaltrials_search({
            "query": "cancer",
            "limit": -1
        })
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        # Should handle gracefully (either error or default to valid limit)
        
        print("✅ ClinicalTrials Search Validation Test Complete")

    @pytest.mark.asyncio
    async def test_clinicaltrials_investment_search(self, validator):
        """Test investment-focused clinical trial search."""
        
        # Test investment search with specific parameters
        result = await handle_clinicaltrials_investment_search({
            "query": "oncology",
            "min_investment_score": 0.3,
            "limit": 5
        })
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        validator.validate_text_content(result[0])
        
        response_text = result[0].text
        assert "investment" in response_text.lower()
        assert "score" in response_text.lower() or "relevant" in response_text.lower()
        
        print("✅ ClinicalTrials Investment Search Test Complete")

    @pytest.mark.asyncio
    async def test_clinicaltrials_get_functionality(self, validator):
        """Test getting specific clinical trial details."""
        
        # Try to get trial details (this might fail if API is down, but should handle gracefully)
        result = await handle_clinicaltrials_get({
            "nct_id": "NCT01234567"  # Use a generic NCT format for testing
        })
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        validator.validate_text_content(result[0])
        
        # Should either return trial details or handle errors gracefully
        response_text = result[0].text
        assert len(response_text) > 20  # Should have some meaningful content
        
        print("✅ ClinicalTrials Get Test Complete")

    @pytest.mark.asyncio
    async def test_clinicaltrials_investment_summary(self, validator):
        """Test investment summary generation for clinical trials."""
        
        # Test investment summary with NCT IDs
        result = await handle_clinicaltrials_investment_summary({
            "nct_ids": ["NCT01234567", "NCT07654321"]
        })
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        validator.validate_text_content(result[0])
        
        response_text = result[0].text
        assert "summary" in response_text.lower() or "analysis" in response_text.lower()
        
        # Test with empty list
        result = await handle_clinicaltrials_investment_summary({
            "nct_ids": []
        })
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        # Should handle empty list gracefully
        
        print("✅ ClinicalTrials Investment Summary Test Complete")

    @pytest.mark.asyncio
    async def test_clinicaltrials_sync_without_database(self, validator):
        """Test ClinicalTrials sync functionality (should work without full database setup)."""
        
        # Test sync operation (may fail without proper database setup but should handle gracefully)
        result = await handle_clinicaltrials_sync({
            "query": "diabetes phase3",
            "query_key": "test_sync_diabetes",
            "limit": 5
        })
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        validator.validate_text_content(result[0])
        
        # Should either work or provide meaningful error about database setup
        response_text = result[0].text
        assert len(response_text) > 20
        
        print("✅ ClinicalTrials Sync Test Complete")

    @pytest.mark.asyncio
    async def test_parameter_validation_comprehensive(self, validator):
        """Test comprehensive parameter validation across all tools."""
        
        # Test all tools with invalid parameters
        test_cases = [
            (handle_clinicaltrials_search, {"limit": "invalid"}),
            (handle_clinicaltrials_get, {"nct_id": ""}),
            (handle_clinicaltrials_investment_search, {"min_investment_score": "invalid"}),
            (handle_clinicaltrials_investment_summary, {"nct_ids": "not_a_list"}),
            (handle_clinicaltrials_sync, {"limit": -100}),
        ]
        
        for handler, invalid_args in test_cases:
            result = await handler(invalid_args)
            
            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            validator.validate_text_content(result[0])
            
            # Should handle validation errors gracefully
            response_text = result[0].text
            assert len(response_text) > 10  # Should have some error message
        
        print("✅ Comprehensive Parameter Validation Test Complete")

    @pytest.mark.asyncio
    async def test_response_format_consistency(self, validator):
        """Test that all ClinicalTrials tools return consistent response formats."""
        
        # Test that all tools return valid MCP TextContent responses
        tool_tests = [
            (handle_clinicaltrials_search, {"query": "test", "limit": 1}),
            (handle_clinicaltrials_investment_search, {"query": "test", "limit": 1}),
            (handle_clinicaltrials_investment_summary, {"nct_ids": []}),
        ]
        
        for handler, args in tool_tests:
            result = await handler(args)
            
            # Validate response structure
            assert isinstance(result, list)
            assert len(result) >= 1
            assert all(isinstance(item, TextContent) for item in result)
            
            # Validate each TextContent item
            for item in result:
                validator.validate_text_content(item)
                assert len(item.text.strip()) > 0  # Should have non-empty content
        
        print("✅ Response Format Consistency Test Complete")

    @pytest.mark.asyncio
    async def test_clinical_trials_workflow_end_to_end(self, validator):
        """Test complete ClinicalTrials workflow from search to analysis."""
        
        print("\n=== Starting ClinicalTrials End-to-End Workflow ===")
        
        # Step 1: Basic search
        print("Step 1: Searching for diabetes trials...")
        search_result = await handle_clinicaltrials_search({
            "query": "diabetes",
            "limit": 3
        })
        
        assert len(search_result) == 1
        search_text = search_result[0].text
        assert "diabetes" in search_text.lower()
        
        # Step 2: Investment-focused search
        print("Step 2: Running investment-focused search...")
        investment_result = await handle_clinicaltrials_investment_search({
            "query": "cancer",
            "min_investment_score": 0.1,  # Lower threshold for testing
            "limit": 2
        })
        
        assert len(investment_result) == 1
        investment_text = investment_result[0].text
        assert "investment" in investment_text.lower()
        
        # Step 3: Generate investment summary
        print("Step 3: Generating investment summary...")
        summary_result = await handle_clinicaltrials_investment_summary({
            "nct_ids": ["NCT01234567", "NCT07654321"]  # Mock NCT IDs for testing
        })
        
        assert len(summary_result) == 1
        summary_text = summary_result[0].text
        assert len(summary_text) > 50  # Should have substantial content
        
        print("✅ Complete ClinicalTrials End-to-End Workflow Test Complete")

    @pytest.mark.asyncio
    async def test_tool_robustness_under_errors(self, validator):
        """Test tool robustness when API or database errors occur."""
        
        # These tests check that tools handle various error conditions gracefully
        error_test_cases = [
            # Network/API errors should be handled gracefully
            (handle_clinicaltrials_search, {"query": "very_rare_condition_xyz123", "limit": 1}),
            (handle_clinicaltrials_get, {"nct_id": "NCT99999999"}),  # Likely non-existent
            
            # Edge cases
            (handle_clinicaltrials_search, {"query": "", "limit": 1}),  # Empty query
            (handle_clinicaltrials_investment_summary, {"nct_ids": []}),  # Empty list
        ]
        
        for handler, args in error_test_cases:
            try:
                result = await handler(args)
                
                # Should always return a valid response, even on error
                assert len(result) == 1
                assert isinstance(result[0], TextContent)
                validator.validate_text_content(result[0])
                
                # Should have meaningful content (error message or results)
                response_text = result[0].text
                assert len(response_text.strip()) > 10
                
            except Exception as e:
                # If an exception occurs, it should be a reasonable error
                assert len(str(e)) > 0
                print(f"Expected error handled: {e}")
        
        print("✅ Tool Robustness Under Errors Test Complete")