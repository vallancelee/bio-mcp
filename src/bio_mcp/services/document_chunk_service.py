"""
Document chunking service for DocumentChunk_v2 with Weaviate OpenAI vectorizer.

This service handles document chunking and storage, while Weaviate manages
OpenAI embeddings through its text2vec-openai module.
"""

from __future__ import annotations

from typing import Any

from weaviate.classes.query import Filter, MetadataQuery

from bio_mcp.config.config import config
from bio_mcp.config.logging_config import get_logger
from bio_mcp.models.document import Document
from bio_mcp.services.chunking import AbstractChunker, ChunkingConfig
from bio_mcp.services.weaviate_schema import CollectionConfig, WeaviateSchemaManager
from bio_mcp.shared.clients.weaviate_client import WeaviateClient, get_weaviate_client

logger = get_logger(__name__)


class DocumentChunkService:
    """Document chunking and storage service with Weaviate OpenAI vectorizer."""

    def __init__(
        self,
        weaviate_client: WeaviateClient | None = None,
        collection_name: str | None = None,
    ):
        self.config = config
        self.weaviate_client = weaviate_client
        self.collection_name = collection_name or self.config.weaviate_collection_v2
        # Initialize chunking service with config
        chunking_config = ChunkingConfig(
            target_tokens=self.config.chunker_target_tokens,
            max_tokens=self.config.chunker_max_tokens,
            min_tokens=self.config.chunker_min_tokens,
            overlap_tokens=self.config.chunker_overlap_tokens,
            chunker_version=self.config.chunker_version,
        )
        self.chunking_service = AbstractChunker(chunking_config)
        self.schema_manager = None
        self._initialized = False

    async def connect(self) -> None:
        """Connect to Weaviate with proper error handling."""
        if self._initialized:
            return

        try:
            if not self.weaviate_client:
                self.weaviate_client = get_weaviate_client()

            await self.weaviate_client.initialize()

            logger.info("Connected to Weaviate successfully")

            # Create schema manager
            self.schema_manager = WeaviateSchemaManager(
                self.weaviate_client.client, CollectionConfig(name=self.collection_name)
            )

            # Create collection if it doesn't exist
            if not self.weaviate_client.client.collections.exists(self.collection_name):
                logger.info(
                    f"Collection {self.collection_name} doesn't exist, creating it..."
                )
                success = (
                    await self.schema_manager.create_document_chunk_v2_collection()
                )
                if not success:
                    raise RuntimeError(
                        f"Failed to create collection {self.collection_name}"
                    )

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Weaviate."""
        if self.weaviate_client:
            await self.weaviate_client.close()
            self.weaviate_client = None
        self._initialized = False

    def _build_chunk_metadata(
        self, document: Document, chunk_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Build complete metadata for chunk storage."""
        # Start with chunking metadata
        meta = {
            "chunker_version": self.config.chunker_version,
            "vectorizer": "text2vec-openai",
            "model": self.config.openai_embedding_model,
            **chunk_metadata,
        }

        # Add source-specific metadata
        if document.source == "pubmed":
            meta["src"] = {
                "pubmed": {
                    **document.detail,
                    "identifiers": document.identifiers,
                    "authors": document.authors or [],
                    "provenance": document.provenance,
                }
            }
        else:
            # Generic source handling
            meta["src"] = {
                document.source: {
                    **document.detail,
                    "identifiers": document.identifiers,
                    "authors": document.authors or [],
                    "provenance": document.provenance,
                }
            }

        return meta

    def _convert_filters_to_weaviate(self, filters: dict) -> list[Filter]:
        """
        Convert generic filters dict to Weaviate Filter objects.

        Supports various filter formats:
        - Simple equality: {"section": "Background"}
        - Multiple values: {"source": ["pubmed", "ctgov"]}
        - Range filters: {"year": {"gte": 2020, "lte": 2024}}
        - Quality filters: {"quality": {"gte": 0.8}}
        """
        conditions = []

        for field, value in filters.items():
            if isinstance(value, str | int | float):
                # Simple equality filter
                conditions.append(Filter.by_property(field).equal(value))
            elif isinstance(value, list):
                # Multiple values - use any_of
                field_conditions = [Filter.by_property(field).equal(v) for v in value]
                if len(field_conditions) == 1:
                    conditions.append(field_conditions[0])
                else:
                    conditions.append(Filter.any_of(field_conditions))
            elif isinstance(value, dict):
                # Range filters
                if "gte" in value:
                    conditions.append(
                        Filter.by_property(field).greater_or_equal(value["gte"])
                    )
                if "gt" in value:
                    conditions.append(
                        Filter.by_property(field).greater_than(value["gt"])
                    )
                if "lte" in value:
                    conditions.append(
                        Filter.by_property(field).less_or_equal(value["lte"])
                    )
                if "lt" in value:
                    conditions.append(Filter.by_property(field).less_than(value["lt"]))
                if "eq" in value:
                    conditions.append(Filter.by_property(field).equal(value["eq"]))

        return conditions

    async def store_document_chunks(
        self, document: Document, quality_score: float | None = None
    ) -> list[str]:
        """
        Chunk document and store in Weaviate with deterministic UUIDs.
        Returns list of chunk UUIDs for tracking.
        """
        if not self._initialized:
            await self.connect()

        try:
            # Generate chunks
            chunks = self.chunking_service.chunk_document(document)

            if not chunks:
                logger.warning(f"No chunks generated for document {document.uid}")
                return []

            collection = self.weaviate_client.client.collections.get(
                self.collection_name
            )
            chunk_uuids = []

            for chunk in chunks:
                # Build complete metadata
                chunk.meta = self._build_chunk_metadata(document, chunk.meta or {})

                # Prepare properties for Weaviate
                properties = {
                    "parent_uid": chunk.parent_uid,
                    "source": chunk.source,
                    "section": chunk.section or "Unstructured",
                    "title": chunk.title or "",
                    "text": chunk.text,
                    "published_at": (
                        document.published_at.isoformat() + "Z"
                        if document.published_at and document.published_at.tzinfo is None
                        else document.published_at.isoformat()
                    )
                    if document.published_at
                    else None,
                    "year": document.published_at.year
                    if document.published_at
                    else None,
                    "tokens": chunk.tokens,
                    "n_sentences": chunk.n_sentences,
                    "quality_total": quality_score or 0.0,
                    "meta": chunk.meta,
                }

                # Remove None values and ensure object fields have content
                properties = {k: v for k, v in properties.items() if v is not None}

                # Ensure nested objects have content (Weaviate requirement)
                if properties.get("meta"):
                    # Clean up empty nested objects
                    meta = properties["meta"]
                    if "src" in meta:
                        for source_key, source_data in list(meta["src"].items()):
                            if isinstance(source_data, dict):
                                # Remove empty dict fields or add default content
                                cleaned_source = {}
                                for k, v in source_data.items():
                                    if v is not None and v != {} and v != []:
                                        cleaned_source[k] = v

                                # If provenance is empty, add a default
                                if (
                                    "provenance" not in cleaned_source
                                    or not cleaned_source.get("provenance")
                                ):
                                    cleaned_source["provenance"] = {
                                        "ingestion_source": "bio-mcp-v2"
                                    }

                                meta["src"][source_key] = cleaned_source

                # Insert with deterministic UUID (idempotent)
                try:
                    collection.data.insert(uuid=chunk.uuid, properties=properties)
                    chunk_uuids.append(chunk.uuid)
                    logger.debug(
                        f"Stored chunk {chunk.uuid} for document {document.uid}"
                    )

                except Exception as e:
                    # Check if this is a "already exists" error (idempotent behavior)
                    error_msg = str(e).lower()
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        # This is expected for idempotent storage
                        chunk_uuids.append(chunk.uuid)
                        logger.debug(f"Chunk {chunk.uuid} already exists (idempotent)")
                    else:
                        logger.error(f"Failed to store chunk {chunk.uuid}: {e}")
                        # Continue with other chunks

            logger.info(f"Stored {len(chunk_uuids)} chunks for document {document.uid}")
            return chunk_uuids

        except Exception as e:
            logger.error(f"Failed to store document chunks for {document.uid}: {e}")
            raise

    async def search_chunks(
        self,
        query: str,
        limit: int = 10,
        search_mode: str = "hybrid",
        alpha: float = 0.5,
        filters: dict | None = None,
        # Specific filters for convenience (maintained for backward compatibility)
        source_filter: str | None = None,
        year_filter: tuple[int, int] | None = None,
        section_filter: list[str] | None = None,
        quality_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search chunks using different search modes with filtering and quality boosting.

        Args:
            query: Search query text
            limit: Maximum number of chunks to return
            search_mode: 'semantic', 'bm25', or 'hybrid' (default)
            alpha: Hybrid search balance (0.0=pure BM25, 1.0=pure vector)
            filters: Generic filters dict for flexible filtering
            source_filter: Filter by source (convenience parameter)
            year_filter: Filter by year range (convenience parameter)
            section_filter: Filter by sections (convenience parameter)
            quality_threshold: Filter by quality threshold (convenience parameter)

        Returns:
            List of matching chunk results with metadata
        """
        if not self._initialized:
            await self.connect()

        try:
            collection = self.weaviate_client.client.collections.get(
                self.collection_name
            )

            # Build filter conditions from both generic filters and specific filters
            where_conditions = []

            # Process generic filters first
            if filters:
                generic_conditions = self._convert_filters_to_weaviate(filters)
                if generic_conditions:
                    where_conditions.extend(generic_conditions)

            if source_filter:
                where_conditions.append(
                    Filter.by_property("source").equal(source_filter)
                )

            if year_filter:
                start_year, end_year = year_filter
                where_conditions.append(
                    Filter.by_property("year").greater_or_equal(start_year)
                )
                where_conditions.append(
                    Filter.by_property("year").less_or_equal(end_year)
                )

            if section_filter:
                section_conditions = [
                    Filter.by_property("section").equal(section)
                    for section in section_filter
                ]
                if len(section_conditions) == 1:
                    where_conditions.append(section_conditions[0])
                else:
                    where_conditions.append(Filter.any_of(section_conditions))

            if quality_threshold:
                where_conditions.append(
                    Filter.by_property("quality_total").greater_or_equal(
                        quality_threshold
                    )
                )

            # Combine conditions
            where_filter = None
            if where_conditions:
                if len(where_conditions) == 1:
                    where_filter = where_conditions[0]
                else:
                    where_filter = Filter.all_of(where_conditions)

            # Execute search based on mode with proper server-side filtering
            if search_mode == "bm25":
                # Pure BM25 keyword search
                if where_filter:
                    response = collection.query.bm25(
                        query=query,
                        filters=where_filter,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True),
                    )
                else:
                    response = collection.query.bm25(
                        query=query,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True),
                    )
            elif search_mode == "semantic":
                # Pure semantic search with vectors
                if where_filter:
                    response = collection.query.near_text(
                        query=query,
                        filters=where_filter,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True, distance=True),
                    )
                else:
                    response = collection.query.near_text(
                        query=query,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True, distance=True),
                    )
            else:  # hybrid (default)
                # Hybrid search combining BM25 and vector similarity
                if where_filter:
                    response = collection.query.hybrid(
                        query=query,
                        alpha=alpha,
                        filters=where_filter,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True, distance=True),
                    )
                else:
                    response = collection.query.hybrid(
                        query=query,
                        alpha=alpha,
                        limit=limit,
                        return_metadata=MetadataQuery(score=True, distance=True),
                    )

            # Process results with enhanced quality boosting
            results = []
            for item in response.objects:
                # Apply enhanced section boost
                section_boost = self._get_section_boost(
                    item.properties.get("section", "")
                )

                # Apply quality boost
                quality_total = item.properties.get("quality_total", 0.0)
                quality_boost = quality_total * float(self.config.quality_boost_factor)

                # Apply recency boost
                recency_boost = self._get_recency_boost(item.properties.get("year"))

                # Calculate final score
                base_score = item.metadata.score or 0.0

                # Handle Weaviate's different score formats
                if base_score == 0.0:
                    # For semantic search, Weaviate returns distance instead of score
                    distance = getattr(item.metadata, "distance", None)
                    if distance is not None:
                        # Convert distance (0-2 range) to similarity score (0-1 range)
                        # Lower distance = higher similarity
                        base_score = max(0.0, 1.0 - (distance / 2.0))
                    else:
                        # For BM25 or other searches, use minimal base score
                        # so quality boosting still has an effect
                        base_score = 0.1

                final_score = base_score * (
                    1 + section_boost + quality_boost + recency_boost
                )

                result = {
                    "uuid": str(item.uuid),
                    "parent_uid": item.properties.get("parent_uid"),
                    "source": item.properties.get("source"),
                    "title": item.properties.get("title"),
                    "text": item.properties.get("text"),
                    "section": item.properties.get("section"),
                    "published_at": item.properties.get("published_at"),
                    "year": item.properties.get("year"),
                    "tokens": item.properties.get("tokens"),
                    "quality_total": quality_total,
                    "score": final_score,
                    "base_score": base_score,
                    "section_boost": section_boost,
                    "quality_boost": quality_boost,
                    "recency_boost": recency_boost,
                    "meta": item.properties.get("meta", {}),
                }
                results.append(result)

            # Re-sort by final score
            results.sort(key=lambda x: x["score"], reverse=True)

            logger.info(f"Found {len(results)} chunks for query: '{query[:50]}...'")
            return results

        except Exception as e:
            logger.error(f"Failed to search chunks: {e}")
            raise

    def _get_section_boost(self, section: str) -> float:
        """Get boost factor for document section."""
        section_weights = {
            "Results": float(self.config.boost_results_section),
            "Conclusions": float(self.config.boost_conclusions_section),
            "Methods": float(self.config.boost_methods_section),
            "Background": float(self.config.boost_background_section),
            "Unstructured": 0.0,
            "Other": 0.0,
        }
        return section_weights.get(section, 0.0)

    def _get_recency_boost(self, year: int | None) -> float:
        """Get boost factor for document recency."""
        if not year or not isinstance(year, int):
            return 0.0

        from datetime import datetime

        current_year = datetime.now().year
        years_old = current_year - year

        if years_old <= int(self.config.recency_recent_years):
            return 0.1  # Strong boost for very recent
        elif years_old <= int(self.config.recency_moderate_years):
            return 0.05  # Moderate boost for recent
        elif years_old <= int(self.config.recency_old_years):
            return 0.02  # Small boost for somewhat recent
        else:
            return 0.0  # No boost for old documents

    async def get_chunk_by_uuid(self, chunk_uuid: str) -> dict[str, Any] | None:
        """Retrieve a specific chunk by UUID."""
        if not self._initialized:
            await self.connect()

        try:
            collection = self.weaviate_client.client.collections.get(
                self.collection_name
            )

            response = collection.query.fetch_object_by_id(chunk_uuid)

            if response:
                return {
                    "uuid": str(response.uuid),
                    "parent_uid": response.properties.get("parent_uid"),
                    "source": response.properties.get("source"),
                    "title": response.properties.get("title"),
                    "text": response.properties.get("text"),
                    "section": response.properties.get("section"),
                    "published_at": response.properties.get("published_at"),
                    "year": response.properties.get("year"),
                    "tokens": response.properties.get("tokens"),
                    "quality_total": response.properties.get("quality_total"),
                    "meta": response.properties.get("meta", {}),
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get chunk {chunk_uuid}: {e}")
            return None

    async def delete_document_chunks(self, parent_uid: str) -> int:
        """Delete all chunks for a document. Returns count of deleted chunks."""
        if not self._initialized:
            await self.connect()

        try:
            collection = self.weaviate_client.client.collections.get(
                self.collection_name
            )

            # Use delete_many directly without counting first
            try:
                result = collection.data.delete_many(
                    where=Filter.by_property("parent_uid").equal(parent_uid)
                )

                # Check if result has information about deleted objects
                if hasattr(result, "successful") and hasattr(result, "objects"):
                    chunk_count = (
                        len(result.objects) if result.objects else result.successful
                    )
                else:
                    # Fallback: assume successful if no error
                    chunk_count = 1 if result else 0

                if chunk_count > 0:
                    logger.info(
                        f"Deleted {chunk_count} chunks for document {parent_uid}"
                    )

                return chunk_count

            except Exception as delete_error:
                logger.warning(f"Delete operation encountered error: {delete_error}")
                # Try alternative approach: search and delete individual objects
                try:
                    search_response = collection.query.bm25(
                        query=parent_uid,  # Search for parent_uid in text
                        limit=1000,
                    )

                    individual_deletes = 0
                    for obj in search_response.objects:
                        if obj.properties.get("parent_uid") == parent_uid:
                            try:
                                collection.data.delete_by_id(obj.uuid)
                                individual_deletes += 1
                            except Exception:
                                continue

                    logger.info(
                        f"Deleted {individual_deletes} chunks individually for document {parent_uid}"
                    )
                    return individual_deletes

                except Exception as fallback_error:
                    logger.error(f"Both delete approaches failed: {fallback_error}")
                    return 0

        except Exception as e:
            logger.error(f"Failed to delete chunks for document {parent_uid}: {e}")
            raise

    async def get_collection_stats(self) -> dict[str, Any]:
        """Get collection statistics for monitoring."""
        if not self._initialized:
            await self.connect()

        try:
            collection = self.weaviate_client.client.collections.get(
                self.collection_name
            )

            # Get total count
            aggregate_response = collection.aggregate.over_all(total_count=True)
            total_count = aggregate_response.total_count

            # Get source breakdown
            source_response = collection.aggregate.over_all(group_by="source")

            source_counts = {}
            for group in source_response.groups:
                # Handle GroupedBy object properly
                try:
                    # GroupedBy object has a 'value' attribute containing the actual grouped value
                    if hasattr(group.grouped_by, "value"):
                        source = group.grouped_by.value
                    elif isinstance(group.grouped_by, dict):
                        source = group.grouped_by.get("source", "unknown")
                    else:
                        # Last resort: convert to string
                        source = str(group.grouped_by)

                    count = group.total_count
                    source_counts[source] = count
                except Exception as e:
                    logger.warning(
                        f"Failed to parse group: {e}, group: {group.grouped_by}"
                    )
                    # Skip this group rather than failing completely
                    continue

            return {
                "total_chunks": total_count,
                "source_breakdown": source_counts,
                "collection_name": self.collection_name,
                "model_name": self.config.openai_embedding_model,
            }

        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}

    async def health_check(self) -> dict[str, Any]:
        """Check health of embedding service with OpenAI vectorizer testing."""
        try:
            if not self._initialized:
                await self.connect()

            # Test basic connectivity
            if not self.weaviate_client.client.is_ready():
                return {"status": "unhealthy", "error": "Weaviate client not ready"}

            # Test collection access
            if not self.weaviate_client.client.collections.exists(self.collection_name):
                return {
                    "status": "unhealthy",
                    "error": f"Collection {self.collection_name} does not exist",
                }

            collection = self.weaviate_client.client.collections.get(
                self.collection_name
            )

            # Test OpenAI embedding generation by inserting a test document
            embeddings_working = True
            embedding_error = None

            if self.config.openai_api_key:
                try:
                    # Create test document for embedding verification
                    test_doc = Document(
                        uid="health:test",
                        source="health_check",
                        title="Health Check Test",
                        text="Diabetes mellitus treatment with metformin therapy",
                    )

                    # Generate single chunk and store it
                    chunks = self.chunking_service.chunk_document(test_doc)
                    if chunks:
                        test_chunk = chunks[0]
                        test_properties = {
                            "parent_uid": test_chunk.parent_uid,
                            "source": "health_check",
                            "title": "Health Check Test",
                            "text": test_chunk.text,
                            "section": "Test",
                            "tokens": test_chunk.tokens,
                            "n_sentences": test_chunk.n_sentences,
                            "quality_total": 1.0,
                            "meta": {"chunker_version": self.config.chunker_version},
                        }

                        # Insert test chunk (will generate embedding)
                        collection.data.insert(
                            uuid=test_chunk.uuid, properties=test_properties
                        )

                        # Verify embedding was generated
                        retrieved = collection.query.fetch_object_by_id(
                            test_chunk.uuid, include_vector=True
                        )

                        if not retrieved or not retrieved.vector:
                            embeddings_working = False
                            embedding_error = "No vector generated for test document"
                        elif len(retrieved.vector) != (
                            self.config.openai_embedding_dimensions or 1536
                        ):
                            embeddings_working = False
                            embedding_error = f"Vector dimension mismatch: expected {self.config.openai_embedding_dimensions or 1536}, got {len(retrieved.vector)}"

                        # Clean up test document
                        collection.data.delete_by_id(test_chunk.uuid)

                except Exception as e:
                    embeddings_working = False
                    embedding_error = f"Embedding test failed: {e!s}"
            else:
                embeddings_working = False
                embedding_error = (
                    "OpenAI API key not configured - falling back to BM25-only search"
                )

            # Get basic stats
            stats = await self.get_collection_stats()

            health_status = {
                "status": "healthy" if embeddings_working else "degraded",
                "collection": self.collection_name,
                "total_chunks": stats.get("total_chunks", 0),
                "sources": list(stats.get("source_breakdown", {}).keys()),
                "vectorizer": "text2vec-openai"
                if embeddings_working
                else "none (BM25-only)",
                "model": self.config.openai_embedding_model,
                "dimensions": self.config.openai_embedding_dimensions,
                "embeddings_working": embeddings_working,
            }

            if embedding_error:
                health_status["embedding_error"] = embedding_error

            return health_status

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    # Legacy compatibility methods
    async def initialize(self) -> None:
        """Initialize the embedding service (legacy compatibility)."""
        await self.connect()
