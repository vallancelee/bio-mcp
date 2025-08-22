"""Tests for job worker pool and execution."""

import asyncio

import pytest

from bio_mcp.http.jobs.models import JobData
from bio_mcp.http.jobs.worker import JobWorker


class MockToolExecutor:
    """Mock tool executor for testing worker."""

    def __init__(self):
        self.executions = []  # Track tool executions
        self.execution_results = {}  # Map tool_name -> result/exception
        self.execution_delays = {}  # Map tool_name -> delay in seconds

    def set_result(self, tool_name: str, result: any, delay: float = 0.1):
        """Set mock result for tool."""
        self.execution_results[tool_name] = result
        self.execution_delays[tool_name] = delay

    def set_error(self, tool_name: str, error: Exception, delay: float = 0.1):
        """Set mock error for tool."""
        self.execution_results[tool_name] = error
        self.execution_delays[tool_name] = delay

    async def execute_tool(self, tool_name: str, parameters: dict) -> any:
        """Mock tool execution."""
        self.executions.append((tool_name, parameters))

        # Simulate execution delay
        delay = self.execution_delays.get(tool_name, 0.1)
        await asyncio.sleep(delay)

        # Return result or raise error
        result = self.execution_results.get(tool_name)
        if isinstance(result, Exception):
            raise result
        return result


class MockJobService:
    """Mock job service for testing worker."""

    def __init__(self):
        self.jobs = {}
        self.pending_jobs = []
        self.status_updates = []  # Track status changes

    def add_pending_job(self, job_data: JobData):
        """Add job to pending queue."""
        self.jobs[job_data.id] = job_data
        self.pending_jobs.append(job_data)

    async def get_pending_jobs(self, limit: int = 10) -> list[JobData]:
        """Get pending jobs for processing."""
        jobs = self.pending_jobs[:limit]
        self.pending_jobs = self.pending_jobs[limit:]
        return jobs

    async def start_job(self, job_id: str) -> None:
        """Mark job as started."""
        if job_id in self.jobs:
            self.jobs[job_id].start_execution()
            self.status_updates.append(("start", job_id))

    async def complete_job(self, job_id: str, result: any) -> None:
        """Complete job with result."""
        if job_id in self.jobs:
            self.jobs[job_id].complete_with_result(result)
            self.status_updates.append(("complete", job_id, result))

    async def fail_job(self, job_id: str, error_message: str) -> None:
        """Fail job with error."""
        if job_id in self.jobs:
            self.jobs[job_id].fail_with_error(error_message)
            self.status_updates.append(("fail", job_id, error_message))


class TestJobWorker:
    """Test job worker pool functionality."""

    @pytest.fixture
    def mock_tool_executor(self):
        """Create mock tool executor."""
        return MockToolExecutor()

    @pytest.fixture
    def mock_job_service(self):
        """Create mock job service."""
        return MockJobService()

    @pytest.fixture
    def job_worker(self, mock_tool_executor, mock_job_service):
        """Create job worker with mocks."""
        return JobWorker(
            tool_executor=mock_tool_executor,
            job_service=mock_job_service,
            max_concurrent_jobs=3,
            poll_interval_seconds=0.1,
        )

    @pytest.mark.asyncio
    async def test_worker_initialization(self, job_worker):
        """Test worker initialization with correct settings."""
        assert job_worker.max_concurrent_jobs == 3
        assert job_worker.poll_interval_seconds == 0.1
        assert job_worker.running_jobs == {}
        assert not job_worker.is_running

    @pytest.mark.asyncio
    async def test_execute_single_job_success(
        self, job_worker, mock_tool_executor, mock_job_service
    ):
        """Test executing a single job successfully."""
        # Setup mock tool result
        mock_tool_executor.set_result("ping", {"status": "pong"})

        # Create test job and add to mock service
        job_data = JobData.create_new("ping", {}, "trace-123")
        mock_job_service.add_pending_job(job_data)

        # Execute job
        await job_worker.execute_job(job_data)

        # Verify tool was executed
        assert len(mock_tool_executor.executions) == 1
        assert mock_tool_executor.executions[0] == ("ping", {})

        # Verify job status updates
        updates = mock_job_service.status_updates
        assert len(updates) == 2
        assert updates[0] == ("start", job_data.id)
        assert updates[1] == ("complete", job_data.id, {"status": "pong"})

    @pytest.mark.asyncio
    async def test_execute_single_job_failure(
        self, job_worker, mock_tool_executor, mock_job_service
    ):
        """Test executing a job that fails."""
        # Setup mock tool error
        mock_tool_executor.set_error("failing-tool", Exception("Tool crashed"))

        # Create test job and add to mock service
        job_data = JobData.create_new("failing-tool", {"param": "value"}, "trace-456")
        mock_job_service.add_pending_job(job_data)

        # Execute job
        await job_worker.execute_job(job_data)

        # Verify tool was executed
        assert len(mock_tool_executor.executions) == 1
        assert mock_tool_executor.executions[0] == ("failing-tool", {"param": "value"})

        # Verify job failed
        updates = mock_job_service.status_updates
        assert len(updates) == 2
        assert updates[0] == ("start", job_data.id)
        assert updates[1] == ("fail", job_data.id, "Tool crashed")

    @pytest.mark.asyncio
    async def test_worker_concurrency_limit(
        self, job_worker, mock_tool_executor, mock_job_service
    ):
        """Test worker respects concurrency limits."""
        # Setup slow tool execution
        mock_tool_executor.set_result("slow-tool", {"done": True}, delay=0.3)

        # Create multiple jobs
        jobs = []
        for i in range(5):  # More than max_concurrent (3)
            job_data = JobData.create_new("slow-tool", {"id": i}, f"trace-{i}")
            jobs.append(job_data)
            mock_job_service.add_pending_job(job_data)

        # Start worker pool
        worker_task = asyncio.create_task(job_worker.start_worker_pool())

        # Let it run for a bit
        await asyncio.sleep(0.5)

        # Stop worker
        await job_worker.stop_worker_pool()
        worker_task.cancel()

        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Should have processed jobs with concurrency limit
        completed_jobs = [
            u for u in mock_job_service.status_updates if u[0] == "complete"
        ]
        assert len(completed_jobs) >= 3  # At least 3 should be processed
        assert len(job_worker.running_jobs) == 0  # All should be cleaned up

    @pytest.mark.asyncio
    async def test_worker_job_polling(
        self, job_worker, mock_tool_executor, mock_job_service
    ):
        """Test worker polls for pending jobs."""
        # Setup fast tool
        mock_tool_executor.set_result("fast-tool", {"result": "success"}, delay=0.05)

        # Add jobs to queue over time
        job1 = JobData.create_new("fast-tool", {"batch": 1}, "trace-1")
        mock_job_service.add_pending_job(job1)

        # Start worker
        worker_task = asyncio.create_task(job_worker.start_worker_pool())

        # Wait a bit, then add another job
        await asyncio.sleep(0.15)
        job2 = JobData.create_new("fast-tool", {"batch": 2}, "trace-2")
        mock_job_service.add_pending_job(job2)

        # Wait for processing
        await asyncio.sleep(0.2)

        # Stop worker
        await job_worker.stop_worker_pool()
        worker_task.cancel()

        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Both jobs should be processed
        completed_jobs = [
            u for u in mock_job_service.status_updates if u[0] == "complete"
        ]
        assert len(completed_jobs) == 2

    @pytest.mark.asyncio
    async def test_worker_graceful_shutdown(
        self, job_worker, mock_tool_executor, mock_job_service
    ):
        """Test worker shuts down gracefully."""
        # Setup slow tool
        mock_tool_executor.set_result("slow-tool", {"done": True}, delay=0.2)

        # Add job
        job_data = JobData.create_new("slow-tool", {}, "trace-123")
        mock_job_service.add_pending_job(job_data)

        # Start worker
        worker_task = asyncio.create_task(job_worker.start_worker_pool())

        # Wait for job to start
        await asyncio.sleep(0.1)
        assert len(job_worker.running_jobs) == 1

        # Stop worker (should wait for job completion)
        await job_worker.stop_worker_pool()
        worker_task.cancel()

        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Job should complete
        completed_jobs = [
            u for u in mock_job_service.status_updates if u[0] == "complete"
        ]
        assert len(completed_jobs) == 1
        assert len(job_worker.running_jobs) == 0

    @pytest.mark.asyncio
    async def test_worker_error_handling(
        self, job_worker, mock_tool_executor, mock_job_service
    ):
        """Test worker handles job execution errors gracefully."""
        # Setup tools with different behaviors
        mock_tool_executor.set_result("good-tool", {"status": "ok"})
        mock_tool_executor.set_error("bad-tool", RuntimeError("Critical error"))

        # Add mixed jobs
        good_job = JobData.create_new("good-tool", {}, "trace-good")
        bad_job = JobData.create_new("bad-tool", {}, "trace-bad")
        mock_job_service.add_pending_job(good_job)
        mock_job_service.add_pending_job(bad_job)

        # Start worker
        worker_task = asyncio.create_task(job_worker.start_worker_pool())

        # Wait for processing
        await asyncio.sleep(0.3)

        # Stop worker
        await job_worker.stop_worker_pool()
        worker_task.cancel()

        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Both jobs should be processed (one success, one failure)
        updates = mock_job_service.status_updates
        completed = [u for u in updates if u[0] == "complete"]
        failed = [u for u in updates if u[0] == "fail"]

        assert len(completed) == 1
        assert len(failed) == 1
        assert failed[0][2] == "Critical error"  # Error message
