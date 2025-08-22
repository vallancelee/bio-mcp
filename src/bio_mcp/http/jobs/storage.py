"""Job storage implementation using SQLAlchemy."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bio_mcp.http.jobs.models import JobData
from bio_mcp.http.jobs.service import JobNotFoundError, JobRepository
from bio_mcp.shared.models.database_models import JobRecord, JobStatus


class SQLAlchemyJobRepository(JobRepository):
    """SQLAlchemy implementation of job repository."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def save(self, job_data: JobData) -> None:
        """Save job data to database.

        Args:
            job_data: Job data to save
        """
        # Check if job already exists
        stmt = select(JobRecord).where(JobRecord.id == job_data.id)
        result = await self.session.execute(stmt)
        existing_record = result.scalar_one_or_none()

        if existing_record:
            # Update existing record
            existing_record.status = job_data.status
            existing_record.result = job_data.result
            existing_record.error_message = job_data.error_message
            existing_record.started_at = job_data.started_at
            existing_record.completed_at = job_data.completed_at
            # Note: Don't update immutable fields like id, tool_name, parameters, etc.
        else:
            # Create new record
            new_record = JobRecord.from_job_data(job_data)
            self.session.add(new_record)

        await self.session.commit()

    async def get_by_id(self, job_id: str) -> JobData:
        """Get job by ID from database.

        Args:
            job_id: Job ID to retrieve

        Returns:
            JobData object

        Raises:
            JobNotFoundError: If job not found
        """
        stmt = select(JobRecord).where(JobRecord.id == job_id)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            raise JobNotFoundError(f"Job {job_id} not found")

        return record.to_job_data()

    async def list_jobs(
        self, status: JobStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[JobData]:
        """List jobs with optional filtering and pagination.

        Args:
            status: Optional status filter
            limit: Maximum jobs to return
            offset: Number of jobs to skip

        Returns:
            List of JobData objects
        """
        stmt = select(JobRecord)

        # Apply status filter if provided
        if status is not None:
            stmt = stmt.where(JobRecord.status == status)

        # Order by creation time (newest first)
        stmt = stmt.order_by(JobRecord.created_at.desc())

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        records = result.scalars().all()

        return [record.to_job_data() for record in records]

    async def cleanup_expired(self) -> int:
        """Remove expired jobs from database.

        Returns:
            Number of jobs removed
        """
        now = datetime.now(UTC)

        # Delete expired jobs
        stmt = delete(JobRecord).where(JobRecord.expires_at <= now)
        result = await self.session.execute(stmt)

        await self.session.commit()

        return result.rowcount

    async def get_pending_jobs(self, limit: int = 10) -> list[JobData]:
        """Get pending jobs for worker processing.

        Args:
            limit: Maximum jobs to return

        Returns:
            List of pending JobData objects ordered by creation time
        """
        stmt = (
            select(JobRecord)
            .where(JobRecord.status == JobStatus.PENDING)
            .order_by(JobRecord.created_at.asc())  # FIFO processing
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        records = result.scalars().all()

        return [record.to_job_data() for record in records]

    async def get_jobs_by_status(self, status: JobStatus) -> list[JobData]:
        """Get all jobs with specific status.

        Args:
            status: Job status to filter by

        Returns:
            List of JobData objects
        """
        stmt = select(JobRecord).where(JobRecord.status == status)
        result = await self.session.execute(stmt)
        records = result.scalars().all()

        return [record.to_job_data() for record in records]
