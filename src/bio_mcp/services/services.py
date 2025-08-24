"""
Service classes for Bio-MCP server.
Focused service classes that follow Single Responsibility Principle.
"""
# type: ignore  # Legacy code with complex typing issues

from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.models.document import Document
from bio_mcp.services.document_chunk_service import DocumentChunkService
from bio_mcp.shared.clients.database import DatabaseConfig, DatabaseManager
from bio_mcp.sources.pubmed.client import PubMedClient
from bio_mcp.sources.pubmed.config import PubMedConfig

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

        if self.client is None:
            raise ValueError("PubMed client not initialized")
        return await self.client.search(query, limit=limit, offset=offset)

    async def search_incremental(
        self,
        query: str,
        last_edat: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        """Search PubMed incrementally using EDAT watermark."""
        if not self._initialized:
            await self.initialize()

        if self.client is None:
            raise ValueError("PubMed client not initialized")
        return await self.client.search_incremental(
            query, last_edat=last_edat, limit=limit, offset=offset
        )

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
    """
    Service for vector store operations using the Document/Chunk model.
    """

    def __init__(self, use_v2: bool = True):
        """Initialize VectorService with chunk-based approach."""
        self.use_v2 = use_v2
        self.document_chunk_service: DocumentChunkService | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize vector service."""
        if self._initialized:
            return

        logger.info("Initializing vector service", use_v2=self.use_v2)
        
        if self.use_v2:
            self.document_chunk_service = DocumentChunkService()
            await self.document_chunk_service.connect()
        else:
            raise ValueError("Legacy embedding service (use_v2=False) is no longer supported")
            
        self._initialized = True
        logger.info("Vector service initialized successfully", use_v2=self.use_v2)

    async def close(self) -> None:
        """Close vector store connections."""
        if self.document_chunk_service:
            await self.document_chunk_service.disconnect()
            self.document_chunk_service = None
        self._initialized = False
        logger.info("Vector service closed")

    async def store_document_chunks(self, document: Document, quality_score: float | None = None) -> list[str]:
        """
        Store document as chunks in vector store.

        Args:
            document: Document to chunk and store
            quality_score: Optional quality score for V2 service

        Returns:
            List of Weaviate UUIDs for stored chunks
        """
        if not self._initialized:
            await self.initialize()

        if not self.document_chunk_service:
            raise ValueError("Document chunk service not initialized")
        return await self.document_chunk_service.store_document_chunks(document, quality_score)

    async def search_chunks(
        self,
        query: str,
        limit: int = 5,
        search_mode: str = "semantic",
        alpha: float = 0.5,
        filters: dict | None = None,
        source_filter: str | None = None,
        year_filter: tuple[int, int] | None = None,
        section_filter: list[str] | None = None,
        quality_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search chunks using different search modes.

        Args:
            query: Search query text
            limit: Maximum number of chunks to return
            search_mode: 'semantic', 'bm25', or 'hybrid'
            alpha: Hybrid search balance (0.0=BM25, 1.0=vector)
            filters: Generic filters dict for flexible filtering
            source_filter: Filter by source (convenience parameter)
            year_filter: Filter by year range (convenience parameter)
            section_filter: Filter by sections (convenience parameter)
            quality_threshold: Filter by quality threshold (convenience parameter)

        Returns:
            List of matching chunk results with metadata
        """
        if not self._initialized:
            await self.initialize()

        if not self.document_chunk_service:
            raise ValueError("Document chunk service not initialized")
        return await self.document_chunk_service.search_chunks(
            query=query,
            limit=limit,
            search_mode=search_mode,
            alpha=alpha,
            filters=filters,
            source_filter=source_filter,
            year_filter=year_filter,
            section_filter=section_filter,
            quality_threshold=quality_threshold,
        )

    async def store_document(
        self,
        pmid: str,
        title: str,
        abstract: str | None = None,
        authors: list[str] | None = None,
        journal: str | None = None,
        publication_date: str | None = None,
        doi: str | None = None,
        keywords: list[str] | None = None,
    ) -> list[str]:
        """
        Store document in vector store as chunks.

        This method provides backward compatibility by converting legacy parameters
        to the Document model internally.

        Returns:
            List of chunk UUIDs
        """
        if not self._initialized:
            await self.initialize()

        if not self.document_chunk_service:
            raise ValueError("Document chunk service not initialized")

        # Convert legacy parameters to Document model using the normalizer
        from bio_mcp.services.normalization.pubmed import PubMedNormalizer

        raw_data = {
            "pmid": pmid,
            "title": title,
            "abstract": abstract or "",
            "authors": authors or [],
            "journal": journal,
            "publication_date": publication_date,
            "doi": doi,
            "keywords": keywords or [],
        }

        document = PubMedNormalizer.from_raw_dict(
            raw_data,
            s3_raw_uri=f"s3://bio-mcp-temp/pubmed/{pmid}.json",  # Placeholder S3 URI
            content_hash=f"temp_{pmid}",  # Placeholder hash
        )

        chunk_uuids = await self.document_chunk_service.store_document_chunks(document)
        logger.info(
            "Stored document as chunks", pmid=pmid, chunk_count=len(chunk_uuids)
        )
        return chunk_uuids

    async def search_documents(
        self,
        query: str,
        limit: int = 5,
        search_mode: str = "semantic",
        alpha: float = 0.5,
        filters: dict | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search documents/chunks using the chunk-based approach.

        Returns results in a unified format.
        """
        if not self._initialized:
            await self.initialize()

        if not self.document_chunk_service:
            raise ValueError("Document chunk service not initialized")

        return await self.document_chunk_service.search_chunks(
            query=query,
            limit=limit
        )


class SyncOrchestrator:
    """Orchestrates sync operations across PubMed, database, and vector store services."""

    def __init__(
        self,
        pubmed_service: PubMedService | None = None,
        document_service: DocumentService | None = None,
        vector_service: VectorService | None = None,
    ):
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
                "pmids_failed": [],
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
                            publication_date=doc.publication_date.isoformat()
                            if doc.publication_date
                            else None,
                            doi=doc.doi,
                            keywords=doc.keywords or [],
                        )

                        synced_pmids.append(doc.pmid)
                        logger.debug("Document successfully synced", pmid=doc.pmid)

                    except Exception as e:
                        # Check if this is an "already exists" error (integrity constraint)
                        error_str = str(e).lower()
                        if any(
                            keyword in error_str
                            for keyword in [
                                "integrity",
                                "duplicate",
                                "unique",
                                "already exists",
                            ]
                        ):
                            # Document already exists - check if it's actually in the database
                            try:
                                exists = await self.document_service.document_exists(
                                    doc.pmid
                                )
                                if exists:
                                    # Document exists, treat as "already existed" rather than failure
                                    existing_pmids.append(doc.pmid)
                                    logger.debug(
                                        "Document already exists, skipping",
                                        pmid=doc.pmid,
                                    )
                                    continue
                                else:
                                    # Integrity error but document doesn't exist - this is a real problem
                                    logger.error(
                                        "Integrity error but document not found",
                                        pmid=doc.pmid,
                                        error=str(e),
                                    )
                                    failed_pmids.append(doc.pmid)
                            except Exception as check_error:
                                # Error checking existence - treat as failure
                                logger.error(
                                    "Failed to check document existence after integrity error",
                                    pmid=doc.pmid,
                                    error=str(check_error),
                                )
                                failed_pmids.append(doc.pmid)
                        else:
                            # Real failure (network, validation, etc.)
                            logger.error(
                                "Failed to store document", pmid=doc.pmid, error=str(e)
                            )
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
            "pmids_failed": failed_pmids,
        }

        logger.info(
            "Orchestrated sync completed",
            **{
                k: v
                for k, v in result.items()
                if k not in ["pmids_synced", "pmids_failed"]
            },
        )
        return result

    async def sync_documents_incremental(self, query: str, limit: int = 100):
        """
        Orchestrate incremental document sync using EDAT watermarks:
        1. Get last sync watermark for this query
        2. Search PubMed for documents newer than watermark
        3. Check database for existing documents
        4. Fetch missing documents from PubMed
        5. Store in database and vector store
        6. Update sync watermark
        """
        if not self._initialized:
            await self.initialize()

        # Generate a stable query key for watermark tracking
        import hashlib

        query_key = hashlib.md5(query.encode()).hexdigest()[:16]

        logger.info(
            "Starting incremental sync", query=query, query_key=query_key, limit=limit
        )

        # Step 1: Get sync watermark to determine incremental starting point
        try:
            watermark = await self.document_service.manager.get_sync_watermark(
                query_key
            )
            last_edat = watermark.last_edat if watermark else None
            logger.info(
                "Retrieved sync watermark", query_key=query_key, last_edat=last_edat
            )
        except Exception as e:
            logger.warning(
                "Failed to get sync watermark, using full sync",
                query_key=query_key,
                error=str(e),
            )
            last_edat = None

        # Step 2: Search PubMed incrementally
        try:
            search_result = await self.pubmed_service.client.search_incremental(
                query=query, last_edat=last_edat, limit=limit
            )
            pmids = search_result.pmids
        except Exception as e:
            logger.error(
                "Incremental search failed, falling back to regular search",
                error=str(e),
            )
            search_result = await self.pubmed_service.search(query, limit=limit)
            pmids = search_result.pmids

        if not pmids:
            logger.info(
                "No new PMIDs found for incremental sync",
                query=query,
                last_edat=last_edat,
            )
            # Still update watermark to mark this sync attempt
            if last_edat:
                from datetime import datetime

                current_edat = datetime.now().strftime("%Y/%m/%d")
                try:
                    await self.document_service.manager.create_or_update_sync_watermark(
                        query_key=query_key, last_edat=current_edat, last_sync_count="0"
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to update watermark after empty sync", error=str(e)
                    )

            return {
                "total_requested": 0,
                "successfully_synced": 0,
                "already_existed": 0,
                "failed": 0,
                "pmids_synced": [],
                "pmids_failed": [],
                "incremental": True,
                "last_edat": last_edat,
                "query_key": query_key,
            }

        # Step 3: Check which documents already exist
        existing_pmids = []
        new_pmids = []

        for pmid in pmids:
            exists = await self.document_service.document_exists(pmid)
            if exists:
                existing_pmids.append(pmid)
            else:
                new_pmids.append(pmid)

        logger.info(
            "Document existence check completed",
            total_pmids=len(pmids),
            existing=len(existing_pmids),
            new=len(new_pmids),
        )

        # Step 4: Fetch and store new documents
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

                        # Store in vector store if available
                        if self.vector_service:
                            await self.vector_service.store_document(
                                pmid=doc.pmid,
                                title=doc.title,
                                abstract=doc.abstract or "",
                                authors=doc.authors or [],
                                journal=doc.journal,
                                publication_date=doc.publication_date.isoformat()
                                if doc.publication_date
                                else None,
                                doi=doc.doi,
                                keywords=doc.keywords or [],
                            )

                        synced_pmids.append(doc.pmid)
                        logger.debug("Document successfully synced", pmid=doc.pmid)

                    except Exception as e:
                        logger.error(
                            "Failed to store document", pmid=doc.pmid, error=str(e)
                        )
                        failed_pmids.append(doc.pmid)

            except Exception as e:
                logger.error("Failed to fetch documents from PubMed", error=str(e))
                failed_pmids.extend(new_pmids)

        # Step 5: Update sync watermark with current date
        from datetime import datetime

        current_edat = datetime.now().strftime("%Y/%m/%d")
        total_synced_now = len(synced_pmids)

        try:
            # Get current total count
            if watermark:
                previous_total = int(watermark.total_synced)
                new_total = str(previous_total + total_synced_now)
            else:
                new_total = str(total_synced_now)

            await self.document_service.manager.create_or_update_sync_watermark(
                query_key=query_key,
                last_edat=current_edat,
                total_synced=new_total,
                last_sync_count=str(total_synced_now),
            )
            logger.info(
                "Sync watermark updated",
                query_key=query_key,
                last_edat=current_edat,
                total_synced=new_total,
            )
        except Exception as e:
            logger.warning(
                "Failed to update sync watermark", query_key=query_key, error=str(e)
            )

        result = {
            "total_requested": len(pmids),
            "successfully_synced": len(synced_pmids),
            "already_existed": len(existing_pmids),
            "failed": len(failed_pmids),
            "pmids_synced": synced_pmids,
            "pmids_failed": failed_pmids,
            "incremental": True,
            "last_edat": last_edat,
            "new_edat": current_edat,
            "query_key": query_key,
        }

        logger.info(
            "Incremental sync completed",
            **{
                k: v
                for k, v in result.items()
                if k not in ["pmids_synced", "pmids_failed"]
            },
        )
        return result


class CorpusCheckpointService:
    """Service for corpus checkpoint management and research reproducibility."""

    def __init__(self, config: DatabaseConfig | None = None):
        self.config = config or DatabaseConfig.from_env()
        self.manager: DatabaseManager | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database manager."""
        if self._initialized:
            return

        logger.info("Initializing corpus checkpoint service")
        self.manager = DatabaseManager(self.config)
        await self.manager.initialize()
        self._initialized = True
        logger.info("Corpus checkpoint service initialized successfully")

    async def close(self) -> None:
        """Close database connections."""
        if self.manager:
            await self.manager.close()
            self.manager = None
        self._initialized = False
        logger.info("Corpus checkpoint service closed")

    async def create_checkpoint(
        self,
        checkpoint_id: str,
        name: str,
        description: str | None = None,
        primary_queries: list[str] | None = None,
        parent_checkpoint_id: str | None = None,
    ):
        """Create a new corpus checkpoint."""
        if not self._initialized:
            await self.initialize()

        return await self.manager.create_corpus_checkpoint(
            checkpoint_id=checkpoint_id,
            name=name,
            description=description,
            primary_queries=primary_queries,
            parent_checkpoint_id=parent_checkpoint_id,
        )

    async def get_checkpoint(self, checkpoint_id: str):
        """Get corpus checkpoint by ID."""
        if not self._initialized:
            await self.initialize()

        return await self.manager.get_corpus_checkpoint(checkpoint_id)

    async def list_checkpoints(self, limit: int = 50, offset: int = 0):
        """List all corpus checkpoints."""
        if not self._initialized:
            await self.initialize()

        return await self.manager.list_corpus_checkpoints(limit=limit, offset=offset)

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a corpus checkpoint."""
        if not self._initialized:
            await self.initialize()

        return await self.manager.delete_corpus_checkpoint(checkpoint_id)

    async def get_checkpoint_lineage(self, checkpoint_id: str) -> list:
        """Get the lineage (parent chain) of a checkpoint."""
        if not self._initialized:
            await self.initialize()

        lineage = []
        current_id = checkpoint_id

        while current_id:
            checkpoint = await self.manager.get_corpus_checkpoint(current_id)
            if not checkpoint:
                break

            lineage.append(
                {
                    "checkpoint_id": checkpoint.checkpoint_id,
                    "name": checkpoint.name,
                    "created_at": checkpoint.created_at.isoformat(),
                    "total_documents": checkpoint.total_documents,
                    "version": checkpoint.version,
                }
            )

            current_id = checkpoint.parent_checkpoint_id

            # Prevent infinite loops
            if len(lineage) > 50:
                logger.warning(
                    "Checkpoint lineage too deep, truncating",
                    checkpoint_id=checkpoint_id,
                )
                break

        return lineage
