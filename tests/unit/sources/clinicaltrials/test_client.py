"""
Unit tests for ClinicalTrials.gov API client.
"""

import asyncio
from datetime import date
from unittest.mock import Mock, patch

import httpx
import pytest

from bio_mcp.sources.clinicaltrials.client import (
    ClinicalTrialsAPIError,
    ClinicalTrialsClient,
    RateLimiter,
    RateLimitError,
)
from bio_mcp.sources.clinicaltrials.config import ClinicalTrialsConfig


class TestRateLimiter:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_delay(self):
        """Test that rate limiter enforces minimum delay between calls."""
        rate_limiter = RateLimiter(rate_per_second=2)  # 0.5 second intervals

        # First call should not delay
        await rate_limiter.wait_if_needed()
        first_call_time = asyncio.get_event_loop().time()

        # Second call should be delayed
        await rate_limiter.wait_if_needed()
        second_call_time = asyncio.get_event_loop().time()

        # Should have waited at least 0.5 seconds
        elapsed = second_call_time - first_call_time
        assert elapsed >= 0.5, f"Expected at least 0.5s delay, got {elapsed}s"

    @pytest.mark.asyncio
    async def test_rate_limiter_no_delay_when_time_passed(self):
        """Test that no delay occurs if enough time has already passed."""
        rate_limiter = RateLimiter(rate_per_second=10)  # 0.1 second intervals

        await rate_limiter.wait_if_needed()

        # Simulate time passage
        await asyncio.sleep(0.2)

        start_time = asyncio.get_event_loop().time()
        await rate_limiter.wait_if_needed()
        end_time = asyncio.get_event_loop().time()

        # Should not have added any significant delay
        elapsed = end_time - start_time
        assert elapsed < 0.05, f"Expected minimal delay, got {elapsed}s"


class TestClinicalTrialsClient:
    """Test ClinicalTrials.gov API client."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = ClinicalTrialsConfig(
            base_url="https://test-api.clinicaltrials.gov/api/v2",
            rate_limit_per_second=10,
            timeout=5.0,
            retries=1,
            page_size=50,
        )
        self.client = ClinicalTrialsClient(self.config)

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization."""
        client = ClinicalTrialsClient()
        assert client.config is not None
        assert client.session is None

        # Test with custom config
        custom_config = ClinicalTrialsConfig(rate_limit_per_second=1)
        client = ClinicalTrialsClient(custom_config)
        assert client.config.rate_limit_per_second == 1

    @pytest.mark.asyncio
    async def test_session_management(self):
        """Test HTTP session initialization and cleanup."""
        client = ClinicalTrialsClient(self.config)

        # Session should be None initially
        assert client.session is None

        # Initialize session
        await client._init_session()
        assert client.session is not None
        assert isinstance(client.session, httpx.AsyncClient)

        # Close session
        await client.close()
        # Session reference should be cleared
        assert client.session is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        async with ClinicalTrialsClient(self.config) as client:
            assert client.session is not None

        # Session should be closed after exiting context
        assert client.session is None

    @pytest.mark.asyncio
    async def test_make_request_success(self):
        """Test successful API request."""
        mock_response_data = {
            "studies": [
                {"protocolSection": {"identificationModule": {"nctId": "NCT12345678"}}}
            ]
        }

        with patch.object(self.client, "session") as mock_session:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None

            # Make get method async
            async def mock_get(*args, **kwargs):
                return mock_response

            mock_session.get = mock_get

            result = await self.client._make_request(
                "https://test.com/api", {"param": "value"}
            )

            assert result == mock_response_data

    @pytest.mark.asyncio
    async def test_make_request_rate_limit_error(self):
        """Test handling of rate limit errors."""
        with patch.object(self.client, "session") as mock_session:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_session.get.side_effect = httpx.HTTPStatusError(
                "Rate limit exceeded", request=Mock(), response=mock_response
            )

            with pytest.raises(RateLimitError, match="Rate limit exceeded"):
                await self.client._make_request("https://test.com/api", {})

    @pytest.mark.asyncio
    async def test_make_request_http_error(self):
        """Test handling of HTTP errors."""
        with patch.object(self.client, "session") as mock_session:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_session.get.side_effect = httpx.HTTPStatusError(
                "Server error", request=Mock(), response=mock_response
            )

            with pytest.raises(ClinicalTrialsAPIError, match="HTTP 500"):
                await self.client._make_request("https://test.com/api", {})

    @pytest.mark.asyncio
    async def test_make_request_generic_error(self):
        """Test handling of generic errors."""
        with patch.object(self.client, "session") as mock_session:
            mock_session.get.side_effect = Exception("Connection error")

            with pytest.raises(ClinicalTrialsAPIError, match="Request failed"):
                await self.client._make_request("https://test.com/api", {})

    @pytest.mark.asyncio
    async def test_search_basic(self):
        """Test basic search functionality."""
        mock_response = {
            "studies": [
                {"protocolSection": {"identificationModule": {"nctId": "NCT12345678"}}},
                {"protocolSection": {"identificationModule": {"nctId": "NCT87654321"}}},
            ]
        }

        with patch.object(self.client, "_make_request", return_value=mock_response):
            nct_ids = await self.client.search_trials(condition="diabetes", limit=10)

            assert len(nct_ids) == 2
            assert "NCT12345678" in nct_ids
            assert "NCT87654321" in nct_ids

    @pytest.mark.asyncio
    async def test_search_with_all_filters(self):
        """Test search with all filter parameters."""
        mock_response = {"studies": []}

        with patch.object(
            self.client, "_make_request", return_value=mock_response
        ) as mock_request:
            await self.client.search_trials(
                condition="cancer",
                intervention="drug x",
                phase="PHASE3",
                status="RECRUITING",
                sponsor_class="INDUSTRY",
                updated_after=date(2024, 1, 1),
                limit=50,
            )

            # Verify request was made with correct parameters
            call_args = mock_request.call_args
            params = call_args[0][1]  # Second argument is params

            assert params["filter.condition"] == "cancer"
            assert params["filter.intervention"] == "drug x"
            assert params["filter.phase"] == "PHASE3"
            assert params["filter.status"] == "RECRUITING"
            assert params["filter.sponsorType"] == "INDUSTRY"
            assert params["filter.lastUpdatePostedDate"] == "2024-01-01:3000-12-31"
            assert params["pageSize"] == 50  # Should be integer, not string

    @pytest.mark.asyncio
    async def test_search_retry_logic(self):
        """Test search retry logic on failures."""
        mock_response = {
            "studies": [
                {"protocolSection": {"identificationModule": {"nctId": "NCT12345678"}}}
            ]
        }

        with patch.object(self.client, "_make_request") as mock_request:
            # First call fails, second succeeds
            mock_request.side_effect = [Exception("Temporary error"), mock_response]

            with patch("asyncio.sleep"):  # Speed up test by mocking sleep
                nct_ids = await self.client.search_trials(condition="test", retries=1)

            assert len(nct_ids) == 1
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_search_retry_exhausted(self):
        """Test search when all retries are exhausted."""
        with patch.object(self.client, "_make_request") as mock_request:
            mock_request.side_effect = Exception("Persistent error")

            with patch("asyncio.sleep"):  # Speed up test
                with pytest.raises(ClinicalTrialsAPIError, match="Search failed"):
                    await self.client.search_trials(condition="test", retries=1)

            assert mock_request.call_count == 2  # Initial + 1 retry

    @pytest.mark.asyncio
    async def test_get_study_success(self):
        """Test successful single study retrieval."""
        mock_study_data = {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT12345678",
                    "briefTitle": "Test Study",
                }
            }
        }
        mock_response = {"studies": [mock_study_data]}

        with patch.object(self.client, "_make_request", return_value=mock_response):
            study = await self.client.get_study("NCT12345678")

            assert study == mock_study_data
            assert (
                study["protocolSection"]["identificationModule"]["nctId"]
                == "NCT12345678"
            )

    @pytest.mark.asyncio
    async def test_get_study_not_found(self):
        """Test handling when study is not found."""
        mock_response = {"studies": []}

        with patch.object(self.client, "_make_request", return_value=mock_response):
            study = await self.client.get_study("NCT99999999")

            assert study is None

    @pytest.mark.asyncio
    async def test_get_study_api_error(self):
        """Test handling of API errors in get_study."""
        with patch.object(self.client, "_make_request") as mock_request:
            mock_request.side_effect = ClinicalTrialsAPIError("API Error")

            study = await self.client.get_study("NCT12345678")

            assert study is None

    @pytest.mark.asyncio
    async def test_get_studies_batch_empty_list(self):
        """Test batch retrieval with empty list."""
        studies = await self.client.get_studies_batch([])
        assert studies == []

    @pytest.mark.asyncio
    async def test_get_studies_batch_success(self):
        """Test successful batch study retrieval."""
        mock_study1 = {
            "protocolSection": {"identificationModule": {"nctId": "NCT11111111"}}
        }
        mock_study2 = {
            "protocolSection": {"identificationModule": {"nctId": "NCT22222222"}}
        }

        with patch.object(self.client, "get_study") as mock_get_study:
            mock_get_study.side_effect = [mock_study1, mock_study2]

            studies = await self.client.get_studies_batch(
                ["NCT11111111", "NCT22222222"]
            )

            assert len(studies) == 2
            assert studies[0] == mock_study1
            assert studies[1] == mock_study2

    @pytest.mark.asyncio
    async def test_get_studies_batch_partial_failures(self):
        """Test batch retrieval with some failures."""
        mock_study1 = {
            "protocolSection": {"identificationModule": {"nctId": "NCT11111111"}}
        }

        with patch.object(self.client, "get_study") as mock_get_study:
            # First succeeds, second returns None, third raises exception
            mock_get_study.side_effect = [mock_study1, None, Exception("Error")]

            studies = await self.client.get_studies_batch(
                ["NCT11111111", "NCT22222222", "NCT33333333"]
            )

            # Should only return successful results
            assert len(studies) == 1
            assert studies[0] == mock_study1

    @pytest.mark.asyncio
    async def test_parse_search_response_valid(self):
        """Test parsing of valid search response."""
        response_data = {
            "studies": [
                {"protocolSection": {"identificationModule": {"nctId": "NCT12345678"}}},
                {"protocolSection": {"identificationModule": {"nctId": "NCT87654321"}}},
            ]
        }

        nct_ids = self.client._parse_search_response(response_data)

        assert len(nct_ids) == 2
        assert "NCT12345678" in nct_ids
        assert "NCT87654321" in nct_ids

    @pytest.mark.asyncio
    async def test_parse_search_response_missing_nct_id(self):
        """Test parsing when some studies are missing NCT IDs."""
        response_data = {
            "studies": [
                {"protocolSection": {"identificationModule": {"nctId": "NCT12345678"}}},
                {
                    "protocolSection": {
                        "identificationModule": {}  # Missing nctId
                    }
                },
            ]
        }

        nct_ids = self.client._parse_search_response(response_data)

        # Should only return valid NCT IDs
        assert len(nct_ids) == 1
        assert "NCT12345678" in nct_ids

    @pytest.mark.asyncio
    async def test_parse_search_response_invalid_format(self):
        """Test parsing of invalid response format."""
        response_data = {"invalid": "format"}

        nct_ids = self.client._parse_search_response(response_data)

        # Should return empty list for invalid format
        assert nct_ids == []

    @pytest.mark.asyncio
    async def test_search_updated_since(self):
        """Test search for studies updated since a specific date."""
        with patch.object(
            self.client, "search_trials", return_value=["NCT12345678"]
        ) as mock_search:
            nct_ids = await self.client.search_updated_since(
                date(2024, 1, 1), limit=100
            )

            mock_search.assert_called_once_with(
                updated_after=date(2024, 1, 1),
                limit=100,
            )
            assert nct_ids == ["NCT12345678"]

    @pytest.mark.asyncio
    async def test_client_with_default_config(self):
        """Test client creation with default configuration."""
        with patch.dict("os.environ", {}, clear=True):
            client = ClinicalTrialsClient()

            assert client.config.base_url == "https://clinicaltrials.gov/api/v2"
            assert client.config.rate_limit_per_second == 5
            assert client.config.timeout == 30.0
            assert client.config.retries == 3
            assert client.config.page_size == 100

    @pytest.mark.asyncio
    async def test_client_respects_rate_limiting(self):
        """Test that client respects rate limiting."""
        config = ClinicalTrialsConfig(rate_limit_per_second=2)  # Very slow rate
        client = ClinicalTrialsClient(config)

        mock_response = {"studies": []}

        with patch.object(client, "session") as mock_session:
            mock_response_obj = Mock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None

            # Make get method async
            async def mock_get(*args, **kwargs):
                return mock_response_obj

            mock_session.get = mock_get

            # Make two requests and measure time
            start_time = asyncio.get_event_loop().time()
            await client._make_request("https://test.com/1", {})
            await client._make_request("https://test.com/2", {})
            elapsed = asyncio.get_event_loop().time() - start_time

            # Should have taken at least 0.5 seconds (1/2 rate)
            assert elapsed >= 0.5, f"Expected rate limiting delay, got {elapsed}s"
