"""
Embedding service for storing and retrieving document chunks.

This service handles the new chunk-based embedding workflow, supporting
both the legacy document-based approach and the new multi-source chunk approach.
"""

from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.models.document import Document
from bio_mcp.shared.clients.weaviate_client import WeaviateClient, get_weaviate_client
from bio_mcp.shared.core.embeddings import AbstractChunker

logger = get_logger(__name__)


class EmbeddingService:
    """
    Service for embedding and storing document chunks in vector store.

    Supports both new Document/Chunk workflow and legacy backward compatibility.
    """

    def __init__(self, weaviate_client: WeaviateClient | None = None):
        self.weaviate_client = weaviate_client
        self.chunker = AbstractChunker()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the embedding service and dependencies."""
        if self._initialized:
            return

        logger.info("Initializing embedding service")

        if not self.weaviate_client:
            self.weaviate_client = get_weaviate_client()

        await self.weaviate_client.initialize()
        await self._ensure_chunk_collection_exists()

        self._initialized = True
        logger.info("Embedding service initialized successfully")

    async def close(self) -> None:
        """Close embedding service connections."""
        if self.weaviate_client:
            await self.weaviate_client.close()
            self.weaviate_client = None
        self._initialized = False
        logger.info("Embedding service closed")

    async def _ensure_chunk_collection_exists(self) -> None:
        """Ensure the DocumentChunk collection exists with proper schema."""
        if not self.weaviate_client or not self.weaviate_client.client:
            raise RuntimeError("Weaviate client not initialized")

        collection_name = "DocumentChunk"

        # Check if collection exists
        if self.weaviate_client.client.collections.exists(collection_name):
            logger.debug(
                "DocumentChunk collection already exists", collection=collection_name
            )
            return

        # Create collection with schema for chunks
        logger.info("Creating DocumentChunk collection", collection=collection_name)

        from weaviate.classes.config import Configure, DataType, Property

        # Check if we should use vectorizer
        vectorizer_config = None
        try:
            # Check if text2vec-transformers is available in Weaviate meta
            meta = self.weaviate_client.client.get_meta()
            if "text2vec-transformers" in meta.get("modules", {}):
                logger.info("Using text2vec-transformers vectorizer")
                vectorizer_config = Configure.Vectorizer.text2vec_transformers(
                    pooling_strategy="masked_mean"
                )
            else:
                logger.warning(
                    "text2vec-transformers not available, creating collection without vectorizer"
                )
        except Exception as e:
            logger.warning(f"Failed to check vectorizer availability: {e}")
            pass  # Use no vectorizer for basic testcontainers

        create_args = {
            "name": collection_name,
            "properties": [
                # Core chunk identity
                Property(name="chunk_id", data_type=DataType.TEXT),
                Property(name="parent_uid", data_type=DataType.TEXT),
                Property(name="source", data_type=DataType.TEXT),
                Property(name="chunk_idx", data_type=DataType.INT),
                # Content
                Property(name="text", data_type=DataType.TEXT),
                # Inherited metadata from parent
                Property(name="title", data_type=DataType.TEXT),
                Property(name="published_at", data_type=DataType.DATE),
                # Chunking metadata
                Property(name="tokens", data_type=DataType.INT),
                Property(name="section", data_type=DataType.TEXT),
                # Additional metadata (generic for multi-source compatibility)
                Property(
                    name="meta",
                    data_type=DataType.OBJECT,
                    nested_properties=[
                        # Chunking metadata (common to all sources)
                        Property(name="chunker_version", data_type=DataType.TEXT),
                        Property(name="chunk_strategy", data_type=DataType.TEXT),
                        Property(name="n_sentences", data_type=DataType.INT),
                        Property(name="legacy_chunk_id", data_type=DataType.TEXT),
                        Property(name="quality_total", data_type=DataType.NUMBER),
                        # Generic temporal metadata (compatible across sources)
                        Property(name="year", data_type=DataType.INT),
                        Property(name="language", data_type=DataType.TEXT),
                        # Source-specific metadata stored as flexible fields
                        Property(
                            name="source_detail", data_type=DataType.TEXT
                        ),  # JSON string for source-specific data
                    ],
                ),
            ],
        }

        if vectorizer_config:
            create_args["vectorizer_config"] = vectorizer_config

        self.weaviate_client.client.collections.create(**create_args)

        logger.info(
            "DocumentChunk collection created successfully", collection=collection_name
        )

    async def store_document_chunks(self, document: Document) -> list[str]:
        """
        Store document as chunks in vector store.

        Args:
            document: Document to chunk and store

        Returns:
            List of Weaviate UUIDs for stored chunks
        """
        if not self._initialized:
            await self.initialize()

        logger.info("Storing document chunks", document_uid=document.uid)

        # Chunk the document
        chunks = self.chunker.chunk_document(document)

        if not chunks:
            logger.warning(
                "No chunks generated for document", document_uid=document.uid
            )
            return []

        # Store chunks in Weaviate
        collection = self.weaviate_client.client.collections.get("DocumentChunk")
        chunk_uuids = []

        for chunk in chunks:
            chunk_data = {
                "chunk_id": chunk.chunk_id,
                "parent_uid": chunk.parent_uid,
                "source": chunk.source,
                "chunk_idx": chunk.chunk_idx,
                "text": chunk.text,
                "title": chunk.title,
                "published_at": chunk.published_at.isoformat()
                if chunk.published_at
                else None,
                "tokens": chunk.tokens,
                "section": chunk.section,
                "meta": chunk.meta,
            }

            # Store chunk - Weaviate will automatically generate embeddings
            uuid = collection.data.insert(properties=chunk_data)
            chunk_uuids.append(str(uuid))

            logger.debug(
                "Chunk stored in Weaviate",
                chunk_id=chunk.chunk_id,
                uuid=str(uuid),
                tokens=chunk.tokens,
            )

        logger.info(
            "Document chunks stored successfully",
            document_uid=document.uid,
            chunk_count=len(chunk_uuids),
        )

        return chunk_uuids

    async def search_chunks(
        self,
        query: str,
        limit: int = 5,
        search_mode: str = "semantic",
        alpha: float = 0.5,
        filters: dict | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search chunks using different search modes.

        Args:
            query: Search query text
            limit: Maximum number of chunks to return
            search_mode: 'semantic', 'bm25', or 'hybrid'
            alpha: Hybrid search balance (0.0=BM25, 1.0=semantic)
            filters: Additional filters for search

        Returns:
            List of matching chunk results with metadata
        """
        if not self._initialized:
            await self.initialize()

        collection = self.weaviate_client.client.collections.get("DocumentChunk")

        logger.debug(
            "Performing chunk search",
            query=query,
            search_mode=search_mode,
            limit=limit,
            alpha=alpha,
        )

        # Convert filters to Weaviate format if provided
        weaviate_filter = None
        if filters:
            weaviate_filter = self._convert_filters_to_weaviate(filters)

        from weaviate.classes.query import MetadataQuery

        # Execute search based on mode
        if search_mode == "bm25":
            # Pure BM25 keyword search
            if weaviate_filter:
                response = collection.query.bm25(
                    query=query,
                    limit=limit,
                    filters=weaviate_filter,
                    return_metadata=MetadataQuery(score=True),
                )
            else:
                response = collection.query.bm25(
                    query=query, limit=limit, return_metadata=MetadataQuery(score=True)
                )
        elif search_mode == "hybrid":
            # Hybrid search combining BM25 and vector similarity
            if weaviate_filter:
                response = collection.query.hybrid(
                    query=query,
                    alpha=alpha,  # 0.0=pure BM25, 1.0=pure vector
                    limit=limit,
                    filters=weaviate_filter,
                    return_metadata=MetadataQuery(score=True, explain_score=True),
                )
            else:
                response = collection.query.hybrid(
                    query=query,
                    alpha=alpha,  # 0.0=pure BM25, 1.0=pure vector
                    limit=limit,
                    return_metadata=MetadataQuery(score=True, explain_score=True),
                )
        else:  # semantic (default)
            # Pure semantic search with vectors
            if weaviate_filter:
                response = collection.query.near_text(
                    query=query,
                    limit=limit,
                    filters=weaviate_filter,
                    return_metadata=MetadataQuery(score=True, distance=True),
                )
            else:
                response = collection.query.near_text(
                    query=query,
                    limit=limit,
                    return_metadata=MetadataQuery(score=True, distance=True),
                )

        # Convert results to standard format
        results = []
        for obj in response.objects:
            result = {
                "chunk_id": obj.properties["chunk_id"],
                "parent_uid": obj.properties["parent_uid"],
                "source": obj.properties["source"],
                "chunk_idx": obj.properties["chunk_idx"],
                "text": obj.properties["text"],
                "title": obj.properties.get("title", ""),
                "section": obj.properties.get("section", ""),
                "tokens": obj.properties.get("tokens", 0),
                "published_at": obj.properties.get("published_at"),
                "meta": obj.properties.get("meta", {}),
                "uuid": str(obj.uuid),
            }

            # Add search metadata
            if hasattr(obj.metadata, "score") and obj.metadata.score is not None:
                result["score"] = obj.metadata.score
            if hasattr(obj.metadata, "distance") and obj.metadata.distance is not None:
                result["distance"] = obj.metadata.distance
            if hasattr(obj.metadata, "explain_score"):
                result["explain_score"] = obj.metadata.explain_score

            results.append(result)

        logger.debug("Chunk search completed", query=query, results_found=len(results))

        return results

    async def get_chunk_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """
        Get a specific chunk by its chunk_id.

        Args:
            chunk_id: The chunk_id to search for

        Returns:
            Chunk data if found, None otherwise
        """
        if not self._initialized:
            await self.initialize()

        collection = self.weaviate_client.client.collections.get("DocumentChunk")

        from weaviate.classes.query import Filter

        response = collection.query.fetch_objects(
            filters=Filter.by_property("chunk_id").equal(chunk_id), limit=1
        )

        if response.objects:
            obj = response.objects[0]
            return {
                "chunk_id": obj.properties["chunk_id"],
                "parent_uid": obj.properties["parent_uid"],
                "source": obj.properties["source"],
                "chunk_idx": obj.properties["chunk_idx"],
                "text": obj.properties["text"],
                "title": obj.properties.get("title", ""),
                "section": obj.properties.get("section", ""),
                "tokens": obj.properties.get("tokens", 0),
                "published_at": obj.properties.get("published_at"),
                "meta": obj.properties.get("meta", {}),
                "uuid": str(obj.uuid),
            }

        return None

    def _convert_filters_to_weaviate(self, filters: dict) -> Any:
        """Convert generic filters to Weaviate filter format."""
        # This would need to be implemented based on specific filter requirements
        # For now, return None to disable filtering
        logger.warning("Filter conversion not yet implemented", filters=filters)
        return None

    async def health_check(self) -> dict[str, Any]:
        """Check health of embedding service."""
        try:
            if not self._initialized or not self.weaviate_client:
                return {"status": "error", "message": "Service not initialized"}

            health = await self.weaviate_client.health_check()

            # Check if chunk collection exists
            chunk_collection_exists = self.weaviate_client.client.collections.exists(
                "DocumentChunk"
            )

            return {
                "status": "healthy"
                if health.get("status") == "healthy" and chunk_collection_exists
                else "degraded",
                "weaviate": health,
                "chunk_collection_exists": chunk_collection_exists,
                "chunker_available": self.chunker is not None,
            }
        except Exception as e:
            return {"status": "error", "message": f"Health check failed: {e!s}"}
