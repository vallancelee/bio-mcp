"""
ClinicalTrials.gov-specific sync strategy using lastUpdatePostedDate watermarks.
"""

from datetime import datetime, timedelta
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.shared.models.base_models import BaseSyncStrategy
from bio_mcp.shared.utils.checkpoints import CheckpointManager
from bio_mcp.sources.clinicaltrials.client import ClinicalTrialsClient
from bio_mcp.sources.clinicaltrials.models import ClinicalTrialDocument

logger = get_logger(__name__)


class ClinicalTrialsSyncStrategy(BaseSyncStrategy):
    """lastUpdatePostedDate-based incremental sync for ClinicalTrials.gov."""

    def __init__(
        self, checkpoint_manager: CheckpointManager, client: ClinicalTrialsClient
    ):
        self.checkpoint_manager = checkpoint_manager
        self.client = client
        self.source_name = "ctgov"

    async def get_sync_watermark(self, query_key: str) -> datetime | None:
        """Get last sync timestamp for a ClinicalTrials.gov query."""
        return await self.checkpoint_manager.get_watermark(self.source_name, query_key)

    async def set_sync_watermark(self, query_key: str, timestamp: datetime) -> None:
        """Update sync watermark for a ClinicalTrials.gov query."""
        await self.checkpoint_manager.set_watermark(
            self.source_name, query_key, timestamp
        )

    async def sync_incremental(
        self, query: str, query_key: str, limit: int
    ) -> dict[str, Any]:
        """
        Perform incremental sync using lastUpdatePostedDate watermarks.

        ClinicalTrials.gov provides lastUpdatePostedDate which tracks when
        trial information was last updated, making it ideal for incremental sync.
        """
        logger.info(
            f"Starting incremental sync for ClinicalTrials.gov query: {query_key}"
        )

        last_sync = await self.get_sync_watermark(query_key)
        current_time = datetime.now()

        # Parse query to extract search parameters
        search_params = self._parse_query_parameters(query)

        try:
            if last_sync:
                # Add 2-day overlap to catch late updates and corrections
                # ClinicalTrials.gov updates can sometimes be delayed
                start_date = (last_sync - timedelta(days=2)).date()
                logger.info(f"Incremental sync from {start_date} with 2-day overlap")
            else:
                # First sync - limit to recent period to avoid overwhelming
                start_date = (
                    current_time - timedelta(days=90)
                ).date()  # Start with last 90 days
                logger.info(f"First sync - limiting to last 90 days from {start_date}")

            # Add date filter to search parameters
            search_params["updated_after"] = start_date
            search_params["limit"] = limit

            # Search for trials to sync
            nct_ids = await self.client.search(**search_params)
            logger.info(f"Found {len(nct_ids)} trials to sync")

            if nct_ids:
                # Fetch trial details in batches
                trial_data = await self.client.get_studies_batch(nct_ids)

                # Convert API data to documents
                documents = []
                parse_errors = 0

                for api_data in trial_data:
                    try:
                        doc = ClinicalTrialDocument.from_api_data(api_data)
                        documents.append(doc)
                    except Exception as e:
                        parse_errors += 1
                        logger.warning(f"Failed to parse trial data: {e}")

                if parse_errors > 0:
                    logger.warning(
                        f"Failed to parse {parse_errors} out of {len(trial_data)} trials"
                    )

                # Count new vs updated documents
                new_count = 0
                updated_count = 0

                # Here we would typically:
                # 1. Check which documents are new vs updates by comparing with database
                # 2. Store/update documents in database
                # 3. Update vector embeddings
                # 4. Calculate quality scores and investment metrics

                # For now, assume all are new for simplicity
                # In production, this would check against existing database records
                new_count = len(documents)

                # Update watermark to current time
                await self.set_sync_watermark(query_key, current_time)

                logger.info(
                    f"Successfully synced {len(documents)} ClinicalTrials.gov documents"
                )

                return {
                    "source": self.source_name,
                    "query_key": query_key,
                    "synced": len(documents),
                    "new": new_count,
                    "updated": updated_count,
                    "parse_errors": parse_errors,
                    "watermark_updated": current_time.isoformat(),
                    "investment_relevant_count": sum(
                        1 for doc in documents if doc.investment_relevance_score > 0.5
                    ),
                    "avg_investment_score": sum(
                        doc.investment_relevance_score for doc in documents
                    )
                    / len(documents)
                    if documents
                    else 0,
                    "success": True,
                }
            else:
                # No new trials, just update watermark
                await self.set_sync_watermark(query_key, current_time)

                return {
                    "source": self.source_name,
                    "query_key": query_key,
                    "synced": 0,
                    "new": 0,
                    "updated": 0,
                    "parse_errors": 0,
                    "watermark_updated": current_time.isoformat(),
                    "investment_relevant_count": 0,
                    "avg_investment_score": 0.0,
                    "success": True,
                }

        except Exception as e:
            logger.error(f"Sync failed for ClinicalTrials.gov query {query_key}: {e}")
            return {
                "source": self.source_name,
                "query_key": query_key,
                "synced": 0,
                "new": 0,
                "updated": 0,
                "parse_errors": 0,
                "error": str(e),
                "success": False,
            }

    def _parse_query_parameters(self, query: str) -> dict[str, Any]:
        """
        Parse query string to extract ClinicalTrials.gov search parameters.

        Supports formats like:
        - "condition:cancer phase:PHASE3"
        - "intervention:drug sponsor:INDUSTRY"
        - "cancer"  (simple condition search)
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
            # Simple query - treat as condition search
            params["condition"] = query

        return params

    async def sync_by_nct_ids(self, nct_ids: list[str]) -> dict[str, Any]:
        """
        Sync specific clinical trials by NCT IDs.

        Useful for targeted updates or backfilling specific trials.
        """
        logger.info(f"Starting targeted sync for {len(nct_ids)} NCT IDs")

        # Handle empty list
        if not nct_ids:
            return {
                "source": self.source_name,
                "sync_type": "targeted_nct_ids",
                "requested_count": 0,
                "retrieved_count": 0,
                "synced": 0,
                "parse_errors": 0,
                "investment_relevant_count": 0,
                "avg_investment_score": 0.0,
                "success": True,
            }

        try:
            # Fetch trial details
            trial_data = await self.client.get_studies_batch(nct_ids)

            # Convert API data to documents
            documents = []
            parse_errors = 0

            for api_data in trial_data:
                try:
                    doc = ClinicalTrialDocument.from_api_data(api_data)
                    documents.append(doc)
                except Exception as e:
                    parse_errors += 1
                    logger.warning(f"Failed to parse trial data: {e}")

            logger.info(
                f"Successfully processed {len(documents)} trials with {parse_errors} parse errors"
            )

            return {
                "source": self.source_name,
                "sync_type": "targeted_nct_ids",
                "requested_count": len(nct_ids),
                "retrieved_count": len(trial_data),
                "synced": len(documents),
                "parse_errors": parse_errors,
                "investment_relevant_count": sum(
                    1 for doc in documents if doc.investment_relevance_score > 0.5
                ),
                "avg_investment_score": sum(
                    doc.investment_relevance_score for doc in documents
                )
                / len(documents)
                if documents
                else 0,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Targeted sync failed for NCT IDs: {e}")
            return {
                "source": self.source_name,
                "sync_type": "targeted_nct_ids",
                "requested_count": len(nct_ids),
                "retrieved_count": 0,
                "synced": 0,
                "parse_errors": 0,
                "error": str(e),
                "success": False,
            }
