"""Job models following codebase pattern: dataclass for business logic + SQLAlchemy for persistence."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from bio_mcp.shared.models.database_models import JobStatus


@dataclass
class JobData:
    """Business logic model for job management."""
    id: str
    tool_name: str
    status: JobStatus
    parameters: dict[str, Any]
    trace_id: str
    created_at: datetime
    expires_at: datetime
    result: Any = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    @classmethod
    def create_new(
        cls,
        tool_name: str,
        parameters: dict[str, Any],
        trace_id: str,
        ttl_hours: int = 24
    ) -> "JobData":
        """Create a new job with defaults."""
        now = datetime.now(UTC)
        return cls(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            status=JobStatus.PENDING,
            parameters=parameters,
            trace_id=trace_id,
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours)
        )
    
    @property
    def is_terminal(self) -> bool:
        """Check if job is in terminal state."""
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
    
    @property
    def is_active(self) -> bool:
        """Check if job is actively running."""
        return self.status == JobStatus.RUNNING
    
    @property
    def is_pending(self) -> bool:
        """Check if job is waiting to be executed."""
        return self.status == JobStatus.PENDING
    
    @property
    def duration_ms(self) -> float | None:
        """Calculate job execution duration in milliseconds."""
        if self.started_at is None:
            return None
        
        end_time = self.completed_at or datetime.now(UTC)
        duration = end_time - self.started_at
        return duration.total_seconds() * 1000
    
    def start_execution(self) -> None:
        """Mark job as started."""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.now(UTC)
    
    def complete_with_result(self, result: Any) -> None:
        """Mark job as completed with result."""
        self.status = JobStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now(UTC)
    
    def fail_with_error(self, error_message: str) -> None:
        """Mark job as failed with error."""
        self.status = JobStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now(UTC)
    
    def cancel(self) -> None:
        """Mark job as cancelled."""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.now(UTC)