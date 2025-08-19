"""
RAG tools for Bio-MCP server.
Phase 4A: Basic RAG Tools - Semantic search and document retrieval.

Implements MCP tools for:
- rag.search: Semantic search over document corpus
- rag.get: Retrieve specific document by ID
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from mcp.types import TextContent

from ..clients.database import get_database_manager
from ..clients.weaviate_client import get_weaviate_client
from ..config.logging_config import get_logger
from ..config.search_config import RESPONSE_CONFIG, SEARCH_CONFIG
from ..core.quality_scoring import JournalQualityScorer

logger = get_logger(__name__)


@dataclass
class RAGSearchResult:
    """Result from RAG search operation."""
    query: str
    total_results: int
    documents: list[dict[str, Any]]
    search_type: str  # "semantic" or "text"


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
        self.weaviate = get_weaviate_client()
        self.db_manager = get_database_manager()
        self.quality_scorer = JournalQualityScorer()
    
    async def search_documents(
        self, 
        query: str, 
        top_k: int = 5,
        search_mode: str = "hybrid",
        filters: dict | None = None,
        rerank_by_quality: bool = True,
        alpha: float = 0.5
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
        logger.info("RAG hybrid search", query=query[:50], top_k=top_k, mode=search_mode, alpha=alpha)
        
        try:
            await self.weaviate.initialize()
            
            # Perform search with specified mode
            results = await self.weaviate.search_documents(
                query=query,
                limit=top_k,
                search_mode=search_mode,
                alpha=alpha
            )
            
            # Apply quality-based reranking if enabled
            if rerank_by_quality:
                results = self.quality_scorer.apply_quality_boost(results)
            
            # Format results for consistent output
            formatted_results = []
            for result in results:
                formatted_result = {
                    "uuid": result["uuid"],
                    "pmid": result.get("pmid", ""),
                    "title": result.get("title", ""),
                    "abstract": result.get("abstract", ""),
                    "journal": result.get("journal", ""),
                    "publication_date": result.get("publication_date", ""),
                    "score": result.get("score", 0.0),
                    "distance": result.get("distance"),
                    "content": self._truncate_content(result.get("content", "")),
                    "search_mode": search_mode
                }
                
                # Include hybrid search explanation if available
                if "explain_score" in result:
                    formatted_result["explain_score"] = result["explain_score"]
                    
                formatted_results.append(formatted_result)
            
            return RAGSearchResult(
                query=query,
                total_results=len(formatted_results),
                documents=formatted_results,
                search_type=search_mode
            )
            
        except Exception as e:
            logger.error("RAG search failed", query=query, mode=search_mode, error=str(e))
            return RAGSearchResult(
                query=query,
                total_results=0,
                documents=[],
                search_type=search_mode  # Always use the requested search mode
            )
    
    
    async def get_document(self, doc_id: str, include_chunks: bool = False) -> RAGGetResult:
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
            await self.weaviate.initialize()
            
            if doc_id.startswith("pmid:"):
                pmid = doc_id[5:]
                document = await self.weaviate.get_document_by_pmid(pmid)
            else:
                document = await self.weaviate.get_document_by_pmid(doc_id)
            
            if not document:
                return RAGGetResult(
                    doc_id=doc_id,
                    found=False
                )
            
            chunks = None
            if include_chunks:
                # Note: Document chunking is available but not yet integrated with database storage
                # Currently returning the full document as a single chunk
                chunks = [document]
            
            return RAGGetResult(
                doc_id=doc_id,
                found=True,
                document=document,
                chunks=chunks
            )
            
        except Exception as e:
            logger.error("RAG get document failed", doc_id=doc_id, error=str(e))
            return RAGGetResult(
                doc_id=doc_id,
                found=False
            )
    
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


async def rag_search_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """
    MCP tool: Search the RAG corpus using hybrid, semantic, or BM25 search.
    
    Args:
        query: Search query string
        top_k: Number of results to return (default: 10, max: 50)
        search_mode: 'hybrid' (default), 'semantic', or 'bm25'
        rerank_by_quality: Whether to boost results by quality (default: true)
        
    Returns:
        Formatted search results with hybrid scoring
    """
    query = arguments.get("query", "").strip()
    top_k = min(
        max(arguments.get("top_k", SEARCH_CONFIG.DEFAULT_TOP_K), SEARCH_CONFIG.MIN_TOP_K),
        SEARCH_CONFIG.MAX_TOP_K
    )
    search_mode = arguments.get("search_mode", "hybrid").lower()
    rerank_by_quality = arguments.get("rerank_by_quality", True)
    
    # Validate search mode
    valid_modes = ["hybrid", "semantic", "bm25"]
    if search_mode not in valid_modes:
        search_mode = "hybrid"  # Default fallback
    
    if not query:
        return [TextContent(
            type="text",
            text="❌ Error: Query parameter is required"
        )]
    
    logger.info("RAG hybrid search tool called", query=query, top_k=top_k, mode=search_mode)
    
    try:
        manager = get_rag_manager()
        result = await manager.search_documents(
            query=query, 
            top_k=top_k,
            search_mode=search_mode,
            rerank_by_quality=rerank_by_quality
        )
        
        if result.total_results == 0:
            response_text = f"""🔍 **Hybrid RAG Search Results**

**Query:** {query}
**Search Mode:** {result.search_type.title()}
**Results:** No documents found

Try different keywords, search modes ('hybrid', 'semantic', 'bm25'), or check if documents have been synced to the corpus."""
        else:
            # Format results with enhanced information
            results_text = []
            for i, doc in enumerate(result.documents, 1):
                # Enhanced score display
                score_text = f"Score: {doc['score']:.3f}"
                if 'boosted_score' in doc and abs(doc['boosted_score'] - doc['score']) > 0.001:
                    boost_pct = ((doc['boosted_score'] / doc['score']) - 1) * 100 if doc['score'] > 0 else 0
                    score_text += f" → {doc['boosted_score']:.3f} (+{boost_pct:.1f}%)"
                
                # Add search mode context
                mode_indicator = {
                    "hybrid": "🔀",
                    "semantic": "🧠", 
                    "bm25": "🔎"
                }.get(result.search_type, "📄")
                
                doc_text = f"""**{i}. {doc['title']}**
{mode_indicator} PMID: {doc['pmid']} | {score_text}
📰 Journal: {doc['journal']} | 📅 Date: {doc['publication_date']}

{doc['content']}

---"""
                results_text.append(doc_text)
            
            # Add search statistics
            mode_description = {
                "hybrid": "Hybrid (BM25 + Vector)",
                "semantic": "Semantic (Vector)",
                "bm25": "Keyword (BM25)"
            }.get(result.search_type, result.search_type.title())
            
            quality_note = "Quality boosting: ON" if rerank_by_quality else "Quality boosting: OFF"
            
            response_text = f"""🔍 **Hybrid RAG Search Results**

**Query:** {query}
**Search Mode:** {mode_description}
**{quality_note}**
**Results:** {result.total_results} documents found

{chr(10).join(results_text)}"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        logger.error("RAG hybrid search tool failed", query=query, mode=search_mode, error=str(e))
        return [TextContent(
            type="text",
            text=f"❌ Error during hybrid RAG search: {e!s}"
        )]


async def rag_get_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """
    MCP tool: Get a specific document from the RAG corpus.
    
    Args:
        doc_id: Document ID to retrieve (PMID or UUID)
        
    Returns:
        Document details
    """
    doc_id = arguments.get("doc_id", "").strip()
    
    if not doc_id:
        return [TextContent(
            type="text",
            text="❌ Error: doc_id parameter is required"
        )]
    
    logger.info("RAG get tool called", doc_id=doc_id)
    
    try:
        manager = get_rag_manager()
        result = await manager.get_document(doc_id, include_chunks=True)
        
        if not result.found:
            response_text = f"""📄 **Document Not Found**

**Document ID:** {doc_id}

The requested document was not found in the RAG corpus.
Make sure the document has been synced using the pubmed.sync tool."""
        else:
            doc = result.document
            response_text = f"""📄 **Document Details**

**Title:** {doc['title']}
**PMID:** {doc['pmid']}
**Journal:** {doc['journal']}
**Publication Date:** {doc['publication_date']}
**DOI:** {doc.get('doi', 'N/A')}

**Abstract:**
{doc['abstract']}

**Keywords:** {', '.join(doc.get('keywords', []))}
**Authors:** {', '.join(doc.get('authors', []))}

**Vector Database UUID:** {doc['uuid']}"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        logger.error("RAG get tool failed", doc_id=doc_id, error=str(e))
        return [TextContent(
            type="text",
            text=f"❌ Error retrieving document: {e!s}"
        )]