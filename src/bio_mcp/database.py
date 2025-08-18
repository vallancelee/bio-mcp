"""
Database layer for Bio-MCP server.
Phase 2A: Basic Database with SQLAlchemy models for PubMed documents.
"""

import asyncio
import time
from datetime import datetime, date, timezone
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass
import os

from sqlalchemy import (
    Column, String, Text, JSON, Date, DateTime, Integer, 
    create_engine, text, inspect
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .error_handling import ValidationError
from .logging_config import get_logger

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
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
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
        now = datetime.now(timezone.utc)
        self.created_at = kwargs.get('created_at', now)
        self.updated_at = kwargs.get('updated_at', now)
    
    def __repr__(self):
        return f"<PubMedDocument(pmid='{self.pmid}', title='{self.title[:50]}...')>"


@dataclass
class DatabaseConfig:
    """Configuration for database connections."""
    
    url: Optional[str] = None
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


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
    
    async def initialize(self) -> None:
        """Initialize database engine and create tables."""
        if not self.config.url:
            raise ValidationError("Database URL is required")
        
        logger.info("Initializing database connection", url=self.config.url.split('@')[0] + '@***')
        
        try:
            # Create async engine with asyncpg driver
            self.engine = create_async_engine(
                self.config.url,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                echo=self.config.echo,
                future=True
            )
            
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
    
    async def create_document(self, doc_data: Dict[str, Any]) -> PubMedDocument:
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
    
    async def get_document_by_pmid(self, pmid: str) -> Optional[PubMedDocument]:
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
    
    async def update_document(self, pmid: str, updates: Dict[str, Any]) -> Optional[PubMedDocument]:
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
                document.updated_at = datetime.now(timezone.utc)
                
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
    
    async def list_documents(self, limit: int = 50, offset: int = 0) -> List[PubMedDocument]:
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
    
    async def search_documents_by_title(self, search_term: str) -> List[PubMedDocument]:
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
    
    async def bulk_create_documents(self, docs_data: List[Dict[str, Any]]) -> List[PubMedDocument]:
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


class DatabaseHealthCheck:
    """Health check functionality for database operations."""
    
    def __init__(self, manager: DatabaseManager):
        self.manager = manager
    
    async def check_health(self) -> Dict[str, Any]:
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
    return create_async_engine(
        config.url,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_timeout=config.pool_timeout,
        echo=config.echo,
        future=True
    )


async def init_database(config: DatabaseConfig) -> DatabaseManager:
    """Initialize database with configuration."""
    manager = DatabaseManager(config)
    await manager.initialize()
    return manager


async def get_database_session(manager: DatabaseManager) -> AsyncSession:
    """Get a database session from manager."""
    return manager.get_session()