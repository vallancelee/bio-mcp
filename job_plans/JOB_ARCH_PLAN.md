# IMPLEMENTATION\_PLAN.md

This is a detailed, end‑to‑end plan for Claude to implement the HTTP service, S3 archive, and job/worker architecture for **bio‑mcp** in a single repo and image.

> See companion docs: **HTTP\_APPROACH.md**, **Implementation Manifest — PubMed S3 Archive & Jobs**, **Pipelines & Worker Code Skeletons**.

---

## 0) Assumptions & Ground Rules

* Repo package root: `src/bio_mcp/`.
* Python 3.12+, Poetry/pip ok. Containerized via Docker.
* Env var names follow `BIO_MCP_*` (see `.env.example`).
* Keep **stdio MCP** entrypoint intact; add **HTTP** transport alongside.
* Prefer **single image** with multiple entrypoints (API + Worker).
* Use Postgres, Weaviate, S3, SQS (and optional EventBridge) on AWS.

---

## 1) High‑Level Milestones (in order)

1. **HTTP skeleton**: FastAPI server, `/healthz`, `/readyz`, `/v1/mcp/invoke`, async‑safe adapter, error envelope.
2. **Readiness gates**: DB ping + migration check, Weaviate ping + schema check (cached).
3. **S3 archive**: client + service + DB tables; wire into PubMed flows.
4. **Jobs**: DB jobs table, `/v1/jobs` API, SQS queue, worker entrypoint, progress + idempotency.
5. **Back‑pressure**: per‑tool semaphores, 429 with `Retry‑After`, pool sizing.
6. **Observability**: JSON logs, request/trace IDs, basic metrics.
7. **Auth/secrets**: private by default; bearer/OIDC if public; secrets via AWS.
8. **Tests/CI**: unit, contract, integration (LocalStack/MinIO), smoke, load-lite.
9. **Terraform**: S3, SQS (+DLQ), ECS services, ALB, EventBridge schedule, IAM.
10. **Rollout**: staging → prod with alarms and dashboards.

---

## 2) Branching Plan & PR Checklist

* One feature branch per milestone: `feat/http-skeleton`, `feat/readyz`, `feat/s3-archive`, `feat/jobs`, `feat/backpressure`, `feat/observability`, `feat/auth`, `feat/infra`, `feat/tests-ci`.
* Each PR must include:

  * [ ] Code + unit/contract tests
  * [ ] Docs updated (this file or companion docs)
  * [ ] `make smoke-http` green
  * [ ] No secrets in code or logs

---

## 3) File/Module Work Items

### 3.1 HTTP Skeleton (P0)

**Add files**

```
src/bio_mcp/http/app.py
src/bio_mcp/http/adapters.py
src/bio_mcp/http/lifecycle.py
src/bio_mcp/http/registry.py
src/bio_mcp/main_http.py
```

**Key tasks**

* Build FastAPI app with routes:

  * `GET /healthz` → 200 when process is alive
  * `GET /readyz` → 200 when deps ready (stub initially)
  * `GET /v1/mcp/tools` → list tool names from registry
  * `POST /v1/mcp/invoke` → `{tool, params, idempotency_key?}` → `{ok,result,trace_id,tool}`
* Async‑safe adapter: detect coroutine vs sync; use `anyio.to_thread.run_sync` for sync functions.
* Error envelope: `{ok:false,error_code,message,trace_id,tool}`.
* Uvicorn runner in `main_http.py` with `limit_concurrency`, `log_level` from env.
* Docker: install `fastapi`, `uvicorn[standard]`, `anyio`, `httpx`; expose `8080`; `HEALTHCHECK /healthz`.

**Acceptance**

* `make run-http` starts server; `/healthz` and `/v1/mcp/tools` return 200.
* POST invoke to a simple tool returns 200 with `ok:true`.

---

### 3.2 Readiness Gates (P0)

**Enhance** `http/lifecycle.py`, `http/app.py`:

* DB ping using `BIO_MCP_DATABASE_URL` + `SELECT 1`.
* Alembic migration check: ensure version table at head.
* Weaviate readiness: GET `${BIO_MCP_WEAVIATE_URL}/v1/.well-known/ready`.
* Schema check: confirm required classes exist.
* Cache readiness status for 5s to avoid probe storms; return 503 if not ready.

**Acceptance**

* `/readyz` 503 when DB or Weaviate is down or migrations pending; 200 otherwise.

---

### 3.3 S3 Archive (P0→P1)

**Add** `clients/s3_storage.py`, `services/pubmed_archive_service.py` (see skeletons).

* Env: `BIO_MCP_ARCHIVE_BUCKET`, `BIO_MCP_ARCHIVE_PREFIX`, `BIO_MCP_ARCHIVE_COMPRESSION=zstd|gzip`.
* Write per‑PMID compressed JSON envelopes to S3 with sharded keys.
* Compute SHA‑256 over `payload` bytes; return `(s3_uri, hash)`.
* Upsert pointer into `pubmed_archive` table; optional `pubmed_archive_history`.

**DB migration** (Alembic):

```
CREATE TABLE IF NOT EXISTS pubmed_archive (
  pmid TEXT PRIMARY KEY,
  s3_uri TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL,
  api_etag TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS pubmed_archive_history (
  pmid TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  s3_uri TEXT NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (pmid, content_hash)
);
```

**Wire‑in**

* Call `PubMedArchiveService.archive_article()` in PubMed fetch path(s) before embedding/indexing.
* Ensure idempotency by checking matching `content_hash` results in `skipped` (no double work later).

**Acceptance**

* Running a small sync produces `s3://…/raw/*.json.(zst|gz)` + DB pointers.
* Re‑running with unchanged payloads produces `skipped=true` and no duplicate S3 objects/history rows.

---

### 3.4 Jobs API + Worker (P1)

**DB migration**

```
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

**API routes** in `http/app.py`:

* `POST /v1/jobs` → create row, compute `params_hash`, send SQS message `{job_id, tool, params}`; return `job_id`.
* `GET /v1/jobs/{id}` → `{state, progress, result_ref, error}`.
* Only short tools go through `/v1/mcp/invoke`; long tools use jobs.

**Worker** (see skeletons):

* Files: `pipelines/workers/sqs_worker.py`, `main_worker.py`.
* Env: `BIO_MCP_JOBS_QUEUE_URL`, `BIO_MCP_MAX_CONCURRENCY`, per‑tool limits.
* On message: mark running → run tool with progress callback → mark succeeded/failed → delete message (or DLQ policy).
* Implement `_tool_registry()` binding for `pubmed.sync` first.

**Acceptance**

* POST job returns an id immediately; worker consumes and updates DB state; GET job shows progress and final result.
* Duplicate `POST` with same `idempotency_key` returns same job id; no duplicated work.

---

### 3.5 Back‑pressure (P1)

* Add per‑tool semaphores (e.g., `rag.search=50`, `pubmed.sync=8`).
* Uvicorn `limit_concurrency` aligned with DB/Weaviate pool sizes.
* If limit reached, return **429** with `Retry‑After` header.

**Acceptance**

* Load test exceeding limits returns 429s; no cascade failures to DB/Weaviate.

---

### 3.6 Observability (P2)

* JSON logs for API and worker: `ts, level, service, trace_id, job_id, tool, pmid, s3_uri, status, latency_ms, attempt`.
* Generate `trace_id` per request; include in error envelope and logs.
* Basic metrics counters/histograms (CloudWatch EMF or Prometheus if available):

  * `requests_total{tool}`, `errors_total{tool}`, `latency_ms{tool}`
  * Worker `jobs_running`, `jobs_succeeded_total`, `jobs_failed_total`, `progress_pct`

**Acceptance**

* Logs parse as JSON; metrics visible locally/in staging.

---

### 3.7 Auth & Secrets (P2)

* Default private (VPC‑only). If public access:

  * Bearer/OIDC auth middleware for `/v1/*` routes.
  * Do not expose `/v1/mcp/tools` without auth.
* Terraform: inject secrets via AWS Secrets Manager/SSM; no plaintext in code.

**Acceptance**

* Unauthenticated requests rejected (public mode); secrets not printed or stored in logs.

---

## 4) Tests & CI

### 4.1 Unit

* `clients/s3_storage_test.py`: key sharding, compression roundtrip, sha256 stable.
* `services/pubmed_archive_service_test.py`: archive writes pointer rows; history optional.
* Adapter tests: error envelope, async vs sync function invocation.

### 4.2 Contract

* Golden I/O for tools via stdio and HTTP (`/v1/mcp/invoke`).
* Error codes map deterministically (e.g., Weaviate timeout → `WEAVIATE_TIMEOUT`).

### 4.3 Integration

* Compose or pytest services with LocalStack (S3/SQS), Postgres, Weaviate.
* Scenarios: single sync end‑to‑end (S3 + DB); re‑run idempotent; worker consumes SQS and completes job; simulate PubMed 429 and S3 failures.

### 4.4 Load/Smoke

* `make smoke-http` hits `/healthz`, `/readyz`, `/v1/mcp/tools`.
* Optional small load: ensure 429 on back‑pressure and healthy latencies under light load.

### 4.5 CI Pipeline

* Lint/typecheck (ruff, mypy) → unit+contract → integration (services) → image build → staging deploy (infra plan/apply).

---

## 5) Terraform / AWS Work

* **S3**: versioning, SSE‑KMS, lifecycle (raw→Glacier 60–90d), bucket policy deny unencrypted PUTs.
* **SQS**: main + DLQ; visibility timeout > max job duration; metrics/alarms on age and DLQ size.
* **ECS**: two task definitions (same image) → API (port 8080) + Worker (no ports). Services: API behind ALB; Worker autoscale on queue depth or use RunTask for rarely used jobs.
* **ALB**: target group health check `/healthz`; idle timeout ≥120s unless job API used exclusively.
* **EventBridge**: schedule incremental `pubmed.sync.incremental` → SQS or `RunTask`.
* **IAM**: task roles for S3, SQS, Secrets Manager/SSM, KMS decrypt; least privilege to bucket prefix.

**Acceptance**

* Staging deploy succeeds; `/readyz` green; job runs end‑to‑end; S3 objects appear; logs/metrics flow.

---

## 6) Monitoring & Alerts

* **API**: 5xx rate > threshold (5 min) → alert; `/readyz` failing consecutively → alert.
* **Worker/SQS**: `ApproximateAgeOfOldestMessage` > N minutes → alert; DLQ > 0 → alert.
* **Sync freshness**: no successful incremental sync in 24h for configured topics → warn.
* **S3**: 4xx/5xx PUT errors in logs → warn.

---

## 7) Rollout Plan

1. Land HTTP skeleton + readiness to main; deploy staging.
2. Add S3 archive + DB pointers; validate on staging with a tiny PMID set.
3. Add Jobs API + worker; run an incremental sync via SQS; verify progress and completion.
4. Enable per‑tool limits; run light load test; tune pools.
5. Wire logs/metrics/alarms; confirm dashboards.
6. Promote to prod with rolling deploy and health gates.

---

## 8) Developer Experience (Makefile)

```
run-http:     UVICORN_LIMIT=200 LOG_LEVEL=info python -m bio_mcp.main_http
run-worker:   python -m bio_mcp.main_worker
smoke-http:   curl -fsS localhost:8080/healthz && curl -fsS localhost:8080/readyz
invoke:       curl -s -X POST localhost:8080/v1/mcp/invoke -H 'content-type: application/json' -d '{"tool":"pubmed.search","params":{"q":"glioblastoma","limit":2}}' | jq .
```

---

## 9) Definition of Done (Global)

* `/healthz` and gated `/readyz` implemented; Docker/ECS health checks pass.
* S3 archive writes per‑PMID compressed JSON; DB pointers upserted; idempotent re‑runs.
* Jobs API returns job ids; worker consumes from SQS; progress visible; idempotent job submission.
* Back‑pressure enforced with 429; no dependency saturation under light load.
* JSON logs with `trace_id` in API + worker; basic metrics emitted; alerts configured.
* Terraform creates S3, SQS(+DLQ), ECS services, ALB, EventBridge, IAM; staging green.
* CI green (unit, contract, integration) and `make smoke-http` passes.

---

## 10) Nice‑to‑Haves (Post‑GA)

* Step Functions for multi‑step jobs (e.g., fetch → archive → embed → index → evaluate).
* SSE or WebSocket stream for job progress.
* Athena/Glue table over bronze Parquet view for analytics.
* OTEL traces across tool → service → client calls.
