"""Job service layer for business logic and job management."""

from abc import ABC, abstractmethod
from typing import Any

from bio_mcp.http.jobs.models import JobData, JobStatus


class JobNotFoundError(Exception):
    """Raised when a job is not found."""

    pass


class JobRepository(ABC):
    """Abstract repository interface for job persistence."""

    @abstractmethod
    async def save(self, job_data: JobData) -> None:
        """Save job data to storage."""
        pass

    @abstractmethod
    async def get_by_id(self, job_id: str) -> JobData:
        """Get job by ID, raises JobNotFoundError if not found."""
        pass

    @abstractmethod
    async def list_jobs(
        self, status: JobStatus = None, limit: int = 50, offset: int = 0
    ) -> list[JobData]:
        """List jobs with optional filtering and pagination."""
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove expired jobs and return count of removed jobs."""
        pass


class JobService:
    """Business logic service for job management."""

    def __init__(self, repository: JobRepository):
        """Initialize job service with repository."""
        self.repository = repository

    async def create_job(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        trace_id: str,
        ttl_hours: int = 24,
    ) -> str:
        """Create a new job and return job ID.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for tool execution
            trace_id: Trace ID for correlation
            ttl_hours: Job TTL in hours (default 24)

        Returns:
            Job ID string
        """
        job_data = JobData.create_new(
            tool_name=tool_name,
            parameters=parameters,
            trace_id=trace_id,
            ttl_hours=ttl_hours,
        )

        await self.repository.save(job_data)
        return job_data.id

    async def get_job_status(self, job_id: str) -> JobData:
        """Get current job status and data.

        Args:
            job_id: Job ID to query

        Returns:
            JobData with current status

        Raises:
            JobNotFoundError: If job doesn't exist
        """
        return await self.repository.get_by_id(job_id)

    async def start_job(self, job_id: str) -> None:
        """Mark job as started.

        Args:
            job_id: Job ID to start

        Raises:
            JobNotFoundError: If job doesn't exist
        """
        job_data = await self.repository.get_by_id(job_id)
        job_data.start_execution()
        await self.repository.save(job_data)

    async def complete_job(self, job_id: str, result: Any) -> None:
        """Complete job with result.

        Args:
            job_id: Job ID to complete
            result: Job execution result

        Raises:
            JobNotFoundError: If job doesn't exist
        """
        job_data = await self.repository.get_by_id(job_id)
        job_data.complete_with_result(result)
        await self.repository.save(job_data)

    async def fail_job(self, job_id: str, error_message: str) -> None:
        """Mark job as failed with error.

        Args:
            job_id: Job ID to fail
            error_message: Error description

        Raises:
            JobNotFoundError: If job doesn't exist
        """
        job_data = await self.repository.get_by_id(job_id)
        job_data.fail_with_error(error_message)
        await self.repository.save(job_data)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if possible.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if cancelled, False if job is already terminal

        Raises:
            JobNotFoundError: If job doesn't exist
        """
        job_data = await self.repository.get_by_id(job_id)

        if job_data.is_terminal:
            return False  # Can't cancel terminal jobs

        job_data.cancel()
        await self.repository.save(job_data)
        return True

    async def list_jobs(
        self, status: JobStatus = None, limit: int = 50, offset: int = 0
    ) -> list[JobData]:
        """List jobs with optional filtering.

        Args:
            status: Optional status filter
            limit: Maximum jobs to return (default 50)
            offset: Number of jobs to skip (default 0)

        Returns:
            List of JobData objects
        """
        return await self.repository.list_jobs(status, limit, offset)

    async def get_pending_jobs(self, limit: int = 10) -> list[JobData]:
        """Get pending jobs for worker processing.

        Args:
            limit: Maximum jobs to return

        Returns:
            List of pending JobData objects
        """
        return await self.repository.list_jobs(JobStatus.PENDING, limit, 0)

    async def cleanup_expired_jobs(self) -> int:
        """Remove expired jobs from storage.

        Returns:
            Number of jobs removed
        """
        return await self.repository.cleanup_expired()
