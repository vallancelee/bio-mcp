"""
Service classes for Bio-MCP server.
Focused service classes that follow Single Responsibility Principle.
"""

from typing import Any

from ..clients.database import DatabaseConfig, DatabaseManager
from ..config.logging_config import get_logger
from ..clients.pubmed_client import PubMedClient, PubMedConfig
from ..clients.weaviate_client import WeaviateClient, get_weaviate_client

logger = get_logger(__name__)


class PubMedService:
    """Service for PubMed API operations only."""
    
    def __init__(self, config: PubMedConfig | None = None):
        self.config = config or PubMedConfig.from_env()
        self.client: PubMedClient | None = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize PubMed client."""
        if self._initialized:
            return
        
        logger.info("Initializing PubMed service")
        self.client = PubMedClient(self.config)
        self._initialized = True
        logger.info("PubMed service initialized successfully")
    
    async def close(self) -> None:
        """Close PubMed client connections."""
        if self.client:
            await self.client.close()
            self.client = None
        self._initialized = False
        logger.info("PubMed service closed")
    
    async def search(self, query: str, limit: int = 10, offset: int = 0):
        """Search PubMed for documents."""
        if not self._initialized:
            await self.initialize()
        
        return await self.client.search(query, limit=limit, offset=offset)
    
    async def fetch_documents(self, pmids: list[str]):
        """Fetch documents by PMIDs."""
        if not self._initialized:
            await self.initialize()
        
        return await self.client.fetch_documents(pmids)


class DocumentService:
    """Service for database document operations only."""
    
    def __init__(self, config: DatabaseConfig | None = None):
        self.config = config or DatabaseConfig.from_env()
        self.manager: DatabaseManager | None = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database manager."""
        if self._initialized:
            return
        
        logger.info("Initializing document service")
        self.manager = DatabaseManager(self.config)
        await self.manager.initialize()
        self._initialized = True
        logger.info("Document service initialized successfully")
    
    async def close(self) -> None:
        """Close database connections."""
        if self.manager:
            await self.manager.close()
            self.manager = None
        self._initialized = False
        logger.info("Document service closed")
    
    async def get_document_by_pmid(self, pmid: str):
        """Get document by PMID from database."""
        if not self._initialized:
            await self.initialize()
        
        return await self.manager.get_document_by_pmid(pmid)
    
    async def document_exists(self, pmid: str) -> bool:
        """Check if document exists in database."""
        if not self._initialized:
            await self.initialize()
        
        return await self.manager.document_exists(pmid)
    
    async def create_document(self, document_data: dict[str, Any]) -> None:
        """Create document in database."""
        if not self._initialized:
            await self.initialize()
        
        return await self.manager.create_document(document_data)


class VectorService:
    """Service for vector store operations only."""
    
    def __init__(self):
        self.client: WeaviateClient | None = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize Weaviate client."""
        if self._initialized:
            return
        
        logger.info("Initializing vector service")
        self.client = get_weaviate_client()
        await self.client.initialize()
        self._initialized = True
        logger.info("Vector service initialized successfully")
    
    async def close(self) -> None:
        """Close vector store connections."""
        if self.client:
            await self.client.close()
            self.client = None
        self._initialized = False
        logger.info("Vector service closed")
    
    async def store_document(self, pmid: str, title: str, abstract: str | None = None,
                           authors: list[str] | None = None, journal: str | None = None,
                           publication_date: str | None = None, doi: str | None = None,
                           keywords: list[str] | None = None) -> str:
        """Store document in vector store."""
        if not self._initialized:
            await self.initialize()
        
        return await self.client.store_document(
            pmid=pmid, title=title, abstract=abstract, authors=authors,
            journal=journal, publication_date=publication_date,
            doi=doi, keywords=keywords
        )


class SyncOrchestrator:
    """Orchestrates sync operations across PubMed, database, and vector store services."""
    
    def __init__(self, pubmed_service: PubMedService | None = None,
                 document_service: DocumentService | None = None,
                 vector_service: VectorService | None = None):
        self.pubmed_service = pubmed_service or PubMedService()
        self.document_service = document_service or DocumentService()
        self.vector_service = vector_service or VectorService()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all services."""
        if self._initialized:
            return
        
        logger.info("Initializing sync orchestrator")
        await self.pubmed_service.initialize()
        await self.document_service.initialize()
        await self.vector_service.initialize()
        self._initialized = True
        logger.info("Sync orchestrator initialized successfully")
    
    async def close(self) -> None:
        """Close all service connections."""
        if self.pubmed_service:
            await self.pubmed_service.close()
        if self.document_service:
            await self.document_service.close()
        if self.vector_service:
            await self.vector_service.close()
        self._initialized = False
        logger.info("Sync orchestrator closed")
    
    async def sync_documents(self, query: str, limit: int = 10):
        """
        Orchestrate complete document sync process:
        1. Search PubMed
        2. Check database for existing documents
        3. Fetch missing documents from PubMed
        4. Store in database and vector store
        """
        if not self._initialized:
            await self.initialize()
        
        logger.info("Starting orchestrated sync", query=query, limit=limit)
        
        # Step 1: Search PubMed for document IDs
        search_result = await self.pubmed_service.search(query, limit=limit)
        pmids = search_result.pmids
        
        if not pmids:
            logger.info("No PMIDs found for query", query=query)
            return {
                "total_requested": 0,
                "successfully_synced": 0,
                "already_existed": 0,
                "failed": 0,
                "pmids_synced": [],
                "pmids_failed": []
            }
        
        # Step 2: Check which documents already exist
        existing_pmids = []
        new_pmids = []
        
        for pmid in pmids:
            exists = await self.document_service.document_exists(pmid)
            if exists:
                existing_pmids.append(pmid)
            else:
                new_pmids.append(pmid)
        
        # Step 3: Fetch and store new documents
        synced_pmids = []
        failed_pmids = []
        
        if new_pmids:
            try:
                documents = await self.pubmed_service.fetch_documents(new_pmids)
                
                for doc in documents:
                    try:
                        # Store in database
                        db_data = doc.to_database_format()
                        await self.document_service.create_document(db_data)
                        
                        # Store in vector store
                        await self.vector_service.store_document(
                            pmid=doc.pmid,
                            title=doc.title,
                            abstract=doc.abstract or "",
                            authors=doc.authors or [],
                            journal=doc.journal,
                            publication_date=doc.publication_date.isoformat() if doc.publication_date else None,
                            doi=doc.doi,
                            keywords=doc.keywords or []
                        )
                        
                        synced_pmids.append(doc.pmid)
                        logger.debug("Document successfully synced", pmid=doc.pmid)
                    
                    except Exception as e:
                        logger.error("Failed to store document", pmid=doc.pmid, error=str(e))
                        failed_pmids.append(doc.pmid)
            
            except Exception as e:
                logger.error("Failed to fetch documents from PubMed", error=str(e))
                failed_pmids.extend(new_pmids)
        
        result = {
            "total_requested": len(pmids),
            "successfully_synced": len(synced_pmids),
            "already_existed": len(existing_pmids),
            "failed": len(failed_pmids),
            "pmids_synced": synced_pmids,
            "pmids_failed": failed_pmids
        }
        
        logger.info("Orchestrated sync completed", **{k: v for k, v in result.items() if k not in ["pmids_synced", "pmids_failed"]})
        return result