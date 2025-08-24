# RAG Step 4A: BioBERT Vectorizer Implementation

**Objective:** Implement proper BioBERT embedding integration using Weaviate's text2vec-transformers module, following the specifications in RAG_IMPLEMENTATION_PLAN_V2.md.

**Success Criteria:**
- Weaviate configured with BioBERT model (`pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb`)
- DocumentChunk_v2 collection using BioBERT embeddings
- Simplified service architecture (Weaviate handles all vectorization)
- Removal of misleading tokenizer code
- Idempotent storage with deterministic UUIDs
- Performance validation with biomedical text

---

## Current State Analysis

### Issues with Current Implementation
1. **Misleading BioBERT integration**: Loads BioBERT tokenizer but never generates embeddings
2. **Inconsistent architecture**: Claims BioBERT but uses Weaviate's generic vectorizer
3. **Unnecessary complexity**: Token counting and validation that doesn't match actual embedder
4. **Legacy code**: Multiple embedding services with overlapping functionality
5. **Non-functional RAGService**: Makes API calls to non-existent methods

### What Actually Needs BioBERT
According to RAG_IMPLEMENTATION_PLAN_V2.md:
- **Vectorizer**: `pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb`
- **Two options specified**:
  - Option A: `text2vec-huggingface` (cloud API)
  - Option B: `text2vec-transformers` (local) ← **Recommended**

---

## Implementation Plan

### Phase 1: Clean Up Current Implementation
**Files to modify:**
- `src/bio_mcp/services/embedding_service_v2.py`
- `src/bio_mcp/services/embedding_service.py` (delete)
- `src/bio_mcp/shared/services/rag_service.py` (delete)

**Changes:**
1. **Remove misleading BioBERT tokenizer code**:
   - Delete `_initialize_tokenizer()` method
   - Delete `_count_tokens()` method
   - Remove `transformers` import and warning suppression
   - Remove tokenizer references in metadata

2. **Simplify EmbeddingServiceV2**:
   - Focus on chunking and storage only
   - Let Weaviate handle all vectorization
   - Remove legacy compatibility methods
   - Clean up metadata handling

3. **Delete non-functional services**:
   - `embedding_service.py` (legacy)
   - `rag_service.py` (broken API calls)
   - Associated unit tests

### Phase 2: Configure Weaviate for BioBERT

**Files to create/modify:**
- `src/bio_mcp/services/weaviate_schema.py` (update)
- `scripts/create_weaviate_schema.py` (create)
- `docker-compose.yml` (update)

**Changes:**

1. **Update WeaviateSchemaManager**:
```python
def _get_vectorizer_config(self) -> Configure.Vectorizer:
    """Get BioBERT vectorizer configuration."""
    if self.config.vectorizer_type == VectorizerType.TRANSFORMERS_LOCAL:
        return Configure.Vectorizer.text2vec_transformers(
            model="pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
            pooling_strategy="masked_mean",
            vectorize_collection_name=False
        )
    else:
        raise ValueError(f"Unsupported vectorizer type: {self.config.vectorizer_type}")
```

2. **Create DocumentChunk_v2 schema**:
```python
def create_document_chunk_v2_collection(self) -> bool:
    """Create DocumentChunk_v2 collection with BioBERT vectorizer."""
    properties = [
        Property(name="parent_uid", data_type=DataType.TEXT),
        Property(name="source", data_type=DataType.TEXT),
        Property(name="section", data_type=DataType.TEXT),
        Property(name="title", data_type=DataType.TEXT),
        Property(name="text", data_type=DataType.TEXT),
        Property(name="published_at", data_type=DataType.DATE),
        Property(name="year", data_type=DataType.INT),
        Property(name="tokens", data_type=DataType.INT),
        Property(name="n_sentences", data_type=DataType.INT),
        Property(name="quality_total", data_type=DataType.NUMBER),
        Property(name="meta", data_type=DataType.OBJECT),
    ]
    
    vectorizer_config = Configure.Vectorizer.text2vec_transformers(
        model="pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
        pooling_strategy="masked_mean"
    )
    
    self.client.collections.create(
        name=self.config.name,
        properties=properties,
        vectorizer_config=vectorizer_config
    )
```

3. **Update Docker configuration**:
```yaml
# docker-compose.yml
services:
  weaviate:
    environment:
      ENABLE_MODULES: 'text2vec-transformers'
      DEFAULT_VECTORIZER_MODULE: 'text2vec-transformers'
      TRANSFORMERS_INFERENCE_API: 'http://t2v-transformers:8080'
    
  t2v-transformers:
    image: semitechnologies/transformers-inference:sentence-transformers-pritamdeka-BioBERT-mnli-snli-scinli-scitail-mednli-stsb
    environment:
      ENABLE_CUDA: 0  # Set to 1 if GPU available
```

### Phase 3: Update Configuration

**Files to modify:**
- `src/bio_mcp/config/config.py`
- `.env.example`

**Changes:**
```python
# config.py
class Config:
    # BioBERT embedding model (handled by Weaviate)
    biobert_model_name: str = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
    
    # Weaviate V2 Configuration  
    weaviate_collection_v2: str = "DocumentChunk_v2"
    
    # Remove: tokenizer_model, huggingface_api_key, etc.
```

```bash
# .env.example
BIO_MCP_EMBED_MODEL=pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb
BIO_MCP_WEAVIATE_COLLECTION_V2=DocumentChunk_v2
BIO_MCP_UUID_NAMESPACE=1b2c3d4e-0000-0000-0000-000000000000
```

### Phase 4: Create Management Scripts

**Files to create:**
- `scripts/create_weaviate_schema.py`
- `scripts/validate_biobert_setup.py`

```python
# scripts/create_weaviate_schema.py
#!/usr/bin/env python3
"""Create DocumentChunk_v2 collection with BioBERT vectorizer."""

import asyncio
import click
from bio_mcp.config.config import Config
from bio_mcp.services.weaviate_schema import WeaviateSchemaManager, CollectionConfig
from bio_mcp.shared.clients.weaviate_client import get_weaviate_client

@click.command()
@click.option('--collection', default='DocumentChunk_v2', help='Collection name')
@click.option('--drop-first', is_flag=True, help='Drop existing collection first')
async def main(collection, drop_first):
    """Create Weaviate collection with BioBERT vectorizer."""
    config = Config()
    client = get_weaviate_client()
    await client.initialize()
    
    collection_config = CollectionConfig(
        name=collection,
        vectorizer_type=VectorizerType.TRANSFORMERS_LOCAL,
        model_name=config.biobert_model_name
    )
    
    schema_manager = WeaviateSchemaManager(client.client, collection_config)
    
    if drop_first and client.client.collections.exists(collection):
        click.echo(f"Dropping existing collection: {collection}")
        await schema_manager.drop_collection(collection)
    
    click.echo(f"Creating collection: {collection}")
    success = await schema_manager.create_document_chunk_v2_collection()
    
    if success:
        click.echo("✅ Collection created successfully")
        
        # Verify BioBERT model is loaded
        info = schema_manager.get_collection_info(collection)
        click.echo(f"Collection info: {info}")
    else:
        click.echo("❌ Failed to create collection")

if __name__ == "__main__":
    asyncio.run(main())
```

### Phase 5: Update Tests

**Files to modify:**
- `tests/unit/services/test_embedding_service_v2.py`
- `tests/integration/test_weaviate_v2.py`
- Delete: `tests/unit/services/test_embedding_service.py`

**Changes:**
1. **Remove tokenizer tests**: No longer relevant since Weaviate handles tokenization
2. **Add schema validation tests**: Verify BioBERT model is configured correctly
3. **Test embedding generation**: Verify that search results use BioBERT vectors
4. **Integration tests**: Test end-to-end flow with real BioBERT embeddings

Example test:
```python
@pytest.mark.integration
async def test_biobert_embeddings(self, embedding_service):
    """Test that BioBERT embeddings are generated correctly."""
    # Store biomedical document
    document = create_biomedical_test_document()
    chunk_uuids = await embedding_service.store_document_chunks(document)
    
    # Search with biomedical terms
    results = await embedding_service.search_chunks(
        query="cancer immunotherapy mechanisms",
        limit=5
    )
    
    # Should find relevant biomedical content
    assert len(results) > 0
    assert any("cancer" in result["text"].lower() for result in results)
    
    # Verify search scores are reasonable for biomedical text
    assert all(result["score"] > 0.1 for result in results)
```

### Phase 6: Makefile Integration

**File to update:** `Makefile`

```makefile
# BioBERT schema management
schema-create-v2:
	uv run python scripts/create_weaviate_schema.py --collection DocumentChunk_v2

schema-drop-v2:
	uv run python scripts/create_weaviate_schema.py --collection DocumentChunk_v2 --drop-first

validate-biobert:
	uv run python scripts/validate_biobert_setup.py

# Test BioBERT functionality
test-biobert-integration:
	uv run pytest tests/integration/test_weaviate_v2.py::TestBioBERTIntegration -v
```

---

## Validation Steps

### 1. Schema Validation
```bash
make schema-create-v2
make validate-biobert
```

### 2. Integration Testing
```bash
make test-biobert-integration
```

### 3. Performance Testing
- Verify embedding generation latency
- Test with biomedical terminology
- Compare search quality vs generic embeddings

### 4. Manual Verification
```python
# Test BioBERT understanding of biomedical terms
await embedding_service.search_chunks("glioblastoma temozolomide resistance")
await embedding_service.search_chunks("CAR-T cell immunotherapy")
await embedding_service.search_chunks("CRISPR gene editing mechanisms")
```

---

## Expected Outcomes

### Architecture Simplification
- **Remove**: 400+ lines of misleading tokenizer code
- **Remove**: Non-functional RAGService
- **Simplify**: EmbeddingServiceV2 to focus on chunking/storage
- **Clarify**: Weaviate handles all embedding generation

### BioBERT Integration
- **Model**: `pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb`
- **Method**: Weaviate's text2vec-transformers module
- **Benefits**: Better biomedical term understanding, proper semantic search
- **Performance**: ~420MB model, 1-2GB memory, local inference

### Improved Search Quality
- Better understanding of biomedical terminology
- Improved semantic similarity for drug names, diseases, treatments
- More relevant search results for biomedical queries
- Maintained performance with local inference

---

## Risk Assessment

### Low Risk
- Weaviate handles model loading and inference
- Well-documented BioBERT model
- No breaking API changes
- Fallback to generic vectorizer if needed

### Medium Risk  
- Model download size (420MB)
- Memory usage (1-2GB when loaded)
- GPU recommended but not required
- First-time model loading latency

### Mitigation
- Pre-download model in Docker image
- Configure appropriate memory limits
- Test thoroughly in staging environment
- Monitor memory usage and performance

---

## Success Metrics

1. **Technical**:
   - BioBERT model loads successfully in Weaviate
   - DocumentChunk_v2 collection created with proper schema
   - Search latency < 200ms for typical queries
   - Memory usage < 2GB for embedding service

2. **Quality**:
   - Improved search results for biomedical terms
   - Better semantic understanding compared to generic embeddings
   - Maintained or improved search precision/recall

3. **Maintainability**:
   - Reduced codebase complexity (fewer lines)
   - Clear separation of concerns
   - Comprehensive test coverage
   - Clear documentation

---

**Estimated Implementation Time:** 4-6 hours
**Risk Level:** Low-Medium
**Dependencies:** Weaviate with text2vec-transformers module