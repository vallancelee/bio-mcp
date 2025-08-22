"""
RAG tools for Bio-MCP server.
Phase 4A: Basic RAG Tools - Semantic search and document retrieval.

Implements MCP tools for:
- rag.search: Semantic search over document corpus
- rag.get: Retrieve specific document by ID
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from mcp.types import TextContent

from bio_mcp.config.logging_config import get_logger
from bio_mcp.config.search_config import RESPONSE_CONFIG, SEARCH_CONFIG
from bio_mcp.mcp.response_builder import (
    MCPResponseBuilder,
    ErrorCodes,
    get_format_preference,
    format_rag_search_human,
    format_rag_get_human
)
from bio_mcp.shared.clients.database import get_database_manager
from bio_mcp.services.embedding_service import EmbeddingService
from bio_mcp.sources.pubmed.quality import JournalQualityScorer

logger = get_logger(__name__)


@dataclass
class RAGSearchResult:
    """Result from RAG search operation."""

    query: str
    total_results: int
    documents: list[dict[str, Any]]
    search_type: str  # "semantic" or "text"
    performance: dict[str, float] | None = None  # Performance metrics


@dataclass
class RAGGetResult:
    """Result from RAG document retrieval."""

    doc_id: str
    found: bool
    document: dict[str, Any] | None = None
    chunks: list[dict[str, Any]] | None = None


class RAGToolsManager:
    """Manager for RAG-related operations."""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.db_manager = get_database_manager()
        self.quality_scorer = JournalQualityScorer()

    async def search_documents(
        self,
        query: str,
        top_k: int = 5,
        search_mode: str = "hybrid",
        filters: dict | None = None,
        rerank_by_quality: bool = True,
        alpha: float = 0.5,
    ) -> RAGSearchResult:
        """
        Search documents using hybrid, semantic, or BM25 search.

        Args:
            query: Search query
            top_k: Number of results to return
            search_mode: 'semantic', 'bm25', or 'hybrid'
            filters: Metadata filters (future enhancement)
            rerank_by_quality: Whether to apply quality score boosting
            alpha: Hybrid search weighting (0.0=pure BM25, 1.0=pure vector)

        Returns:
            RAGSearchResult with found documents
        """
        logger.info(
            "RAG hybrid search",
            query=query[:50],
            top_k=top_k,
            mode=search_mode,
            alpha=alpha,
        )

        search_start_time = time.time()

        try:
            await self.embedding_service.initialize()

            # Perform search with specified mode using the chunk-based approach
            search_time_start = time.time()
            results = await self.embedding_service.search_chunks(
                query=query,
                limit=top_k,
                search_mode=search_mode,
                alpha=alpha,
                filters=filters,
            )
            search_time_ms = (time.time() - search_time_start) * 1000

            # Apply quality-based reranking if enabled
            quality_time_start = time.time()
            if rerank_by_quality:
                results = self.quality_scorer.apply_quality_boost(results)
            quality_time_ms = (time.time() - quality_time_start) * 1000

            # Calculate total processing time
            total_time_ms = (time.time() - search_start_time) * 1000

            # Log performance metrics
            logger.info(
                "RAG search performance",
                search_time_ms=f"{search_time_ms:.1f}",
                quality_time_ms=f"{quality_time_ms:.1f}",
                total_time_ms=f"{total_time_ms:.1f}",
                results_count=len(results),
            )

            # Format chunk results for consistent output
            formatted_results = []
            for result in results:
                # Extract PMID from parent_uid (format: "pubmed:12345678")
                pmid = ""
                if "parent_uid" in result:
                    parent_uid = result["parent_uid"]
                    if parent_uid.startswith("pubmed:"):
                        pmid = parent_uid[7:]  # Remove "pubmed:" prefix

                # Handle date serialization
                pub_date = result.get("published_at", "")
                if hasattr(pub_date, 'isoformat'):
                    pub_date = pub_date.isoformat()
                elif pub_date is None:
                    pub_date = ""
                
                formatted_result = {
                    "uuid": result["uuid"],
                    "pmid": pmid,
                    "title": result.get("title", ""),
                    "abstract": result.get("text", ""),  # chunks have 'text' not 'abstract'
                    "journal": "",  # journal info not stored in chunks currently
                    "publication_date": pub_date,
                    "score": result.get("score", 0.0),
                    "distance": result.get("distance"),
                    "content": self._truncate_content(result.get("text", "")),
                    "search_mode": search_mode,
                }

                # Include hybrid search explanation if available
                if "explain_score" in result:
                    formatted_result["explain_score"] = result["explain_score"]

                formatted_results.append(formatted_result)

            # Add performance metadata to the result
            search_result = RAGSearchResult(
                query=query,
                total_results=len(formatted_results),
                documents=formatted_results,
                search_type=search_mode,
            )

            # Add performance data for display
            search_result.performance = {
                "search_time_ms": search_time_ms,
                "quality_time_ms": quality_time_ms,
                "total_time_ms": total_time_ms,
                "target_time_ms": 200.0,  # Phase 4B.1 target
            }

            return search_result

        except Exception as e:
            logger.error(
                "RAG search failed", query=query, mode=search_mode, error=str(e)
            )
            return RAGSearchResult(
                query=query,
                total_results=0,
                documents=[],
                search_type=search_mode,  # Always use the requested search mode
            )

    async def get_document(
        self, doc_id: str, include_chunks: bool = False
    ) -> RAGGetResult:
        """
        Get a specific document by ID (PMID or UUID).

        Args:
            doc_id: Document ID (PMID or UUID)
            include_chunks: Whether to include document chunks

        Returns:
            RAGGetResult with document data
        """
        logger.info("RAG get document", doc_id=doc_id, include_chunks=include_chunks)

        try:
            await self.embedding_service.initialize()

            # For chunk-based approach, search for chunks by parent_uid
            if doc_id.startswith("pmid:"):
                parent_uid = doc_id  # Already in format "pmid:12345678"
            else:
                parent_uid = f"pubmed:{doc_id}"  # Convert PMID to parent_uid format

            # Search for all chunks belonging to this document
            from weaviate.classes.query import Filter
            collection = self.embedding_service.weaviate_client.client.collections.get("DocumentChunk")
            
            response = collection.query.fetch_objects(
                filters=Filter.by_property("parent_uid").equal(parent_uid)
            )

            if not response.objects:
                return RAGGetResult(doc_id=doc_id, found=False)

            # Reconstruct document from first chunk's metadata
            first_chunk = response.objects[0]
            document = {
                "uuid": str(first_chunk.uuid),
                "pmid": parent_uid.replace("pubmed:", "") if parent_uid.startswith("pubmed:") else parent_uid,
                "title": first_chunk.properties.get("title", ""),
                "abstract": "",  # We'll combine all chunk texts
                "journal": "",  # Not available in chunks
                "publication_date": first_chunk.properties.get("published_at", ""),
                "parent_uid": parent_uid
            }

            chunks = []
            combined_text = []
            for obj in response.objects:
                chunk = {
                    "chunk_id": obj.properties["chunk_id"],
                    "text": obj.properties.get("text", ""),
                    "section": obj.properties.get("section", ""),
                    "tokens": obj.properties.get("tokens", 0),
                    "chunk_idx": obj.properties.get("chunk_idx", 0)
                }
                chunks.append(chunk)
                combined_text.append(obj.properties.get("text", ""))
            
            # Combine all chunk texts to form the full abstract
            document["abstract"] = " ".join(combined_text)

            result_chunks = chunks if include_chunks else None
            return RAGGetResult(
                doc_id=doc_id, found=True, document=document, chunks=result_chunks
            )

        except Exception as e:
            logger.error("RAG get document failed", doc_id=doc_id, error=str(e))
            return RAGGetResult(doc_id=doc_id, found=False)

    def _truncate_content(self, content: str) -> str:
        """Truncate content for display based on configuration."""
        if not content:
            return content

        max_length = RESPONSE_CONFIG.MAX_CONTENT_PREVIEW_LENGTH
        if len(content) > max_length:
            return content[:max_length] + RESPONSE_CONFIG.CONTENT_TRUNCATION_SUFFIX
        return content


# Global manager instance
_rag_manager: RAGToolsManager | None = None


def get_rag_manager() -> RAGToolsManager:
    """Get the global RAG tools manager instance."""
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = RAGToolsManager()
    return _rag_manager


async def rag_search_tool(
    name: str, arguments: dict[str, Any]
) -> Sequence[TextContent]:
    """
    MCP tool: Search the RAG corpus using hybrid, semantic, or BM25 search.

    Args:
        query: Search query string
        top_k: Number of results to return (default: 10, max: 50)
        search_mode: 'hybrid' (default), 'semantic', or 'bm25'
        alpha: Hybrid search weighting (0.0=pure BM25, 1.0=pure vector, 0.5=balanced)
        rerank_by_quality: Whether to boost results by quality (default: true)
        filters: Metadata filters for date ranges, journals, etc.

    Returns:
        Formatted search results with hybrid scoring
    """
    # Initialize response builder
    builder = MCPResponseBuilder("rag.search")
    format_type = get_format_preference(arguments)

    # Extract and validate parameters
    query = arguments.get("query", "").strip()
    if not query:
        return builder.error(
            ErrorCodes.MISSING_PARAMETER,
            "Query parameter is required",
            format_type=format_type
        )

    top_k = min(
        max(
            arguments.get("top_k", SEARCH_CONFIG.DEFAULT_TOP_K), SEARCH_CONFIG.MIN_TOP_K
        ),
        SEARCH_CONFIG.MAX_TOP_K,
    )
    search_mode = arguments.get("search_mode", "hybrid").lower()
    alpha = float(arguments.get("alpha", 0.5))
    rerank_by_quality = arguments.get("rerank_by_quality", True)
    filters = arguments.get("filters", {})

    # Validate alpha parameter
    alpha = max(0.0, min(1.0, alpha))  # Clamp to [0.0, 1.0]

    # Validate search mode
    valid_modes = ["hybrid", "semantic", "bm25"]
    if search_mode not in valid_modes:
        search_mode = "hybrid"  # Default fallback

    logger.info(
        "RAG hybrid search tool called",
        query=query,
        top_k=top_k,
        mode=search_mode,
        alpha=alpha,
    )

    try:
        manager = get_rag_manager()
        result = await manager.search_documents(
            query=query,
            top_k=top_k,
            search_mode=search_mode,
            filters=filters,
            rerank_by_quality=rerank_by_quality,
            alpha=alpha,
        )

        # Format results for JSON response
        formatted_results = []
        for doc in result.documents:
            formatted_result = {
                "uuid": doc["uuid"],
                "pmid": doc.get("pmid", ""),
                "title": doc.get("title", ""),
                "abstract": doc.get("abstract", ""),
                "journal": doc.get("journal", ""),
                "publication_date": doc.get("publication_date", ""),
                "score": doc.get("score", 0.0),
                "content": doc.get("content", "")
            }
            
            # Add optional fields if present
            if "boosted_score" in doc:
                formatted_result["boosted_score"] = doc["boosted_score"]
            if "quality_boost" in doc:
                formatted_result["quality_boost"] = doc["quality_boost"]
            if "distance" in doc:
                formatted_result["distance"] = doc["distance"]
            if "explain_score" in doc:
                formatted_result["explain_score"] = doc["explain_score"]
            
            formatted_results.append(formatted_result)

        # Build response data
        response_data = {
            "query": query,
            "search_mode": result.search_type,
            "total_results": result.total_results,
            "results": formatted_results,
            "parameters": {
                "top_k": top_k,
                "alpha": alpha,
                "quality_bias": rerank_by_quality,
                "filters": filters
            }
        }

        # Add performance data if available
        if result.performance:
            response_data["performance"] = result.performance

        return builder.success(
            data=response_data,
            format_type=format_type,
            human_formatter=format_rag_search_human
        )

    except Exception as e:
        logger.error(
            "RAG hybrid search tool failed", query=query, mode=search_mode, error=str(e)
        )
        return builder.error(
            ErrorCodes.OPERATION_FAILED,
            f"RAG search failed: {str(e)}",
            details={"query": query, "search_mode": search_mode},
            format_type=format_type
        )


async def rag_get_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """
    MCP tool: Get a specific document from the RAG corpus.

    Args:
        doc_id: Document ID to retrieve (PMID or UUID)
        format: Response format ('json' or 'human', default: 'json')

    Returns:
        Document details in JSON format
    """
    # Initialize response builder
    builder = MCPResponseBuilder("rag.get")
    format_type = get_format_preference(arguments)
    
    doc_id = arguments.get("doc_id", "").strip()

    if not doc_id:
        return builder.error(
            ErrorCodes.MISSING_PARAMETER,
            "doc_id parameter is required",
            format_type=format_type
        )

    logger.info("RAG get tool called", doc_id=doc_id)

    try:
        manager = get_rag_manager()
        result = await manager.get_document(doc_id, include_chunks=True)

        if not result.found:
            return builder.error(
                ErrorCodes.NOT_FOUND,
                f"Document not found: {doc_id}",
                details="The document may not be synced to the corpus yet",
                format_type=format_type
            )

        doc = result.document
        
        # Format document for JSON response
        document_data = {
            "doc_id": doc_id,
            "document": {
                "uuid": doc["uuid"],
                "pmid": doc.get("pmid", ""),
                "title": doc.get("title", ""),
                "abstract": doc.get("abstract", ""),
                "journal": doc.get("journal", ""),
                "publication_date": doc.get("publication_date", ""),
                "doi": doc.get("doi"),
                "authors": doc.get("authors", []),
                "keywords": doc.get("keywords", []),
                "pub_types": doc.get("pub_types", []),
                "quality": doc.get("quality"),
            }
        }

        # Add optional fields if present
        if "mesh_terms" in doc:
            document_data["document"]["mesh_terms"] = doc["mesh_terms"]
        if "edat" in doc:
            document_data["document"]["entry_date"] = doc["edat"]
        if "lr" in doc:
            document_data["document"]["last_revision"] = doc["lr"]
        if result.chunks:
            document_data["chunks"] = [
                {
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk.get("text", ""),
                    "section": chunk.get("section", ""),
                    "tokens": chunk.get("tokens", 0)
                }
                for chunk in result.chunks
            ]

        return builder.success(
            data=document_data,
            format_type=format_type,
            human_formatter=format_rag_get_human
        )

    except Exception as e:
        logger.error("RAG get tool failed", doc_id=doc_id, error=str(e))
        return builder.error(
            ErrorCodes.OPERATION_FAILED,
            f"Failed to retrieve document: {str(e)}",
            details={"doc_id": doc_id},
            format_type=format_type
        )
