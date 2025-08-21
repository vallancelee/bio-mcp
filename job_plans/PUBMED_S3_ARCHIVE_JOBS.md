# Implementation Manifest — PubMed S3 Archive & Jobs

Use this as a precise build plan Claude can follow. It standardizes files, function contracts, env vars, schemas, and acceptance criteria. Keep one repo & image; add two entrypoints.

---

## 0) Scope

* Persist PubMed raw payloads (per PMID) to S3 as compressed JSON.
* Record S3 pointer + content hash in Postgres (idempotent upsert).
* Expose long-running sync via a **Job API** backed by SQS + ECS worker.
* Keep existing MCP tools intact.

---

## 1) Config / Env Vars (add to `.env.example`)

```
BIO_MCP_ARCHIVE_BUCKET=<required>
BIO_MCP_ARCHIVE_PREFIX=pubmed
BIO_MCP_ARCHIVE_COMPRESSION=zstd   # zstd|gzip
BIO_MCP_DATABASE_URL=...
BIO_MCP_WEAVIATE_URL=...
BIO_MCP_PUBMED_API_KEY=...
BIO_MCP_OPENAI_API_KEY=...
BIO_MCP_LOG_LEVEL=INFO
BIO_MCP_JSON_LOGS=true
# Worker/queue
BIO_MCP_JOBS_QUEUE_URL=<sqs-url>
BIO_MCP_MAX_CONCURRENCY=200
BIO_MCP_TOOL_LIMIT_RAG_SEARCH=50
BIO_MCP_TOOL_LIMIT_PUBMED_SYNC=8
```

---

## 2) S3 Object Layout

```
s3://$BIO_MCP_ARCHIVE_BUCKET/$BIO_MCP_ARCHIVE_PREFIX/raw/
  pmid=000/123/456/12345678.json.zst   # zero-padded sharded path
s3://.../$PREFIX/manifests/sync_run=<ISO8601>.json
```

* Zero‑pad PMIDs to 8–9 digits; shard as `AAA/BBB/CCC/PMID`.
* Content: exact upstream payload wrapped in a small envelope.

**Raw object JSON**

```json
{
  "pmid": "12345678",
  "fetched_at": "<RFC3339>",
  "source": {"api": "pubmed", "endpoint": "...", "params": {...}},
  "http": {"status": 200, "etag": "..."},
  "payload": { /* exact upstream JSON */ },
  "hash": {"algo": "sha256", "value": "..."},
  "version": 1
}
```

---

## 3) Database

### 3.1 Archive pointer table (new)

```sql
CREATE TABLE IF NOT EXISTS pubmed_archive (
  pmid TEXT PRIMARY KEY,
  s3_uri TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL,
  api_etag TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Optional if you want history
CREATE TABLE IF NOT EXISTS pubmed_archive_history (
  pmid TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  s3_uri TEXT NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (pmid, content_hash)
);
```

### 3.2 Jobs table (long-running orchestration)

```sql
CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY,
  tool TEXT NOT NULL,
  params_hash TEXT NOT NULL,
  idempotency_key TEXT,
  state TEXT NOT NULL CHECK (state IN ('queued','running','succeeded','failed')),
  progress JSONB,
  result_ref TEXT,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_idem
  ON jobs (tool, params_hash, COALESCE(idempotency_key, ''));
```

---

## 4) Python Modules & Contracts

### 4.1 `src/bio_mcp/clients/s3_storage.py`

```python
from typing import Optional, Tuple
class S3Storage:
    def __init__(self, bucket: str, prefix: str, compression: str = "zstd"): ...
    def object_key_for_pmid(self, pmid: str) -> str: ...  # returns shard path + filename
    def put_json(self, key: str, data: dict) -> Tuple[str, str]: ...
    # returns (s3_uri, sha256_hex)
```

* Implement zstd/gzip compression; compute SHA‑256 over **payload bytes**.

### 4.2 `src/bio_mcp/services/pubmed_archive_service.py`

```python
from typing import Dict, Any
class PubMedArchiveService:
    def __init__(self, s3: S3Storage, db): ...
    def archive_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Compute hash → write raw object → upsert pubmed_archive → return {pmid,s3_uri,hash,skipped:bool}."""
```

### 4.3 Wire into existing sync flow (`services/services.py` or equivalent)

* After fetching each article: `archive_service.archive_article(article)` prior to embedding/indexing.
* Respect result `skipped=True` to avoid unnecessary downstream work.

---

## 5) HTTP + Jobs (reuse earlier HTTP plan)

### 5.1 API (FastAPI)

* `POST /v1/jobs` → enqueue `{tool, params, idempotency_key}` to SQS; write `jobs` row; return `job_id`.
* `GET /v1/jobs/{id}` → return `{state, progress, result_ref, error}`.
* `POST /v1/mcp/invoke` → for short tools only (rag.get/search, checkpoint ops).

### 5.2 Worker (`src/bio_mcp/main_worker.py`)

```python
# Pseudocode
while True:
  msg = sqs.receive()
  job = parse(msg)
  try:
    mark_running(job.id)
    result_ref = run_tool(job.tool, job.params, progress_cb)
    mark_succeeded(job.id, result_ref)
    sqs.delete(msg)
  except Retryable as e:
    update_progress(job.id, {"warning": str(e)})
    sqs.change_visibility(msg, backoff())
  except Exception as e:
    mark_failed(job.id, str(e))
    sqs.delete(msg)  # or let DLQ handle
```

* Concurrency: per-tool semaphores; global max from `BIO_MCP_MAX_CONCURRENCY`.

---

## 6) Terraform (shape only; fill variables)

* **S3 bucket** with versioning, SSE‑KMS, lifecycle (raw→Glacier after 60d).
* **SQS main + DLQ**; visibility timeout > max job time (e.g., 2 hours).
* **ECS TaskDefs**: `bio-mcp-api` (port 8080) and `bio-mcp-worker` (no ports).
* **ECS Services**: API behind ALB; Worker service (or EventBridge → RunTask for on‑demand).
* **IAM**: Task roles with `s3:PutObject/GetObject`, `sqs:ReceiveMessage/DeleteMessage`, `kms:Decrypt`.
* **EventBridge**: schedule incremental `pubmed.sync.incremental` into SQS.

---

## 7) Makefile Targets

```
run-http:     UVICORN_LIMIT=200 LOG_LEVEL=info python -m bio_mcp.main_http
run-worker:   python -m bio_mcp.main_worker
smoke-http:   curl -fsS localhost:8080/healthz && curl -fsS localhost:8080/readyz
invoke:       curl -s -X POST localhost:8080/v1/mcp/invoke -H 'content-type: application/json' -d '{"tool":"pubmed.search","params":{"q":"glioblastoma","limit":2}}' | jq .
```

---

## 8) Acceptance Criteria (Definition of Done)

* **S3 archive**: Running a sync produces `raw/*.json.zst` objects per PMID; re‑running with unchanged payloads results in `skipped=true` without new objects.
* **DB pointers**: `pubmed_archive` row exists for each archived PMID with `s3_uri` and `content_hash` matching the object.
* **Jobs**: `POST /v1/jobs` returns `job_id`; worker consumes from SQS, updates progress, and marks `succeeded` with `result_ref` pointing to manifest or summary.
* **Readiness**: `/readyz` returns 200 only when DB migrated and S3 bucket accessible (optional check) and Weaviate classes exist.
* **Back‑pressure**: Exceeding configured limits yields `429` with `Retry-After`.
* **Logging**: JSON logs include `trace_id`, `tool`, `pmid`, `s3_uri`, `latency_ms`.

---

## 9) Guardrails

* Bucket is **private**; SSE‑KMS enforced; deny unencrypted PUTs.
* No PII; abstracts are internal-use only; do not redistribute objects.
* Idempotency enforced with `UNIQUE (pmid)` in pointer table and optional history table for corrections/errata.
* Multipart uploads aborted on failure; retries use exponential backoff.

---

## 10) Test Plan (minimum)

* **Unit**: `object_key_for_pmid`, compression round‑trip, sha256 consistency.
* **Integration**: write→read with moto/minio; DB upsert idempotency; archive skip when payload unchanged.
* **Worker**: fake SQS message drives `pubmed.sync`; progress updates and success path; retry path for simulated 429.
* **E2E**: small list of PMIDs runs through API→SQS→worker → S3 + DB pointers; manifest written.

---

## 11) Rollout Steps

1. Land S3 storage client + archive service + DB migration.
2. Wire archive into existing PubMed sync; run locally with MinIO.
3. Add HTTP Jobs API + SQS worker; test locally with LocalStack or real SQS.
4. Terraform S3/SQS/ECS; deploy to staging; verify acceptance checks.
5. Enable EventBridge schedule for incremental syncs; monitor costs and queue depth.
