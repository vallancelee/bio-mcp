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

from .database import get_database_manager
from .logging_config import get_logger
from .weaviate_client import get_weaviate_client

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
    
    async def search_documents(
        self, 
        query: str, 
        top_k: int = 5,
        use_semantic: bool = True,
        quality_boost: bool = True
    ) -> RAGSearchResult:
        """
        Search documents using semantic or text-based search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            use_semantic: Whether to use semantic search (embeddings)
            quality_boost: Whether to apply quality score boosting
            
        Returns:
            RAGSearchResult with found documents
        """
        logger.info("RAG search", query=query[:50], top_k=top_k, semantic=use_semantic)
        
        try:
            await self.weaviate.initialize()
            
            search_type = "semantic"
            results = await self.weaviate.search_documents(
                query=query,
                limit=top_k
            )
            
            if quality_boost:
                results = self._apply_quality_boost(results)
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
                    "content": result.get("content", "")[:500] + "..." if len(result.get("content", "")) > 500 else result.get("content", "")
                }
                formatted_results.append(formatted_result)
            
            return RAGSearchResult(
                query=query,
                total_results=len(formatted_results),
                documents=formatted_results,
                search_type=search_type
            )
            
        except Exception as e:
            logger.error("RAG search failed", query=query, error=str(e))
            return RAGSearchResult(
                query=query,
                total_results=0,
                documents=[],
                search_type=search_type if 'search_type' in locals() else "unknown"
            )
    
    def _apply_quality_boost(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply quality score boosting to search results."""
        for result in results:
            quality_total = result.get("quality_total", 0) or 0
            original_score = result.get("score", 0.0)
            
            if original_score and quality_total:
                boosted_score = original_score * (1 + quality_total / 10)
                result["boosted_score"] = boosted_score
                result["quality_boost"] = quality_total / 10
            else:
                result["boosted_score"] = original_score
                result["quality_boost"] = 0
        
        results.sort(key=lambda x: x.get("boosted_score", 0), reverse=True)
        return results
    
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
                # TODO: Implement chunk retrieval from database
                # For now, return the single document as a "chunk"
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
    MCP tool: Search the RAG corpus for relevant documents.
    
    Args:
        query: Search query string
        top_k: Number of results to return (default: 5, max: 50)
        
    Returns:
        Formatted search results
    """
    query = arguments.get("query", "").strip()
    top_k = min(max(arguments.get("top_k", 5), 1), 50)
    
    if not query:
        return [TextContent(
            type="text",
            text="❌ Error: Query parameter is required"
        )]
    
    logger.info("RAG search tool called", query=query, top_k=top_k)
    
    try:
        manager = get_rag_manager()
        result = await manager.search_documents(query, top_k)
        
        if result.total_results == 0:
            response_text = f"""🔍 **RAG Search Results**

**Query:** {query}
**Search Type:** {result.search_type}
**Results:** No documents found

Try different keywords or check if documents have been synced to the corpus."""
        else:
            # Format results nicely
            results_text = []
            for i, doc in enumerate(result.documents, 1):
                score_text = f"Score: {doc['score']:.3f}"
                if 'boosted_score' in doc and doc['boosted_score'] != doc['score']:
                    score_text += f" (boosted: {doc['boosted_score']:.3f})"
                
                doc_text = f"""**{i}. {doc['title']}**
PMID: {doc['pmid']} | {score_text}
Journal: {doc['journal']} | Date: {doc['publication_date']}

{doc['content']}

---"""
                results_text.append(doc_text)
            
            response_text = f"""🔍 **RAG Search Results**

**Query:** {query}
**Search Type:** {result.search_type.title()} Search
**Results:** {result.total_results} documents found

{chr(10).join(results_text)}"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        logger.error("RAG search tool failed", query=query, error=str(e))
        return [TextContent(
            type="text",
            text=f"❌ Error during RAG search: {e!s}"
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