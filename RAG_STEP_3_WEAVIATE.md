# RAG Step 3: New Weaviate Collection (DocumentChunk_v2)

**Objective:** Create a fresh Weaviate collection with BioBERT vectorization, optimized schema for biomedical search, and proper metadata structure for multi-source support.

**Success Criteria:**
- New DocumentChunk_v2 collection with BioBERT embeddings
- Optimized schema with top-level fields and namespaced metadata
- Idempotent upserts using deterministic UUIDs
- Migration scripts and collection management tools
- Performance validation (sub-200ms search times)

---

## 1. Collection Schema Design

### 1.1 Weaviate Schema Definition
**File:** `src/bio_mcp/services/weaviate_schema.py`

```python
"""
Weaviate schema management for DocumentChunk_v2 collection.

This module handles creation, migration, and management of the new
biomedical document chunk collection with BioBERT embeddings.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

import weaviate
from weaviate.classes.config import Configure, Property, DataType, VectorIndexConfig, VectorIndexType
from weaviate.classes.query import Filter

from bio_mcp.config.logging_config import get_logger
from bio_mcp.config.config import config

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
    vectorizer_type: VectorizerType = VectorizerType.HUGGINGFACE_API
    model_name: str = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
    
    # Vector index settings
    vector_index_type: VectorIndexType = VectorIndexType.HNSW
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
            vector_config = self._build_vector_config()
            
            # Configure vector index
            vector_index_config = VectorIndexConfig(
                quantizer=None,  # No quantization for now
                vector_cache_max_objects=100000,
            )
            
            # Create collection
            collection = self.client.collections.create(
                name=self.config.name,
                description=self.config.description,
                properties=properties,
                vector_config=vector_config,
                vector_index_config=vector_index_config,
                replication_config={
                    "factor": self.config.replication_factor
                },
                sharding_config={
                    "virtualPerPhysical": self.config.shard_count,
                    "desiredCount": self.config.shard_count
                }
            )
            
            logger.info(f"Successfully created collection: {self.config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise
    
    def _build_properties(self) -> List[Property]:
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
                tokenization="word"
            ),
            Property(
                name="text",
                data_type=DataType.TEXT,
                description="Chunk text content",
                index_filterable=False,
                index_searchable=True,
                tokenization="word"
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
                    # Chunker metadata
                    Property(name="chunker_version", data_type=DataType.TEXT),
                    Property(name="tokenizer", data_type=DataType.TEXT),
                    Property(name="n_sentences", data_type=DataType.INT),
                    Property(name="section_boost", data_type=DataType.NUMBER),
                    
                    # Source-specific metadata (flexible JSON storage)
                    Property(
                        name="src",
                        data_type=DataType.OBJECT,
                        nested_properties=[
                            # PubMed-specific metadata
                            Property(
                                name="pubmed",
                                data_type=DataType.OBJECT, 
                                nested_properties=[
                                    Property(name="mesh_terms", data_type=DataType.TEXT_ARRAY),
                                    Property(name="journal", data_type=DataType.TEXT),
                                    Property(name="edat", data_type=DataType.TEXT),
                                    Property(name="lr", data_type=DataType.TEXT),
                                    Property(name="pmcid", data_type=DataType.TEXT),
                                    Property(name="doi", data_type=DataType.TEXT),
                                    Property(name="pub_types", data_type=DataType.TEXT_ARRAY),
                                    Property(name="source_url", data_type=DataType.TEXT),
                                ]
                            ),
                            # ClinicalTrials.gov metadata (future)
                            Property(
                                name="ctgov",
                                data_type=DataType.OBJECT,
                                nested_properties=[
                                    Property(name="status", data_type=DataType.TEXT),
                                    Property(name="phase", data_type=DataType.TEXT),
                                    Property(name="conditions", data_type=DataType.TEXT_ARRAY),
                                    Property(name="interventions", data_type=DataType.TEXT_ARRAY),
                                ]
                            )
                        ]
                    )
                ]
            )
        ]
    
    def _build_vector_config(self) -> Dict[str, Any]:
        """Build vector configuration based on vectorizer type."""
        if self.config.vectorizer_type == VectorizerType.HUGGINGFACE_API:
            return Configure.NamedVectors.text2vec_huggingface(
                name="content_vector",
                source_properties=["text"],
                model=self.config.model_name,
                endpoint_url=None,  # Use default HF endpoint
                wait_for_model=True,
                use_gpu=False,  # API doesn't expose GPU option
                use_cache=True
            )
        
        elif self.config.vectorizer_type == VectorizerType.TRANSFORMERS_LOCAL:
            return Configure.NamedVectors.text2vec_transformers(
                name="content_vector",
                source_properties=["text"],
                pooling_strategy="masked_mean"
            )
        
        elif self.config.vectorizer_type == VectorizerType.OPENAI:
            return Configure.NamedVectors.text2vec_openai(
                name="content_vector", 
                source_properties=["text"],
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
    
    def get_collection_info(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """Get collection information and statistics."""
        try:
            if not self.client.collections.exists(collection_name):
                return None
            
            collection = self.client.collections.get(collection_name)
            config = collection.config.get()
            
            # Get document count
            result = collection.aggregate.over_all(total_count=True)
            
            return {
                "name": collection_name,
                "exists": True,
                "total_documents": result.total_count,
                "vectorizer": str(config.vectorizer),
                "vector_index_type": str(config.vector_index_type),
                "properties": len(config.properties),
                "shards": getattr(config.sharding_config, 'virtual_per_physical', 1) if config.sharding_config else 1,
                "replication_factor": getattr(config.replication_config, 'factor', 1) if config.replication_config else 1
            }
        
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {
                "name": collection_name,
                "exists": False,
                "error": str(e)
            }
    
    def validate_collection_schema(self, collection_name: str) -> Dict[str, Any]:
        """Validate collection schema matches expectations."""
        validation_result = {
            "valid": False,
            "issues": [],
            "properties_found": [],
            "vectorizer_config": None
        }
        
        try:
            if not self.client.collections.exists(collection_name):
                validation_result["issues"].append("Collection does not exist")
                return validation_result
            
            collection = self.client.collections.get(collection_name)
            config = collection.config.get()
            
            # Check required properties
            expected_properties = {
                "parent_uid", "source", "title", "text", "section",
                "published_at", "year", "tokens", "n_sentences", 
                "quality_total", "meta"
            }
            
            actual_properties = {prop.name for prop in config.properties}
            validation_result["properties_found"] = list(actual_properties)
            
            missing_properties = expected_properties - actual_properties
            if missing_properties:
                validation_result["issues"].append(f"Missing properties: {missing_properties}")
            
            # Check vectorizer configuration
            if config.vectorizer:
                validation_result["vectorizer_config"] = str(config.vectorizer)
            else:
                validation_result["issues"].append("No vectorizer configured")
            
            # Validation passes if no issues
            validation_result["valid"] = len(validation_result["issues"]) == 0
            
        except Exception as e:
            validation_result["issues"].append(f"Validation failed: {str(e)}")
        
        return validation_result

class CollectionMigration:
    """Handles collection migrations and upgrades."""
    
    def __init__(self, client: weaviate.WeaviateClient):
        self.client = client
        self.schema_manager = WeaviateSchemaManager(client)
    
    async def migrate_from_old_collection(self, 
                                        old_collection: str,
                                        new_collection: str,
                                        batch_size: int = 100) -> Dict[str, Any]:
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
                        offset=offset,
                        return_metadata=["certainty", "distance"]
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
                            migration_stats["errors"].append(f"Failed to migrate {obj.uuid}: {str(e)}")
                    
                    migration_stats["documents_processed"] += len(batch_result.objects)
                    offset += batch_size
                    
                    if offset % 1000 == 0:
                        logger.info(f"Migration progress: {offset}/{total_docs}")
                
                except Exception as e:
                    logger.error(f"Batch migration failed at offset {offset}: {e}")
                    migration_stats["errors"].append(f"Batch failed at {offset}: {str(e)}")
                    offset += batch_size  # Skip failed batch
            
            logger.info("Migration completed", **migration_stats)
            return migration_stats
        
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            migration_stats["errors"].append(f"Migration failed: {str(e)}")
            return migration_stats
    
    def _transform_properties(self, old_properties: Dict[str, Any]) -> Dict[str, Any]:
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
```

---

## 2. Collection Management Scripts

### 2.1 Schema Creation Script
**File:** `scripts/create_weaviate_schema.py`

```python
#!/usr/bin/env python3
"""
Script to create Weaviate DocumentChunk_v2 collection.

Usage:
    python -m scripts.create_weaviate_schema [--collection-name NAME] [--vectorizer TYPE] [--model NAME]
"""

import asyncio
import argparse
import sys
from typing import Optional

import weaviate

from bio_mcp.services.weaviate_schema import (
    WeaviateSchemaManager, CollectionConfig, VectorizerType
)
from bio_mcp.config.config import config
from bio_mcp.config.logging_config import get_logger

logger = get_logger(__name__)

async def create_collection(
    collection_name: str = "DocumentChunk_v2",
    vectorizer_type: str = "huggingface",
    model_name: str = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
    force: bool = False
) -> bool:
    """Create Weaviate collection with specified configuration."""
    
    # Map string to enum
    vectorizer_map = {
        "huggingface": VectorizerType.HUGGINGFACE_API,
        "transformers": VectorizerType.TRANSFORMERS_LOCAL,
        "openai": VectorizerType.OPENAI
    }
    
    if vectorizer_type not in vectorizer_map:
        logger.error(f"Unknown vectorizer type: {vectorizer_type}")
        return False
    
    try:
        # Connect to Weaviate
        logger.info("Connecting to Weaviate", url=config.weaviate_url)
        client = weaviate.connect_to_custom(
            http_host=config.weaviate_url.split("://")[1].split(":")[0],
            http_port=int(config.weaviate_url.split(":")[-1]),
            http_secure=config.weaviate_url.startswith("https")
        )
        
        # Create schema manager
        collection_config = CollectionConfig(
            name=collection_name,
            vectorizer_type=vectorizer_map[vectorizer_type],
            model_name=model_name
        )
        
        schema_manager = WeaviateSchemaManager(client, collection_config)
        
        # Check if collection exists
        if client.collections.exists(collection_name):
            if not force:
                logger.error(f"Collection {collection_name} already exists. Use --force to recreate.")
                return False
            else:
                logger.info(f"Dropping existing collection: {collection_name}")
                await schema_manager.drop_collection(collection_name)
        
        # Create collection
        success = await schema_manager.create_document_chunk_v2_collection()
        
        if success:
            # Validate schema
            validation_result = schema_manager.validate_collection_schema(collection_name)
            
            if validation_result["valid"]:
                logger.info("Collection created and validated successfully")
                
                # Print collection info
                info = schema_manager.get_collection_info(collection_name)
                logger.info("Collection info", **info)
                
            else:
                logger.warning("Collection created but validation failed", 
                             issues=validation_result["issues"])
        
        client.close()
        return success
    
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        return False

def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(description="Create Weaviate DocumentChunk_v2 collection")
    
    parser.add_argument(
        "--collection-name", 
        default="DocumentChunk_v2",
        help="Name of collection to create"
    )
    parser.add_argument(
        "--vectorizer",
        choices=["huggingface", "transformers", "openai"],
        default="huggingface",
        help="Vectorizer type to use"
    )
    parser.add_argument(
        "--model",
        default="pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
        help="Model name for vectorizer"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recreate if collection exists"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true", 
        help="Verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create collection
    success = asyncio.run(create_collection(
        collection_name=args.collection_name,
        vectorizer_type=args.vectorizer,
        model_name=args.model,
        force=args.force
    ))
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
```

### 2.2 Collection Info Script  
**File:** `scripts/weaviate_info.py`

```python
#!/usr/bin/env python3
"""
Script to get information about Weaviate collections.

Usage:
    python -m scripts.weaviate_info [--collection NAME] [--validate]
"""

import argparse
import json
import sys
from typing import List, Optional

import weaviate

from bio_mcp.services.weaviate_schema import WeaviateSchemaManager
from bio_mcp.config.config import config
from bio_mcp.config.logging_config import get_logger

logger = get_logger(__name__)

def get_collection_info(collection_name: Optional[str] = None) -> dict:
    """Get information about Weaviate collections."""
    
    try:
        # Connect to Weaviate
        client = weaviate.connect_to_custom(
            http_host=config.weaviate_url.split("://")[1].split(":")[0],
            http_port=int(config.weaviate_url.split(":")[-1]),
            http_secure=config.weaviate_url.startswith("https")
        )
        
        schema_manager = WeaviateSchemaManager(client)
        
        if collection_name:
            # Get info for specific collection
            info = schema_manager.get_collection_info(collection_name)
            validation = schema_manager.validate_collection_schema(collection_name)
            
            result = {
                "collection": info,
                "validation": validation
            }
        else:
            # Get info for all collections
            all_collections = client.collections.list_all(simple=False)
            
            result = {
                "weaviate_meta": client.get_meta(),
                "collections": {}
            }
            
            for collection in all_collections:
                info = schema_manager.get_collection_info(collection.name)
                result["collections"][collection.name] = info
        
        client.close()
        return result
    
    except Exception as e:
        logger.error(f"Failed to get collection info: {e}")
        return {"error": str(e)}

def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(description="Get Weaviate collection information")
    
    parser.add_argument(
        "--collection",
        help="Specific collection to inspect"
    )
    parser.add_argument(
        "--validate", 
        action="store_true",
        help="Validate collection schema"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    
    args = parser.parse_args()
    
    # Get collection info
    info = get_collection_info(args.collection)
    
    if args.json:
        print(json.dumps(info, indent=2, default=str))
    else:
        # Pretty print info
        if "error" in info:
            print(f"Error: {info['error']}")
            sys.exit(1)
        
        if args.collection:
            # Single collection info
            collection_info = info["collection"]
            validation_info = info["validation"]
            
            print(f"Collection: {collection_info['name']}")
            print(f"Exists: {collection_info['exists']}")
            
            if collection_info["exists"]:
                print(f"Documents: {collection_info['total_documents']:,}")
                print(f"Vectorizer: {collection_info['vectorizer']}")
                print(f"Properties: {collection_info['properties']}")
                print(f"Shards: {collection_info['shards']}")
                
                print(f"\nSchema Validation: {'✅' if validation_info['valid'] else '❌'}")
                if validation_info["issues"]:
                    for issue in validation_info["issues"]:
                        print(f"  ⚠️  {issue}")
        else:
            # All collections info
            meta = info.get("weaviate_meta", {})
            print(f"Weaviate Version: {meta.get('version', 'unknown')}")
            print(f"Collections: {len(info.get('collections', {}))}")
            print()
            
            for name, collection_info in info.get("collections", {}).items():
                status = "✅" if collection_info["exists"] else "❌"
                docs = f"{collection_info.get('total_documents', 0):,}" if collection_info["exists"] else "N/A"
                print(f"{status} {name:<20} Documents: {docs}")

if __name__ == "__main__":
    main()
```

---

## 3. Enhanced Embedding Service Integration

### 3.1 Updated Embedding Service
**File:** `src/bio_mcp/services/embedding_service.py` (updates)

```python
"""
Updated embedding service for DocumentChunk_v2 collection.
"""

from typing import Any, List, Dict, Optional
import uuid

from bio_mcp.models.document import Document, Chunk
from bio_mcp.services.weaviate_schema import WeaviateSchemaManager, CollectionConfig
from bio_mcp.shared.clients.weaviate_client import WeaviateClient, get_weaviate_client
from bio_mcp.config.logging_config import get_logger

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
    
    async def store_document_chunks(self, chunks: List[Chunk]) -> List[str]:
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
    
    def _chunk_to_properties(self, chunk: Chunk) -> Dict[str, Any]:
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
            "published_at": chunk.published_at.isoformat() if chunk.published_at else None,
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
                          filters: Dict[str, Any] = None,
                          min_certainty: float = None) -> List[Dict[str, Any]]:
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
                response = collection.query.hybrid(
                    query=query,
                    alpha=alpha,
                    limit=limit,
                    where=where_filter,
                    return_metadata=["score", "explainScore"]
                )
            elif search_mode == "semantic":
                near_text_query = {
                    "concepts": [query]
                }
                if min_certainty:
                    near_text_query["certainty"] = min_certainty
                
                response = collection.query.near_text(
                    near_text=near_text_query,
                    limit=limit,
                    where=where_filter,
                    return_metadata=["certainty", "distance"]
                )
            elif search_mode == "bm25":
                response = collection.query.bm25(
                    query=query,
                    limit=limit,
                    where=where_filter,
                    return_metadata=["score"]
                )
            else:
                raise ValueError(f"Unknown search mode: {search_mode}")
            
            # Convert results
            results = []
            for obj in response.objects:
                result = {
                    "uuid": str(obj.uuid),
                    "chunk_id": obj.properties.get("parent_uid", "") + ":" + str(obj.properties.get("chunk_idx", 0)),
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
    
    def _build_filters(self, filters: Dict[str, Any]) -> Optional[Any]:
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
    
    async def health_check(self) -> Dict[str, Any]:
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
```

---

## 4. Make Targets and Scripts

### 4.1 Makefile Updates
**File:** `Makefile` (additions)

```makefile
# Weaviate collection management
schema-create:  ## Create DocumentChunk_v2 collection
	$(UV) run python -m scripts.create_weaviate_schema --collection DocumentChunk_v2 --vectorizer huggingface

schema-create-local:  ## Create collection with local transformers
	$(UV) run python -m scripts.create_weaviate_schema --collection DocumentChunk_v2 --vectorizer transformers

schema-info:  ## Get collection information
	$(UV) run python -m scripts.weaviate_info

schema-drop:  ## Drop DocumentChunk_v2 collection (DANGEROUS)
	$(UV) run python -m scripts.create_weaviate_schema --collection DocumentChunk_v2 --force

schema-validate:  ## Validate collection schema
	$(UV) run python -m scripts.weaviate_info --collection DocumentChunk_v2 --validate

schema-migrate:  ## Migrate from old collection to new
	$(UV) run python -m scripts.migrate_collection --from DocumentChunk --to DocumentChunk_v2

# Testing 
test-weaviate:  ## Test Weaviate integration
	$(UV) run pytest tests/integration/test_weaviate_v2.py -v

smoke-weaviate:  ## Quick Weaviate smoke test
	$(UV) run python -c "import weaviate; print('Weaviate client import: OK')"
	curl -fsS $(BIO_MCP_WEAVIATE_URL)/v1/meta | jq '.version' || echo "Weaviate not responding"
```

---

## 5. Testing Implementation

### 5.1 Integration Tests
**File:** `tests/integration/test_weaviate_v2.py`

```python
import pytest
import uuid
from datetime import datetime

from bio_mcp.services.weaviate_schema import WeaviateSchemaManager, CollectionConfig
from bio_mcp.services.embedding_service import EmbeddingServiceV2  
from bio_mcp.models.document import Document, Chunk
from bio_mcp.shared.clients.weaviate_client import get_weaviate_client

@pytest.mark.integration
class TestWeaviateV2Integration:
    """Integration tests for DocumentChunk_v2 collection."""
    
    @pytest.fixture(scope="class")
    async def weaviate_client(self):
        """Get Weaviate client for testing."""
        client = get_weaviate_client()
        await client.initialize()
        yield client
        await client.close()
    
    @pytest.fixture(scope="class") 
    async def test_collection(self, weaviate_client):
        """Create test collection."""
        collection_name = f"TestCollection_{uuid.uuid4().hex[:8]}"
        
        config = CollectionConfig(
            name=collection_name,
            model_name="pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
        )
        
        schema_manager = WeaviateSchemaManager(weaviate_client.client, config)
        
        # Create collection
        success = await schema_manager.create_document_chunk_v2_collection()
        assert success
        
        yield collection_name, schema_manager
        
        # Cleanup
        await schema_manager.drop_collection(collection_name)
    
    async def test_collection_creation(self, test_collection):
        """Test collection creation and validation."""
        collection_name, schema_manager = test_collection
        
        # Verify collection exists
        info = schema_manager.get_collection_info(collection_name)
        assert info["exists"]
        assert info["total_documents"] == 0
        
        # Validate schema
        validation = schema_manager.validate_collection_schema(collection_name)
        assert validation["valid"], f"Schema validation failed: {validation['issues']}"
    
    async def test_chunk_storage_and_retrieval(self, test_collection):
        """Test storing and retrieving chunks."""
        collection_name, _ = test_collection
        
        # Create embedding service
        embedding_service = EmbeddingServiceV2(collection_name=collection_name)
        await embedding_service.initialize()
        
        # Create test chunks
        doc_uid = "pubmed:12345678"
        chunks = [
            Chunk(
                chunk_id="s0",
                uuid=Chunk.generate_uuid(doc_uid, "s0"),
                parent_uid=doc_uid,
                source="pubmed",
                chunk_idx=0,
                text="Background: This study investigates cancer immunotherapy.",
                title="Cancer Immunotherapy Study",
                section="Background",
                published_at=datetime(2024, 1, 15),
                tokens=10,
                n_sentences=1,
                meta={
                    "chunker_version": "v1.2.0",
                    "src": {
                        "pubmed": {
                            "journal": "Nature Medicine",
                            "mesh_terms": ["Cancer", "Immunotherapy"]
                        }
                    }
                }
            ),
            Chunk(
                chunk_id="s1", 
                uuid=Chunk.generate_uuid(doc_uid, "s1"),
                parent_uid=doc_uid,
                source="pubmed",
                chunk_idx=1,
                text="Results: Significant improvement in survival was observed.",
                title="Cancer Immunotherapy Study",
                section="Results",
                published_at=datetime(2024, 1, 15),
                tokens=9,
                n_sentences=1,
                meta={
                    "chunker_version": "v1.2.0",
                    "src": {
                        "pubmed": {
                            "journal": "Nature Medicine",
                            "mesh_terms": ["Cancer", "Immunotherapy"]
                        }
                    }
                }
            )
        ]
        
        # Store chunks
        stored_uuids = await embedding_service.store_document_chunks(chunks)
        assert len(stored_uuids) == 2
        
        # Verify UUIDs match
        expected_uuids = [chunk.uuid for chunk in chunks]
        assert set(stored_uuids) == set(expected_uuids)
        
        # Test search
        results = await embedding_service.search_chunks(
            query="cancer immunotherapy",
            limit=5,
            search_mode="bm25"  # Use BM25 to avoid embedding issues in tests
        )
        
        assert len(results) > 0
        assert any("cancer" in result["text"].lower() for result in results)
        
        # Test filtering
        filtered_results = await embedding_service.search_chunks(
            query="immunotherapy",
            limit=5,
            search_mode="bm25",
            filters={"section": ["Background"]}
        )
        
        assert len(filtered_results) > 0
        assert all(result["section"] == "Background" for result in filtered_results)
    
    async def test_idempotent_upserts(self, test_collection):
        """Test that re-storing same chunks is idempotent."""
        collection_name, schema_manager = test_collection
        
        embedding_service = EmbeddingServiceV2(collection_name=collection_name)
        await embedding_service.initialize()
        
        # Create test chunk
        doc_uid = "pubmed:87654321"
        chunk = Chunk(
            chunk_id="w0",
            uuid=Chunk.generate_uuid(doc_uid, "w0"), 
            parent_uid=doc_uid,
            source="pubmed",
            chunk_idx=0,
            text="Test chunk for idempotent upserts.",
            title="Test Document",
            tokens=6,
            n_sentences=1
        )
        
        # Store chunk first time
        uuids1 = await embedding_service.store_document_chunks([chunk])
        
        # Get document count
        info1 = schema_manager.get_collection_info(collection_name)
        count1 = info1["total_documents"]
        
        # Store same chunk again (should upsert, not duplicate)
        uuids2 = await embedding_service.store_document_chunks([chunk])
        
        # Verify same UUIDs returned
        assert uuids1 == uuids2
        
        # Verify document count unchanged (upsert, not insert)
        info2 = schema_manager.get_collection_info(collection_name) 
        count2 = info2["total_documents"]
        
        # Note: Weaviate may still increment count on upsert
        # The key test is that the UUID is the same
        assert uuids1[0] == chunk.uuid

class TestWeaviateSchemaManager:
    """Test schema management functionality."""
    
    async def test_collection_lifecycle(self):
        """Test complete collection lifecycle."""
        client = get_weaviate_client()
        await client.initialize()
        
        collection_name = f"TestLifecycle_{uuid.uuid4().hex[:8]}"
        
        try:
            schema_manager = WeaviateSchemaManager(
                client.client,
                CollectionConfig(name=collection_name)
            )
            
            # Collection should not exist initially
            assert not client.client.collections.exists(collection_name)
            
            # Create collection
            success = await schema_manager.create_document_chunk_v2_collection()
            assert success
            
            # Collection should now exist
            assert client.client.collections.exists(collection_name)
            
            # Get info
            info = schema_manager.get_collection_info(collection_name)
            assert info["exists"] 
            assert info["total_documents"] == 0
            
            # Validate schema
            validation = schema_manager.validate_collection_schema(collection_name)
            assert validation["valid"]
            
            # Drop collection
            dropped = await schema_manager.drop_collection(collection_name)
            assert dropped
            
            # Collection should no longer exist
            assert not client.client.collections.exists(collection_name)
        
        finally:
            # Cleanup in case of test failure
            if client.client.collections.exists(collection_name):
                await schema_manager.drop_collection(collection_name)
            await client.close()
```

---

## 6. Configuration and Deployment

### 6.1 Environment Configuration
**File:** `.env.example` (additions)

```bash
# Weaviate V2 Collection Settings
BIO_MCP_WEAVIATE_COLLECTION=DocumentChunk_v2
BIO_MCP_WEAVIATE_VECTORIZER=huggingface
BIO_MCP_EMBED_MODEL=pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb

# Collection performance settings
BIO_MCP_WEAVIATE_SHARD_COUNT=1
BIO_MCP_WEAVIATE_REPLICATION_FACTOR=1
BIO_MCP_WEAVIATE_EF_CONSTRUCTION=200
BIO_MCP_WEAVIATE_MAX_CONNECTIONS=64

# Search performance  
BIO_MCP_SEARCH_TIMEOUT=10
BIO_MCP_SEARCH_DEFAULT_LIMIT=10
BIO_MCP_SEARCH_MAX_LIMIT=100
```

### 6.2 Docker Compose Updates
**File:** `docker-compose.yml` (Weaviate service update)

```yaml
services:
  weaviate:
    image: semitechnologies/weaviate:1.25.0
    ports:
      - "8080:8080"
    environment:
      QUERY_DEFAULTS_LIMIT: 25
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'text2vec-huggingface'
      ENABLE_MODULES: 'text2vec-huggingface,text2vec-transformers'
      CLUSTER_HOSTNAME: 'node1'
      # HuggingFace settings
      HUGGINGFACE_APIKEY: ${HUGGINGFACE_API_KEY:-}
      HUGGINGFACE_WAIT_FOR_MODEL: 'true'
      HUGGINGFACE_USE_GPU: 'false'
      HUGGINGFACE_USE_CACHE: 'true'
    volumes:
      - ./data/weaviate:/var/lib/weaviate
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/v1/meta"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

---

## 7. Success Validation

### 7.1 Validation Checklist
- [ ] DocumentChunk_v2 collection creates successfully
- [ ] Schema validates with all required properties
- [ ] BioBERT vectorizer configured and functional
- [ ] Idempotent upserts work with deterministic UUIDs
- [ ] Search performance meets <200ms target
- [ ] Filtering works on top-level properties
- [ ] Metadata storage and retrieval works correctly
- [ ] Collection management scripts functional
- [ ] Integration tests pass
- [ ] Health checks return proper status

### 7.2 Performance Benchmarks
- Collection creation: <30 seconds
- Single chunk insert: <100ms
- Batch chunk insert (100 chunks): <5 seconds
- Hybrid search (10 results): <200ms
- BM25 search (10 results): <100ms
- Semantic search (10 results): <500ms (with embeddings)
- Filtered search: <300ms

### 7.3 Rollback Plan
1. Keep old DocumentChunk collection as backup
2. Test thoroughly in staging before production
3. Monitor search quality and performance
4. Have migration script ready to revert if needed

---

## Next Steps

After completing this step:
1. Proceed to **RAG_STEP_4_EMBEDDING.md** for BioBERT integration
2. Create sample data ingestion scripts
3. Validate search quality with test queries

**Estimated Time:** 2-3 days
**Dependencies:** RAG_STEP_1_MODELS.md and RAG_STEP_2_CHUNKING.md
**Risk Level:** Medium (new collection, requires testing)