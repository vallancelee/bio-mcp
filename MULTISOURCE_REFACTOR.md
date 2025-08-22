# Refactor Plan — Shared `Document` (PubMed‑first)

Audience: **Claude** (primary implementer). Purpose: introduce a **minimal, shared `Document` model** used by chunking/embedding/indexing while keeping **source‑specific richness** via extensions. **Phase 1 focuses on PubMed only**; other sources (e.g., ClinicalTrials.gov) can plug in later without breaking contracts.

---

## 0) Objectives & Non‑Goals

**Objectives**

* Define a **stable, minimal `Document` base** powering shared pipelines (chunk → embed → index).
* Refactor PubMed ingest to emit `Document` (and `Chunk`) without changing user‑visible behavior.
* Preserve **raw S3 archive** and DB pointers; add normalized layer cleanly.

**Non‑Goals (Phase 1)**

* No changes to ClinicalTrials.gov or other sources yet.
* No changes to HTTP/MCP API surface beyond internal wiring.
* No ranking changes beyond metadata passing; keep results identical where possible.

---

## 1) Design Tenets

* **Minimal base; rich extensions**: keep base fields only for cross‑source operations. Put source‑specific details in `detail` (validated per source) or future subclasses.
* **Stable IDs**: `uid = f"{source}:{source_id}"` (e.g., `pubmed:12345678`).
* **Reproducible provenance**: carry `content_hash` and `s3_raw_uri` from raw archive.
* **Backwards compatibility**: chunk text stays the same; we add metadata, not remove.

---

## 2) Data Model (Pydantic)

Create `src/bio_mcp/models/document.py`.

```python
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class Document(BaseModel):
    uid: str                          # e.g., "pubmed:12345678"
    source: str                       # "pubmed"
    source_id: str                    # "12345678"

    title: Optional[str] = None
    text: str                         # main text to chunk (abstract/summary)

    published_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    language: Optional[str] = None

    authors: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    identifiers: Dict[str, str] = Field(default_factory=dict)  # e.g., {"doi": "10.1234/..."}

    provenance: Dict[str, Any] = Field(default_factory=dict)   # {"s3_raw_uri":..., "content_hash":...}
    license: Optional[str] = None

    detail: Dict[str, Any] = Field(default_factory=dict)       # source‑specific extra fields
    schema_version: int = 1

class Chunk(BaseModel):
    chunk_id: str                     # uid + ":" + idx
    parent_uid: str                   # equals Document.uid
    source: str                       # "pubmed"
    chunk_idx: int
    text: str
    title: Optional[str] = None
    tokens: Optional[int] = None
    section: Optional[str] = None
    published_at: Optional[datetime] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
```

**Rationale**

* `text` is the only required content for embedding, keeping base minimal.
* `detail` provides room for MeSH terms, journal, etc., without baking them into base.
* `provenance` holds S3 pointer + `content_hash` for audit, reproducibility, and dedupe.

---

## 3) PubMed Normalization (new service)

Add `src/bio_mcp/services/normalize_pubmed.py`.

```python
from __future__ import annotations
from typing import Dict, Any
from datetime import datetime
from .pubmed_utils import parse_pubmed_dates  # implement if missing
from bio_mcp.models.document import Document


def to_document(raw: Dict[str, Any], *, s3_raw_uri: str, content_hash: str) -> Document:
    pmid = str(raw.get("pmid") or raw.get("PMID"))
    title = raw.get("title") or raw.get("Title")
    abstract = raw.get("abstract") or raw.get("Abstract") or ""
    published_at = parse_pubmed_dates(raw)
    authors = raw.get("authors") or raw.get("Authors")
    doi = (raw.get("doi") or raw.get("DOI") or "").strip() or None
    language = (raw.get("language") or raw.get("Language") or None)

    detail = {
        "journal": raw.get("journal") or raw.get("Journal"),
        "mesh_terms": raw.get("mesh_terms") or raw.get("MeSH"),
        "keywords": raw.get("keywords") or raw.get("Keywords"),
        "affiliations": raw.get("affiliations") or raw.get("Affiliations"),
    }

    return Document(
        uid=f"pubmed:{pmid}",
        source="pubmed",
        source_id=pmid,
        title=title,
        text=abstract,
        published_at=published_at,
        fetched_at=datetime.utcnow(),
        language=language,
        authors=authors,
        labels=None,
        identifiers={"doi": doi} if doi else {},
        provenance={"s3_raw_uri": s3_raw_uri, "content_hash": content_hash},
        detail={k: v for k, v in detail.items() if v is not None},
    )
```

**Rationale**

* Keep mapping shallow and resilient to raw schema variants.
* PubMed‑only enrichments go under `detail` to avoid polluting base.

---

## 4) Chunking Changes

Update existing chunker to accept `Document` instead of ad‑hoc dicts. Place in `src/bio_mcp/services/chunking.py`.

```python
from __future__ import annotations
from typing import List
from bio_mcp.models.document import Document, Chunk

MAX_CHARS = 2000  # example; keep your current policy


def chunk_document(doc: Document) -> List[Chunk]:
    text = doc.text or ""
    pieces = _split(text, MAX_CHARS)
    chunks: List[Chunk] = []
    for i, piece in enumerate(pieces):
        chunks.append(Chunk(
            chunk_id=f"{doc.uid}:{i}",
            parent_uid=doc.uid,
            source=doc.source,
            chunk_idx=i,
            text=piece,
            title=doc.title,
            published_at=doc.published_at,
            meta={"language": doc.language}
        ))
    return chunks


def _split(text: str, max_chars: int) -> List[str]:
    # Replace with your current strategy (sentence / token aware). This is a placeholder.
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
```

**Rationale**

* Keep existing behavior but formalize the types for consistency.

---

## 5) Embedding & Indexing Updates

Refactor embedding to accept `Chunk` and attach base metadata. File: `src/bio_mcp/services/embed_index.py`.

```python
from __future__ import annotations
from typing import List
from bio_mcp.models.document import Chunk

# pseudo imports: your embedding + weaviate clients

async def embed_and_index(chunks: List[Chunk]):
    # 1) embed in batches (keep your provider)
    vecs = await embed([c.text for c in chunks])

    # 2) upsert to vector store with metadata
    payloads = []
    for c, v in zip(chunks, vecs):
        payloads.append({
            "id": c.chunk_id,
            "vector": v,
            "properties": {
                "parent_uid": c.parent_uid,
                "source": c.source,
                "title": c.title,
                "text": c.text,
                "published_at": c.published_at.isoformat() if c.published_at else None,
                **({"language": c.meta.get("language")} if c.meta else {}),
            }
        })
    await weaviate_batch_upsert(payloads)
```

**Weaviate schema**

* Continue using your existing class (e.g., `DocumentChunk`). Ensure it contains at least: `id`, `parent_uid`, `source`, `title`, `text`, `published_at`, plus any existing fields.

---

## 6) Ingest Flow Wiring (PubMed)

Where you currently process PubMed records (likely within a sync/fetch service):

1. **Fetch raw** via existing client.
2. **Archive to S3** (unchanged): obtain `s3_raw_uri`, `content_hash`.
3. **Normalize**: `doc = to_document(raw, s3_raw_uri=…, content_hash=…)`.
4. **Chunk**: `chunks = chunk_document(doc)`.
5. **Embed & index**: `await embed_and_index(chunks)`.
6. **Persist normalized pointer (optional)**: add a `documents` table row keyed by `uid` with `provenance` and high‑level metadata (title, published\_at) for browsing/debugging.

**Optional Table** `documents` (helps with audits and cross‑source dedupe later):

```sql
CREATE TABLE IF NOT EXISTS documents (
  uid TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  source_id TEXT NOT NULL,
  title TEXT,
  published_at TIMESTAMPTZ,
  s3_raw_uri TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 7) Backward Compatibility & Migration

* **No data loss**: Keep raw S3 + pointer tables as‑is.
* **Index continuity**: Chunk text, count, and ids remain stable. If you change `chunk_id` format, add a migration script or reindex.
* **Gradual rollout**: Behind a feature flag `BIO_MCP_USE_DOCUMENT_MODEL=true` so you can flip back.

---

## 8) Testing Plan

**Unit**

* `Document`/`Chunk` Pydantic validation (required/optional fields).
* PubMed normalizer: varied raw shapes → expected `Document` values.
* Chunker: stable chunk boundaries given same input.

**Contract**

* Tool invocation (`pubmed.get`, `pubmed.sync`) produces identical **observable** results (e.g., number of chunks indexed, titles) before vs. after refactor.

**Integration**

* End-to-end: raw → S3 → normalize → chunk → embed → index; verify vector count and metadata.
* Idempotency preserved when re-running the same PubMed article.

**Golden Data**

* Keep 3–5 PubMed records with known fields (title, abstract, mesh). Assert normalized values.

---

## 9) Implementation Steps (PR‑by‑PR)

1. **Models PR**: add `Document` & `Chunk` + tests; no runtime usage.
2. **Normalizer PR**: add `normalize_pubmed.to_document()` + unit tests.
3. **Chunker PR**: adapt chunker to `Document` inputs; keep legacy wrapper for old call sites.
4. **Embed/Index PR**: accept `Chunk`; keep legacy wrapper.
5. **Wire‑in PR** (feature‑flagged): PubMed pipeline calls normalize → chunk → embed; add optional `documents` table.
6. **Clean‑up PR**: remove legacy adapters, flip flag on in staging; contract tests must be identical.

---

## 10) Design Choices (explained)

* **Base + detail**: Avoid lowest‑common‑denominator trap; base is minimal (id, text, times, authors), and `detail` carries MeSH/journal without breaking cross‑source reuse.
* **Stable `uid`**: Enables cross‑source linking and consistent chunk ids (`uid:idx`).
* **Pydantic models**: Strong typing + validation + JSON serialization for tools and debugging.
* **Optional `documents` table**: Not required for search but valuable for audits, backfills, and joins (e.g., to manifests).
* **Feature flag**: Safe rollout with quick revert.

---

## 11) Acceptance Criteria (Phase 1)

* `Document` & `Chunk` classes exist with tests and docs.
* PubMed ingest produces `Document` instances and `Chunk`s; embeddings/indexing succeed.
* No regression in retrieval quality or latency for PubMed operations.
* Raw S3 archive and pointer tables continue to be written identically.
* Optional `documents` table shows 1 row per PubMed article with correct `uid`, `s3_raw_uri`, and `content_hash`.
* Feature flag default **on** in staging, **off** in prod until validated.

---

## 12) Follow‑ups (later phases)

* Add `ClinicalTrials.gov` normalizer/client and plug into the same pipeline.
* Consider per‑type subclasses (`ArticleDocument`, `TrialDocument`) if behavior diverges.
* Expand Weaviate schema with a small number of high‑signal extension fields (e.g., `phase`, `status`) once trials are added.
