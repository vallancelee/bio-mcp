"""
Universal database models for multi-source documents.
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class UniversalDocument(Base):
    """Universal document model for all sources."""

    __tablename__ = "documents_universal"

    id = Column(
        String(255), primary_key=True
    )  # source-prefixed: "pubmed:12345", "clinicaltrials:NCT01234"
    source = Column(String(50), nullable=False, index=True)
    source_id = Column(String(100), nullable=False)  # Original ID from source
    title = Column(Text, nullable=False)
    abstract = Column(Text)
    content = Column(Text)  # Full searchable content
    authors = Column(JSON)
    publication_date = Column(DateTime, index=True)
    source_metadata = Column(JSON)  # Source-specific fields
    quality_score = Column(Integer, index=True, default=0)
    last_updated = Column(DateTime, index=True)  # For sync watermarking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class SyncWatermark(Base):
    """Watermarks for incremental sync across sources."""

    __tablename__ = "sync_watermarks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)
    query_key = Column(String(255), nullable=False)
    last_sync = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        # Ensure unique combination of source and query_key
        {"mysql_engine": "InnoDB"},
    )


class CorpusCheckpoint(Base):
    """Corpus checkpoints for reproducible research."""

    __tablename__ = "corpus_checkpoints"

    checkpoint_id = Column(String(255), primary_key=True)
    name = Column(String(500), nullable=False)
    description = Column(Text)
    version = Column(String(50))
    parent_checkpoint_id = Column(String(255))
    document_count = Column(String(50))  # Using string to match test expectations
    last_sync_edat = Column(String(50))
    primary_queries = Column(JSON)  # List of primary search queries
    total_documents = Column(String(50))
    total_vectors = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class NormalizedDocument(Base):
    """Normalized document metadata table for multi-source pipeline."""

    __tablename__ = "documents"

    uid = Column(String(255), primary_key=True)  # e.g., "pubmed:12345678"
    source = Column(String(50), nullable=False, index=True)  # e.g., "pubmed"
    source_id = Column(String(100), nullable=False)  # e.g., "12345678"
    title = Column(Text)
    published_at = Column(DateTime(timezone=True), index=True)
    s3_raw_uri = Column(Text, nullable=False)  # S3 location of raw data
    content_hash = Column(String(64), nullable=False)  # SHA256 hash for deduplication
    created_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(UTC), 
        nullable=False
    )

    def to_document_dict(self) -> dict:
        """Convert database record to dictionary for API responses."""
        return {
            "uid": self.uid,
            "source": self.source,
            "source_id": self.source_id,
            "title": self.title,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "s3_raw_uri": self.s3_raw_uri,
            "content_hash": self.content_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_document(cls, document, s3_raw_uri: str, content_hash: str):
        """Create database record from Document model instance."""
        return cls(
            uid=document.uid,
            source=document.source,
            source_id=document.source_id,
            title=document.title,
            published_at=document.published_at,
            s3_raw_uri=s3_raw_uri,
            content_hash=content_hash,
        )


class JobStatus(enum.Enum):
    """Job execution status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobRecord(Base):
    """SQLAlchemy model for async job persistence."""

    __tablename__ = "jobs"

    # Primary identifier
    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)

    # Job metadata
    tool_name = Column(String(100), nullable=False, index=True)
    status = Column(
        Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True
    )
    trace_id = Column(String(36), nullable=False, index=True)

    # Job data (stored as JSONB for PostgreSQL, JSON for others)
    parameters = Column(JSONB, nullable=False)
    result = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    def to_job_data(self):
        """Convert SQLAlchemy record to business logic model."""
        from bio_mcp.http.jobs.models import JobData

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
            expires_at=self.expires_at,
        )

    @classmethod
    def from_job_data(cls, job_data):
        """Create SQLAlchemy record from business logic model."""
        import uuid

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
            expires_at=job_data.expires_at,
        )

    def __repr__(self) -> str:
        return f"<JobRecord(id='{self.id}', tool='{self.tool_name}', status='{self.status.value}')>"
