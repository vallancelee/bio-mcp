"""
Multi-source RAG service for biomedical research.
"""

from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.shared.clients.weaviate_client import get_weaviate_client
from bio_mcp.shared.services.base_service import BaseSourceService

logger = get_logger(__name__)


class MultiSourceRAGService:
    """RAG service supporting multiple biomedical data sources."""
    
    def __init__(self):
        self.weaviate_client = None  # Initialized lazily
        self.source_services: dict[str, BaseSourceService] = {}
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize the RAG service and its dependencies."""
        if self._initialized:
            return
            
        logger.info("Initializing multi-source RAG service")
        self.weaviate_client = get_weaviate_client()
        
        # Initialize all registered source services
        for source_name, service in self.source_services.items():
            await service.ensure_initialized()
            logger.info(f"Initialized source service: {source_name}")
            
        self._initialized = True
        
    def register_source(self, source_name: str, service: BaseSourceService) -> None:
        """Register a data source service."""
        self.source_services[source_name] = service
        logger.info(f"Registered source service: {source_name}")
        
    async def search(
        self, 
        query: str,
        sources: list[str] | None = None,     # Filter to specific sources
        search_mode: str = "hybrid",          # "vector", "bm25", "hybrid"
        filters: dict | None = None,          # Cross-source filters
        date_range: dict | None = None,       # Date filtering
        quality_threshold: int = 50,          # Minimum quality score
        top_k: int = 10
    ) -> dict[str, Any]:
        """Multi-source hybrid search with unified ranking."""
        
        await self.initialize()
        
        # Build source filter
        source_filter = {}
        if sources:
            source_filter["source"] = {"valueText": sources}
        
        # Build date filter
        date_filter = {}
        if date_range:
            if "start" in date_range:
                date_filter["publication_date"] = {"valueDate": f">={date_range['start']}"}
            if "end" in date_range:
                date_filter["publication_date"] = {"valueDate": f"<={date_range['end']}"}
        
        # Combine all filters
        combined_filters = {
            **source_filter,
            **date_filter,
            **(filters or {}),
            "quality_score": {"valueInt": f">={quality_threshold}"}
        }
        
        # Execute search based on mode
        if search_mode == "hybrid":
            results = await self._hybrid_search(query, combined_filters, top_k)
        elif search_mode == "vector":
            results = await self._vector_search(query, combined_filters, top_k)
        elif search_mode == "bm25":
            results = await self._bm25_search(query, combined_filters, top_k)
        else:
            raise ValueError(f"Invalid search_mode: {search_mode}")
        
        # Re-rank with cross-source quality normalization
        reranked = await self._rerank_cross_source(results)
        
        return {
            "query": query,
            "sources_searched": sources or list(self.source_services.keys()),
            "search_mode": search_mode,
            "total_results": len(reranked),
            "results": reranked[:top_k]
        }
    
    async def _hybrid_search(self, query: str, filters: dict, limit: int) -> list[dict]:
        """Execute hybrid search (BM25 + vector)."""
        # Implementation will use weaviate_client hybrid search
        if not self.weaviate_client:
            raise RuntimeError("Weaviate client not initialized")
            
        return await self.weaviate_client.hybrid_search(
            query=query,
            filters=filters,
            limit=limit
        )
    
    async def _vector_search(self, query: str, filters: dict, limit: int) -> list[dict]:
        """Execute vector-only search."""
        if not self.weaviate_client:
            raise RuntimeError("Weaviate client not initialized")
            
        return await self.weaviate_client.vector_search(
            query=query,
            filters=filters,
            limit=limit
        )
    
    async def _bm25_search(self, query: str, filters: dict, limit: int) -> list[dict]:
        """Execute BM25-only search."""
        if not self.weaviate_client:
            raise RuntimeError("Weaviate client not initialized")
            
        return await self.weaviate_client.bm25_search(
            query=query,
            filters=filters,
            limit=limit
        )
    
    async def _rerank_cross_source(self, results: list[dict]) -> list[dict]:
        """Apply cross-source quality normalization and re-ranking."""
        
        # Normalize quality scores across different source types
        for result in results:
            source = result.get("source")
            quality_score = result.get("quality_score", 0)
            
            if source == "pubmed":
                # PubMed uses citation-based scoring (0-100)
                # Keep as-is for now
                pass
            elif source == "clinicaltrials":
                # Clinical trials use phase/enrollment-based scoring
                # Boost clinical trials slightly for treatment queries
                result["quality_score"] = min(quality_score * 1.1, 100)
            else:
                # Unknown source - keep original score
                pass
        
        # Sort by normalized quality score
        return sorted(results, key=lambda x: x.get("quality_score", 0), reverse=True)
    
    async def get_document(self, universal_id: str) -> dict | None:
        """Get document by universal ID (e.g., 'pubmed:12345', 'clinicaltrials:NCT01234')."""
        
        await self.initialize()
        
        if ":" not in universal_id:
            raise ValueError(f"Invalid universal ID format: {universal_id}")
        
        source, source_id = universal_id.split(":", 1)
        
        if source not in self.source_services:
            raise ValueError(f"Unknown source: {source}")
        
        service = self.source_services[source]
        return await service.get_document(source_id)