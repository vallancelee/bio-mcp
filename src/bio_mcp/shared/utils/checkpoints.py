"""
Watermark management utilities for incremental sync.
"""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bio_mcp.config.logging_config import get_logger
from bio_mcp.shared.models.database_models import SyncWatermark

logger = get_logger(__name__)


class CheckpointManager:
    """Manager for sync watermarks across data sources."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_watermark(self, source: str, query_key: str) -> datetime | None:
        """Get the last sync watermark for a source/query combination."""

        stmt = select(SyncWatermark.last_sync).where(
            SyncWatermark.source == source, SyncWatermark.query_key == query_key
        )

        result = await self.db_session.execute(stmt)
        watermark = result.scalar_one_or_none()

        if watermark:
            logger.debug(f"Retrieved watermark for {source}:{query_key}: {watermark}")
        else:
            logger.debug(f"No watermark found for {source}:{query_key}")

        return watermark

    async def set_watermark(
        self, source: str, query_key: str, timestamp: datetime
    ) -> None:
        """Set the sync watermark for a source/query combination."""

        # Check if watermark exists
        existing_stmt = select(SyncWatermark).where(
            SyncWatermark.source == source, SyncWatermark.query_key == query_key
        )

        result = await self.db_session.execute(existing_stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing watermark
            update_stmt = (
                update(SyncWatermark)
                .where(
                    SyncWatermark.source == source, SyncWatermark.query_key == query_key
                )
                .values(last_sync=timestamp, updated_at=datetime.utcnow())
            )
            await self.db_session.execute(update_stmt)
            logger.info(f"Updated watermark for {source}:{query_key}: {timestamp}")
        else:
            # Create new watermark
            new_watermark = SyncWatermark(
                source=source, query_key=query_key, last_sync=timestamp
            )
            self.db_session.add(new_watermark)
            logger.info(f"Created new watermark for {source}:{query_key}: {timestamp}")

        await self.db_session.commit()

    async def list_watermarks(self, source: str | None = None) -> list[dict]:
        """List all watermarks, optionally filtered by source."""

        stmt = select(SyncWatermark)
        if source:
            stmt = stmt.where(SyncWatermark.source == source)

        result = await self.db_session.execute(stmt)
        watermarks = result.scalars().all()

        return [
            {
                "source": w.source,
                "query_key": w.query_key,
                "last_sync": w.last_sync,
                "created_at": w.created_at,
                "updated_at": w.updated_at,
            }
            for w in watermarks
        ]
