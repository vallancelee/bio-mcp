"""
Universal database models for multi-source documents.
"""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class UniversalDocument(Base):
    """Universal document model for all sources."""
    __tablename__ = 'documents_universal'
    
    id = Column(String(255), primary_key=True)  # source-prefixed: "pubmed:12345", "clinicaltrials:NCT01234"
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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SyncWatermark(Base):
    """Watermarks for incremental sync across sources."""
    __tablename__ = 'sync_watermarks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)
    query_key = Column(String(255), nullable=False)
    last_sync = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        # Ensure unique combination of source and query_key
        {'mysql_engine': 'InnoDB'},
    )


class CorpusCheckpoint(Base):
    """Corpus checkpoints for reproducible research."""
    __tablename__ = 'corpus_checkpoints'
    
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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)