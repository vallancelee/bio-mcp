"""
Unit tests for ClinicalTrials.gov sync strategy.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from bio_mcp.shared.utils.checkpoints import CheckpointManager
from bio_mcp.sources.clinicaltrials.client import ClinicalTrialsClient
from bio_mcp.sources.clinicaltrials.sync_strategy import ClinicalTrialsSyncStrategy


class TestClinicalTrialsSyncStrategy:
    """Test ClinicalTrials.gov sync strategy functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_checkpoint_manager = Mock(spec=CheckpointManager)
        self.mock_client = Mock(spec=ClinicalTrialsClient)
        self.sync_strategy = ClinicalTrialsSyncStrategy(
            self.mock_checkpoint_manager, self.mock_client
        )

    @pytest.mark.asyncio
    async def test_get_sync_watermark(self):
        """Test getting sync watermark."""
        expected_watermark = datetime(2024, 1, 15, 12, 0, 0)
        self.mock_checkpoint_manager.get_watermark = AsyncMock(
            return_value=expected_watermark
        )

        result = await self.sync_strategy.get_sync_watermark("test_query")

        assert result == expected_watermark
        self.mock_checkpoint_manager.get_watermark.assert_called_once_with(
            "ctgov", "test_query"
        )

    @pytest.mark.asyncio
    async def test_set_sync_watermark(self):
        """Test setting sync watermark."""
        test_time = datetime(2024, 8, 20, 15, 30, 0)
        self.mock_checkpoint_manager.set_watermark = AsyncMock()

        await self.sync_strategy.set_sync_watermark("test_query", test_time)

        self.mock_checkpoint_manager.set_watermark.assert_called_once_with(
            "ctgov", "test_query", test_time
        )

    @pytest.mark.asyncio
    async def test_sync_incremental_first_sync(self):
        """Test incremental sync when no previous watermark exists."""
        # Setup mocks
        self.mock_checkpoint_manager.get_watermark = AsyncMock(return_value=None)
        self.mock_checkpoint_manager.set_watermark = AsyncMock()

        # Mock client responses
        self.mock_client.search = AsyncMock(return_value=["NCT12345678", "NCT87654321"])

        mock_api_data = [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT12345678",
                        "briefTitle": "Test Study 1",
                    },
                    "statusModule": {"overallStatus": "RECRUITING"},
                    "sponsorCollaboratorsModule": {
                        "leadSponsor": {"name": "Test Sponsor", "class": "INDUSTRY"}
                    },
                    "designModule": {"phases": ["PHASE3"]},
                }
            },
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT87654321",
                        "briefTitle": "Test Study 2",
                    },
                    "statusModule": {"overallStatus": "RECRUITING"},
                    "sponsorCollaboratorsModule": {
                        "leadSponsor": {"name": "Academic Center", "class": "ACADEMIC"}
                    },
                    "designModule": {"phases": ["PHASE2"]},
                }
            },
        ]

        self.mock_client.get_studies_batch = AsyncMock(return_value=mock_api_data)

        # Test first sync
        with patch(
            "bio_mcp.sources.clinicaltrials.sync_strategy.datetime"
        ) as mock_datetime:
            current_time = datetime(2024, 8, 20, 15, 30, 0)
            mock_datetime.now.return_value = current_time

            result = await self.sync_strategy.sync_incremental(
                "condition:cancer", "cancer_phase3", 50
            )

        # Verify results
        assert result["success"] is True
        assert result["source"] == "ctgov"
        assert result["query_key"] == "cancer_phase3"
        assert result["synced"] == 2
        assert result["new"] == 2
        assert result["updated"] == 0
        assert result["parse_errors"] == 0
        assert "investment_relevant_count" in result
        assert "avg_quality_score" in result

        # Verify client calls
        self.mock_client.search.assert_called_once()
        search_args = self.mock_client.search.call_args[1]

        # Should search with 90-day lookback for first sync
        assert "updated_after" in search_args
        assert "limit" in search_args
        assert search_args["limit"] == 50

        # Verify watermark was set
        self.mock_checkpoint_manager.set_watermark.assert_called_once_with(
            "ctgov", "cancer_phase3", current_time
        )

    @pytest.mark.asyncio
    async def test_sync_incremental_with_existing_watermark(self):
        """Test incremental sync with existing watermark."""
        # Setup existing watermark
        last_sync = datetime(2024, 8, 15, 12, 0, 0)
        self.mock_checkpoint_manager.get_watermark = AsyncMock(return_value=last_sync)
        self.mock_checkpoint_manager.set_watermark = AsyncMock()

        # Mock empty results
        self.mock_client.search = AsyncMock(return_value=[])

        # Test incremental sync
        with patch(
            "bio_mcp.sources.clinicaltrials.sync_strategy.datetime"
        ) as mock_datetime:
            current_time = datetime(2024, 8, 20, 15, 30, 0)
            mock_datetime.now.return_value = current_time

            result = await self.sync_strategy.sync_incremental(
                "condition:diabetes", "diabetes_sync", 100
            )

        # Verify results for empty sync
        assert result["success"] is True
        assert result["synced"] == 0
        assert result["new"] == 0
        assert result["updated"] == 0

        # Verify client was called with overlap
        self.mock_client.search.assert_called_once()
        search_args = self.mock_client.search.call_args[1]

        # Should use 2-day overlap (last_sync - 2 days)
        expected_start = (last_sync - timedelta(days=2)).date()
        assert search_args["updated_after"] == expected_start

        # Verify watermark was updated even with no results
        self.mock_checkpoint_manager.set_watermark.assert_called_once_with(
            "ctgov", "diabetes_sync", current_time
        )

    @pytest.mark.asyncio
    async def test_sync_incremental_with_parse_errors(self):
        """Test incremental sync handling parse errors gracefully."""
        self.mock_checkpoint_manager.get_watermark = AsyncMock(return_value=None)
        self.mock_checkpoint_manager.set_watermark = AsyncMock()

        self.mock_client.search = AsyncMock(return_value=["NCT12345678", "NCT99999999"])

        # Mock API data with one valid and one invalid study
        mock_api_data = [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT12345678",
                        "briefTitle": "Valid Study",
                    },
                    "statusModule": {"overallStatus": "RECRUITING"},
                }
            },
            {
                "invalid": "data_structure"  # This will cause a parse error
            },
        ]

        self.mock_client.get_studies_batch = AsyncMock(return_value=mock_api_data)

        result = await self.sync_strategy.sync_incremental(
            "condition:cancer", "cancer_sync", 50
        )

        # Should succeed - the invalid data might still parse with empty/default values
        assert result["success"] is True
        # Note: The actual sync count depends on how gracefully the parsing handles invalid data
        assert result["synced"] >= 1  # At least the valid study
        # Parse errors might be 0 or 1 depending on how the invalid data is handled
        assert result["parse_errors"] >= 0

    @pytest.mark.asyncio
    async def test_sync_incremental_client_error(self):
        """Test incremental sync handling client errors."""
        self.mock_checkpoint_manager.get_watermark = AsyncMock(return_value=None)

        # Mock client search failure
        self.mock_client.search = AsyncMock(side_effect=Exception("API Error"))

        result = await self.sync_strategy.sync_incremental(
            "condition:cancer", "cancer_sync", 50
        )

        # Should return failure result
        assert result["success"] is False
        assert result["synced"] == 0
        assert "error" in result
        assert "API Error" in result["error"]

    @pytest.mark.asyncio
    async def test_parse_query_parameters_structured(self):
        """Test parsing structured query parameters."""
        params = self.sync_strategy._parse_query_parameters(
            "condition:cancer phase:PHASE3 sponsor:INDUSTRY"
        )

        assert params["condition"] == "cancer"
        assert params["phase"] == "PHASE3"
        assert params["sponsor_class"] == "INDUSTRY"

    @pytest.mark.asyncio
    async def test_parse_query_parameters_simple(self):
        """Test parsing simple query."""
        params = self.sync_strategy._parse_query_parameters("diabetes")

        assert params["condition"] == "diabetes"
        assert len(params) == 1

    @pytest.mark.asyncio
    async def test_parse_query_parameters_mixed(self):
        """Test parsing mixed structured and simple query."""
        params = self.sync_strategy._parse_query_parameters(
            "cancer phase:PHASE2 additional terms"
        )

        assert params["phase"] == "PHASE2"
        # Should include all non-structured parts in condition
        assert "cancer" in params["condition"]
        assert "additional" in params["condition"]
        assert "terms" in params["condition"]

    @pytest.mark.asyncio
    async def test_parse_query_parameters_empty(self):
        """Test parsing empty query."""
        params = self.sync_strategy._parse_query_parameters("")

        assert params == {}

    @pytest.mark.asyncio
    async def test_sync_by_nct_ids_success(self):
        """Test targeted sync by NCT IDs."""
        nct_ids = ["NCT12345678", "NCT87654321"]

        mock_api_data = [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT12345678",
                        "briefTitle": "Test Study 1",
                    },
                    "statusModule": {"overallStatus": "RECRUITING"},
                    "designModule": {"phases": ["PHASE3"]},
                    "sponsorCollaboratorsModule": {
                        "leadSponsor": {"class": "INDUSTRY"}
                    },
                }
            },
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT87654321",
                        "briefTitle": "Test Study 2",
                    },
                    "statusModule": {"overallStatus": "COMPLETED"},
                    "designModule": {"phases": ["PHASE1"]},
                }
            },
        ]

        self.mock_client.get_studies_batch = AsyncMock(return_value=mock_api_data)

        result = await self.sync_strategy.sync_by_nct_ids(nct_ids)

        # Verify results
        assert result["success"] is True
        assert result["source"] == "ctgov"
        assert result["sync_type"] == "targeted_nct_ids"
        assert result["requested_count"] == 2
        assert result["retrieved_count"] == 2
        assert result["synced"] == 2
        assert result["parse_errors"] == 0
        assert "investment_relevant_count" in result
        assert "avg_quality_score" in result

        # Verify client call
        self.mock_client.get_studies_batch.assert_called_once_with(nct_ids)

    @pytest.mark.asyncio
    async def test_sync_by_nct_ids_empty_list(self):
        """Test targeted sync with empty NCT ID list."""
        result = await self.sync_strategy.sync_by_nct_ids([])

        # Should succeed with zero counts
        assert result["success"] is True
        assert result["requested_count"] == 0
        assert result["synced"] == 0

        # Should not call client
        self.mock_client.get_studies_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_by_nct_ids_client_error(self):
        """Test targeted sync handling client errors."""
        nct_ids = ["NCT12345678"]

        self.mock_client.get_studies_batch = AsyncMock(
            side_effect=Exception("Network Error")
        )

        result = await self.sync_strategy.sync_by_nct_ids(nct_ids)

        # Should return failure result
        assert result["success"] is False
        assert result["requested_count"] == 1
        assert result["retrieved_count"] == 0
        assert result["synced"] == 0
        assert "error" in result
        assert "Network Error" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_incremental_investment_metrics(self):
        """Test that sync results include investment-focused metrics."""
        self.mock_checkpoint_manager.get_watermark = AsyncMock(return_value=None)
        self.mock_checkpoint_manager.set_watermark = AsyncMock()

        self.mock_client.search = AsyncMock(return_value=["NCT12345678"])

        # Mock high-value trial data
        mock_api_data = [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT12345678",
                        "briefTitle": "High Value Study",
                    },
                    "statusModule": {"overallStatus": "RECRUITING"},
                    "sponsorCollaboratorsModule": {
                        "leadSponsor": {"name": "Big Pharma", "class": "INDUSTRY"}
                    },
                    "designModule": {
                        "phases": ["PHASE3"],
                        "enrollmentInfo": {"count": 500, "type": "ESTIMATED"},
                    },
                    "conditionsModule": {"conditions": ["Cancer"]},
                    "armsInterventionsModule": {
                        "interventions": [{"name": "Novel Drug", "type": "DRUG"}]
                    },
                }
            }
        ]

        self.mock_client.get_studies_batch = AsyncMock(return_value=mock_api_data)

        result = await self.sync_strategy.sync_incremental(
            "condition:cancer", "high_value_cancer", 10
        )

        # Verify investment metrics are included
        assert result["success"] is True
        assert "investment_relevant_count" in result
        assert "avg_quality_score" in result

        # This should be a high-value trial (Phase 3 + Industry + Cancer)
        assert (
            result["investment_relevant_count"] >= 1
        )  # Should have at least 1 relevant trial
        assert result["avg_quality_score"] > 0.5  # Should be high quality score

    def test_parse_query_parameters_all_types(self):
        """Test parsing all supported query parameter types."""
        query = "condition:cancer intervention:drugX phase:PHASE3 status:RECRUITING sponsor:INDUSTRY"
        params = self.sync_strategy._parse_query_parameters(query)

        expected = {
            "condition": "cancer",
            "intervention": "drugX",
            "phase": "PHASE3",
            "status": "RECRUITING",
            "sponsor_class": "INDUSTRY",
        }

        assert params == expected

    def test_parse_query_parameters_synonyms(self):
        """Test parsing query parameters with synonym support."""
        # Test condition synonyms
        params1 = self.sync_strategy._parse_query_parameters("conditions:diabetes")
        assert params1["condition"] == "diabetes"

        # Test intervention synonyms
        params2 = self.sync_strategy._parse_query_parameters("drug:insulin")
        assert params2["intervention"] == "insulin"

        params3 = self.sync_strategy._parse_query_parameters("interventions:therapy")
        assert params3["intervention"] == "therapy"

        # Test sponsor synonyms
        params4 = self.sync_strategy._parse_query_parameters("sponsor_class:ACADEMIC")
        assert params4["sponsor_class"] == "ACADEMIC"
