# IMPLEMENTATION\_PLAN\_V2.md

Audience: **Claude**. Purpose: ship the next iteration of **bio‑mcp** with a shared `Document` model, deterministic chunk IDs, a multi‑source metadata pattern, and a clean re‑ingest using a new Weaviate collection and embedding model.

> **Assumption:** We’re starting fresh—no data migration required. We will (re)create the vector collection and re‑ingest.

---

## 0) Goals

1. Introduce a **minimal shared `Document` base** + **namespaced source metadata**.
2. Implement the **chunking strategy** (section‑aware, token budgets, overlap, numeric‑safety) with **deterministic chunk IDs**.
3. Define and create a **new Weaviate collection** (fresh index) with the right schema.
4. Use a **biomedical embedding model** (Hugging Face) with Weaviate (`text2vec-huggingface` or local transformers container).
5. Preserve/extend S3 archiving and jobs infra; keep HTTP/MCP surface stable.
6. Land tests, docs, and Make targets so devs can iterate quickly.

---

## 1) High‑Level Plan (Milestones)

1. **Models**: add `Document` + `Chunk` models; finalize metadata shape (top‑level + namespaced `meta.src.<source>`).
2. **Chunker**: implement section‑aware chunking per strategy + UUIDv5 chunk IDs; tests and invariants.
3. **Weaviate schema**: create a new collection (fresh) with explicit properties and the chosen vectorizer.
4. **Embedding pipeline**: update `EmbeddingService` to write deterministic IDs, complete metadata, and use the HF BioBERT model.
5. **Re‑ingest**: run a small seed set; then run full PubMed flow; verify quality.
6. **RAG tweaks**: apply section & quality boosts post‑search; fix abstract reconstruction.
7. **DX/CI**: tests (unit/contract/integration), Makefile targets, and ONBOARDING docs validated.

---

## 2) Data Models (Pydantic)

**File:** `src/bio_mcp/models/document.py`

```python
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class Document(BaseModel):
    uid: str                  # e.g., "pubmed:12345678"
    source: str               # "pubmed", "ctgov", ...
    source_id: str            # external ID, e.g., PMID

    title: Optional[str] = None
    text: str                 # main body to chunk (abstract/summary)

    published_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    language: Optional[str] = None

    authors: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    identifiers: Dict[str, str] = Field(default_factory=dict)  # e.g., {"doi": "10.1234/..."}

    provenance: Dict[str, Any] = Field(default_factory=dict)   # {"s3_raw_uri":..., "content_hash":...}
    license: Optional[str] = None

    detail: Dict[str, Any] = Field(default_factory=dict)       # source-specific fields
    schema_version: int = 1

class Chunk(BaseModel):
    chunk_id: str             # stable short ID within doc, e.g., "s0", "w1" (section/window)
    uuid: str                 # UUIDv5 computed from parent_uid + chunk_id
    parent_uid: str           # equals Document.uid
    source: str               # "pubmed"

    chunk_idx: int
    text: str
    title: Optional[str] = None
    section: Optional[str] = None  # Background/Methods/Results/Conclusions/Other

    tokens: Optional[int] = None
    n_sentences: Optional[int] = None

    published_at: Optional[datetime] = None
    meta: Dict[str, Any] = Field(default_factory=dict)  # holds chunker_version, tokenizer, and src namespaced data
```

**Rationale**

* Keep base minimal for cross‑source ops; hang richer source data off `detail`/`meta.src.<source>`.

---

## 3) Chunking Strategy (must‑dos)

**File:** `src/bio_mcp/services/chunking.py`

**Constants**

* Target window: **250–350 tokens**
* Hard max: **450 tokens**
* Overlap: **50 tokens** (for long sections/windows only)
* Min section size before chunking: **≥120 tokens**
* Title prefix: **only on chunk 0** (we’ll store title separately and avoid duplicating on rebuild)
* Header hint: add lightweight `[Section] Results` prefix **in metadata** (not in `text`) to keep `rag.get` clean
* Record: `tokens`, `n_sentences`, `section`, `chunker_version`, `tokenizer`

**Algorithm (outline)**

1. **Detect sections** (Regex for common PubMed headings; fallback = single section).
2. **Sentence‑aware split** per section; merge sentences until target window (≤450), add 50‑token overlap if window > target.
3. **Numeric safety expansion**: ensure effect sizes and comparators live in the same chunk (include adjacent sentence if needed).
4. **Chunk IDs**: enumerate per doc as `s0`, `s1`, … or `w0`, `w1` when no sections.
5. **UUIDv5** per chunk: `uuid5(NAMESPACE, f"{parent_uid}:{chunk_id}")`.

**Tests**

* Gold abstracts → assert: boundaries, overlap, section labels, token counts, deterministic IDs.
* Tokenizer parity: use the same tokenizer as the embedder (HF tokenizer if using HF model).

---

## 4) Metadata Pattern (multi‑source friendly)

**Top‑level** (fast filter/score across sources):

* `parent_uid`, `source`, `section`, `title`, `text`, `published_at`, `year`, `tokens`, `n_sentences`, `quality_total`

**Namespaced blob** (per source):

* `meta.src.pubmed`: `{ mesh_terms, journal, edat, lr, source_url, pmcid, doi_alt, ... }`
* `meta.src.ctgov`: `{ status, phase, conditions[], interventions[], ... }`
* Keep chunker internals: `meta.chunker_version`, `meta.tokenizer`.

**Rule:** Promote to top‑level only if used frequently in filters/ranking. Everything else stays in `meta.src.<source>`.

---

## 5) Weaviate Collection (fresh index)

**Name:** `DocumentChunk_v2` (new; do not reuse old collection)

**Vectorizer option A (cloud/HF API):** `text2vec-huggingface` with model `pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb`.

**Vectorizer option B (local):** `text2vec-transformers` with a baked inference container that includes the same model.

**Schema (pseudo with v4 client)**

```python
from weaviate.classes.config import Configure, Property, DataType

client.collections.create(
  name="DocumentChunk_v2",
  properties=[
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
    Property(name="meta", data_type=DataType.OBJECT),  # or meta_json TEXT if nested objects are problematic
  ],
  vector_config=[
    Configure.Vectors.text2vec_huggingface(
      name="abstract_vec",
      source_properties=["text"],
      model="pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
    )
  ],
)
```

**Insert rule:** always provide **`id=<chunk.uuid>`** so re‑ingest is idempotent.

---

## 6) Embedding & Storage Flow (code changes)

**Files**

* `src/bio_mcp/services/embedding_service.py` (update)
* `src/bio_mcp/services/services.py` (wire chunking + embedding)
* `src/bio_mcp/sources/pubmed/*` (ensure normalizer provides needed fields)

**Changes**

* Construct `Document` from normalized PubMed record (include `provenance` with S3 URI and content hash).
* Run chunker → `List[Chunk]` with `uuid` populated (UUIDv5).
* Insert into `DocumentChunk_v2` with `id=chunk.uuid` + properties above; attach `meta.src.pubmed.*` fields.
* Ensure tokens/n\_sentences are computed with the same tokenizer used by the embedder’s family.

**RAG adjustments**

* After retrieval, apply section boosts (`Results`, `Conclusions`) and `quality_total` scaling.
* In `rag.get`, reconstruct the abstract **without** duplicating title/headers (use stored `title` + clean chunk `text`).

---

## 7) S3 Archive + Jobs (unchanged structure)

* Keep per‑PMID S3 raw envelope (`.json.zst`) and DB pointers.
* Jobs API + worker continue to orchestrate long runs (PubMed sync).
* Add manifest S3 path in job result for audit.

---

## 8) Configuration

Update `.env.example` (local defaults):

```
BIO_MCP_ARCHIVE_BUCKET=bio-mcp-local
BIO_MCP_ARCHIVE_PREFIX=pubmed
BIO_MCP_ARCHIVE_COMPRESSION=zstd
BIO_MCP_WEAVIATE_URL=http://localhost:8080
BIO_MCP_WEAVIATE_COLLECTION=DocumentChunk_v2
BIO_MCP_EMBED_MODEL=pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb
BIO_MCP_UUID_NAMESPACE=1b2c3d4e-0000-0000-0000-000000000000
BIO_MCP_JSON_LOGS=true
BIO_MCP_LOG_LEVEL=INFO
```

> Choose and fix a UUID namespace once; don’t rotate it.

---

## 9) Tests

**Unit**

* Chunker golden tests (sectioning, overlap, numeric safety, tokens, UUIDv5 stability).
* Document→Chunk mapping and metadata population.

**Contract**

* `rag.search` and `rag.get` return the same observable fields as before; title duplication fixed.

**Integration**

* LocalStack/MinIO + Postgres + Weaviate: end‑to‑end ingest and search of a small PubMed set.
* Idempotent re‑ingest (same UUIDs, no dupes).

**Evaluation (optional but recommended)**

* Small recall\@K/NDCG harness for 50–100 labeled queries.

---

## 10) Makefile Targets

```
# run stack
up:            docker compose up -d
run-http:      python -m bio_mcp.main_http
run-worker:    python -m bio_mcp.main_worker

# schema
schema-create: python -m scripts.create_weaviate_schema --collection DocumentChunk_v2
schema-drop:   python -m scripts.drop_weaviate_schema --collection DocumentChunk_v2

# ingest
ingest-sample: python -m scripts.ingest_pubmed_sample --pmids 1234,5678,9012

# tests
test:          pytest -q
test-unit:     pytest -q tests/unit
test-int:      pytest -q tests/integration
smoke-http:    curl -fsS localhost:8080/healthz && curl -fsS localhost:8080/readyz
```

---

## 11) Rollout (fresh index)

1. **Create collection** `DocumentChunk_v2` with the chosen vectorizer.
2. **Ingest sample** (50–100 PMIDs); validate quality, section boosts, abstract reconstruction.
3. **Re‑ingest full** PubMed slice; monitor write throughput and Weaviate RAM/IO.
4. **Switch RAG** to query the new collection name.
5. Keep the old collection temporarily for comparison; delete when satisfied.

---

## 12) Observability & Guardrails

* JSON logs with `trace_id`, `job_id`, `doc.uid`, `chunk.uuid`, elapsed ms.
* Metrics: requests/errors/latency; ingest throughput; Weaviate 5xx; queue depth.
* Back‑pressure: per‑tool semaphores; return 429 on saturation.
* Readiness: gate on DB + Weaviate schema present; optional S3 probe in staging.

---

## 13) PR Sequence (for Claude)

1. **feat(models):** add `Document`, `Chunk` + tests.
2. **feat(chunker):** implement section‑aware chunker + UUIDv5; tests.
3. **feat(schema):** create `DocumentChunk_v2` schema script (HF model config) + Make targets.
4. **feat(embedding):** deterministic insert with `id`, full metadata (`meta.src.pubmed`); tokenizer parity.
5. **feat(rag):** section/quality boosts; fix `rag.get` reconstruction.
6. **chore(e2e):** ingest sample PMIDs; integration tests; docs.
7. **deploy:** create collection in staging; ingest; switch RAG; soak; then prod.

**Each PR must include:** tests, docs update, and `make smoke-http` green.

---

## 14) Design Choices (context)

* **Minimal base + namespaced metadata** avoids lowest‑common‑denominator schemas while keeping query‑critical fields fast.
* **UUIDv5 chunk IDs** guarantee idempotent upserts and stable references over re‑runs.
* **Section‑aware chunking** (with overlap and numeric safety) improves recall/precision for abstracts.
* **Fresh collection** avoids migration complexity and lets us evaluate the new embedding model cleanly.

---

## 15) Appendix: Example Insert Payload

```python
properties = {
  "parent_uid": "pubmed:12345678",
  "source": "pubmed",
  "section": "Results",
  "title": "Temozolomide in Glioblastoma",
  "text": "...chunk text...",
  "published_at": "2023-08-01T00:00:00Z",
  "year": 2023,
  "tokens": 322,
  "n_sentences": 9,
  "quality_total": 0.7,
  "meta": {
    "chunker_version": "v1.2.0",
    "tokenizer": "hf:pritamdeka/BioBERT-...",
    "src": {
      "pubmed": {
        "mesh_terms": ["Glioblastoma", "Temozolomide"],
        "journal": "NEJM",
        "edat": "2023-08-02T00:00:00Z",
        "lr": "2024-01-05T00:00:00Z",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "pmcid": "PMC12345",
        "doi": "10.1056/NEJM..."
      }
    }
  }
}
collection.data.insert(id=chunk.uuid, properties=properties)
```

---

**End of Plan** — This file is meant to be self‑contained context for Claude to implement V2 without hunting through prior threads.
