# Bio-MCP API Contracts

This document defines the public contracts between MCP clients and the bio-mcp server, plus internal adapter boundaries. All request/response bodies are JSON. Changes follow semantic versioning; breaking changes bump the major version.

---

## 🔄 MCP API (Public)

### Tool: `pubmed.sync.incremental`

**Purpose:** Search PubMed and sync documents incrementally using EDAT watermarks for efficient updates.

#### Request Schema
```json
{
  "type": "object",
  "required": ["query"],
  "properties": {
    "query": { 
      "type": "string", 
      "minLength": 1,
      "description": "Search query for PubMed documents to sync incrementally"
    },
    "limit": { 
      "type": "integer", 
      "minimum": 1, 
      "maximum": 500,
      "default": 100,
      "description": "Maximum number of new documents to sync in this batch"
    }
  },
  "additionalProperties": false
}
```

#### Response Schema
```json
{
  "type": "object",
  "required": ["synced_documents", "total_found"],
  "properties": {
    "synced_documents": { 
      "type": "integer",
      "minimum": 0,
      "description": "Number of documents successfully synced"
    },
    "total_found": { 
      "type": "integer", 
      "minimum": 0,
      "description": "Total number of documents found in search"
    },
    "status": {
      "type": "string",
      "description": "Status message"
    }
  },
  "additionalProperties": false
}
```

#### Guarantees
- ✅ **Idempotent**: Safe to replay multiple times
- ✅ **Incremental**: Only syncs new documents not already in database

### Tool: `rag.search`

**Purpose:** Advanced hybrid search combining BM25 keyword search with vector similarity, optimized for biotech investment research.

#### Request Schema
```json
{
  "type": "object",
  "required": ["query"],
  "properties": {
    "query": { 
      "type": "string", 
      "minLength": 1,
      "description": "Search query for biomedical literature"
    },
    "top_k": { 
      "type": "integer", 
      "minimum": 1, 
      "maximum": 50, 
      "default": 10,
      "description": "Number of results to return"
    },
    "search_mode": {
      "type": "string",
      "enum": ["hybrid", "semantic", "bm25"],
      "description": "Search strategy: 'hybrid' (BM25+vector), 'semantic' (vector only), 'bm25' (keyword only)",
      "default": "hybrid"
    },
    "alpha": {
      "type": "number",
      "description": "Hybrid search weighting: 0.0=pure BM25 keyword, 1.0=pure vector semantic, 0.5=balanced",
      "default": 0.5,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "rerank_by_quality": { 
      "type": "boolean", 
      "default": true,
      "description": "Boost results by PubMed quality metrics, journal impact, and investment relevance"
    },
    "return_chunks": {
      "type": "boolean",
      "default": false,
      "description": "Return individual chunks or reconstructed documents"
    },
    "enhance_query": {
      "type": "boolean", 
      "default": true,
      "description": "Enhance query with biomedical synonyms and terms"
    },
    "filters": {
      "type": "object",
      "description": "Metadata filters for date ranges, journals, etc.",
      "properties": {
        "date_from": {
          "type": "string",
          "description": "Filter results from this date (YYYY-MM-DD)"
        },
        "date_to": {
          "type": "string",
          "description": "Filter results to this date (YYYY-MM-DD)"
        },
        "journals": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Filter by specific journals"
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

#### Response Schema
```json
{
  "type": "object",
  "required": ["documents", "total_results"],
  "properties": {
    "documents": {
      "type": "array",
      "description": "Search results ordered by relevance score",
      "items": {
        "type": "object",
        "description": "Document or chunk result with metadata",
        "properties": {
          "uuid": { 
            "type": "string",
            "description": "Unique document/chunk identifier"
          },
          "title": {
            "type": ["string", "null"],
            "description": "Document title"
          },
          "abstract": {
            "type": ["string", "null"], 
            "description": "Document abstract or chunk text"
          },
          "score": { 
            "type": "number",
            "description": "Final combined relevance score"
          },
          "sections_found": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Document sections found (for document results)"
          },
          "chunk_count": {
            "type": "integer",
            "description": "Number of chunks in document (for document results)"
          },
          "source_url": {
            "type": ["string", "null"],
            "description": "Source URL if available"
          }
        },
        "additionalProperties": true
      }
    },
    "total_results": {
      "type": "integer",
      "minimum": 0,
      "description": "Total number of results returned"
    },
    "performance": {
      "type": "object",
      "description": "Performance and execution metadata",
      "properties": {
        "search_time_ms": {"type": "string"},
        "total_time_ms": {"type": "string"}, 
        "target_time_ms": {"type": "number"},
        "enhanced_query": {"type": "boolean"},
        "reconstructed_docs": {"type": "boolean"}
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

#### Guarantees
- ✅ **Score Ordering**: `score` is the final rerank key (quality-weighted if enabled)
- ✅ **Stable IDs**: `doc_id` is the stable key for `rag.get` / resource lookup

### Tool: `rag.get`

**Purpose:** Fetch the normalized document metadata and quality scores for a doc_id.

#### Request Schema
```json
{
  "type": "object",
  "required": ["doc_id"],
  "properties": {
    "doc_id": { 
      "type": "string", 
      "pattern": "^pmid:[0-9]+$",
      "description": "PubMed ID in format 'pmid:12345'"
    }
  },
  "additionalProperties": false
}
```

#### Response Schema
```json
{
  "type": "object",
  "required": ["doc_id", "title", "journal", "pub_types", "quality", "version"],
  "properties": {
    "doc_id": { 
      "type": "string",
      "description": "PubMed document identifier"
    },
    "title": { 
      "type": ["string","null"],
      "description": "Article title"
    },
    "abstract": { 
      "type": ["string","null"],
      "description": "Article abstract text"
    },
    "journal": { 
      "type": ["string","null"],
      "description": "Journal name"
    },
    "pub_types": { 
      "type": "array", 
      "items": { "type": "string" },
      "description": "Publication types (e.g., 'Randomized Controlled Trial')"
    },
    "pdat": { 
      "type": ["string","null"],
      "description": "Publication date (YYYY-MM-DD)"
    },
    "edat": { 
      "type": ["string","null"],
      "description": "Entrez date (ISO8601 UTC)"
    },
    "lr": { 
      "type": ["string","null"],
      "description": "Last revision date (ISO8601 UTC)"
    },
    "pmcid": { 
      "type": ["string","null"],
      "description": "PubMed Central ID"
    },
    "quality": {
      "type": "object",
      "required": ["total"],
      "description": "Quality scoring breakdown",
      "properties": {
        "design": { 
          "type": ["integer","null"],
          "description": "Study design quality score"
        },
        "recency": { 
          "type": ["integer","null"],
          "description": "Publication recency score"
        },
        "journal": { 
          "type": ["integer","null"],
          "description": "Journal impact score"
        },
        "human": { 
          "type": ["integer","null"],
          "description": "Human studies relevance score"
        },
        "total": { 
          "type": "integer",
          "description": "Combined quality score"
        }
      },
      "additionalProperties": false
    },
    "version": { 
      "type": "integer", 
      "minimum": 1,
      "description": "Document version number"
    }
  },
  "additionalProperties": false
}
```

### Tool: `corpus.checkpoint.get`

**Purpose:** Get corpus checkpoint details by ID.

#### Request Schema
```json
{
  "type": "object",
  "required": ["checkpoint_id"],
  "properties": { 
    "checkpoint_id": { 
      "type": "string", 
      "minLength": 1,
      "description": "Unique checkpoint identifier"
    } 
  },
  "additionalProperties": false
}
```

#### Response Schema
```json
{
  "type": "object",
  "required": ["checkpoint_id", "name", "created_at"],
  "properties": {
    "checkpoint_id": { 
      "type": "string",
      "description": "Checkpoint identifier"
    },
    "name": {
      "type": "string",
      "description": "Human-readable checkpoint name"
    },
    "description": {
      "type": ["string", "null"],
      "description": "Optional checkpoint description"
    },
    "created_at": { 
      "type": "string", 
      "description": "Creation timestamp (ISO8601 UTC)"
    },
    "primary_queries": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Primary queries associated with this checkpoint"
    }
  },
  "additionalProperties": false
}
```

#### Guarantees
- ✅ **Immutable**: Checkpoints are read-only once created
- ✅ **Versioned**: Each checkpoint captures a point-in-time corpus state

---

## ❌ Error Handling

### Error Envelope (all tools/resources)

On failure, all responses adopt this standard error envelope:

```json
{
  "type": "object",
  "required": ["error"],
  "properties": {
    "error": {
      "type": "object",
      "required": ["code", "message"],
      "properties": {
        "code": {
          "type": "string",
          "enum": [
            "RATE_LIMIT",        // API rate limit exceeded
            "UPSTREAM",          // External service error
            "VALIDATION",        // Invalid request parameters
            "NOT_FOUND",         // Resource not found
            "INVARIANT_FAILURE", // Internal consistency error
            "STORE",             // Database/storage error
            "EMBEDDINGS",        // Embedding service error
            "WEAVIATE",          // Vector database error
            "ENTREZ",            // PubMed API error
            "UNKNOWN"            // Unexpected error
          ]
        },
        "message": { 
          "type": "string",
          "description": "Human-readable error description"
        },
        "details": { 
          "type": ["object","array","string","null"],
          "description": "Additional error context (optional)"
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

---

## 📄 MCP Resources

### Resource: `resource://pubmed/paper/{pmid}`

**Purpose:** Direct access to PubMed document metadata.

#### Path Parameters
- `{pmid}`: PubMed ID (digits only, e.g., `12345678`)

#### Response
- **Schema**: Identical to `rag.get` response (document metadata)
- **Content-Type**: `application/json`

#### Guarantees
- ✅ **Read-only**: No mutations allowed
- ✅ **Consistency**: Always consistent with metadata store

---

## 🔧 Internal Adapter Contracts
*Non-public but stable interfaces for internal components*

### Weaviate Adapter

#### Configuration
- **Class Name**: Configurable via `WEAVIATE_CLASS` (default: `PubMedChunk`)

#### Schema Properties

**Required on upsert:**
- `pmid`: string
- `chunk_id`: string  
- `text`: string
- `vector`: number[]

**Optional properties:**
- `journal`: string
- `pub_types`: string[]
- `year`: number
- `quality_total`: number
- `edat`: string (ISO8601)
- `lr`: string (ISO8601)
- `source_url`: string

#### Interface Methods

```python
def ensure_schema() -> None
    """Initialize Weaviate schema if needed"""

def upsert_chunks(chunks: Iterable[dict]) -> BatchResult
    """Batch upsert document chunks"""

def hybrid_search(query: str, limit: int) -> List[SearchResult]
    """Perform hybrid semantic + BM25 search"""
    # Returns: [{"uuid": str, "pmid": str, "sim": float?, "bm25": float?, "quality": float?}]
```

#### Invariants
- ✅ **Stable UUIDs**: `uuid5(namespace, f"{pmid}:{chunk_id}")`
- ✅ **Vector Consistency**: `len(vector) == Embeddings.dim`
- ✅ **Normalized Vectors**: All vectors are L2-normalized

### Embeddings Adapter

#### Interface Definition
```python
class Embeddings:
    @property
    def dim(self) -> int:
        """Embedding dimensionality"""
        
    def embed(self, texts: Iterable[str]) -> List[List[float]]:
        """Generate embeddings for input texts"""
```

#### Supported Providers
- `openai`: OpenAI embedding models
- `hf`: Hugging Face transformers

#### Guarantees
- ✅ **One-to-One**: One vector per input text
- ✅ **Batched Processing**: Efficient batch operations
- ✅ **Error Handling**: Errors surfaced as typed exceptions
- ✅ **Normalized Vectors**: All output vectors are L2-normalized

### Entrez (PubMed) Client

#### Interface Methods
```python
def esearch_delta(term: str, mindate: str, maxdate: str, datetype: str = "edat") -> List[str]:
    """Search PubMed for PMIDs in date range"""
    # Returns: List of PMID strings

def esummary_batch(pmids: List[str]) -> List[DocSummary]:
    """Fetch document summaries for PMIDs"""
    # Returns: List of document metadata
```

#### DocSummary Schema
```python
@dataclass
class DocSummary:
    pmid: str
    title: Optional[str] = None
    journal: Optional[str] = None
    pub_types: List[str] = field(default_factory=list)
    pdat: Optional[str] = None      # Publication date
    edat: Optional[str] = None      # Entrez date
    lr: Optional[str] = None        # Last revision
    pmcid: Optional[str] = None     # PMC ID
    authors: Optional[List[str]] = None
    abstract: Optional[str] = None
```

#### Rate Limiting
- **Limit**: ≤ ~3 requests/second with API key
- **Backoff**: Exponential backoff on 429/5xx responses

### Metadata Store (SQL)

#### Interface Methods
```python
def upsert_pubmed_docs(docs: List[DocSummary]) -> UpsertResult:
    """Upsert document metadata with deduplication"""
    # Returns: {"inserted": int, "updated": int, "skipped": int, "max_edat_seen": str?}

def get_pubmed_doc(pmid: str) -> Optional[Doc]:
    """Retrieve document by PMID"""

def get_checkpoint(query_key: str) -> CheckpointResult:
    """Get last processed EDAT for query"""
    # Returns: {"last_edat": str?}

def set_checkpoint(query_key: str, last_edat: str) -> None:
    """Update query checkpoint watermark"""
```

#### Invariants
- ✅ **Unique PMIDs**: Each PMID appears once in the store
- ✅ **Version Control**: Version increments on content_hash change or LR advance
- ✅ **Audit Trail**: All checkpoint changes are logged

---

## 📋 Versioning Policy

### MCP Tool/Request/Response Changes

| Change Type | Version Impact | Examples |
|-------------|----------------|----------|
| **Additive fields** | Minor version bump | Adding optional request parameters, new response fields |
| **Breaking changes** | Major version bump | Field removal, rename, type changes, semantic changes |

### Database Schema Changes

| Change Type | Action Required |
|-------------|----------------|
| **Additive only** | No version bump needed |
| **Breaking changes** | Migration + major version bump |

### Examples
- ✅ **Minor**: Adding `include_abstracts: boolean` to search requests
- ❌ **Major**: Changing `pmid` from string to integer
- ❌ **Major**: Renaming `quality.total` to `quality.score`

---

## 💡 Usage Examples

### PubMed Sync Delta

**Request:**
```json
{
  "query_key": "glp1_obesity_v1", 
  "term": "(GLP-1 receptor agonist) AND obesity", 
  "overlap_days": 5
}
```

**Response:**
```json
{
  "job_id": "sync_2025-08-17T16:02:10Z",
  "inserted": 37,
  "updated": 12,
  "skipped": 441,
  "pmids_processed": 490,
  "max_edat_seen": "2025-08-17T15:59:02Z",
  "warnings": []
}
```

### RAG Search

**Request:**
```json
{
  "query": "phase 2 weight loss vs placebo", 
  "top_k": 10, 
  "quality_bias": true
}
```

**Response:**
```json
{
  "results": [
    {
      "doc_id": "pmid:384001", 
      "uuid": "7d5c...", 
      "sim": 0.72, 
      "bm25": 14.2, 
      "quality": 9, 
      "score": 1.37
    },
    {
      "doc_id": "pmid:383912", 
      "uuid": "a1b2...", 
      "sim": 0.69, 
      "bm25": 13.1, 
      "quality": 8, 
      "score": 1.25
    }
  ]
}
```

### Document Retrieval

**Request:**
```json
{
  "doc_id": "pmid:384001"
}
```

**Response:**
```json
{
  "doc_id": "pmid:384001",
  "title": "Once-weekly XYZ shows weight reduction vs placebo...",
  "abstract": "Background: ... Methods: ... Results: ...",
  "journal": "The New England Journal of Medicine",
  "pub_types": ["Randomized Controlled Trial"],
  "pdat": "2024-05-11",
  "edat": "2024-06-02T00:00:00Z",
  "lr": "2024-06-15T00:00:00Z",
  "pmcid": "PMC1234567",
  "quality": {
    "design": 2, 
    "recency": 2, 
    "journal": 2, 
    "human": 2, 
    "total": 8
  },
  "version": 2
}
```

---

## 🧪 Testing Strategy

### Contract Tests
**Purpose:** Validate all tool inputs/outputs against JSON schemas
- ✅ Request parameter validation
- ✅ Response schema compliance
- ✅ Error envelope format

### Golden Tests  
**Purpose:** Ensure consistency across versions
- ✅ Fixed PMID set with known metadata
- ✅ Assert scoring algorithm stability
- ✅ Verify Weaviate UUID consistency
- ✅ Version increment behavior

### Smoke Tests
**Purpose:** End-to-end integration testing
1. Start local Weaviate via Docker Compose
2. Run `pubmed.sync_delta` on narrow search term
3. Execute `rag.search` with test queries
4. Verify `rag.get` returns expected metadata

### Performance Tests
**Purpose:** Validate scalability requirements
- ✅ Batch processing throughput
- ✅ Search response times
- ✅ Concurrent request handling