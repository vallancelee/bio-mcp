"""
Enhanced embedding service for DocumentChunk_v2 collection.

This service integrates with the new optimized Weaviate collection schema
and provides advanced search capabilities with BioBERT embeddings.
"""

import uuid
from typing import Any

from weaviate.classes.query import MetadataQuery

from bio_mcp.config.logging_config import get_logger
from bio_mcp.models.document import Chunk
from bio_mcp.services.weaviate_schema import CollectionConfig, WeaviateSchemaManager
from bio_mcp.shared.clients.weaviate_client import WeaviateClient, get_weaviate_client

logger = get_logger(__name__)


class EmbeddingServiceV2:
    """Enhanced embedding service for DocumentChunk_v2 collection."""
    
    def __init__(self, 
                 weaviate_client: WeaviateClient = None,
                 collection_name: str = "DocumentChunk_v2"):
        self.weaviate_client = weaviate_client or get_weaviate_client()
        self.collection_name = collection_name
        self.schema_manager = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the embedding service."""
        if self._initialized:
            return
        
        logger.info("Initializing EmbeddingServiceV2", collection=self.collection_name)
        
        if not self.weaviate_client:
            self.weaviate_client = get_weaviate_client()
        
        await self.weaviate_client.initialize()
        
        # Create schema manager
        self.schema_manager = WeaviateSchemaManager(
            self.weaviate_client.client,
            CollectionConfig(name=self.collection_name)
        )
        
        # Ensure collection exists
        await self._ensure_collection_exists()
        
        self._initialized = True
        logger.info("EmbeddingServiceV2 initialized successfully")
    
    async def _ensure_collection_exists(self) -> None:
        """Ensure the collection exists with proper schema."""
        if not self.weaviate_client.client.collections.exists(self.collection_name):
            logger.info(f"Creating collection: {self.collection_name}")
            await self.schema_manager.create_document_chunk_v2_collection()
        else:
            # Validate existing schema
            validation = self.schema_manager.validate_collection_schema(self.collection_name)
            if not validation["valid"]:
                logger.warning("Collection schema validation failed", 
                             issues=validation["issues"])
    
    async def store_document_chunks(self, chunks: list[Chunk]) -> list[str]:
        """Store document chunks with deterministic UUIDs."""
        if not self._initialized:
            await self.initialize()
        
        logger.info("Storing document chunks", chunk_count=len(chunks))
        
        if not chunks:
            return []
        
        collection = self.weaviate_client.client.collections.get(self.collection_name)
        stored_uuids = []
        
        # Prepare batch data
        batch_data = []
        for chunk in chunks:
            properties = self._chunk_to_properties(chunk)
            
            batch_data.append({
                "uuid": uuid.UUID(chunk.uuid),  # Use chunk's deterministic UUID
                "properties": properties
            })
        
        # Batch insert with error handling
        try:
            with collection.batch.dynamic() as batch:
                for item in batch_data:
                    batch.add_object(
                        uuid=item["uuid"],
                        properties=item["properties"]
                    )
            
            stored_uuids = [str(item["uuid"]) for item in batch_data]
            
            logger.info("Document chunks stored successfully", 
                       stored_count=len(stored_uuids),
                       parent_uid=chunks[0].parent_uid if chunks else None)
        
        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")
            raise
        
        return stored_uuids
    
    def _chunk_to_properties(self, chunk: Chunk) -> dict[str, Any]:
        """Convert Chunk model to Weaviate properties."""
        
        # Extract quality score from metadata
        quality_total = 0.0
        if chunk.meta and "src" in chunk.meta:
            # Try to extract quality from source-specific metadata
            for source_data in chunk.meta["src"].values():
                if isinstance(source_data, dict) and "quality_total" in source_data:
                    quality_total = float(source_data["quality_total"])
                    break
        
        return {
            "parent_uid": chunk.parent_uid,
            "source": chunk.source,
            "title": chunk.title or "",
            "text": chunk.text,
            "section": chunk.section or "Unstructured",
            "published_at": chunk.published_at.strftime('%Y-%m-%dT%H:%M:%SZ') if chunk.published_at else None,
            "year": chunk.published_at.year if chunk.published_at else None,
            "tokens": chunk.tokens or 0,
            "n_sentences": chunk.n_sentences or 0,
            "quality_total": quality_total,
            "meta": chunk.meta or {}
        }
    
    async def search_chunks(self,
                          query: str,
                          limit: int = 5,
                          search_mode: str = "hybrid",
                          alpha: float = 0.5,
                          filters: dict[str, Any] | None = None,
                          min_certainty: float | None = None) -> list[dict[str, Any]]:
        """Search chunks using the new collection."""
        if not self._initialized:
            await self.initialize()
        
        collection = self.weaviate_client.client.collections.get(self.collection_name)
        
        logger.debug("Performing chunk search",
                    query=query[:50],
                    search_mode=search_mode,
                    limit=limit)
        
        # Build filters
        where_filter = self._build_filters(filters) if filters else None
        
        try:
            if search_mode == "hybrid":
                if where_filter:
                    response = collection.query.hybrid(
                        query=query,
                        alpha=alpha,
                        limit=limit,
                        filters=where_filter,
                        return_metadata=MetadataQuery(score=True, explain_score=True)
                    )
                else:
                    response = collection.query.hybrid(
                        query=query,
                        alpha=alpha,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True, explain_score=True)
                    )
            elif search_mode == "semantic":
                if where_filter:
                    response = collection.query.near_text(
                        query=query,
                        limit=limit,
                        filters=where_filter,
                        return_metadata=MetadataQuery(score=True, distance=True)
                    )
                else:
                    response = collection.query.near_text(
                        query=query,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True, distance=True)
                    )
            elif search_mode == "bm25":
                # Note: BM25 doesn't support filters in this approach
                response = collection.query.bm25(
                    query=query,
                    limit=limit,
                    return_metadata=MetadataQuery(score=True)
                )
            else:
                raise ValueError(f"Unknown search mode: {search_mode}")
            
            # Convert results
            results = []
            for obj in response.objects:
                result = {
                    "uuid": str(obj.uuid),
                    "chunk_id": obj.properties.get("parent_uid", "") + ":s0",  # Simplified for now
                    "parent_uid": obj.properties["parent_uid"],
                    "source": obj.properties["source"],
                    "title": obj.properties["title"],
                    "text": obj.properties["text"], 
                    "section": obj.properties["section"],
                    "published_at": obj.properties.get("published_at"),
                    "tokens": obj.properties.get("tokens", 0),
                    "n_sentences": obj.properties.get("n_sentences", 0),
                    "quality_total": obj.properties.get("quality_total", 0.0),
                    "meta": obj.properties.get("meta", {})
                }
                
                # Add search-specific metadata
                if hasattr(obj.metadata, 'score') and obj.metadata.score is not None:
                    result["score"] = obj.metadata.score
                if hasattr(obj.metadata, 'certainty') and obj.metadata.certainty is not None:
                    result["certainty"] = obj.metadata.certainty
                if hasattr(obj.metadata, 'distance') and obj.metadata.distance is not None:
                    result["distance"] = obj.metadata.distance
                if hasattr(obj.metadata, 'explain_score'):
                    result["explain_score"] = obj.metadata.explain_score
                
                results.append(result)
            
            logger.debug("Chunk search completed", 
                        query=query,
                        results_found=len(results))
            
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    def _build_filters(self, filters: dict[str, Any]) -> Any | None:
        """Build Weaviate where filters from search filters."""
        from weaviate.classes.query import Filter
        
        conditions = []
        
        # Date range filters
        if "date_from" in filters:
            conditions.append(Filter.by_property("published_at").greater_or_equal(filters["date_from"]))
        if "date_to" in filters:
            conditions.append(Filter.by_property("published_at").less_or_equal(filters["date_to"]))
        
        # Year filter
        if "year" in filters:
            conditions.append(Filter.by_property("year").equal(filters["year"]))
        
        # Source filter
        if "source" in filters:
            if isinstance(filters["source"], list):
                source_conditions = [Filter.by_property("source").equal(s) for s in filters["source"]]
                conditions.append(Filter.any_of(source_conditions))
            else:
                conditions.append(Filter.by_property("source").equal(filters["source"]))
        
        # Section filter
        if "section" in filters:
            if isinstance(filters["section"], list):
                section_conditions = [Filter.by_property("section").equal(s) for s in filters["section"]]
                conditions.append(Filter.any_of(section_conditions))
            else:
                conditions.append(Filter.by_property("section").equal(filters["section"]))
        
        # Quality threshold
        if "min_quality" in filters:
            conditions.append(Filter.by_property("quality_total").greater_or_equal(filters["min_quality"]))
        
        # Token range
        if "min_tokens" in filters:
            conditions.append(Filter.by_property("tokens").greater_or_equal(filters["min_tokens"]))
        if "max_tokens" in filters:
            conditions.append(Filter.by_property("tokens").less_or_equal(filters["max_tokens"]))
        
        # Journal filter (nested in metadata)
        if "journals" in filters:
            journal_conditions = []
            for journal in filters["journals"]:
                journal_conditions.append(Filter.by_property("meta.src.pubmed.journal").equal(journal))
            if journal_conditions:
                conditions.append(Filter.any_of(journal_conditions))
        
        # Combine conditions
        if len(conditions) == 0:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return Filter.all_of(conditions)
    
    async def health_check(self) -> dict[str, Any]:
        """Check health of embedding service and collection."""
        try:
            if not self._initialized:
                return {"status": "not_initialized"}
            
            # Check collection exists and get info
            info = self.schema_manager.get_collection_info(self.collection_name)
            validation = self.schema_manager.validate_collection_schema(self.collection_name)
            
            status = "healthy"
            if not info["exists"]:
                status = "error"
            elif not validation["valid"]:
                status = "degraded"
            
            return {
                "status": status,
                "collection": info,
                "validation": validation,
                "weaviate_connected": self.weaviate_client.client is not None
            }
        
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }