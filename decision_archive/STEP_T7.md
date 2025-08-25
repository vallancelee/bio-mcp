# STEP T7: Multi-Source Document Abstraction

## Summary
Introduce a minimal, shared `Document` model that enables multiple biomedical sources (starting with PubMed) while preserving source-specific richness through extensions. This refactoring prepares the pipeline for adding ClinicalTrials.gov and other sources without breaking existing contracts.

## Context
Currently, the system is tightly coupled to PubMed's data structure. To support multiple document sources efficiently, we need:
- A stable, minimal base model for cross-source operations
- Source-specific extensions without polluting the core model  
- Reproducible provenance and deduplication capabilities
- Backward compatibility with existing PubMed workflows

## Technical Approach

### 1. Core Models (Day 1)
Create shared document abstractions in `src/bio_mcp/models/document.py`:

```python
class Document(BaseModel):
    # Core identity
    uid: str                    # e.g., "pubmed:12345678"
    source: str                 # "pubmed", "clinicaltrials", etc.
    source_id: str             # Source-specific ID
    
    # Minimal content
    title: Optional[str]
    text: str                  # Main text to chunk/embed
    
    # Temporal metadata
    published_at: Optional[datetime]
    fetched_at: Optional[datetime]
    
    # Common metadata
    authors: Optional[List[str]]
    labels: Optional[List[str]]
    identifiers: Dict[str, str]  # {"doi": "10.1234/..."}
    
    # Provenance & extensions
    provenance: Dict[str, Any]   # {"s3_raw_uri": ..., "content_hash": ...}
    detail: Dict[str, Any]       # Source-specific fields
    schema_version: int = 1

class Chunk(BaseModel):
    chunk_id: str               # uid + ":" + idx
    parent_uid: str             # Document.uid
    source: str
    chunk_idx: int
    text: str
    # Inheritable metadata
    title: Optional[str]
    published_at: Optional[datetime]
    meta: Dict[str, Any]
```

### 2. PubMed Normalizer (Day 1-2)
Create `src/bio_mcp/services/normalize_pubmed.py`:

```python
def to_document(raw: Dict[str, Any], *, 
                s3_raw_uri: str, 
                content_hash: str) -> Document:
    """Convert raw PubMed data to normalized Document."""
    pmid = str(raw.get("pmid"))
    
    # Map to base fields
    doc = Document(
        uid=f"pubmed:{pmid}",
        source="pubmed",
        source_id=pmid,
        title=raw.get("title"),
        text=raw.get("abstract", ""),
        published_at=parse_pubmed_dates(raw),
        authors=raw.get("authors"),
        identifiers={"doi": raw.get("doi")} if raw.get("doi") else {},
        provenance={
            "s3_raw_uri": s3_raw_uri,
            "content_hash": content_hash
        },
        # PubMed-specific fields go in detail
        detail={
            "journal": raw.get("journal"),
            "mesh_terms": raw.get("mesh_terms"),
            "keywords": raw.get("keywords"),
            "affiliations": raw.get("affiliations")
        }
    )
    return doc
```

### 3. Chunking Service Update (Day 2)
Refactor `src/bio_mcp/services/chunking.py`:

```python
def chunk_document(doc: Document, 
                  strategy: ChunkingStrategy = DEFAULT) -> List[Chunk]:
    """Chunk a normalized document."""
    text_segments = strategy.split(doc.text)
    
    chunks = []
    for idx, segment in enumerate(text_segments):
        chunk = Chunk(
            chunk_id=f"{doc.uid}:{idx}",
            parent_uid=doc.uid,
            source=doc.source,
            chunk_idx=idx,
            text=segment,
            title=doc.title,
            published_at=doc.published_at,
            meta={"language": doc.detail.get("language")}
        )
        chunks.append(chunk)
    
    return chunks
```

### 4. Embedding/Indexing Updates (Day 2-3)
Update `src/bio_mcp/services/embed_index.py`:

```python
async def embed_and_index_chunks(chunks: List[Chunk]) -> IndexResult:
    """Embed and index normalized chunks."""
    # Batch embed
    embeddings = await embed_texts([c.text for c in chunks])
    
    # Prepare payloads with metadata
    payloads = []
    for chunk, embedding in zip(chunks, embeddings):
        payload = {
            "id": chunk.chunk_id,
            "vector": embedding,
            "properties": {
                "parent_uid": chunk.parent_uid,
                "source": chunk.source,
                "title": chunk.title,
                "text": chunk.text,
                "published_at": chunk.published_at.isoformat() 
                               if chunk.published_at else None,
                **chunk.meta
            }
        }
        payloads.append(payload)
    
    # Batch upsert to Weaviate
    return await weaviate_client.batch_upsert(payloads)
```

### 5. Database Schema (Day 3)
Add normalized document tracking table:

```sql
-- Migration: add_documents_table.py
CREATE TABLE documents (
    uid TEXT PRIMARY KEY,                    -- "pubmed:12345678"
    source TEXT NOT NULL,                    -- "pubmed"
    source_id TEXT NOT NULL,                 -- "12345678"
    title TEXT,
    published_at TIMESTAMPTZ,
    s3_raw_uri TEXT NOT NULL,                -- Provenance
    content_hash TEXT NOT NULL,              -- Deduplication
    detail JSONB,                           -- Source-specific data
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_documents_source (source),
    INDEX idx_documents_published (published_at),
    INDEX idx_documents_hash (content_hash),
    UNIQUE INDEX idx_documents_source_id (source, source_id)
);
```

### 6. Pipeline Integration (Day 3-4)
Wire the new models into PubMed sync with feature flag:

```python
# src/bio_mcp/services/pubmed_sync.py
async def process_pubmed_article(raw: Dict[str, Any]) -> SyncResult:
    # 1. Archive raw to S3 (unchanged)
    s3_uri, content_hash = await archive_to_s3(raw)
    
    # 2. Check feature flag
    if config.use_document_model:
        # New path
        doc = normalize_pubmed.to_document(
            raw, 
            s3_raw_uri=s3_uri,
            content_hash=content_hash
        )
        
        # Store normalized document
        await db.upsert_document(doc)
        
        # Chunk and index
        chunks = chunk_document(doc)
        await embed_and_index_chunks(chunks)
    else:
        # Legacy path (unchanged)
        await legacy_process(raw)
    
    return SyncResult(success=True, doc_uid=doc.uid if doc else None)
```

## Implementation Plan

### Phase 1: Models & Normalizer (Day 1)
1. Create `src/bio_mcp/models/document.py` with Document and Chunk models
2. Add comprehensive Pydantic validation tests
3. Create `src/bio_mcp/services/normalize_pubmed.py`
4. Unit tests for PubMed normalizer with varied input shapes

### Phase 2: Service Updates (Day 2)
1. Update chunking service to accept Document input
2. Add backward compatibility wrapper for legacy calls
3. Update embedding/indexing to use Chunk model
4. Create adapter tests ensuring identical output

### Phase 3: Database & Pipeline (Day 3)
1. Create and run migration for documents table
2. Add DocumentRepository with CRUD operations
3. Wire normalized flow into PubMed sync (feature-flagged)
4. Integration tests for full pipeline

### Phase 4: Validation & Rollout (Day 4)
1. Contract tests comparing legacy vs new pipeline outputs
2. Golden dataset tests with known PubMed records
3. Performance benchmarks (should be neutral or better)
4. Enable feature flag in staging environment

### Phase 5: Cleanup (Day 5)
1. Monitor staging for 24 hours
2. Remove legacy adapters after validation
3. Enable feature flag in production
4. Documentation updates

## Testing Strategy

### Unit Tests
- Document/Chunk model validation
- PubMed normalizer edge cases
- Chunking boundary stability
- Embedding metadata preservation

### Contract Tests
```python
@pytest.mark.contract
async def test_pubmed_sync_backward_compatible():
    """Ensure identical behavior with new models."""
    raw_article = load_test_article()
    
    # Run both paths
    legacy_result = await legacy_process(raw_article)
    new_result = await process_with_document_model(raw_article)
    
    # Compare observable outputs
    assert legacy_result.chunk_count == new_result.chunk_count
    assert legacy_result.indexed_text == new_result.indexed_text
    assert legacy_result.metadata_keys == new_result.metadata_keys
```

### Integration Tests
- End-to-end: raw → S3 → normalize → chunk → embed → index
- Idempotency: re-processing same article produces same result
- Deduplication: content_hash prevents duplicate processing

### Golden Dataset
Create `tests/fixtures/golden_pubmed_articles.json` with 5 representative articles covering:
- Standard article with abstract
- Article without abstract
- Article with multiple authors
- Article with MeSH terms
- Non-English article

## Success Metrics
- ✅ All existing PubMed tests pass unchanged
- ✅ Document/Chunk models handle 100% of current PubMed data
- ✅ No performance regression (±5% latency/throughput)
- ✅ Feature flag allows instant rollback
- ✅ Documents table correctly tracks all processed articles

## Rollback Plan
1. Set `BIO_MCP_USE_DOCUMENT_MODEL=false`
2. System immediately reverts to legacy pipeline
3. No data loss (raw S3 and legacy tables unchanged)
4. Fix issues and re-deploy with flag off

## Future Extensions (Not in Scope)
- ClinicalTrials.gov normalizer
- Patent document normalizer  
- Preprint server integration
- Cross-source deduplication
- Document-level quality scoring

## Dependencies
- Existing: PubMed sync, chunking, embedding services
- New: None (self-contained refactor)
- External: No API changes

## Configuration
```yaml
# Environment variables
BIO_MCP_USE_DOCUMENT_MODEL: "false"  # Feature flag (default off)
BIO_MCP_DOCUMENT_SCHEMA_VERSION: "1"  # For future migrations

# Chunking strategy (unchanged)
BIO_MCP_CHUNK_MAX_TOKENS: "512"
BIO_MCP_CHUNK_OVERLAP: "50"
```

## Notes
- Preserves all existing functionality
- Zero changes to user-facing APIs
- Enables future multi-source support
- Maintains full backward compatibility
- Clean abstraction boundaries

---

**Status**: Ready for implementation
**Priority**: High (blocks multi-source support)
**Estimated**: 5 days
**Team**: Backend engineering