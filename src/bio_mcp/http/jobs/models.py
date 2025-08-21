"""Job models following codebase pattern: dataclass for business logic + SQLAlchemy for persistence."""

import enum
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Column, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from bio_mcp.shared.models.database_models import Base


class JobStatus(enum.Enum):
    """Job execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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


class JobRecord(Base):
    """SQLAlchemy model for job persistence."""
    __tablename__ = "jobs"
    
    # Primary identifier
    id = Column(
        UUID(as_uuid=True), 
        primary_key=True,
        nullable=False
    )
    
    # Job metadata
    tool_name = Column(String(100), nullable=False, index=True)
    status = Column(
        Enum(JobStatus), 
        nullable=False,
        index=True
    )
    
    # Job data
    parameters = Column(JSONB, nullable=False)
    result = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), 
        nullable=False,
        index=True
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(
        DateTime(timezone=True), 
        nullable=False,
        index=True
    )
    
    # Tracing
    trace_id = Column(String(36), nullable=True, index=True)
    
    def to_job_data(self) -> JobData:
        """Convert SQLAlchemy record to business logic model."""
        return JobData(
            id=str(self.id),
            tool_name=self.tool_name,
            status=self.status,
            parameters=self.parameters,
            result=self.result,
            error_message=self.error_message,
            trace_id=self.trace_id,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            expires_at=self.expires_at
        )
    
    @classmethod
    def from_job_data(cls, job_data: JobData) -> "JobRecord":
        """Create SQLAlchemy record from business logic model."""
        return cls(
            id=uuid.UUID(job_data.id),
            tool_name=job_data.tool_name,
            status=job_data.status,
            parameters=job_data.parameters,
            result=job_data.result,
            error_message=job_data.error_message,
            trace_id=job_data.trace_id,
            created_at=job_data.created_at,
            started_at=job_data.started_at,
            completed_at=job_data.completed_at,
            expires_at=job_data.expires_at
        )
    
    def __repr__(self) -> str:
        """String representation of job record."""
        return (
            f"JobRecord(id={self.id}, tool={self.tool_name}, "
            f"status={self.status.value}, created_at={self.created_at})"
        )