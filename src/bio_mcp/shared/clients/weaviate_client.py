"""
Weaviate client for Bio-MCP server.
Vector storage and semantic search with local transformers.
"""

from typing import Any

import weaviate
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.query import MetadataQuery

from bio_mcp.config.config import config
from bio_mcp.config.logging_config import get_logger

logger = get_logger(__name__)


class WeaviateClient:
    """Client for Weaviate vector database operations."""
    
    def __init__(self, url: str | None = None):
        self.url = url or config.weaviate_url
        self.client: weaviate.WeaviateClient | None = None
        self.collection_name = "PubMedDocument"
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Weaviate client and ensure schema exists."""
        if self._initialized:
            return
        
        logger.info("Initializing Weaviate client", url=self.url)
        
        try:
            logger.debug("Connecting to Weaviate", url=self.url)
            # Use the provided URL instead of hardcoded localhost
            if self.url.startswith("http://localhost:8080"):
                self.client = weaviate.connect_to_local()
            else:
                # Parse URL components
                host = self.url.split("://")[1].split(":")[0]
                port = int(self.url.split(":")[-1])
                secure = self.url.startswith("https")
                
                # Use dynamic gRPC settings if available (for testcontainers)
                grpc_host = getattr(self, '_grpc_host', host)
                grpc_port = getattr(self, '_grpc_port', 50051)
                
                self.client = weaviate.connect_to_custom(
                    http_host=host,
                    http_port=port,
                    http_secure=secure,
                    grpc_host=grpc_host,
                    grpc_port=grpc_port,
                    grpc_secure=secure
                )
            
            logger.debug("Testing Weaviate connection")
            meta = self.client.get_meta()
            logger.debug("Weaviate meta", meta=meta)
            
            await self._ensure_collection_exists()
            
            self._initialized = True
            logger.info("Weaviate client initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Weaviate client", error=str(e))
            raise

    async def close(self) -> None:
        """Close Weaviate client connection."""
        if self.client:
            self.client.close()
            self.client = None
            self._initialized = False
            logger.info("Weaviate client closed")

    async def _ensure_collection_exists(self) -> None:
        """Ensure the PubMedDocument collection exists with proper schema."""
        if not self.client:
            raise RuntimeError("Weaviate client not initialized")
        
        collection_name = self.collection_name
        
        # Check if collection exists
        if self.client.collections.exists(collection_name):
            logger.debug("Weaviate collection already exists", collection=collection_name)
            return
        
        # Create collection with schema
        logger.info("Creating Weaviate collection", collection=collection_name)
        
        # Check if we should use vectorizer (disable for test containers without transformers)
        vectorizer_config = None
        try:
            # Test if transformers module is available
            meta = self.client.get_meta()
            modules = meta.get("modules", {})
            if "text2vec-transformers" in modules:
                vectorizer_config = Configure.Vectorizer.text2vec_transformers()
        except Exception:
            pass  # Use no vectorizer for basic testcontainers
        
        create_args = {
            "name": collection_name,
            "properties": [
                Property(name="pmid", data_type=DataType.TEXT),
                Property(name="title", data_type=DataType.TEXT),
                Property(name="abstract", data_type=DataType.TEXT),
                Property(name="authors", data_type=DataType.TEXT_ARRAY),
                Property(name="journal", data_type=DataType.TEXT),
                Property(name="publication_date", data_type=DataType.DATE),
                Property(name="doi", data_type=DataType.TEXT),
                Property(name="keywords", data_type=DataType.TEXT_ARRAY),
                Property(name="content", data_type=DataType.TEXT),  # Combined searchable content
            ],
            "description": "PubMed documents for biomedical research"
        }
        
        if vectorizer_config:
            create_args["vectorizer_config"] = vectorizer_config
        
        self.client.collections.create(**create_args)
        
        logger.info("Weaviate collection created successfully", collection=collection_name)

    async def store_document(self, pmid: str, title: str, abstract: str | None = None, 
                           authors: list[str] | None = None, journal: str | None = None,
                           publication_date: str | None = None, doi: str | None = None, 
                           keywords: list[str] | None = None) -> str:
        """Store a document with its embedding in Weaviate."""
        if not self._initialized:
            await self.initialize()
        
        collection = self.client.collections.get(self.collection_name)
        
        # Create combined searchable content
        content_parts = [title or ""]
        if abstract:
            content_parts.append(abstract)
        if authors:
            content_parts.append(" ".join(authors))
        if journal:
            content_parts.append(journal)
        content = " ".join(content_parts).strip()
        
        formatted_date = None
        if publication_date:
            if isinstance(publication_date, str) and 'T' not in publication_date:
                formatted_date = f"{publication_date}T00:00:00Z"
            else:
                formatted_date = publication_date
        
        doc_data = {
            "pmid": pmid,
            "title": title or "",
            "abstract": abstract or "",
            "authors": authors or [],
            "journal": journal or "",
            "publication_date": formatted_date,
            "doi": doi or "",
            "keywords": keywords or [],
            "content": content
        }
        
        # Store document - Weaviate will automatically generate embeddings
        uuid = collection.data.insert(properties=doc_data)
        
        logger.debug("Document stored in Weaviate", pmid=pmid, uuid=str(uuid))
        return str(uuid)

    async def search_documents(self, query: str, limit: int = 5, search_mode: str = "semantic", 
                             alpha: float = 0.5, filters: dict | None = None) -> list[dict[str, Any]]:
        """Search documents using different search modes.
        
        Args:
            query: Search query text
            limit: Maximum number of results to return
            search_mode: 'semantic', 'bm25', or 'hybrid'
            alpha: Weighting for hybrid search (0.0=pure BM25, 1.0=pure vector)
            filters: Metadata filters for date ranges, journals, etc.
            
        Returns:
            List of search results with scores and metadata
        """
        if not self._initialized:
            await self.initialize()
        
        collection = self.client.collections.get(self.collection_name)
        
        logger.debug("Performing search", query=query[:50], limit=limit, mode=search_mode, alpha=alpha, filters=filters)
        
        # Build Weaviate filters if provided
        weaviate_filter = self._build_weaviate_filter(filters) if filters else None
        
        if search_mode == "bm25":
            # Pure BM25 keyword search
            if weaviate_filter:
                response = collection.query.bm25(
                    query=query,
                    limit=limit,
                    filters=weaviate_filter,
                    return_metadata=MetadataQuery(score=True)
                )
            else:
                response = collection.query.bm25(
                    query=query,
                    limit=limit,
                    return_metadata=MetadataQuery(score=True)
                )
        elif search_mode == "hybrid":
            # Hybrid search combining BM25 and vector similarity
            if weaviate_filter:
                response = collection.query.hybrid(
                    query=query,
                    alpha=alpha,  # 0.0=pure BM25, 1.0=pure vector
                    limit=limit,
                    filters=weaviate_filter,
                    return_metadata=MetadataQuery(score=True, explain_score=True)
                )
            else:
                response = collection.query.hybrid(
                    query=query,
                    alpha=alpha,  # 0.0=pure BM25, 1.0=pure vector
                    limit=limit,
                    return_metadata=MetadataQuery(score=True, explain_score=True)
                )
        else:  # semantic (default)
            # Pure semantic search with vectors
            if weaviate_filter:
                response = collection.query.near_text(
                    query=query,
                    limit=limit,
                    filters=weaviate_filter,
                    return_metadata=MetadataQuery(score=True, distance=True)
                )
            else:
                response = collection.query.near_text(
                    query=query,
                    limit=limit,
                    return_metadata=MetadataQuery(score=True, distance=True)
                )
        
        # Convert response to list of dictionaries
        results = []
        for obj in response.objects:
            # Use scores and distances as returned by Weaviate
            score = getattr(obj.metadata, 'score', None)
            distance = getattr(obj.metadata, 'distance', None)
            
            result = {
                "uuid": str(obj.uuid),
                "score": score,
                "distance": distance,
                **obj.properties
            }
            
            # Add explain_score for hybrid searches if available
            if hasattr(obj.metadata, 'explain_score'):
                result["explain_score"] = obj.metadata.explain_score
                
            results.append(result)
        
        logger.info("Search completed", query=query[:50], mode=search_mode, results_count=len(results))
        return results

    def _build_weaviate_filter(self, filters: dict) -> Any:
        """Build Weaviate filter from metadata filters."""
        from weaviate.classes.query import Filter
        
        filter_conditions = []
        
        # Date range filters
        if filters.get("date_from"):
            try:
                # Convert YYYY-MM-DD to RFC3339 format for Weaviate
                date_from = f"{filters['date_from']}T00:00:00Z"
                filter_conditions.append(
                    Filter.by_property("publication_date").greater_or_equal(date_from)
                )
            except Exception as e:
                logger.warning("Invalid date_from filter", date_from=filters.get("date_from"), error=str(e))
        
        if filters.get("date_to"):
            try:
                # Convert YYYY-MM-DD to RFC3339 format for Weaviate
                date_to = f"{filters['date_to']}T23:59:59Z"
                filter_conditions.append(
                    Filter.by_property("publication_date").less_or_equal(date_to)
                )
            except Exception as e:
                logger.warning("Invalid date_to filter", date_to=filters.get("date_to"), error=str(e))
        
        # Journal filters
        if filters.get("journals") and isinstance(filters["journals"], list):
            # Create OR condition for multiple journals
            journal_conditions = []
            for journal in filters["journals"]:
                if journal and isinstance(journal, str):
                    journal_conditions.append(
                        Filter.by_property("journal").contains_any([journal])
                    )
            
            if journal_conditions:
                if len(journal_conditions) == 1:
                    filter_conditions.append(journal_conditions[0])
                else:
                    # Combine multiple journal conditions with OR
                    combined_journal_filter = journal_conditions[0]
                    for condition in journal_conditions[1:]:
                        combined_journal_filter = combined_journal_filter | condition
                    filter_conditions.append(combined_journal_filter)
        
        # Combine all conditions with AND
        if not filter_conditions:
            return None
        elif len(filter_conditions) == 1:
            return filter_conditions[0]
        else:
            combined_filter = filter_conditions[0]
            for condition in filter_conditions[1:]:
                combined_filter = combined_filter & condition
            return combined_filter

    async def get_document_by_pmid(self, pmid: str) -> dict[str, Any] | None:
        """Get a document by its PMID."""
        if not self._initialized:
            await self.initialize()
        
        collection = self.client.collections.get(self.collection_name)
        
        # Use Weaviate v4 query syntax
        from weaviate.classes.query import Filter
        
        response = collection.query.fetch_objects(
            filters=Filter.by_property("pmid").equal(pmid),
            limit=1
        )
        
        if response.objects:
            obj = response.objects[0]
            return {
                "uuid": str(obj.uuid),
                **obj.properties
            }
        
        return None

    async def document_exists(self, pmid: str) -> bool:
        """Check if a document exists by PMID."""
        doc = await self.get_document_by_pmid(pmid)
        return doc is not None

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on Weaviate connection."""
        try:
            if not self.client:
                return {"status": "error", "message": "Client not initialized"}
            
            is_ready = self.client.is_ready()
            collection_exists = self.client.collections.exists(self.collection_name)
            
            return {
                "status": "healthy" if is_ready and collection_exists else "degraded",
                "ready": is_ready,
                "collection_exists": collection_exists,
                "url": self.url
            }
        except Exception as e:
            return {
                "status": "error", 
                "message": str(e),
                "url": self.url
            }


# Global client instance
_weaviate_client: WeaviateClient | None = None


def get_weaviate_client() -> WeaviateClient:
    """Get the global Weaviate client instance."""
    global _weaviate_client
    if _weaviate_client is None:
        _weaviate_client = WeaviateClient()
    return _weaviate_client