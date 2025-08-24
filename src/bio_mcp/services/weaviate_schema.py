"""
Weaviate schema management for DocumentChunk_v2 collection.

This module handles creation, migration, and management of the new
biomedical document chunk collection with BioBERT embeddings.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import weaviate
from weaviate.classes.config import Configure, DataType, Property, Tokenization

from bio_mcp.config.logging_config import get_logger

logger = get_logger(__name__)


class VectorizerType(Enum):
    """Supported vectorizer types."""
    HUGGINGFACE_API = "text2vec-huggingface"
    TRANSFORMERS_LOCAL = "text2vec-transformers"
    OPENAI = "text2vec-openai"


@dataclass
class CollectionConfig:
    """Configuration for DocumentChunk_v2 collection."""
    
    # Collection settings
    name: str = "DocumentChunk_v2"
    description: str = "Biomedical document chunks with BioBERT embeddings"
    
    # Vectorizer settings
    vectorizer_type: VectorizerType = VectorizerType.TRANSFORMERS_LOCAL
    model_name: str = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
    
    # Vector index settings
    ef_construction: int = 200
    max_connections: int = 64
    
    # Performance settings
    shard_count: int = 1
    replication_factor: int = 1


class WeaviateSchemaManager:
    """Manages Weaviate collection schemas."""
    
    def __init__(self, client: weaviate.WeaviateClient, config: CollectionConfig = None):
        self.client = client
        self.config = config or CollectionConfig()
    
    async def create_document_chunk_v2_collection(self) -> bool:
        """Create DocumentChunk_v2 collection with optimized schema."""
        logger.info("Creating DocumentChunk_v2 collection", 
                   vectorizer=self.config.vectorizer_type.value,
                   model=self.config.model_name)
        
        try:
            # Check if collection already exists
            if self.client.collections.exists(self.config.name):
                logger.warning(f"Collection {self.config.name} already exists")
                return False
            
            # Define properties
            properties = self._build_properties()
            
            # Configure vectorizer
            vectorizer_config = self._build_vectorizer_config()
            
            # Create collection
            self.client.collections.create(
                name=self.config.name,
                description=self.config.description,
                properties=properties,
                vector_config=vectorizer_config,
                replication_config=Configure.replication(factor=self.config.replication_factor),
                sharding_config=Configure.sharding(
                    virtual_per_physical=self.config.shard_count,
                    desired_count=self.config.shard_count
                )
            )
            
            logger.info(f"Successfully created collection: {self.config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise
    
    def _build_properties(self) -> list[Property]:
        """Build property schema for document chunks."""
        return [
            # Core identity and relationships
            Property(
                name="parent_uid",
                data_type=DataType.TEXT,
                description="Parent document UID (e.g., pubmed:12345678)",
                index_filterable=True,
                index_searchable=False
            ),
            Property(
                name="source", 
                data_type=DataType.TEXT,
                description="Document source (pubmed, ctgov, etc.)",
                index_filterable=True,
                index_searchable=False
            ),
            
            # Content fields (searchable)
            Property(
                name="title",
                data_type=DataType.TEXT, 
                description="Parent document title",
                index_filterable=False,
                index_searchable=True,
                tokenization=Tokenization.WORD
            ),
            Property(
                name="text",
                data_type=DataType.TEXT,
                description="Chunk text content",
                index_filterable=False,
                index_searchable=True,
                tokenization=Tokenization.WORD
            ),
            Property(
                name="section",
                data_type=DataType.TEXT,
                description="Document section (Background/Methods/Results/Conclusions)",
                index_filterable=True,
                index_searchable=False
            ),
            
            # Temporal metadata (filterable)
            Property(
                name="published_at",
                data_type=DataType.DATE,
                description="Document publication date",
                index_filterable=True,
                index_searchable=False
            ),
            Property(
                name="year",
                data_type=DataType.INT,
                description="Publication year (extracted for fast filtering)",
                index_filterable=True,
                index_searchable=False
            ),
            
            # Chunk metadata (filterable/numeric)
            Property(
                name="tokens",
                data_type=DataType.INT,
                description="Token count in chunk",
                index_filterable=True,
                index_searchable=False
            ),
            Property(
                name="n_sentences", 
                data_type=DataType.INT,
                description="Number of sentences in chunk",
                index_filterable=True,
                index_searchable=False
            ),
            
            # Quality scoring (numeric, filterable)
            Property(
                name="quality_total",
                data_type=DataType.NUMBER,
                description="Document quality score for ranking",
                index_filterable=True,
                index_searchable=False
            ),
            
            # Flexible metadata storage
            Property(
                name="meta",
                data_type=DataType.OBJECT,
                description="Structured metadata including chunker info and source-specific data",
                nested_properties=[
                    Property(name="chunker_version", data_type=DataType.TEXT),
                    Property(name="src", data_type=DataType.OBJECT, nested_properties=[
                        Property(name="pubmed", data_type=DataType.OBJECT, nested_properties=[
                            Property(name="journal", data_type=DataType.TEXT),
                            Property(name="mesh_terms", data_type=DataType.TEXT_ARRAY),
                            Property(name="quality_total", data_type=DataType.NUMBER)
                        ])
                    ])
                ]
            )
        ]
    
    def _build_vectorizer_config(self) -> dict[str, Any]:
        """Build vectorizer configuration based on vectorizer type."""
        if self.config.vectorizer_type == VectorizerType.HUGGINGFACE_API:
            return Configure.Vectors.text2vec_huggingface(
                model=self.config.model_name,
                wait_for_model=True,
                use_gpu=False,  # API doesn't expose GPU option
                use_cache=True
            )
        
        elif self.config.vectorizer_type == VectorizerType.TRANSFORMERS_LOCAL:
            return Configure.Vectors.text2vec_transformers(
                pooling_strategy="masked_mean",
                vectorize_collection_name=False
            )
        
        elif self.config.vectorizer_type == VectorizerType.OPENAI:
            return Configure.Vectors.text2vec_openai(
                model="text-embedding-3-small"
            )
        
        else:
            raise ValueError(f"Unsupported vectorizer type: {self.config.vectorizer_type}")
    
    async def drop_collection(self, collection_name: str) -> bool:
        """Drop a collection (use with caution)."""
        logger.warning(f"Dropping collection: {collection_name}")
        
        try:
            if self.client.collections.exists(collection_name):
                self.client.collections.delete(collection_name)
                logger.info(f"Successfully dropped collection: {collection_name}")
                return True
            else:
                logger.warning(f"Collection {collection_name} does not exist")
                return False
        except Exception as e:
            logger.error(f"Failed to drop collection: {e}")
            raise
    
    def get_collection_info(self, collection_name: str) -> dict[str, Any] | None:
        """Get collection information and statistics."""
        try:
            if not self.client.collections.exists(collection_name):
                return {
                    "name": collection_name,
                    "exists": False
                }
            
            collection = self.client.collections.get(collection_name)
            
            # Get document count
            result = collection.aggregate.over_all(total_count=True)
            
            # Get basic collection info
            return {
                "name": collection_name,
                "exists": True,
                "total_documents": result.total_count,
                "collection_name": collection.name
            }
        
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {
                "name": collection_name,
                "exists": False,
                "error": str(e)
            }
    
    def validate_collection_schema(self, collection_name: str) -> dict[str, Any]:
        """Validate collection schema matches expectations."""
        validation_result = {
            "valid": False,
            "issues": [],
            "properties_found": []
        }
        
        try:
            if not self.client.collections.exists(collection_name):
                validation_result["issues"].append("Collection does not exist")
                return validation_result
            
            collection = self.client.collections.get(collection_name)
            config_obj = collection.config.get()
            
            # Check required properties
            expected_properties = {
                "parent_uid", "source", "title", "text", "section",
                "published_at", "year", "tokens", "n_sentences", 
                "quality_total", "meta"
            }
            
            actual_properties = {prop.name for prop in config_obj.properties}
            validation_result["properties_found"] = list(actual_properties)
            
            missing_properties = expected_properties - actual_properties
            if missing_properties:
                validation_result["issues"].append(f"Missing properties: {missing_properties}")
            
            # Validation passes if no issues
            validation_result["valid"] = len(validation_result["issues"]) == 0
            
        except Exception as e:
            validation_result["issues"].append(f"Validation failed: {e!s}")
        
        return validation_result


class CollectionMigration:
    """Handles collection migrations and upgrades."""
    
    def __init__(self, client: weaviate.WeaviateClient):
        self.client = client
        self.schema_manager = WeaviateSchemaManager(client)
    
    async def migrate_from_old_collection(self, 
                                        old_collection: str,
                                        new_collection: str,
                                        batch_size: int = 100) -> dict[str, Any]:
        """Migrate data from old collection to new collection."""
        logger.info(f"Starting migration from {old_collection} to {new_collection}")
        
        migration_stats = {
            "documents_processed": 0,
            "documents_migrated": 0,
            "documents_failed": 0,
            "errors": []
        }
        
        try:
            # Verify collections exist
            if not self.client.collections.exists(old_collection):
                raise ValueError(f"Source collection {old_collection} does not exist")
            
            if not self.client.collections.exists(new_collection):
                raise ValueError(f"Target collection {new_collection} does not exist")
            
            old_col = self.client.collections.get(old_collection)
            new_col = self.client.collections.get(new_collection)
            
            # Get total count
            total_result = old_col.aggregate.over_all(total_count=True)
            total_docs = total_result.total_count
            
            logger.info(f"Migrating {total_docs} documents")
            
            # Migrate in batches
            offset = 0
            while offset < total_docs:
                try:
                    # Fetch batch from old collection
                    batch_result = old_col.query.fetch_objects(
                        limit=batch_size,
                        offset=offset
                    )
                    
                    if not batch_result.objects:
                        break
                    
                    # Transform and insert into new collection
                    for obj in batch_result.objects:
                        try:
                            # Transform old format to new format
                            new_properties = self._transform_properties(obj.properties)
                            
                            # Insert with original UUID to maintain references
                            new_col.data.insert(
                                uuid=obj.uuid,
                                properties=new_properties
                            )
                            
                            migration_stats["documents_migrated"] += 1
                        
                        except Exception as e:
                            migration_stats["documents_failed"] += 1
                            migration_stats["errors"].append(f"Failed to migrate {obj.uuid}: {e!s}")
                    
                    migration_stats["documents_processed"] += len(batch_result.objects)
                    offset += batch_size
                    
                    if offset % 1000 == 0:
                        logger.info(f"Migration progress: {offset}/{total_docs}")
                
                except Exception as e:
                    logger.error(f"Batch migration failed at offset {offset}: {e}")
                    migration_stats["errors"].append(f"Batch failed at {offset}: {e!s}")
                    offset += batch_size  # Skip failed batch
            
            logger.info("Migration completed", **migration_stats)
            return migration_stats
        
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            migration_stats["errors"].append(f"Migration failed: {e!s}")
            return migration_stats
    
    def _transform_properties(self, old_properties: dict[str, Any]) -> dict[str, Any]:
        """Transform old collection properties to new schema."""
        # This is a placeholder - implement based on actual old schema
        return {
            "parent_uid": old_properties.get("parent_uid", ""),
            "source": old_properties.get("source", ""),
            "title": old_properties.get("title", ""),
            "text": old_properties.get("text", ""),
            "section": old_properties.get("section", "Unstructured"),
            "published_at": old_properties.get("published_at"),
            "year": old_properties.get("year"),
            "tokens": old_properties.get("tokens", 0),
            "n_sentences": old_properties.get("n_sentences", 0),
            "quality_total": old_properties.get("quality_total", 0.0),
            "meta": old_properties.get("meta", {})
        }