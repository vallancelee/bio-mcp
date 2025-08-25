"""
ClinicalTrials.gov service implementation with investment-focused features.
"""

from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.shared.services.base_service import BaseSourceService
from bio_mcp.shared.utils.checkpoints import CheckpointManager
from bio_mcp.sources.clinicaltrials.client import ClinicalTrialsClient
from bio_mcp.sources.clinicaltrials.config import ClinicalTrialsConfig
from bio_mcp.sources.clinicaltrials.models import ClinicalTrialDocument
from bio_mcp.sources.clinicaltrials.sync_strategy import ClinicalTrialsSyncStrategy

logger = get_logger(__name__)


class ClinicalTrialsService(BaseSourceService[ClinicalTrialDocument]):
    """Service for ClinicalTrials.gov operations with multi-source architecture."""

    def __init__(
        self,
        config: ClinicalTrialsConfig | None = None,
        checkpoint_manager: CheckpointManager | None = None,
    ):
        super().__init__("ctgov")
        self.config = config or ClinicalTrialsConfig.from_env()
        self.checkpoint_manager = checkpoint_manager
        self.client: ClinicalTrialsClient | None = None
        self.sync_strategy: ClinicalTrialsSyncStrategy | None = None

    async def initialize(self) -> None:
        """Initialize ClinicalTrials.gov service with client and sync strategy."""
        if self._initialized:
            return

        logger.info("Initializing ClinicalTrials.gov service")

        # Initialize ClinicalTrials.gov client
        self.client = ClinicalTrialsClient(self.config)

        # Initialize sync strategy if checkpoint manager available
        if self.checkpoint_manager:
            self.sync_strategy = ClinicalTrialsSyncStrategy(
                self.checkpoint_manager, self.client
            )

        self._initialized = True
        logger.info("ClinicalTrials.gov service initialized successfully")

    async def cleanup(self) -> None:
        """Cleanup service resources."""
        if self.client:
            await self.client.close()
            self.client = None

        self._initialized = False
        logger.info("ClinicalTrials.gov service cleaned up")

    async def search(self, query: str, **kwargs) -> list[str]:
        """
        Search ClinicalTrials.gov trials.

        Args:
            query: Search query (can be structured or simple text)
            **kwargs: Additional search parameters like limit, phase, status, etc.

        Returns:
            List of NCT IDs matching the search criteria
        """
        await self.ensure_initialized()

        if not self.client:
            raise RuntimeError("ClinicalTrials.gov client not initialized")

        # Parse query if it's structured
        search_params = self._parse_search_query(query)

        # Override with any explicit kwargs
        search_params.update(kwargs)

        logger.info(f"Searching ClinicalTrials.gov with params: {search_params}")

        try:
            nct_ids = await self.client.search(query, **search_params)
            logger.info(f"Found {len(nct_ids)} trials matching query")
            return nct_ids

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            raise

    async def get_document(self, nct_id: str) -> ClinicalTrialDocument:
        """
        Get a single clinical trial document by NCT ID.

        Args:
            nct_id: ClinicalTrials.gov identifier (e.g., NCT04567890)

        Returns:
            ClinicalTrialDocument with full trial information
        """
        await self.ensure_initialized()

        if not self.client:
            raise RuntimeError("ClinicalTrials.gov client not initialized")

        logger.debug(f"Fetching clinical trial: {nct_id}")

        try:
            # Get raw API data
            api_data = await self.client.get_study(nct_id)

            if not api_data:
                raise ValueError(f"Clinical trial {nct_id} not found")

            # Convert to document model
            document = ClinicalTrialDocument.from_api_data(api_data)

            logger.debug(
                f"Retrieved trial: {nct_id} (investment score: {document.investment_relevance_score:.2f})"
            )
            return document

        except Exception as e:
            logger.error(f"Failed to fetch clinical trial {nct_id}: {e}")
            raise

    async def get_documents(self, nct_ids: list[str]) -> list[ClinicalTrialDocument]:
        """
        Get multiple clinical trial documents efficiently.

        Args:
            nct_ids: List of NCT IDs to fetch

        Returns:
            List of ClinicalTrialDocument objects
        """
        await self.ensure_initialized()

        if not self.client:
            raise RuntimeError("ClinicalTrials.gov client not initialized")

        if not nct_ids:
            return []

        logger.info(f"Fetching {len(nct_ids)} clinical trials in batch")

        try:
            # Get raw API data for all trials
            api_data_list = await self.client.get_studies_batch(nct_ids)

            # Convert to document models
            documents = []
            parse_errors = 0

            for api_data in api_data_list:
                try:
                    doc = ClinicalTrialDocument.from_api_data(api_data)
                    documents.append(doc)
                except Exception as e:
                    parse_errors += 1
                    logger.warning(f"Failed to parse trial data: {e}")

            if parse_errors > 0:
                logger.warning(
                    f"Failed to parse {parse_errors} out of {len(api_data_list)} trials"
                )

            logger.info(f"Successfully processed {len(documents)} clinical trials")
            return documents

        except Exception as e:
            logger.error(f"Failed to fetch clinical trials in batch: {e}")
            raise

    async def sync_documents(
        self, query: str, query_key: str, limit: int
    ) -> dict[str, Any]:
        """
        Sync ClinicalTrials.gov documents using incremental lastUpdatePostedDate strategy.

        Args:
            query: Search query for trials to sync
            query_key: Unique identifier for this sync operation (for watermarking)
            limit: Maximum number of trials to sync in this batch

        Returns:
            Dictionary with sync results including counts and metrics
        """
        await self.ensure_initialized()

        if not self.sync_strategy:
            raise RuntimeError(
                "Sync strategy not initialized - checkpoint manager required"
            )

        logger.info(f"Starting sync for query_key: {query_key} with limit: {limit}")

        try:
            result = await self.sync_strategy.sync_incremental(query, query_key, limit)

            # Log investment-focused metrics
            if result.get("success"):
                investment_count = result.get("investment_relevant_count", 0)
                avg_score = result.get("avg_investment_score", 0.0)
                total_synced = result.get("synced", 0)

                if total_synced > 0:
                    investment_percentage = (investment_count / total_synced) * 100
                    logger.info(
                        f"Sync completed: {total_synced} trials, "
                        f"{investment_count} ({investment_percentage:.1f}%) investment-relevant, "
                        f"avg investment score: {avg_score:.2f}"
                    )

            return result

        except Exception as e:
            logger.error(f"Document sync failed for query_key {query_key}: {e}")
            raise

    async def sync_by_nct_ids(self, nct_ids: list[str]) -> dict[str, Any]:
        """
        Sync specific clinical trials by NCT IDs.

        Args:
            nct_ids: List of NCT IDs to sync

        Returns:
            Dictionary with sync results
        """
        await self.ensure_initialized()

        if not self.sync_strategy:
            raise RuntimeError(
                "Sync strategy not initialized - checkpoint manager required"
            )

        logger.info(f"Starting targeted sync for {len(nct_ids)} NCT IDs")

        try:
            return await self.sync_strategy.sync_by_nct_ids(nct_ids)
        except Exception as e:
            logger.error(f"Targeted sync failed for NCT IDs: {e}")
            raise

    async def search_investment_relevant(
        self, query: str = "", min_investment_score: float = 0.5, limit: int = 50
    ) -> list[str]:
        """
        Search for investment-relevant clinical trials.

        Automatically filters for trials likely to be of interest for biotech investment:
        - Phase 2+ trials
        - Industry sponsors
        - High-value therapeutic areas

        Args:
            query: Base search query
            min_investment_score: Minimum investment relevance score (0.0-1.0)
            limit: Maximum number of results

        Returns:
            List of NCT IDs for investment-relevant trials
        """
        await self.ensure_initialized()

        # Build investment-focused search parameters
        search_params = self._parse_search_query(query)

        # Add investment-relevant filters if not specified
        if "phase" not in search_params:
            # Focus on Phase 2+ trials (more likely to be investment relevant)
            search_params["phase"] = "PHASE2"  # This will find PHASE2 and PHASE3

        if "sponsor_class" not in search_params:
            # Focus on industry sponsors for investment relevance
            search_params["sponsor_class"] = "INDUSTRY"

        if "status" not in search_params:
            # Focus on active trials
            search_params["status"] = "RECRUITING"

        search_params["limit"] = limit * 2  # Search more to filter by score

        logger.info(f"Investment-focused search with params: {search_params}")

        try:
            if not self.client:
                raise RuntimeError("ClinicalTrials.gov client not initialized")
            nct_ids = await self.client.search(query, **search_params)

            if not nct_ids or min_investment_score <= 0:
                return nct_ids[:limit]

            # Get documents to calculate investment scores
            documents = await self.get_documents(nct_ids)

            # Filter by investment relevance score
            relevant_docs = [
                doc
                for doc in documents
                if doc.investment_relevance_score >= min_investment_score
            ]

            # Sort by investment score (highest first)
            relevant_docs.sort(key=lambda d: d.investment_relevance_score, reverse=True)

            result_nct_ids = [doc.nct_id for doc in relevant_docs[:limit]]

            logger.info(
                f"Investment filtering: {len(nct_ids)} total -> {len(relevant_docs)} relevant "
                f"(score >= {min_investment_score}) -> {len(result_nct_ids)} returned"
            )

            return result_nct_ids

        except Exception as e:
            logger.error(f"Investment-focused search failed: {e}")
            raise

    def _parse_search_query(self, query: str) -> dict[str, Any]:
        """
        Parse search query into ClinicalTrials.gov API parameters.

        Supports structured queries like:
        - "condition:cancer phase:PHASE3"
        - "diabetes PHASE2 INDUSTRY"
        - "cancer" (simple condition search)
        """
        params: dict[str, Any] = {}

        if not query:
            return params

        # Check if query contains structured parameters
        if ":" in query:
            # Parse structured query
            parts = query.split()
            for part in parts:
                if ":" in part:
                    key, value = part.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()

                    # Map query keys to API parameters
                    if key in ["condition", "conditions"]:
                        params["condition"] = value
                    elif key in ["intervention", "interventions", "drug"]:
                        params["intervention"] = value
                    elif key == "phase":
                        params["phase"] = value.upper()
                    elif key == "status":
                        params["status"] = value.upper()
                    elif key in ["sponsor", "sponsor_class"]:
                        params["sponsor_class"] = value.upper()
                else:
                    # Non-structured part, treat as condition
                    if "condition" not in params:
                        params["condition"] = part
                    else:
                        params["condition"] += f" {part}"
        else:
            # Simple query - check for implicit phase/sponsor indicators
            words = query.split()
            condition_words = []

            for word in words:
                word_upper = word.upper()

                # Check for phase indicators
                if word_upper in [
                    "PHASE1",
                    "PHASE2",
                    "PHASE3",
                    "PHASE4",
                    "EARLY_PHASE1",
                ]:
                    params["phase"] = word_upper
                # Check for sponsor class indicators
                elif word_upper in ["INDUSTRY", "ACADEMIC", "NIH", "OTHER"]:
                    params["sponsor_class"] = word_upper
                # Check for status indicators
                elif word_upper in ["RECRUITING", "ACTIVE_NOT_RECRUITING", "COMPLETED"]:
                    params["status"] = word_upper
                else:
                    condition_words.append(word)

            # Remaining words form the condition
            if condition_words:
                params["condition"] = " ".join(condition_words)

        return params

    async def get_investment_summary(self, nct_ids: list[str]) -> dict[str, Any]:
        """
        Get investment summary for a list of clinical trials.

        Args:
            nct_ids: List of NCT IDs to analyze

        Returns:
            Dictionary with investment analysis metrics
        """
        if not nct_ids:
            return {
                "total_trials": 0,
                "investment_relevant": 0,
                "avg_investment_score": 0.0,
                "phase_distribution": {},
                "sponsor_distribution": {},
                "top_conditions": [],
            }

        try:
            documents = await self.get_documents(nct_ids)

            # Calculate metrics
            investment_relevant = sum(
                1 for doc in documents if doc.investment_relevance_score > 0.5
            )
            avg_score = sum(doc.investment_relevance_score for doc in documents) / len(
                documents
            )

            # Phase distribution
            phase_dist: dict[str, int] = {}
            for doc in documents:
                phase = doc.phase or "UNKNOWN"
                phase_dist[phase] = phase_dist.get(phase, 0) + 1

            # Sponsor class distribution
            sponsor_dist: dict[str, int] = {}
            for doc in documents:
                sponsor = doc.sponsor_class or "UNKNOWN"
                sponsor_dist[sponsor] = sponsor_dist.get(sponsor, 0) + 1

            # Top conditions
            condition_counts: dict[str, int] = {}
            for doc in documents:
                for condition in doc.conditions:
                    condition_counts[condition] = condition_counts.get(condition, 0) + 1

            top_conditions = sorted(
                condition_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]

            return {
                "total_trials": len(documents),
                "investment_relevant": investment_relevant,
                "investment_percentage": (investment_relevant / len(documents)) * 100,
                "avg_investment_score": round(avg_score, 2),
                "phase_distribution": phase_dist,
                "sponsor_distribution": sponsor_dist,
                "top_conditions": [
                    {"condition": cond, "count": count}
                    for cond, count in top_conditions
                ],
                "high_value_trials": [
                    {
                        "nct_id": doc.nct_id,
                        "title": doc.get_display_title(),
                        "investment_score": round(doc.investment_relevance_score, 2),
                        "phase": doc.phase,
                        "sponsor": doc.sponsor_name,
                    }
                    for doc in sorted(
                        documents,
                        key=lambda d: d.investment_relevance_score,
                        reverse=True,
                    )[:5]
                ],
            }

        except Exception as e:
            logger.error(f"Failed to generate investment summary: {e}")
            raise
