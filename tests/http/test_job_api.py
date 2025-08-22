"""Tests for job API endpoints."""

import uuid

import pytest
from fastapi.testclient import TestClient

from bio_mcp.http.jobs.api import create_job_router
from bio_mcp.http.jobs.models import JobData, JobStatus
from bio_mcp.http.jobs.service import JobNotFoundError


class MockJobService:
    """Mock job service for API testing."""

    def __init__(self):
        self.jobs = {}
        self.created_jobs = []

    async def create_job(
        self, tool_name: str, parameters: dict, trace_id: str, ttl_hours: int = 24
    ) -> str:
        """Mock job creation."""
        job_id = str(uuid.uuid4())
        job_data = JobData.create_new(tool_name, parameters, trace_id, ttl_hours)
        job_data.id = job_id  # Use consistent ID
        self.jobs[job_id] = job_data
        self.created_jobs.append((tool_name, parameters, trace_id, ttl_hours))
        return job_id

    async def get_job_status(self, job_id: str) -> JobData:
        """Mock job status retrieval."""
        if job_id not in self.jobs:
            raise JobNotFoundError(f"Job {job_id} not found")
        return self.jobs[job_id]

    async def cancel_job(self, job_id: str) -> bool:
        """Mock job cancellation."""
        if job_id not in self.jobs:
            raise JobNotFoundError(f"Job {job_id} not found")

        job = self.jobs[job_id]
        if job.is_terminal:
            return False

        job.cancel()
        return True

    async def list_jobs(
        self, status: JobStatus = None, limit: int = 50, offset: int = 0
    ) -> list[JobData]:
        """Mock job listing."""
        jobs = list(self.jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs[offset : offset + limit]


class TestJobAPI:
    """Test job API endpoints."""

    @pytest.fixture
    def mock_job_service(self):
        """Create mock job service."""
        return MockJobService()

    @pytest.fixture
    def app_client(self, mock_job_service):
        """Create FastAPI test client with job router."""
        from fastapi import FastAPI

        app = FastAPI()

        # Create router with mock job service factory
        def mock_job_service_factory():
            return mock_job_service

        job_router = create_job_router(job_service_factory=mock_job_service_factory)

        app.include_router(job_router)
        return TestClient(app)

    def test_create_job_success(self, app_client, mock_job_service):
        """Test successful job creation."""
        request_data = {
            "tool": "rag.get",
            "params": {"query": "test query", "limit": 10},
        }

        response = app_client.post("/v1/jobs", json=request_data)

        assert response.status_code == 201
        data = response.json()

        # Should return job ID and status
        assert "job_id" in data
        assert "status" in data
        assert data["status"] == "pending"

        # Verify job was created in service
        assert len(mock_job_service.created_jobs) == 1
        created = mock_job_service.created_jobs[0]
        assert created[0] == "rag.get"  # tool_name
        assert created[1] == {"query": "test query", "limit": 10}  # parameters

    def test_create_job_with_custom_ttl(self, app_client, mock_job_service):
        """Test job creation with custom TTL."""
        request_data = {"tool": "pubmed.sync", "params": {}, "ttl_hours": 48}

        response = app_client.post("/v1/jobs", json=request_data)

        assert response.status_code == 201

        # Verify TTL was passed to service
        created = mock_job_service.created_jobs[0]
        assert created[3] == 48  # ttl_hours

    def test_create_job_invalid_tool(self, app_client):
        """Test job creation with missing tool name."""
        request_data = {"params": {"query": "test"}}

        response = app_client.post("/v1/jobs", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_get_job_status_success(self, app_client, mock_job_service):
        """Test successful job status retrieval."""
        # Create a job first
        job_data = JobData.create_new("ping", {}, "trace-123")
        job_id = job_data.id
        mock_job_service.jobs[job_id] = job_data

        response = app_client.get(f"/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["job_id"] == job_id
        assert data["tool"] == "ping"
        assert data["status"] == "pending"
        assert "created_at" in data
        assert "duration_ms" in data

    def test_get_job_status_not_found(self, app_client):
        """Test job status retrieval for non-existent job."""
        fake_job_id = str(uuid.uuid4())

        response = app_client.get(f"/v1/jobs/{fake_job_id}")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_job_status_completed_with_result(self, app_client, mock_job_service):
        """Test job status for completed job with result."""
        # Create completed job
        job_data = JobData.create_new("rag.get", {"query": "test"}, "trace-456")
        job_data.start_execution()
        job_data.complete_with_result({"documents": ["doc1", "doc2"]})

        job_id = job_data.id
        mock_job_service.jobs[job_id] = job_data

        response = app_client.get(f"/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "completed"
        assert data["result"] == {"documents": ["doc1", "doc2"]}
        assert data["duration_ms"] is not None

    def test_get_job_status_failed_with_error(self, app_client, mock_job_service):
        """Test job status for failed job with error."""
        # Create failed job
        job_data = JobData.create_new("failing-tool", {}, "trace-789")
        job_data.start_execution()
        job_data.fail_with_error("Tool execution timeout")

        job_id = job_data.id
        mock_job_service.jobs[job_id] = job_data

        response = app_client.get(f"/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "failed"
        assert data["error"] == "Tool execution timeout"
        assert data["result"] is None

    def test_cancel_job_success(self, app_client, mock_job_service):
        """Test successful job cancellation."""
        # Create pending job
        job_data = JobData.create_new("slow-tool", {}, "trace-cancel")
        job_id = job_data.id
        mock_job_service.jobs[job_id] = job_data

        response = app_client.delete(f"/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["cancelled"] is True

    def test_cancel_job_not_found(self, app_client):
        """Test cancelling non-existent job."""
        fake_job_id = str(uuid.uuid4())

        response = app_client.delete(f"/v1/jobs/{fake_job_id}")

        assert response.status_code == 404

    def test_cancel_terminal_job(self, app_client, mock_job_service):
        """Test cancelling already completed job."""
        # Create completed job
        job_data = JobData.create_new("finished-tool", {}, "trace-finished")
        job_data.start_execution()
        job_data.complete_with_result({"success": True})

        job_id = job_data.id
        mock_job_service.jobs[job_id] = job_data

        response = app_client.delete(f"/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["cancelled"] is False
        assert "already completed" in data["message"].lower()

    def test_list_jobs_default(self, app_client, mock_job_service):
        """Test listing jobs with default parameters."""
        # Create multiple jobs
        for i in range(3):
            job_data = JobData.create_new(f"tool-{i}", {}, f"trace-{i}")
            mock_job_service.jobs[job_data.id] = job_data

        response = app_client.get("/v1/jobs")

        assert response.status_code == 200
        data = response.json()

        assert "jobs" in data
        assert len(data["jobs"]) == 3
        assert "total" in data
        assert data["total"] == 3

    def test_list_jobs_with_status_filter(self, app_client, mock_job_service):
        """Test listing jobs filtered by status."""
        # Create jobs with different statuses
        pending_job = JobData.create_new("pending-tool", {}, "trace-pending")
        running_job = JobData.create_new("running-tool", {}, "trace-running")
        running_job.start_execution()

        mock_job_service.jobs[pending_job.id] = pending_job
        mock_job_service.jobs[running_job.id] = running_job

        # List only pending jobs
        response = app_client.get("/v1/jobs?status=pending")

        assert response.status_code == 200
        data = response.json()

        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["status"] == "pending"

    def test_list_jobs_with_pagination(self, app_client, mock_job_service):
        """Test job listing with pagination."""
        # Create 5 jobs
        for i in range(5):
            job_data = JobData.create_new(f"tool-{i}", {}, f"trace-{i}")
            mock_job_service.jobs[job_data.id] = job_data

        # Get first 3 jobs
        response = app_client.get("/v1/jobs?limit=3&offset=0")

        assert response.status_code == 200
        data = response.json()

        assert len(data["jobs"]) == 3
        assert (
            data["total"] == 3
        )  # API currently returns count of returned jobs, not total available
        assert data["limit"] == 3
        assert data["offset"] == 0

        # Get next 2 jobs
        response = app_client.get("/v1/jobs?limit=3&offset=3")

        assert response.status_code == 200
        data = response.json()

        assert len(data["jobs"]) == 2
        assert data["offset"] == 3

    def test_list_jobs_invalid_status(self, app_client):
        """Test listing jobs with invalid status."""
        response = app_client.get("/v1/jobs?status=invalid_status")

        assert response.status_code == 422  # Validation error
