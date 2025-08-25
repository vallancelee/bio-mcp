"""Database service for re-ingestion operations."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text

from bio_mcp.config.config import Config
from bio_mcp.shared.clients.database import DatabaseConfig, DatabaseManager
from bio_mcp.shared.models.database_models import (
    JobRecord,
    JobStatus,
)

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for database operations required by re-ingestion."""

    def __init__(self, config: Config):
        self.config = config
        db_config = DatabaseConfig.from_url(config.database_url)
        self.manager = DatabaseManager(db_config)

    async def connect(self):
        """Initialize database connection."""
        await self.manager.initialize()

    async def disconnect(self):
        """Close database connection."""
        await self.manager.close()

    async def create_job(
        self,
        operation: str,
        parameters: dict[str, Any],
        status: JobStatus = JobStatus.PENDING,
    ) -> str:
        """Create a new job record and return job ID."""
        job_id = str(uuid.uuid4())

        async with self.manager.get_session() as session:
            job = JobRecord(
                id=uuid.UUID(job_id),
                tool_name=operation,
                status=status,
                parameters=parameters,
                trace_id=str(uuid.uuid4()),
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow().replace(
                    year=datetime.utcnow().year + 1
                ),  # 1 year expiry
            )
            session.add(job)
            await session.commit()

        return job_id

    async def get_job(self, job_id: str) -> JobRecord:
        """Get job record by ID."""
        async with self.manager.get_session() as session:
            result = await session.get(JobRecord, uuid.UUID(job_id))
            return result

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ):
        """Update job status and result."""
        async with self.manager.get_session() as session:
            job = await session.get(JobRecord, uuid.UUID(job_id))
            if job:
                job.status = status
                if result is not None:
                    job.result = result
                if error_message is not None:
                    job.error_message = error_message

                if status == JobStatus.RUNNING and job.started_at is None:
                    job.started_at = datetime.utcnow()
                elif status in [
                    JobStatus.COMPLETED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                ]:
                    job.completed_at = datetime.utcnow()

                await session.commit()

    async def update_job_progress(
        self, job_id: str, progress: int, stats: dict[str, Any]
    ):
        """Update job progress and intermediate results."""
        async with self.manager.get_session() as session:
            job = await session.get(JobRecord, uuid.UUID(job_id))
            if job:
                # Store progress in result field
                current_result = job.result or {}
                current_result.update({"progress": progress, "stats": stats})
                job.result = current_result
                await session.commit()

    async def get_all_document_refs(
        self, source_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Get all document references for re-ingestion."""
        query = """
        SELECT 
            uid,
            source,
            source_id,
            s3_raw_uri as s3_key,
            content_hash,
            created_at,
            published_at as updated_at
        FROM documents 
        WHERE s3_raw_uri IS NOT NULL
        """
        params = {}

        if source_filter:
            query += " AND source = :source_filter"
            params["source_filter"] = source_filter

        query += " ORDER BY created_at ASC"

        async with self.manager.get_session() as session:
            result = await session.execute(text(query), params)
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]

    async def get_document_refs_since(
        self, since_date: datetime, source_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Get document references modified since a specific date."""
        query = """
        SELECT 
            uid,
            source,
            source_id,
            s3_raw_uri as s3_key,
            content_hash,
            created_at,
            published_at as updated_at
        FROM documents 
        WHERE s3_raw_uri IS NOT NULL 
        AND created_at >= :since_date
        """
        params = {"since_date": since_date}

        if source_filter:
            query += " AND source = :source_filter"
            params["source_filter"] = source_filter

        query += " ORDER BY created_at ASC"

        async with self.manager.get_session() as session:
            result = await session.execute(text(query), params)
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]

    async def get_failed_document_refs(
        self, source_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get documents that failed in previous ingestion attempts.

        Since we don't have a dedicated failure tracking table yet,
        this returns an empty list. In a production system, this could:
        1. Query a failure_log table
        2. Extract failed document UIDs from job error results
        3. Return documents that haven't been successfully processed
        """
        # Option: Return documents that appear in failed job results
        # This is a more sophisticated approach but requires parsing job results
        try:
            query = """
            SELECT DISTINCT
                d.uid,
                d.source,
                d.source_id,
                d.s3_raw_uri as s3_key,
                d.content_hash,
                d.created_at,
                d.published_at as updated_at
            FROM documents d
            JOIN jobs j ON j.tool_name = 'reingest'
            WHERE d.s3_raw_uri IS NOT NULL
            AND j.status = 'failed'
            """
            params = {}

            if source_filter:
                query += " AND d.source = :source_filter"
                params["source_filter"] = source_filter

            query += " LIMIT 100"  # Limit to prevent excessive results

            async with self.manager.get_session() as session:
                result = await session.execute(text(query), params)
                rows = result.fetchall()
                return [dict(row._mapping) for row in rows]

        except Exception as e:
            # If the query fails (e.g., no jobs table), return empty list
            logger.warning(f"Could not query failed documents: {e}")
            return []

    async def get_last_successful_reingest(self) -> datetime | None:
        """Get timestamp of last successful full re-ingestion."""
        query = """
        SELECT MAX(completed_at)
        FROM jobs
        WHERE tool_name = 'reingest'
        AND status = 'completed'
        AND parameters::jsonb->>'mode' = 'full'
        """

        async with self.manager.get_session() as session:
            result = await session.execute(text(query))
            return result.scalar()

    async def get_document_stats(self) -> dict[str, Any]:
        """Get document statistics for validation."""
        query = """
        SELECT 
            COUNT(*) as total_documents,
            COUNT(DISTINCT source) as unique_sources
        FROM documents
        """

        async with self.manager.get_session() as session:
            result = await session.execute(text(query))
            row = result.fetchone()
            return {
                "total_documents": row[0] if row else 0,
                "unique_sources": row[1] if row else 0,
            }

    async def list_jobs(
        self, limit: int = 20, operation_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """List recent jobs, optionally filtered by operation type."""
        query = """
        SELECT 
            id,
            tool_name,
            status,
            created_at,
            started_at,
            completed_at,
            parameters::jsonb->>'mode' as mode
        FROM jobs
        """
        params = {}

        if operation_filter:
            query += " WHERE tool_name = :operation_filter"
            params["operation_filter"] = operation_filter

        query += " ORDER BY created_at DESC LIMIT :limit"
        params["limit"] = limit

        async with self.manager.get_session() as session:
            result = await session.execute(text(query), params)
            rows = result.fetchall()

            jobs = []
            for row in rows:
                job_dict = dict(row._mapping)
                # Convert UUID to string for JSON serialization
                job_dict["id"] = str(job_dict["id"]) if job_dict["id"] else None
                # Convert datetime objects to ISO strings
                for date_field in ["created_at", "started_at", "completed_at"]:
                    if job_dict.get(date_field):
                        job_dict[date_field] = job_dict[date_field].isoformat()
                jobs.append(job_dict)

            return jobs
