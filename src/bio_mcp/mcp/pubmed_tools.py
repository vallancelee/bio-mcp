"""
PubMed MCP tools for Bio-MCP server.
Phase 3A: Basic Biomedical Tools - MCP tool implementations.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from mcp.types import TextContent

from ..config.logging_config import get_logger
from ..config.search_config import RESPONSE_CONFIG
from ..services.services import DocumentService, PubMedService, SyncOrchestrator

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Result of a PubMed search operation."""

    query: str
    total_count: int
    returned_count: int
    pmids: list[str]
    execution_time_ms: float

    def to_mcp_response(self) -> str:
        """Convert to MCP response format."""
        max_display = RESPONSE_CONFIG.MAX_PMIDS_DISPLAY
        pmids_display = ", ".join(self.pmids[:max_display])
        if len(self.pmids) > max_display:
            pmids_display += RESPONSE_CONFIG.PMIDS_TRUNCATION_SUFFIX.format(total=len(self.pmids))

        return f"""Search completed for query: "{self.query}"

Results:
- Total found: {self.total_count:,}
- Returned: {self.returned_count}
- PMIDs: {pmids_display}

Execution time: {self.execution_time_ms:.1f}ms"""


@dataclass
class DocumentResult:
    """Result of a document retrieval operation."""

    pmid: str
    found: bool
    execution_time_ms: float
    title: str | None = None
    abstract: str | None = None
    authors: list[str] | None = None
    journal: str | None = None
    publication_date: date | None = None
    doi: str | None = None

    def to_mcp_response(self) -> str:
        """Convert to MCP response format."""
        if not self.found:
            return f"""Document not found: PMID {self.pmid}

The requested document could not be found in the database or PubMed.

Execution time: {self.execution_time_ms:.1f}ms"""

        authors_str = ", ".join(self.authors) if self.authors else "Not available"
        pub_date_str = (
            self.publication_date.strftime("%Y-%m-%d")
            if self.publication_date
            else "Not available"
        )
        doi_str = self.doi if self.doi else "Not available"
        abstract_str = self.abstract if self.abstract else "No abstract available"

        return f"""Document retrieved: PMID {self.pmid}

Title: {self.title}

Authors: {authors_str}

Journal: {self.journal or "Not available"}

Publication Date: {pub_date_str}

DOI: {doi_str}

Abstract:
{abstract_str}

Execution time: {self.execution_time_ms:.1f}ms"""


@dataclass
class SyncResult:
    """Result of a sync operation."""

    query: str
    total_requested: int
    successfully_synced: int
    already_existed: int
    failed: int
    pmids_synced: list[str]
    pmids_failed: list[str]
    execution_time_ms: float

    def to_mcp_response(self) -> str:
        """Convert to MCP response format."""
        success_rate = (
            (self.successfully_synced / self.total_requested * 100)
            if self.total_requested > 0
            else 0
        )

        result = f"""Sync completed for query: "{self.query}"

Summary:
- Total requested: {self.total_requested}
- Successfully synced: {self.successfully_synced}
- Already existed: {self.already_existed}
- Failed: {self.failed}
- Success rate: {success_rate:.1f}%

Execution time: {self.execution_time_ms:.1f}ms"""

        if self.pmids_failed:
            max_display = RESPONSE_CONFIG.MAX_PMIDS_DISPLAY
            failed_display = ", ".join(self.pmids_failed[:max_display])
            if len(self.pmids_failed) > max_display:
                failed_display += RESPONSE_CONFIG.PMIDS_TRUNCATION_SUFFIX.format(total=len(self.pmids_failed))
            result += f"\n\nFailed PMIDs: {failed_display}"

        return result


class PubMedToolsManager:
    """Manager for PubMed tools operations using service-oriented architecture."""

    def __init__(self) -> None:
        self.pubmed_service = PubMedService()
        self.document_service = DocumentService()
        self.orchestrator = SyncOrchestrator(self.pubmed_service, self.document_service)
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize the tools manager with services."""
        if self.initialized:
            return

        logger.info("Initializing PubMed tools manager")
        await self.orchestrator.initialize()
        self.initialized = True
        logger.info("PubMed tools manager initialized successfully")

    async def close(self) -> None:
        """Close all connections and cleanup."""
        if self.orchestrator:
            await self.orchestrator.close()
        
        self.initialized = False
        logger.info("PubMed tools manager closed")

    async def search(
        self, query: str, limit: int = 10, offset: int = 0
    ) -> SearchResult:
        """Search PubMed for documents."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        logger.info("Searching PubMed", query=query, limit=limit, offset=offset)

        try:
            search_result = await self.pubmed_service.search(
                query, limit=limit, offset=offset
            )

            execution_time = (time.time() - start_time) * 1000

            result = SearchResult(
                query=query,
                total_count=search_result.total_count,
                returned_count=len(search_result.pmids),
                pmids=search_result.pmids,
                execution_time_ms=execution_time,
            )

            logger.info(
                "PubMed search completed",
                query=query,
                total_count=result.total_count,
                returned_count=result.returned_count,
                execution_time_ms=execution_time,
            )

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "PubMed search failed",
                query=query,
                error=str(e),
                execution_time_ms=execution_time,
            )
            raise

    async def get_document(self, pmid: str) -> DocumentResult:
        """Get a document by PMID, checking database first, then PubMed API."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        logger.info("Getting document", pmid=pmid)

        try:
            # Check database first
            db_doc = await self.document_service.get_document_by_pmid(pmid)

            if db_doc:
                execution_time = (time.time() - start_time) * 1000

                logger.info(
                    "Document found in database",
                    pmid=pmid,
                    execution_time_ms=execution_time,
                )

                return DocumentResult(
                    pmid=pmid,
                    found=True,
                    title=db_doc.title,
                    abstract=db_doc.abstract,
                    authors=db_doc.authors,
                    journal=db_doc.journal,
                    publication_date=db_doc.publication_date,
                    doi=db_doc.doi,
                    execution_time_ms=execution_time,
                )

            # Not in database, fetch from PubMed API
            logger.debug(
                "Document not in database, fetching from PubMed API", pmid=pmid
            )

            api_docs = await self.pubmed_service.fetch_documents([pmid])

            execution_time = (time.time() - start_time) * 1000

            if not api_docs:
                logger.warning("Document not found in PubMed API", pmid=pmid)

                return DocumentResult(
                    pmid=pmid, found=False, execution_time_ms=execution_time
                )

            # Document found in API
            doc = api_docs[0]

            logger.info(
                "Document found in PubMed API",
                pmid=pmid,
                execution_time_ms=execution_time,
            )

            return DocumentResult(
                pmid=pmid,
                found=True,
                title=doc.title,
                abstract=doc.abstract,
                authors=doc.authors,
                journal=doc.journal,
                publication_date=doc.publication_date,
                doi=doc.doi,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "Failed to get document",
                pmid=pmid,
                error=str(e),
                execution_time_ms=execution_time,
            )
            raise

    async def sync(self, query: str, limit: int = 10) -> SyncResult:
        """Search PubMed and sync documents to database using orchestrator."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()
        logger.info("Starting sync operation", query=query, limit=limit)

        try:
            # Use orchestrator for the entire sync process
            sync_result = await self.orchestrator.sync_documents(query, limit)
            execution_time = (time.time() - start_time) * 1000

            result = SyncResult(
                query=query,
                total_requested=sync_result["total_requested"],
                successfully_synced=sync_result["successfully_synced"],
                already_existed=sync_result["already_existed"],
                failed=sync_result["failed"],
                pmids_synced=sync_result["pmids_synced"],
                pmids_failed=sync_result["pmids_failed"],
                execution_time_ms=execution_time,
            )

            logger.info(
                "Sync operation completed",
                query=query,
                total_requested=result.total_requested,
                successfully_synced=result.successfully_synced,
                already_existed=result.already_existed,
                failed=result.failed,
                execution_time_ms=execution_time,
            )

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "Sync operation failed",
                query=query,
                error=str(e),
                execution_time_ms=execution_time,
            )
            raise
    
    async def sync_incremental(self, query: str, limit: int = 100) -> SyncResult:
        """Search PubMed and sync documents incrementally using EDAT watermarks."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()
        logger.info("Starting incremental sync operation", query=query, limit=limit)

        try:
            # Use orchestrator for the entire incremental sync process
            sync_result = await self.orchestrator.sync_documents_incremental(query, limit)
            execution_time = (time.time() - start_time) * 1000

            result = SyncResult(
                query=query,
                total_requested=sync_result["total_requested"],
                successfully_synced=sync_result["successfully_synced"],
                already_existed=sync_result["already_existed"],
                failed=sync_result["failed"],
                pmids_synced=sync_result["pmids_synced"],
                pmids_failed=sync_result["pmids_failed"],
                execution_time_ms=execution_time,
            )

            logger.info(
                "Incremental sync operation completed",
                query=query,
                total_requested=result.total_requested,
                successfully_synced=result.successfully_synced,
                already_existed=result.already_existed,
                failed=result.failed,
                incremental=sync_result.get("incremental", False),
                last_edat=sync_result.get("last_edat"),
                new_edat=sync_result.get("new_edat"),
                query_key=sync_result.get("query_key"),
                execution_time_ms=execution_time,
            )

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "Incremental sync operation failed",
                query=query,
                error=str(e),
                execution_time_ms=execution_time,
            )
            raise


# Global manager instance
_tools_manager: PubMedToolsManager | None = None


def get_tools_manager() -> PubMedToolsManager:
    """Get the global tools manager instance."""
    global _tools_manager
    if _tools_manager is None:
        _tools_manager = PubMedToolsManager()
    return _tools_manager


# MCP Tool implementations
async def pubmed_search_tool(
    name: str, arguments: dict[str, Any]
) -> Sequence[TextContent]:
    """MCP tool: Search PubMed for documents."""
    try:
        term = arguments.get("term", "")
        limit = arguments.get("limit", 10)
        offset = arguments.get("offset", 0)

        if not term:
            return [
                TextContent(
                    type="text",
                    text="Error: 'term' parameter is required for PubMed search",
                )
            ]

        manager = get_tools_manager()
        result = await manager.search(term, limit=limit, offset=offset)

        return [TextContent(type="text", text=result.to_mcp_response())]

    except Exception as e:
        logger.error("PubMed search tool error", error=str(e))
        return [TextContent(type="text", text=f"Error searching PubMed: {e!s}")]


async def pubmed_get_tool(
    name: str, arguments: dict[str, Any]
) -> Sequence[TextContent]:
    """MCP tool: Get a PubMed document by PMID."""
    try:
        pmid = arguments.get("pmid", "")

        if not pmid:
            return [
                TextContent(type="text", text="Error: 'pmid' parameter is required")
            ]

        manager = get_tools_manager()
        result = await manager.get_document(pmid)

        return [TextContent(type="text", text=result.to_mcp_response())]

    except Exception as e:
        logger.error("PubMed get tool error", pmid=arguments.get("pmid"), error=str(e))
        return [TextContent(type="text", text=f"Error retrieving document: {e!s}")]


async def pubmed_sync_tool(
    name: str, arguments: dict[str, Any]
) -> Sequence[TextContent]:
    """MCP tool: Search PubMed and sync documents to database."""
    try:
        query = arguments.get("query", "")
        limit = arguments.get("limit", 10)

        if not query:
            return [
                TextContent(
                    type="text",
                    text="Error: 'query' parameter is required for sync operation",
                )
            ]

        manager = get_tools_manager()
        result = await manager.sync(query, limit=limit)

        return [TextContent(type="text", text=result.to_mcp_response())]

    except Exception as e:
        logger.error(
            "PubMed sync tool error", query=arguments.get("query"), error=str(e)
        )
        return [TextContent(type="text", text=f"Error syncing documents: {e!s}")]


async def pubmed_sync_incremental_tool(
    name: str, arguments: dict[str, Any]
) -> Sequence[TextContent]:
    """MCP tool: Search PubMed and sync documents incrementally using EDAT watermarks."""
    try:
        query = arguments.get("query", "")
        limit = arguments.get("limit", 100)

        if not query:
            return [
                TextContent(
                    type="text",
                    text="Error: 'query' parameter is required for incremental sync operation",
                )
            ]

        manager = get_tools_manager()
        result = await manager.sync_incremental(query, limit=limit)

        return [TextContent(type="text", text=result.to_mcp_response())]

    except Exception as e:
        logger.error(
            "PubMed incremental sync tool error", query=arguments.get("query"), error=str(e)
        )
        return [TextContent(type="text", text=f"Error syncing documents incrementally: {e!s}")]


def register_pubmed_tools(server) -> None:
    """Register PubMed tools with the MCP server."""
    # Register the tools with the server
    server.call_tool()(pubmed_search_tool)
    server.call_tool()(pubmed_get_tool)
    server.call_tool()(pubmed_sync_tool)
    server.call_tool()(pubmed_sync_incremental_tool)

    logger.info("PubMed tools registered with MCP server")
