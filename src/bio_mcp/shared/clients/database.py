"""
Database layer for Bio-MCP server.
Phase 2A: Basic Database with SQLAlchemy models for PubMed documents.
"""

import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    Date,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from bio_mcp.config.logging_config import get_logger
from bio_mcp.shared.core.error_handling import ValidationError

logger = get_logger(__name__)

# SQLAlchemy declarative base
Base = declarative_base()


class PubMedDocument(Base):
    """SQLAlchemy model for PubMed documents."""
    
    __tablename__ = "pubmed_documents"
    
    # Primary key
    pmid = Column(String(50), primary_key=True, nullable=False)
    
    # Required fields
    title = Column(String(1000), nullable=False)
    
    # Optional content fields
    abstract = Column(Text, nullable=True)
    authors = Column(JSON, nullable=True, default=list)
    publication_date = Column(Date, nullable=True)
    journal = Column(String(500), nullable=True)
    doi = Column(String(200), nullable=True)
    keywords = Column(JSON, nullable=True, default=list)
    
    # Metadata
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    def __init__(self, pmid: str, title: str, **kwargs):
        """Initialize PubMed document with validation."""
        if pmid is None or not pmid:
            raise ValidationError("PMID is required")
        if title is None or not title:
            raise ValidationError("Title is required")
        
        self.pmid = pmid
        self.title = title
        
        # Set optional fields with defaults
        self.abstract = kwargs.get('abstract')
        self.authors = kwargs.get('authors', [])
        self.publication_date = kwargs.get('publication_date')
        self.journal = kwargs.get('journal')
        self.doi = kwargs.get('doi')
        self.keywords = kwargs.get('keywords', [])
        
        # Set timestamps
        now = datetime.now(UTC)
        self.created_at = kwargs.get('created_at', now)
        self.updated_at = kwargs.get('updated_at', now)
    
    def __repr__(self):
        return f"<PubMedDocument(pmid='{self.pmid}', title='{self.title[:50]}...')>"


class SyncWatermark(Base):
    """SQLAlchemy model for tracking incremental sync progress."""
    
    __tablename__ = "sync_watermarks"
    
    # Primary key - query identifier
    query_key = Column(String(255), primary_key=True, nullable=False)
    
    # Last successful sync timestamp (EDAT format: YYYY/MM/DD)
    last_edat = Column(String(10), nullable=True)
    
    # Statistics
    total_synced = Column(String(20), nullable=False, default="0")
    last_sync_count = Column(String(20), nullable=False, default="0")
    
    # Metadata
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    def __init__(self, query_key: str, **kwargs):
        """Initialize sync watermark with validation."""
        if not query_key:
            raise ValidationError("Query key is required")
        
        self.query_key = query_key
        self.last_edat = kwargs.get('last_edat')
        self.total_synced = kwargs.get('total_synced', "0")
        self.last_sync_count = kwargs.get('last_sync_count', "0")
        
        # Set timestamps
        now = datetime.now(UTC)
        self.created_at = kwargs.get('created_at', now)
        self.updated_at = kwargs.get('updated_at', now)
    
    def __repr__(self):
        return f"<SyncWatermark(query_key='{self.query_key}', last_edat='{self.last_edat}')>"


class CorpusCheckpoint(Base):
    """SQLAlchemy model for managing corpus checkpoints for reproducible research."""
    
    __tablename__ = "corpus_checkpoints"
    
    # Primary key
    checkpoint_id = Column(String(255), primary_key=True, nullable=False)
    
    # Checkpoint metadata
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    
    # Corpus state information
    document_count = Column(String(20), nullable=False, default="0")
    last_sync_edat = Column(String(10), nullable=True)  # YYYY/MM/DD format
    
    # Query configuration that built this corpus
    primary_queries = Column(JSON, nullable=True, default=list)  # List of main queries
    sync_watermarks = Column(JSON, nullable=True, default=dict)  # Query -> watermark mapping
    
    # Corpus statistics
    total_documents = Column(String(20), nullable=False, default="0")
    total_vectors = Column(String(20), nullable=False, default="0")
    
    # Version and lineage
    version = Column(String(50), nullable=False, default="1.0")
    parent_checkpoint_id = Column(String(255), nullable=True)  # For checkpoint lineage
    
    # Metadata timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    def __init__(self, checkpoint_id: str, name: str, **kwargs):
        """Initialize corpus checkpoint with validation."""
        if not checkpoint_id:
            raise ValidationError("Checkpoint ID is required")
        if not name:
            raise ValidationError("Checkpoint name is required")
        
        self.checkpoint_id = checkpoint_id
        self.name = name
        self.description = kwargs.get('description')
        self.document_count = kwargs.get('document_count', "0")
        self.last_sync_edat = kwargs.get('last_sync_edat')
        self.primary_queries = kwargs.get('primary_queries', [])
        self.sync_watermarks = kwargs.get('sync_watermarks', {})
        self.total_documents = kwargs.get('total_documents', "0")
        self.total_vectors = kwargs.get('total_vectors', "0")
        self.version = kwargs.get('version', "1.0")
        self.parent_checkpoint_id = kwargs.get('parent_checkpoint_id')
        
        # Set timestamps
        now = datetime.now(UTC)
        self.created_at = kwargs.get('created_at', now)
        self.updated_at = kwargs.get('updated_at', now)
    
    def __repr__(self):
        return f"<CorpusCheckpoint(id='{self.checkpoint_id}', name='{self.name}', docs='{self.total_documents}')>"


@dataclass
class DatabaseConfig:
    """Configuration for database connections."""
    
    url: str | None = None
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: float = 30.0
    echo: bool = False
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create configuration from environment variables."""
        return cls(
            url=os.getenv('BIO_MCP_DATABASE_URL'),
            pool_size=int(os.getenv('BIO_MCP_DB_POOL_SIZE', '5')),
            max_overflow=int(os.getenv('BIO_MCP_DB_MAX_OVERFLOW', '10')),
            pool_timeout=float(os.getenv('BIO_MCP_DB_POOL_TIMEOUT', '30.0')),
            echo=os.getenv('BIO_MCP_DB_ECHO', '').lower() in ('true', '1', 'yes')
        )
    
    @classmethod
    def from_url(cls, url: str) -> 'DatabaseConfig':
        """Create configuration from database URL."""
        if not url:
            raise ValueError("Database URL is required")
        return cls(url=url)


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker | None = None
    
    async def initialize(self) -> None:
        """Initialize database engine and create tables."""
        if not self.config.url:
            raise ValidationError("Database URL is required")
        
        logger.info("Initializing database connection", url=self.config.url.split('@')[0] + '@***')
        
        try:
            # Create async engine with appropriate configuration
            self.engine = create_database_engine(self.config)
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise
    
    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            logger.info("Closing database connections")
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
    
    def get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self.session_factory:
            raise ValidationError("Database not initialized")
        return self.session_factory()
    
    async def create_document(self, doc_data: dict[str, Any]) -> PubMedDocument:
        """Create a new PubMed document."""
        logger.debug("Creating document", pmid=doc_data.get('pmid'))
        
        try:
            # Create document instance
            document = PubMedDocument(**doc_data)
            
            async with self.get_session() as session:
                session.add(document)
                await session.commit()
                await session.refresh(document)
                
                logger.info("Document created successfully", pmid=document.pmid)
                return document
                
        except IntegrityError as e:
            logger.error("Document creation failed - integrity error", pmid=doc_data.get('pmid'), error=str(e))
            raise ValidationError(f"Document with PMID {doc_data.get('pmid')} already exists")
        except Exception as e:
            logger.error("Document creation failed", pmid=doc_data.get('pmid'), error=str(e))
            raise
    
    async def get_document_by_pmid(self, pmid: str) -> PubMedDocument | None:
        """Retrieve a document by PMID."""
        logger.debug("Retrieving document by PMID", pmid=pmid)
        
        try:
            async with self.get_session() as session:
                result = await session.get(PubMedDocument, pmid)
                
                if result:
                    logger.debug("Document found", pmid=pmid)
                else:
                    logger.debug("Document not found", pmid=pmid)
                
                return result
                
        except Exception as e:
            logger.error("Failed to retrieve document", pmid=pmid, error=str(e))
            raise
    
    async def update_document(self, pmid: str, updates: dict[str, Any]) -> PubMedDocument | None:
        """Update an existing document."""
        logger.debug("Updating document", pmid=pmid, updates=list(updates.keys()))
        
        try:
            async with self.get_session() as session:
                document = await session.get(PubMedDocument, pmid)
                
                if not document:
                    logger.warning("Document not found for update", pmid=pmid)
                    return None
                
                # Apply updates
                for key, value in updates.items():
                    if hasattr(document, key):
                        setattr(document, key, value)
                
                # Update timestamp
                document.updated_at = datetime.now(UTC)
                
                await session.commit()
                await session.refresh(document)
                
                logger.info("Document updated successfully", pmid=pmid)
                return document
                
        except Exception as e:
            logger.error("Failed to update document", pmid=pmid, error=str(e))
            raise
    
    async def delete_document(self, pmid: str) -> bool:
        """Delete a document by PMID."""
        logger.debug("Deleting document", pmid=pmid)
        
        try:
            async with self.get_session() as session:
                document = await session.get(PubMedDocument, pmid)
                
                if not document:
                    logger.warning("Document not found for deletion", pmid=pmid)
                    return False
                
                await session.delete(document)
                await session.commit()
                
                logger.info("Document deleted successfully", pmid=pmid)
                return True
                
        except Exception as e:
            logger.error("Failed to delete document", pmid=pmid, error=str(e))
            raise
    
    async def list_documents(self, limit: int = 50, offset: int = 0) -> list[PubMedDocument]:
        """List documents with pagination."""
        logger.debug("Listing documents", limit=limit, offset=offset)
        
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    text("SELECT * FROM pubmed_documents ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
                    {"limit": limit, "offset": offset}
                )
                
                documents = []
                for row in result.fetchall():
                    doc = PubMedDocument(
                        pmid=row.pmid,
                        title=row.title,
                        abstract=row.abstract,
                        authors=row.authors or [],
                        publication_date=row.publication_date,
                        journal=row.journal,
                        doi=row.doi,
                        keywords=row.keywords or [],
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                    documents.append(doc)
                
                logger.debug("Documents retrieved", count=len(documents))
                return documents
                
        except Exception as e:
            logger.error("Failed to list documents", error=str(e))
            raise
    
    async def search_documents_by_title(self, search_term: str) -> list[PubMedDocument]:
        """Search documents by title."""
        logger.debug("Searching documents by title", search_term=search_term)
        
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    text("SELECT * FROM pubmed_documents WHERE title ILIKE :term ORDER BY created_at DESC"),
                    {"term": f"%{search_term}%"}
                )
                
                documents = []
                for row in result.fetchall():
                    doc = PubMedDocument(
                        pmid=row.pmid,
                        title=row.title,
                        abstract=row.abstract,
                        authors=row.authors or [],
                        publication_date=row.publication_date,
                        journal=row.journal,
                        doi=row.doi,
                        keywords=row.keywords or [],
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                    documents.append(doc)
                
                logger.info("Documents found by title search", search_term=search_term, count=len(documents))
                return documents
                
        except Exception as e:
            logger.error("Failed to search documents by title", search_term=search_term, error=str(e))
            raise
    
    async def bulk_create_documents(self, docs_data: list[dict[str, Any]]) -> list[PubMedDocument]:
        """Create multiple documents in bulk."""
        logger.debug("Bulk creating documents", count=len(docs_data))
        
        try:
            documents = []
            
            async with self.get_session() as session:
                for doc_data in docs_data:
                    document = PubMedDocument(**doc_data)
                    session.add(document)
                    documents.append(document)
                
                await session.commit()
                
                # Refresh all documents
                for document in documents:
                    await session.refresh(document)
                
                logger.info("Bulk document creation completed", count=len(documents))
                return documents
                
        except Exception as e:
            logger.error("Failed to bulk create documents", count=len(docs_data), error=str(e))
            raise
    
    async def document_exists(self, pmid: str) -> bool:
        """Check if a document exists."""
        logger.debug("Checking document existence", pmid=pmid)
        
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    text("SELECT 1 FROM pubmed_documents WHERE pmid = :pmid"),
                    {"pmid": pmid}
                )
                
                exists = result.scalar() is not None
                logger.debug("Document existence check completed", pmid=pmid, exists=exists)
                return exists
                
        except Exception as e:
            logger.error("Failed to check document existence", pmid=pmid, error=str(e))
            raise
    
    # Sync Watermark Methods for Incremental Sync
    
    async def get_sync_watermark(self, query_key: str) -> SyncWatermark | None:
        """Get sync watermark for a query key."""
        logger.debug("Getting sync watermark", query_key=query_key)
        
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    text("SELECT * FROM sync_watermarks WHERE query_key = :query_key"),
                    {"query_key": query_key}
                )
                
                row = result.fetchone()
                if row:
                    watermark = SyncWatermark(
                        query_key=row.query_key,
                        last_edat=row.last_edat,
                        total_synced=row.total_synced,
                        last_sync_count=row.last_sync_count,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                    logger.debug("Sync watermark found", query_key=query_key, last_edat=watermark.last_edat)
                    return watermark
                
                logger.debug("No sync watermark found", query_key=query_key)
                return None
                
        except Exception as e:
            logger.error("Failed to get sync watermark", query_key=query_key, error=str(e))
            raise
    
    async def create_or_update_sync_watermark(
        self,
        query_key: str,
        last_edat: str | None = None,
        total_synced: str | None = None,
        last_sync_count: str | None = None
    ) -> SyncWatermark:
        """Create or update sync watermark for a query key."""
        logger.debug("Creating/updating sync watermark", query_key=query_key, last_edat=last_edat)
        
        try:
            async with self.get_session() as session:
                # Check if watermark exists
                result = await session.execute(
                    text("SELECT * FROM sync_watermarks WHERE query_key = :query_key"),
                    {"query_key": query_key}
                )
                
                existing = result.fetchone()
                now = datetime.now(UTC)
                
                if existing:
                    # Update existing watermark
                    update_data = {"query_key": query_key, "updated_at": now}
                    if last_edat is not None:
                        update_data["last_edat"] = last_edat
                    if total_synced is not None:
                        update_data["total_synced"] = total_synced
                    if last_sync_count is not None:
                        update_data["last_sync_count"] = last_sync_count
                    
                    await session.execute(
                        text("""
                        UPDATE sync_watermarks 
                        SET last_edat = COALESCE(:last_edat, last_edat),
                            total_synced = COALESCE(:total_synced, total_synced),
                            last_sync_count = COALESCE(:last_sync_count, last_sync_count),
                            updated_at = :updated_at
                        WHERE query_key = :query_key
                        """),
                        update_data
                    )
                    
                    # Fetch updated record
                    result = await session.execute(
                        text("SELECT * FROM sync_watermarks WHERE query_key = :query_key"),
                        {"query_key": query_key}
                    )
                    row = result.fetchone()
                    
                    watermark = SyncWatermark(
                        query_key=row.query_key,
                        last_edat=row.last_edat,
                        total_synced=row.total_synced,
                        last_sync_count=row.last_sync_count,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                    
                    logger.info("Sync watermark updated", query_key=query_key, last_edat=watermark.last_edat)
                    
                else:
                    # Create new watermark
                    watermark = SyncWatermark(
                        query_key=query_key,
                        last_edat=last_edat,
                        total_synced=total_synced or "0",
                        last_sync_count=last_sync_count or "0",
                        created_at=now,
                        updated_at=now
                    )
                    
                    await session.execute(
                        text("""
                        INSERT INTO sync_watermarks (query_key, last_edat, total_synced, last_sync_count, created_at, updated_at)
                        VALUES (:query_key, :last_edat, :total_synced, :last_sync_count, :created_at, :updated_at)
                        """),
                        {
                            "query_key": watermark.query_key,
                            "last_edat": watermark.last_edat,
                            "total_synced": watermark.total_synced,
                            "last_sync_count": watermark.last_sync_count,
                            "created_at": watermark.created_at,
                            "updated_at": watermark.updated_at
                        }
                    )
                    
                    logger.info("Sync watermark created", query_key=query_key, last_edat=watermark.last_edat)
                
                await session.commit()
                return watermark
                
        except Exception as e:
            logger.error("Failed to create/update sync watermark", query_key=query_key, error=str(e))
            raise
    
    # Corpus Checkpoint Methods for Research Reproducibility
    
    async def create_corpus_checkpoint(
        self,
        checkpoint_id: str,
        name: str,
        description: str | None = None,
        primary_queries: list[str] | None = None,
        parent_checkpoint_id: str | None = None
    ) -> CorpusCheckpoint:
        """Create a new corpus checkpoint capturing current corpus state."""
        logger.info("Creating corpus checkpoint", checkpoint_id=checkpoint_id, name=name)
        
        try:
            async with self.get_session() as session:
                # Check if checkpoint already exists
                result = await session.execute(
                    text("SELECT checkpoint_id FROM corpus_checkpoints WHERE checkpoint_id = :checkpoint_id"),
                    {"checkpoint_id": checkpoint_id}
                )
                
                if result.fetchone():
                    raise ValidationError(f"Checkpoint '{checkpoint_id}' already exists")
                
                # Get current corpus statistics
                doc_count_result = await session.execute(
                    text("SELECT COUNT(*) as count FROM pubmed_documents")
                )
                doc_count = str(doc_count_result.scalar() or 0)
                
                # Get all current sync watermarks
                watermarks_result = await session.execute(
                    text("SELECT query_key, last_edat, total_synced FROM sync_watermarks")
                )
                sync_watermarks = {
                    row.query_key: {
                        "last_edat": row.last_edat,
                        "total_synced": row.total_synced
                    }
                    for row in watermarks_result.fetchall()
                }
                
                # Get latest EDAT from watermarks
                latest_edat = None
                if sync_watermarks:
                    edats = [w["last_edat"] for w in sync_watermarks.values() if w["last_edat"]]
                    if edats:
                        latest_edat = max(edats)
                
                # Create checkpoint
                checkpoint = CorpusCheckpoint(
                    checkpoint_id=checkpoint_id,
                    name=name,
                    description=description,
                    document_count=doc_count,
                    last_sync_edat=latest_edat,
                    primary_queries=primary_queries or [],
                    sync_watermarks=sync_watermarks,
                    total_documents=doc_count,
                    total_vectors=doc_count,  # Assume 1:1 mapping for now
                    parent_checkpoint_id=parent_checkpoint_id
                )
                
                await session.execute(
                    text("""
                    INSERT INTO corpus_checkpoints (
                        checkpoint_id, name, description, document_count, last_sync_edat,
                        primary_queries, sync_watermarks, total_documents, total_vectors,
                        version, parent_checkpoint_id, created_at, updated_at
                    ) VALUES (
                        :checkpoint_id, :name, :description, :document_count, :last_sync_edat,
                        :primary_queries, :sync_watermarks, :total_documents, :total_vectors,
                        :version, :parent_checkpoint_id, :created_at, :updated_at
                    )
                    """),
                    {
                        "checkpoint_id": checkpoint.checkpoint_id,
                        "name": checkpoint.name,
                        "description": checkpoint.description,
                        "document_count": checkpoint.document_count,
                        "last_sync_edat": checkpoint.last_sync_edat,
                        "primary_queries": checkpoint.primary_queries,
                        "sync_watermarks": checkpoint.sync_watermarks,
                        "total_documents": checkpoint.total_documents,
                        "total_vectors": checkpoint.total_vectors,
                        "version": checkpoint.version,
                        "parent_checkpoint_id": checkpoint.parent_checkpoint_id,
                        "created_at": checkpoint.created_at,
                        "updated_at": checkpoint.updated_at
                    }
                )
                
                await session.commit()
                
                logger.info("Corpus checkpoint created successfully", 
                           checkpoint_id=checkpoint_id, doc_count=doc_count)
                return checkpoint
                
        except Exception as e:
            logger.error("Failed to create corpus checkpoint", checkpoint_id=checkpoint_id, error=str(e))
            raise
    
    async def get_corpus_checkpoint(self, checkpoint_id: str) -> CorpusCheckpoint | None:
        """Get corpus checkpoint by ID."""
        logger.debug("Getting corpus checkpoint", checkpoint_id=checkpoint_id)
        
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    text("SELECT * FROM corpus_checkpoints WHERE checkpoint_id = :checkpoint_id"),
                    {"checkpoint_id": checkpoint_id}
                )
                
                row = result.fetchone()
                if row:
                    checkpoint = CorpusCheckpoint(
                        checkpoint_id=row.checkpoint_id,
                        name=row.name,
                        description=row.description,
                        document_count=row.document_count,
                        last_sync_edat=row.last_sync_edat,
                        primary_queries=row.primary_queries,
                        sync_watermarks=row.sync_watermarks,
                        total_documents=row.total_documents,
                        total_vectors=row.total_vectors,
                        version=row.version,
                        parent_checkpoint_id=row.parent_checkpoint_id,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                    logger.debug("Corpus checkpoint found", checkpoint_id=checkpoint_id)
                    return checkpoint
                
                logger.debug("Corpus checkpoint not found", checkpoint_id=checkpoint_id)
                return None
                
        except Exception as e:
            logger.error("Failed to get corpus checkpoint", checkpoint_id=checkpoint_id, error=str(e))
            raise
    
    async def list_corpus_checkpoints(self, limit: int = 50, offset: int = 0) -> list[CorpusCheckpoint]:
        """List all corpus checkpoints with pagination."""
        logger.debug("Listing corpus checkpoints", limit=limit, offset=offset)
        
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    text("""
                    SELECT * FROM corpus_checkpoints 
                    ORDER BY created_at DESC 
                    LIMIT :limit OFFSET :offset
                    """),
                    {"limit": limit, "offset": offset}
                )
                
                checkpoints = []
                for row in result.fetchall():
                    checkpoint = CorpusCheckpoint(
                        checkpoint_id=row.checkpoint_id,
                        name=row.name,
                        description=row.description,
                        document_count=row.document_count,
                        last_sync_edat=row.last_sync_edat,
                        primary_queries=row.primary_queries,
                        sync_watermarks=row.sync_watermarks,
                        total_documents=row.total_documents,
                        total_vectors=row.total_vectors,
                        version=row.version,
                        parent_checkpoint_id=row.parent_checkpoint_id,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                    checkpoints.append(checkpoint)
                
                logger.debug("Listed corpus checkpoints", count=len(checkpoints))
                return checkpoints
                
        except Exception as e:
            logger.error("Failed to list corpus checkpoints", error=str(e))
            raise
    
    async def delete_corpus_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a corpus checkpoint."""
        logger.info("Deleting corpus checkpoint", checkpoint_id=checkpoint_id)
        
        try:
            async with self.get_session() as session:
                result = await session.execute(
                    text("DELETE FROM corpus_checkpoints WHERE checkpoint_id = :checkpoint_id"),
                    {"checkpoint_id": checkpoint_id}
                )
                
                await session.commit()
                
                deleted = result.rowcount > 0
                if deleted:
                    logger.info("Corpus checkpoint deleted", checkpoint_id=checkpoint_id)
                else:
                    logger.warning("Corpus checkpoint not found for deletion", checkpoint_id=checkpoint_id)
                
                return deleted
                
        except Exception as e:
            logger.error("Failed to delete corpus checkpoint", checkpoint_id=checkpoint_id, error=str(e))
            raise


class DatabaseHealthCheck:
    """Health check functionality for database operations."""
    
    def __init__(self, manager: DatabaseManager):
        self.manager = manager
    
    async def check_health(self) -> dict[str, Any]:
        """Perform comprehensive database health check."""
        logger.debug("Starting database health check")
        
        health_result = {
            "status": "healthy",
            "checks": {}
        }
        
        # Test database connection
        try:
            start_time = time.time()
            
            async with self.manager.get_session() as session:
                await session.execute(text("SELECT 1"))
            
            response_time = (time.time() - start_time) * 1000
            
            health_result["checks"]["database_connection"] = {
                "status": "healthy",
                "message": "Database connection successful",
                "response_time_ms": response_time
            }
            
        except Exception as e:
            health_result["status"] = "unhealthy"
            health_result["checks"]["database_connection"] = {
                "status": "unhealthy",
                "message": "Database connection failed",
                "error": str(e)
            }
        
        # Test table accessibility
        try:
            async with self.manager.get_session() as session:
                await session.execute(text("SELECT COUNT(*) FROM pubmed_documents"))
            
            health_result["checks"]["table_accessibility"] = {
                "status": "healthy",
                "message": "Database tables accessible"
            }
            
        except Exception as e:
            health_result["status"] = "unhealthy"
            health_result["checks"]["table_accessibility"] = {
                "status": "unhealthy",
                "message": "Database tables not accessible",
                "error": str(e)
            }
        
        logger.info("Database health check completed", status=health_result["status"])
        return health_result


# Convenience functions
def create_database_engine(config: DatabaseConfig) -> AsyncEngine:
    """Create an async database engine."""
    engine_kwargs = {
        "echo": config.echo,
        "future": True
    }
    
    # Only add pool parameters for non-SQLite databases
    if config.url and not config.url.startswith('sqlite'):
        engine_kwargs.update({
            "pool_size": config.pool_size,
            "max_overflow": config.max_overflow,
            "pool_timeout": config.pool_timeout,
        })
    
    return create_async_engine(config.url, **engine_kwargs)


async def init_database(config: DatabaseConfig) -> DatabaseManager:
    """Initialize database with configuration."""
    manager = DatabaseManager(config)
    await manager.initialize()
    return manager


async def get_database_session(manager: DatabaseManager) -> AsyncSession:
    """Get a database session from manager."""
    return manager.get_session()


# Global database manager instance
_database_manager: DatabaseManager | None = None


def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _database_manager
    if _database_manager is None:
        from bio_mcp.config.config import config
        db_config = DatabaseConfig.from_url(config.database_url)
        _database_manager = DatabaseManager(db_config)
    return _database_manager