"""Tests for job service business logic layer."""

import uuid
from datetime import UTC, datetime

import pytest

from bio_mcp.http.jobs.models import JobData, JobStatus
from bio_mcp.http.jobs.service import JobNotFoundError, JobService


class MockJobRepository:
    """Mock job repository for testing service layer."""
    
    def __init__(self):
        self.jobs = {}  # Store jobs by ID
        self.save_called = False
        self.get_called = False
    
    async def save(self, job_data: JobData) -> None:
        """Save job to mock storage."""
        self.jobs[job_data.id] = job_data
        self.save_called = True
    
    async def get_by_id(self, job_id: str) -> JobData:
        """Get job by ID from mock storage."""
        self.get_called = True
        if job_id not in self.jobs:
            raise JobNotFoundError(f"Job {job_id} not found")
        return self.jobs[job_id]
    
    async def list_jobs(
        self, 
        status: JobStatus = None, 
        limit: int = 50, 
        offset: int = 0
    ) -> list[JobData]:
        """List jobs from mock storage."""
        jobs = list(self.jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs[offset:offset + limit]
    
    async def cleanup_expired(self) -> int:
        """Remove expired jobs from mock storage."""
        now = datetime.now(UTC)
        expired_ids = [
            job_id for job_id, job in self.jobs.items()
            if job.expires_at <= now
        ]
        for job_id in expired_ids:
            del self.jobs[job_id]
        return len(expired_ids)


class TestJobService:
    """Test job service business logic."""
    
    @pytest.fixture
    def mock_repo(self):
        """Create mock repository for testing."""
        return MockJobRepository()
    
    @pytest.fixture
    def job_service(self, mock_repo):
        """Create job service with mock repository."""
        return JobService(repository=mock_repo)
    
    @pytest.mark.asyncio
    async def test_create_job_with_defaults(self, job_service, mock_repo):
        """Test creating a new job with default settings."""
        tool_name = "rag.get"
        parameters = {"query": "test query", "limit": 10}
        trace_id = str(uuid.uuid4())
        
        job_id = await job_service.create_job(tool_name, parameters, trace_id)
        
        # Should return valid job ID
        assert job_id is not None
        assert uuid.UUID(job_id)  # Valid UUID format
        
        # Should save to repository
        assert mock_repo.save_called
        assert job_id in mock_repo.jobs
        
        # Verify job data
        saved_job = mock_repo.jobs[job_id]
        assert saved_job.tool_name == tool_name
        assert saved_job.parameters == parameters
        assert saved_job.trace_id == trace_id
        assert saved_job.status == JobStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_create_job_with_custom_ttl(self, job_service, mock_repo):
        """Test creating job with custom TTL."""
        job_id = await job_service.create_job(
            "pubmed.sync", 
            {}, 
            "trace-123", 
            ttl_hours=48
        )
        
        saved_job = mock_repo.jobs[job_id]
        expected_ttl = (saved_job.expires_at - saved_job.created_at).total_seconds() / 3600
        assert abs(expected_ttl - 48) < 0.1  # Within 6 minutes
    
    @pytest.mark.asyncio
    async def test_get_job_status_existing_job(self, job_service, mock_repo):
        """Test getting status of existing job."""
        # Create a job first
        job_id = await job_service.create_job("ping", {}, "trace-123")
        
        # Get job status
        job_data = await job_service.get_job_status(job_id)
        
        assert job_data.id == job_id
        assert job_data.tool_name == "ping"
        assert job_data.status == JobStatus.PENDING
        assert mock_repo.get_called
    
    @pytest.mark.asyncio
    async def test_get_job_status_nonexistent_job(self, job_service):
        """Test getting status of non-existent job."""
        fake_job_id = str(uuid.uuid4())
        
        with pytest.raises(JobNotFoundError):
            await job_service.get_job_status(fake_job_id)
    
    @pytest.mark.asyncio
    async def test_update_job_status(self, job_service, mock_repo):
        """Test updating job status and data."""
        # Create a job
        job_id = await job_service.create_job("rag.get", {}, "trace-123")
        
        # Update to running
        await job_service.start_job(job_id)
        
        # Verify update
        job = mock_repo.jobs[job_id]
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None
        assert job.is_active
    
    @pytest.mark.asyncio
    async def test_complete_job_with_result(self, job_service, mock_repo):
        """Test completing job with result."""
        # Create and start job
        job_id = await job_service.create_job("rag.get", {}, "trace-123")
        await job_service.start_job(job_id)
        
        # Complete with result
        result_data = {"documents": ["doc1", "doc2"], "count": 2}
        await job_service.complete_job(job_id, result_data)
        
        # Verify completion
        job = mock_repo.jobs[job_id]
        assert job.status == JobStatus.COMPLETED
        assert job.result == result_data
        assert job.completed_at is not None
        assert job.is_terminal
    
    @pytest.mark.asyncio
    async def test_fail_job_with_error(self, job_service, mock_repo):
        """Test failing job with error message."""
        # Create and start job
        job_id = await job_service.create_job("rag.get", {}, "trace-123")
        await job_service.start_job(job_id)
        
        # Fail with error
        error_message = "Vector search timeout"
        await job_service.fail_job(job_id, error_message)
        
        # Verify failure
        job = mock_repo.jobs[job_id]
        assert job.status == JobStatus.FAILED
        assert job.error_message == error_message
        assert job.completed_at is not None
        assert job.is_terminal
        assert job.result is None
    
    @pytest.mark.asyncio
    async def test_cancel_job(self, job_service, mock_repo):
        """Test job cancellation."""
        # Create pending job
        job_id = await job_service.create_job("pubmed.sync", {}, "trace-123")
        
        # Cancel job
        success = await job_service.cancel_job(job_id)
        
        # Verify cancellation
        assert success is True
        job = mock_repo.jobs[job_id]
        assert job.status == JobStatus.CANCELLED
        assert job.completed_at is not None
        assert job.is_terminal
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, job_service):
        """Test cancelling non-existent job."""
        fake_job_id = str(uuid.uuid4())
        
        with pytest.raises(JobNotFoundError):
            await job_service.cancel_job(fake_job_id)
    
    @pytest.mark.asyncio
    async def test_cancel_terminal_job(self, job_service, mock_repo):
        """Test cancelling already completed job."""
        # Create and complete job
        job_id = await job_service.create_job("ping", {}, "trace-123")
        await job_service.start_job(job_id)
        await job_service.complete_job(job_id, {"success": True})
        
        # Try to cancel completed job
        success = await job_service.cancel_job(job_id)
        
        # Should return False (can't cancel terminal job)
        assert success is False
        job = mock_repo.jobs[job_id]
        assert job.status == JobStatus.COMPLETED  # Unchanged
    
    @pytest.mark.asyncio
    async def test_list_jobs_all(self, job_service, mock_repo):
        """Test listing all jobs."""
        # Create multiple jobs
        job_ids = []
        for i in range(3):
            job_id = await job_service.create_job(f"tool-{i}", {}, f"trace-{i}")
            job_ids.append(job_id)
        
        # List all jobs
        jobs = await job_service.list_jobs()
        
        assert len(jobs) == 3
        job_ids_returned = [job.id for job in jobs]
        assert set(job_ids_returned) == set(job_ids)
    
    @pytest.mark.asyncio
    async def test_list_jobs_by_status(self, job_service, mock_repo):
        """Test listing jobs filtered by status."""
        # Create jobs with different statuses
        pending_id = await job_service.create_job("tool1", {}, "trace-1")
        running_id = await job_service.create_job("tool2", {}, "trace-2")
        await job_service.start_job(running_id)
        
        # List pending jobs
        pending_jobs = await job_service.list_jobs(status=JobStatus.PENDING)
        assert len(pending_jobs) == 1
        assert pending_jobs[0].id == pending_id
        
        # List running jobs
        running_jobs = await job_service.list_jobs(status=JobStatus.RUNNING)
        assert len(running_jobs) == 1
        assert running_jobs[0].id == running_id
    
    @pytest.mark.asyncio
    async def test_list_jobs_with_pagination(self, job_service, mock_repo):
        """Test job listing with pagination."""
        # Create 5 jobs
        job_ids = []
        for i in range(5):
            job_id = await job_service.create_job(f"tool-{i}", {}, f"trace-{i}")
            job_ids.append(job_id)
        
        # Get first 3 jobs
        first_page = await job_service.list_jobs(limit=3, offset=0)
        assert len(first_page) == 3
        
        # Get next 2 jobs
        second_page = await job_service.list_jobs(limit=3, offset=3)
        assert len(second_page) == 2
        
        # No overlap between pages
        first_ids = [job.id for job in first_page]
        second_ids = [job.id for job in second_page]
        assert not set(first_ids).intersection(set(second_ids))
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_jobs(self, job_service, mock_repo):
        """Test cleaning up expired jobs."""
        # Create job that's already expired
        job_data = JobData.create_new("test-tool", {}, "trace-123", ttl_hours=24)
        # Manually set expiry to past
        job_data.expires_at = datetime.now(UTC).replace(year=2020)
        await mock_repo.save(job_data)
        
        # Create current job
        current_job_id = await job_service.create_job("current-tool", {}, "trace-456")
        
        # Cleanup expired
        cleaned_count = await job_service.cleanup_expired_jobs()
        
        # Should have cleaned 1 job
        assert cleaned_count == 1
        
        # Current job should remain
        remaining_jobs = await job_service.list_jobs()
        assert len(remaining_jobs) == 1
        assert remaining_jobs[0].id == current_job_id