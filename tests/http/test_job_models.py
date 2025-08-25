"""Tests for job models (business logic dataclass + persistence SQLAlchemy)."""

import uuid
from datetime import UTC, datetime, timedelta

from bio_mcp.http.jobs.models import JobData
from bio_mcp.shared.models.database_models import JobRecord, JobStatus


class TestJobStatus:
    """Test job status enumeration."""

    def test_job_status_values(self):
        """Test job status enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"

    def test_job_status_progression(self):
        """Test typical job status progression."""
        # Valid transitions
        assert JobStatus.PENDING != JobStatus.RUNNING
        assert JobStatus.RUNNING != JobStatus.COMPLETED

        # All statuses should be distinct
        statuses = list(JobStatus)
        assert len(statuses) == len(set(statuses))


class TestJobData:
    """Test job business logic dataclass."""

    def test_job_creation_factory_method(self):
        """Test creating new job with factory method."""
        tool_name = "rag.get"
        parameters = {"query": "test query", "limit": 10}
        trace_id = str(uuid.uuid4())

        job = JobData.create_new(tool_name, parameters, trace_id)

        assert job.tool_name == tool_name
        assert job.parameters == parameters
        assert job.trace_id == trace_id
        assert job.status == JobStatus.PENDING
        assert job.result is None
        assert job.error_message is None
        assert job.started_at is None
        assert job.completed_at is None

        # Should have valid ID and timestamps
        assert job.id is not None
        assert uuid.UUID(job.id)  # Valid UUID
        assert job.created_at is not None
        assert job.expires_at is not None
        assert job.expires_at > job.created_at

    def test_job_creation_with_custom_ttl(self):
        """Test creating job with custom TTL."""
        job = JobData.create_new("pubmed.sync", {}, "trace-123", ttl_hours=48)

        expected_expiry = job.created_at + timedelta(hours=48)
        assert abs((job.expires_at - expected_expiry).total_seconds()) < 1

    def test_job_terminal_status_check(self):
        """Test terminal status detection."""
        job = JobData.create_new("ping", {}, "trace-123")

        # Pending is not terminal
        job.status = JobStatus.PENDING
        assert not job.is_terminal

        # Running is not terminal
        job.status = JobStatus.RUNNING
        assert not job.is_terminal

        # Completed is terminal
        job.status = JobStatus.COMPLETED
        assert job.is_terminal

        # Failed is terminal
        job.status = JobStatus.FAILED
        assert job.is_terminal

        # Cancelled is terminal
        job.status = JobStatus.CANCELLED
        assert job.is_terminal

    def test_job_active_status_check(self):
        """Test active status detection."""
        job = JobData.create_new("ping", {}, "trace-123")

        # Only running is active
        job.status = JobStatus.RUNNING
        assert job.is_active

        # Other statuses are not active
        for status in [
            JobStatus.PENDING,
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ]:
            job.status = status
            assert not job.is_active

    def test_job_pending_status_check(self):
        """Test pending status detection."""
        job = JobData.create_new("ping", {}, "trace-123")

        # Only pending is pending
        job.status = JobStatus.PENDING
        assert job.is_pending

        # Other statuses are not pending
        for status in [
            JobStatus.RUNNING,
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ]:
            job.status = status
            assert not job.is_pending

    def test_job_duration_calculation(self):
        """Test job duration calculation."""
        job = JobData.create_new("rag.get", {}, "trace-123")

        # No duration when not started
        assert job.duration_ms is None

        # Duration calculated from start to completion
        from datetime import timedelta
        start_time = datetime.now(UTC)
        job.started_at = start_time
        job.completed_at = start_time + timedelta(milliseconds=100)

        duration = job.duration_ms
        assert duration is not None
        assert duration >= 100  # At least 100ms

    def test_job_start_execution(self):
        """Test starting job execution."""
        job = JobData.create_new("rag.get", {}, "trace-123")

        assert job.status == JobStatus.PENDING
        assert job.started_at is None

        job.start_execution()

        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None
        assert job.is_active

    def test_job_complete_with_result(self):
        """Test completing job with result."""
        job = JobData.create_new("rag.get", {}, "trace-123")
        job.start_execution()

        result_data = {"data": "test result"}
        job.complete_with_result(result_data)

        assert job.status == JobStatus.COMPLETED
        assert job.result == result_data
        assert job.completed_at is not None
        assert job.is_terminal

    def test_job_fail_with_error(self):
        """Test failing job with error message."""
        job = JobData.create_new("rag.get", {}, "trace-123")
        job.start_execution()

        error_msg = "Tool execution failed"
        job.fail_with_error(error_msg)

        assert job.status == JobStatus.FAILED
        assert job.error_message == error_msg
        assert job.completed_at is not None
        assert job.is_terminal
        assert job.result is None  # No result on failure

    def test_job_cancellation(self):
        """Test job cancellation."""
        job = JobData.create_new("rag.get", {}, "trace-123")

        job.cancel()

        assert job.status == JobStatus.CANCELLED
        assert job.completed_at is not None
        assert job.is_terminal


class TestJobRecord:
    """Test SQLAlchemy job persistence model."""

    def test_job_record_table_name(self):
        """Test job record maps to correct table."""
        assert JobRecord.__tablename__ == "jobs"

    def test_conversion_to_job_data(self):
        """Test converting SQLAlchemy record to business model."""
        # Create job data
        job_data = JobData.create_new("rag.get", {"query": "test"}, "trace-123")

        # Convert to record and back
        record = JobRecord.from_job_data(job_data)
        converted_data = record.to_job_data()

        # Should be equivalent
        assert converted_data.id == job_data.id
        assert converted_data.tool_name == job_data.tool_name
        assert converted_data.status == job_data.status
        assert converted_data.parameters == job_data.parameters
        assert converted_data.trace_id == job_data.trace_id
        assert converted_data.result == job_data.result
        assert converted_data.error_message == job_data.error_message
        assert converted_data.created_at == job_data.created_at
        assert converted_data.expires_at == job_data.expires_at

    def test_conversion_from_job_data(self):
        """Test creating SQLAlchemy record from business model."""
        job_data = JobData.create_new("pubmed.search", {"term": "covid"}, "trace-456")
        job_data.start_execution()
        job_data.complete_with_result({"count": 100})

        record = JobRecord.from_job_data(job_data)

        assert str(record.id) == job_data.id
        assert record.tool_name == job_data.tool_name
        assert record.status == job_data.status
        assert record.parameters == job_data.parameters
        assert record.result == job_data.result
        assert record.trace_id == job_data.trace_id
        assert record.started_at == job_data.started_at
        assert record.completed_at == job_data.completed_at
