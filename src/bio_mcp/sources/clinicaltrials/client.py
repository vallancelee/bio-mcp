"""
ClinicalTrials.gov API client for Bio-MCP server.

This module provides a comprehensive client for accessing ClinicalTrials.gov
REST API v2, with rate limiting, error handling, and investment-focused
clinical trial data retrieval.
"""

import asyncio
import time
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from bio_mcp.sources.clinicaltrials.models import ClinicalTrialDocument

from bio_mcp.config.logging_config import get_logger
from bio_mcp.shared.models.base_models import BaseClient
from bio_mcp.sources.clinicaltrials.config import ClinicalTrialsConfig

logger = get_logger(__name__)


class ClinicalTrialsAPIError(Exception):
    """Base exception for ClinicalTrials.gov API errors."""

    pass


class RateLimitError(ClinicalTrialsAPIError):
    """Exception for rate limiting errors."""

    pass


class RateLimiter:
    """Simple rate limiter for API requests."""

    def __init__(self, rate_per_second: int):
        self.rate_per_second = rate_per_second
        self.min_interval = 1.0 / rate_per_second
        self.last_request_time = 0.0

    async def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limit."""
        now = time.time()
        time_since_last = now - self.last_request_time

        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()


class ClinicalTrialsClient(BaseClient["ClinicalTrialDocument"]):
    """Client for ClinicalTrials.gov API v2."""

    def __init__(self, config: ClinicalTrialsConfig | None = None):
        self.config = config or ClinicalTrialsConfig.from_env()
        self._rate_limiter = RateLimiter(self.config.rate_limit_per_second)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass

    async def close(self) -> None:
        """Cleanup resources (no-op since we don't maintain sessions)."""
        pass

    async def _make_request(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP request with rate limiting and error handling."""
        await self._rate_limiter.wait_if_needed()

        # Convert all parameters to strings
        str_params = {k: str(v) for k, v in params.items() if v is not None}

        # Create a fresh HTTP client for this request
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            headers={
                "User-Agent": "Bio-MCP/1.0 (biomedical research; contact: bio-mcp@example.com)"
            },
        ) as session:
            try:
                logger.debug(
                    "Making ClinicalTrials.gov API request", url=url, params=str_params
                )

                response = await session.get(url, params=str_params)
                response.raise_for_status()

                data = response.json()
                logger.debug(
                    "ClinicalTrials.gov API response received",
                    status=response.status_code,
                )

                return data

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("ClinicalTrials.gov API rate limit exceeded")
                    raise RateLimitError("Rate limit exceeded")
                else:
                    logger.error(
                        "ClinicalTrials.gov API HTTP error",
                        status=e.response.status_code,
                        error=str(e),
                    )
                    raise ClinicalTrialsAPIError(f"HTTP {e.response.status_code}: {e}")
            except Exception as e:
                logger.error("ClinicalTrials.gov API request failed", error=str(e))
                raise ClinicalTrialsAPIError(f"Request failed: {e}")

    async def search_trials(
        self,
        condition: str | None = None,
        intervention: str | None = None,
        phase: str | None = None,
        status: str | None = None,
        sponsor_class: str | None = None,
        updated_after: date | None = None,
        limit: int = 100,
        retries: int | None = None,
    ) -> list[str]:
        """
        Search clinical trials and return NCT IDs.

        Args:
            condition: Medical condition or disease
            intervention: Drug, device, or treatment
            phase: Trial phase (EARLY_PHASE1, PHASE1, PHASE2, PHASE3, PHASE4)
            status: Recruitment status (RECRUITING, ACTIVE_NOT_RECRUITING, etc.)
            sponsor_class: Sponsor type (INDUSTRY, NIH, ACADEMIC, OTHER)
            updated_after: Filter for studies updated after this date
            limit: Maximum number of results
            retries: Number of retry attempts

        Returns:
            List of NCT IDs matching the search criteria
        """
        if retries is None:
            retries = self.config.retries

        url = f"{self.config.base_url}/studies"
        params: dict[str, Any] = {"pageSize": min(limit, self.config.page_size)}

        # Build query and filter parameters (API v2 format)
        if condition:
            params["query.cond"] = condition
        if intervention:
            params["query.intr"] = intervention
        if phase:
            # Use filter.advanced with AREA syntax for phase filtering
            params["filter.advanced"] = f"AREA[Phase]{phase}"
        if status:
            params["filter.overallStatus"] = status
        if sponsor_class:
            params["query.spons"] = sponsor_class
        if updated_after:
            # Use query.term with AREA syntax for date filtering
            params["query.term"] = (
                f"AREA[LastUpdatePostDate]RANGE[{updated_after.isoformat()},MAX]"
            )

        logger.info(
            "Searching ClinicalTrials.gov",
            condition=condition,
            intervention=intervention,
            phase=phase,
            status=status,
            sponsor_class=sponsor_class,
            limit=limit,
        )

        for attempt in range(retries + 1):
            try:
                response_data = await self._make_request(url, params)
                nct_ids = self._parse_search_response(response_data)

                logger.info(
                    "ClinicalTrials.gov search completed",
                    returned_count=len(nct_ids),
                    condition=condition,
                    intervention=intervention,
                )

                return nct_ids[:limit]  # Ensure we don't exceed requested limit

            except (ClinicalTrialsAPIError, RateLimitError):
                raise
            except Exception as e:
                if attempt == retries:
                    raise ClinicalTrialsAPIError(f"Search failed: {e}")

                wait_time = 2**attempt
                logger.warning(
                    "ClinicalTrials.gov search attempt failed, retrying",
                    attempt=attempt + 1,
                    wait_time=wait_time,
                    error=str(e),
                )
                await asyncio.sleep(wait_time)

        raise ClinicalTrialsAPIError("All retry attempts failed")

    async def get_study(self, nct_id: str) -> dict[str, Any] | None:
        """
        Get detailed study information by NCT ID.

        Args:
            nct_id: ClinicalTrials.gov identifier (e.g., NCT04567890)

        Returns:
            Study data dictionary or None if not found
        """
        url = f"{self.config.base_url}/studies/{nct_id}"

        logger.debug("Fetching clinical trial", nct_id=nct_id)

        try:
            response_data = await self._make_request(url, {})

            # API returns studies array even for single study
            studies = response_data.get("studies", [])
            if not studies:
                logger.warning("Study not found", nct_id=nct_id)
                return None

            study_data = studies[0]
            logger.debug("Clinical trial fetched successfully", nct_id=nct_id)
            return study_data

        except ClinicalTrialsAPIError:
            logger.error("Failed to fetch clinical trial", nct_id=nct_id)
            return None

    async def get_studies_batch(self, nct_ids: list[str]) -> list[dict[str, Any]]:
        """
        Get multiple studies in batch for efficiency.

        Args:
            nct_ids: List of NCT IDs to fetch

        Returns:
            List of study data dictionaries
        """
        if not nct_ids:
            return []

        # ClinicalTrials.gov API doesn't support multi-ID queries like PubMed,
        # so we need to fetch individually but with concurrency control
        logger.info("Fetching clinical trials batch", nct_count=len(nct_ids))

        # Limit concurrency to respect rate limits
        semaphore = asyncio.Semaphore(self.config.rate_limit_per_second)

        async def fetch_single(nct_id: str) -> dict[str, Any] | None:
            async with semaphore:
                return await self.get_study(nct_id)

        # Execute requests concurrently
        tasks = [fetch_single(nct_id) for nct_id in nct_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None results and exceptions
        studies: list[dict[str, Any]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to fetch study in batch",
                    nct_id=nct_ids[i],
                    error=str(result),
                )
            elif result is not None and isinstance(result, dict):
                studies.append(result)

        logger.info(
            "Clinical trials batch fetch completed",
            requested_count=len(nct_ids),
            returned_count=len(studies),
        )

        return studies

    def _parse_search_response(self, response_data: dict[str, Any]) -> list[str]:
        """Parse search response and extract NCT IDs."""
        try:
            studies = response_data.get("studies", [])
            nct_ids = []

            for study in studies:
                protocol_section = study.get("protocolSection", {})
                identification = protocol_section.get("identificationModule", {})
                nct_id = identification.get("nctId")

                if nct_id:
                    nct_ids.append(nct_id)

            return nct_ids

        except (KeyError, TypeError) as e:
            logger.error("Failed to parse search response", error=str(e))
            raise ClinicalTrialsAPIError(f"Invalid search response format: {e}")

    async def search_updated_since(
        self, last_update_date: date, limit: int = 100
    ) -> list[str]:
        """
        Search for studies updated since a specific date.

        Args:
            last_update_date: Date to filter updates from
            limit: Maximum number of results

        Returns:
            List of NCT IDs for studies updated since the date
        """
        return await self.search_trials(
            updated_after=last_update_date,
            limit=limit,
        )

    async def search(self, query: str, **kwargs: Any) -> list[str]:
        """Search clinical trials (BaseClient interface)."""
        # Parse query and merge with kwargs
        # For simplicity, treat query as condition if it doesn't contain structured parameters
        if ":" not in query and query.strip():
            kwargs.setdefault("condition", query.strip())

        # Use the detailed search_trials method
        return await self.search_trials(**kwargs)

    # BaseClient interface methods
    async def get_document(self, doc_id: str) -> "ClinicalTrialDocument":
        """Get single document by NCT ID (BaseClient interface)."""
        from bio_mcp.sources.clinicaltrials.models import ClinicalTrialDocument

        api_data = await self.get_study(doc_id)
        if not api_data:
            raise ValueError(f"Clinical trial {doc_id} not found")

        return ClinicalTrialDocument.from_api_data(api_data)

    async def get_documents(self, doc_ids: list[str]) -> list["ClinicalTrialDocument"]:
        """Get multiple documents by NCT IDs (BaseClient interface)."""
        from bio_mcp.sources.clinicaltrials.models import ClinicalTrialDocument

        if not doc_ids:
            return []

        api_data_list = await self.get_studies_batch(doc_ids)
        documents = []

        for api_data in api_data_list:
            try:
                doc = ClinicalTrialDocument.from_api_data(api_data)
                documents.append(doc)
            except Exception as e:
                # Log but continue processing other documents
                nct_id = (
                    api_data.get("protocolSection", {})
                    .get("identificationModule", {})
                    .get("nctId", "unknown")
                )
                logger.warning(f"Failed to parse clinical trial {nct_id}: {e}")

        return documents

    async def get_updates_since(
        self, timestamp: datetime, limit: int = 100
    ) -> list["ClinicalTrialDocument"]:
        """Get documents updated since timestamp (BaseClient interface)."""
        # Convert datetime to date for ClinicalTrials.gov API
        since_date = timestamp.date()
        nct_ids = await self.search_updated_since(since_date, limit)
        return await self.get_documents(nct_ids)
