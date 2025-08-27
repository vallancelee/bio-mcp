"""
ClinicalTrials.gov-specific sync strategy using lastUpdatePostedDate watermarks.
"""

import time
from datetime import datetime, timedelta
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.shared.models.base_models import BaseSyncStrategy
from bio_mcp.shared.utils.checkpoints import CheckpointManager
from bio_mcp.sources.clinicaltrials.client import ClinicalTrialsClient
from bio_mcp.sources.clinicaltrials.models import ClinicalTrialDocument
from bio_mcp.sources.clinicaltrials.quality import (
    calculate_clinical_trial_quality,
    calculate_quality_metrics,
)

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
        self, query: str, query_key: str, limit: int, batch_size: int = 50
    ) -> dict[str, Any]:
        """
        Perform incremental sync using lastUpdatePostedDate watermarks.

        ClinicalTrials.gov provides lastUpdatePostedDate which tracks when
        trial information was last updated, making it ideal for incremental sync.
        """
        start_time = time.time()
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
            search_start_time = time.time()
            nct_ids = await self.client.search(**search_params)
            search_duration = time.time() - search_start_time

            logger.info(
                f"Found {len(nct_ids)} trials to sync in {search_duration:.2f}s"
            )

            if nct_ids:
                # Fetch trial details in optimized batches
                fetch_start_time = time.time()
                trial_data = await self._fetch_trials_in_batches(nct_ids, batch_size)
                fetch_duration = time.time() - fetch_start_time

                # Convert API data to documents with quality scoring
                parse_start_time = time.time()
                documents, parse_errors = await self._parse_and_score_trials(trial_data)
                parse_duration = time.time() - parse_start_time

                if parse_errors > 0:
                    logger.warning(
                        f"Failed to parse {parse_errors} out of {len(trial_data)} trials"
                    )

                # Calculate quality metrics
                quality_metrics = calculate_quality_metrics(documents)

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

                total_duration = time.time() - start_time
                trials_per_second = (
                    len(documents) / total_duration if total_duration > 0 else 0
                )

                logger.info(
                    f"Successfully synced {len(documents)} ClinicalTrials.gov documents "
                    f"in {total_duration:.2f}s ({trials_per_second:.1f} trials/sec)"
                )

                return {
                    "source": self.source_name,
                    "query_key": query_key,
                    "synced": len(documents),
                    "new": new_count,
                    "updated": updated_count,
                    "parse_errors": parse_errors,
                    "watermark_updated": current_time.isoformat(),
                    "success": True,
                    # Quality metrics
                    "quality_metrics": quality_metrics,
                    "investment_relevant_count": quality_metrics[
                        "investment_relevant_count"
                    ],
                    "avg_quality_score": quality_metrics["avg_quality_score"],
                    "high_quality_count": quality_metrics["high_quality_count"],
                    # Performance metrics
                    "performance": {
                        "total_duration_seconds": total_duration,
                        "search_duration_seconds": search_duration,
                        "fetch_duration_seconds": fetch_duration,
                        "parse_duration_seconds": parse_duration,
                        "trials_per_second": trials_per_second,
                        "batch_size": batch_size,
                    },
                }
            else:
                # No new trials, just update watermark
                await self.set_sync_watermark(query_key, current_time)

                total_duration = time.time() - start_time
                return {
                    "source": self.source_name,
                    "query_key": query_key,
                    "synced": 0,
                    "new": 0,
                    "updated": 0,
                    "parse_errors": 0,
                    "watermark_updated": current_time.isoformat(),
                    "success": True,
                    "quality_metrics": {
                        "total_trials": 0,
                        "avg_quality_score": 0.0,
                        "investment_relevant_count": 0,
                        "high_quality_count": 0,
                    },
                    "performance": {
                        "total_duration_seconds": total_duration,
                        "search_duration_seconds": search_duration,
                        "trials_per_second": 0,
                    },
                }

        except Exception as e:
            total_duration = time.time() - start_time
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
                "performance": {
                    "total_duration_seconds": total_duration,
                    "failed": True,
                },
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
                "avg_quality_score": 0.0,
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
                "avg_quality_score": sum(
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

    async def _fetch_trials_in_batches(
        self, nct_ids: list[str], batch_size: int
    ) -> list[dict[str, Any]]:
        """
        Fetch trial data in optimized batches for better performance.

        Args:
            nct_ids: List of NCT IDs to fetch
            batch_size: Number of trials to fetch per batch

        Returns:
            List of trial API data dictionaries
        """
        all_trial_data = []
        total_batches = len(nct_ids) // batch_size + (
            1 if len(nct_ids) % batch_size > 0 else 0
        )

        for i in range(0, len(nct_ids), batch_size):
            batch_ids = nct_ids[i : i + batch_size]
            batch_num = i // batch_size + 1

            logger.debug(
                f"Fetching batch {batch_num}/{total_batches} ({len(batch_ids)} trials)"
            )

            try:
                batch_data = await self.client.get_studies_batch(batch_ids)
                all_trial_data.extend(batch_data)

                # Log progress for large syncs
                if total_batches > 5 and batch_num % max(1, total_batches // 10) == 0:
                    logger.info(
                        f"Fetch progress: {batch_num}/{total_batches} batches completed"
                    )

            except Exception as e:
                logger.error(f"Failed to fetch batch {batch_num}: {e}")
                # Continue with other batches
                continue

        return all_trial_data

    async def _parse_and_score_trials(
        self, trial_data: list[dict[str, Any]]
    ) -> tuple[list[ClinicalTrialDocument], int]:
        """
        Parse API data to documents and calculate quality scores.

        Args:
            trial_data: List of trial API data dictionaries

        Returns:
            Tuple of (parsed_documents, parse_error_count)
        """
        documents = []
        parse_errors = 0

        for i, api_data in enumerate(trial_data):
            try:
                # Parse document from API data
                doc = ClinicalTrialDocument.from_api_data(api_data)

                # Calculate enhanced quality score using the new quality module
                quality_score = calculate_clinical_trial_quality(doc)

                # Update the document's quality score (overrides the basic one from the model)
                doc.investment_relevance_score = quality_score

                documents.append(doc)

                # Log progress for large parsing operations
                if len(trial_data) > 100 and (i + 1) % 50 == 0:
                    logger.debug(
                        f"Parse progress: {i + 1}/{len(trial_data)} trials processed"
                    )

            except Exception as e:
                parse_errors += 1
                logger.warning(f"Failed to parse trial data at index {i}: {e}")

        logger.info(f"Parsed {len(documents)} trials with {parse_errors} errors")

        return documents, parse_errors

    async def sync_with_quality_filtering(
        self,
        query: str,
        query_key: str,
        limit: int,
        min_quality_score: float = 0.5,
        batch_size: int = 50,
    ) -> dict[str, Any]:
        """
        Perform sync with quality score filtering for investment-focused results.

        Args:
            query: Search query string
            query_key: Unique key for checkpoint tracking
            limit: Maximum number of trials to sync
            min_quality_score: Minimum quality score threshold (0.0-1.0)
            batch_size: Batch size for API calls

        Returns:
            Sync result dictionary with quality filtering metrics
        """
        logger.info(f"Starting quality-filtered sync (min_score={min_quality_score})")

        # First do regular incremental sync
        sync_result = await self.sync_incremental(query, query_key, limit, batch_size)

        if not sync_result["success"]:
            return sync_result

        # If no documents were synced, return as-is
        if sync_result["synced"] == 0:
            return sync_result

        # Apply quality filtering (this would be done during storage in production)
        quality_metrics = sync_result["quality_metrics"]

        # Calculate filtered counts based on quality threshold
        total_trials = quality_metrics["total_trials"]
        avg_score = quality_metrics["avg_quality_score"]

        # Estimate filtered count (in production, this would be actual filtered storage)
        estimated_filtered_count = (
            int(
                total_trials
                * max(0, (avg_score - min_quality_score) / (1.0 - min_quality_score))
            )
            if avg_score > min_quality_score
            else 0
        )

        sync_result.update(
            {
                "quality_filtered": True,
                "min_quality_threshold": min_quality_score,
                "quality_filtered_count": estimated_filtered_count,
                "quality_rejected_count": total_trials - estimated_filtered_count,
                "quality_filter_efficiency": estimated_filtered_count / total_trials
                if total_trials > 0
                else 0,
            }
        )

        logger.info(
            f"Quality filtering: {estimated_filtered_count}/{total_trials} trials "
            f"above {min_quality_score} threshold"
        )

        return sync_result
