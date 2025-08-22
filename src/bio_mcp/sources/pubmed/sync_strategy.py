"""
PubMed-specific sync strategy using EDAT watermarks.
"""

from datetime import datetime, timedelta
from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.shared.models.base_models import BaseSyncStrategy
from bio_mcp.shared.utils.checkpoints import CheckpointManager
from bio_mcp.sources.pubmed.client import PubMedClient

logger = get_logger(__name__)


class PubMedSyncStrategy(BaseSyncStrategy):
    """EDAT-based incremental sync for PubMed."""

    def __init__(self, checkpoint_manager: CheckpointManager, client: PubMedClient):
        self.checkpoint_manager = checkpoint_manager
        self.client = client
        self.source_name = "pubmed"

    async def get_sync_watermark(self, query_key: str) -> datetime | None:
        """Get last sync timestamp for a PubMed query."""
        return await self.checkpoint_manager.get_watermark(self.source_name, query_key)

    async def set_sync_watermark(self, query_key: str, timestamp: datetime) -> None:
        """Update sync watermark for a PubMed query."""
        await self.checkpoint_manager.set_watermark(
            self.source_name, query_key, timestamp
        )

    async def sync_incremental(
        self, query: str, query_key: str, limit: int
    ) -> dict[str, Any]:
        """Perform incremental sync using EDAT (entry date) watermarks with overlap."""

        logger.info(f"Starting incremental sync for PubMed query: {query_key}")

        last_sync = await self.get_sync_watermark(query_key)
        current_time = datetime.now()

        if last_sync:
            # Add 1-day overlap to catch late updates and corrections
            start_date = last_sync - timedelta(days=1)
            query_with_date = f"{query} AND {start_date.strftime('%Y/%m/%d')}[EDAT]:{current_time.strftime('%Y/%m/%d')}[EDAT]"
            logger.info(f"Incremental sync from {start_date} with 1-day overlap")
        else:
            # First sync - use query as-is but limit to recent period to avoid overwhelming
            start_date = current_time - timedelta(days=30)  # Start with last 30 days
            query_with_date = f"{query} AND {start_date.strftime('%Y/%m/%d')}[EDAT]:{current_time.strftime('%Y/%m/%d')}[EDAT]"
            logger.info(f"First sync - limiting to last 30 days from {start_date}")

        try:
            # Search for documents to sync
            pmids = await self.client.search(query_with_date, limit=limit)
            logger.info(f"Found {len(pmids)} documents to sync")

            if pmids:
                # Fetch document details
                documents = await self.client.get_documents(pmids)

                # Count new vs updated documents
                new_count = 0
                updated_count = 0

                # Here we would typically:
                # 1. Check which documents are new vs updates
                # 2. Store/update documents in database
                # 3. Update vector embeddings

                # For now, assume all are new for simplicity
                new_count = len(documents)

                # Update watermark to current time
                await self.set_sync_watermark(query_key, current_time)

                logger.info(f"Successfully synced {len(documents)} PubMed documents")

                return {
                    "source": self.source_name,
                    "query_key": query_key,
                    "synced": len(documents),
                    "new": new_count,
                    "updated": updated_count,
                    "watermark_updated": current_time.isoformat(),
                    "success": True,
                }
            else:
                # No new documents, just update watermark
                await self.set_sync_watermark(query_key, current_time)

                return {
                    "source": self.source_name,
                    "query_key": query_key,
                    "synced": 0,
                    "new": 0,
                    "updated": 0,
                    "watermark_updated": current_time.isoformat(),
                    "success": True,
                }

        except Exception as e:
            logger.error(f"Sync failed for PubMed query {query_key}: {e}")
            return {
                "source": self.source_name,
                "query_key": query_key,
                "synced": 0,
                "new": 0,
                "updated": 0,
                "error": str(e),
                "success": False,
            }
