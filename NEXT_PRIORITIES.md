Here’s a crisp, **prioritized implementation plan** to take the repo from “stdio MCP” to an **ops-ready HTTP service**, while keeping stdio support. Each task has concrete steps, code targets, and acceptance criteria.

# Goals

* Add an HTTP surface (`/healthz`, `/readyz`, `/v1/mcp/invoke`, jobs API) without rewriting business logic.
* Make long operations reliable (job model + idempotency).
* Add back-pressure, structured errors, and basic observability.
* Keep the current stdio MCP entrypoint for compatibility.

# Assumptions

* Repo root: `bio-mcp` with Python package `src/bio_mcp`.
* Env vars per README: `BIO_MCP_DATABASE_URL`, `BIO_MCP_WEAVIATE_URL`, `BIO_MCP_PUBMED_API_KEY`, `BIO_MCP_OPENAI_API_KEY`, `BIO_MCP_LOG_LEVEL`, `BIO_MCP_JSON_LOGS`.

---

## ✅ COMPLETED — Production HTTP Infrastructure (P0-P2)

### ✅ T0. HTTP skeleton (FastAPI + uvicorn) — COMPLETED

**Evidence**: Complete FastAPI implementation with all endpoints
- ✅ `src/bio_mcp/http/app.py` — Full FastAPI app with routes
- ✅ `src/bio_mcp/http/adapters.py` — Async-safe tool invocation
- ✅ `src/bio_mcp/http/lifecycle.py` — Startup/shutdown lifecycle
- ✅ `src/bio_mcp/http/registry.py` — Tool registry mapping
- ✅ `src/bio_mcp/main_http.py` — Uvicorn server entrypoint

**Working Endpoints**:
- ✅ `POST /v1/mcp/invoke` — Tool invocation with trace IDs
- ✅ `GET /v1/mcp/tools` — Tool listing  
- ✅ `GET /healthz` — Liveness check
- ✅ `GET /readyz` — Dependency readiness check

### ✅ T1. Async-safe invocation & error envelope — COMPLETED

**Evidence**: 159/160 HTTP tests passing with proper error handling
- ✅ Async/sync function detection and wrapping
- ✅ Standardized error envelopes with error codes
- ✅ Trace ID generation and propagation
- ✅ Structured error classification (WEAVIATE_TIMEOUT, etc.)

### ✅ T2. Readiness gates — COMPLETED

**Evidence**: Comprehensive health check system
- ✅ Database connectivity and migration checks
- ✅ Weaviate health and schema validation
- ✅ Cached readiness (5s) to prevent probe storms
- ✅ Proper 503/200 responses based on dependency status

### ✅ T3. Job API for long-running tools — COMPLETED

**Evidence**: Complete job system with database persistence
- ✅ Jobs table with proper schema and constraints
- ✅ `POST /v1/jobs`, `GET /v1/jobs/{id}` endpoints
- ✅ Background job worker with progress tracking
- ✅ Idempotency key support for safe retries
- ✅ Job state management (queued→running→succeeded/failed)

### ✅ T4. Back-pressure & per-tool concurrency — COMPLETED

**Evidence**: 11/11 concurrency tests passing
- ✅ Global and per-tool semaphore limits
- ✅ 429 responses with Retry-After headers
- ✅ Circuit breaker pattern for failure isolation
- ✅ Graceful degradation under load

### ✅ T5. Structured JSON logging & metrics — COMPLETED

**Evidence**: Complete observability module
- ✅ JSON log format with trace IDs and tool metadata
- ✅ Sensitive data redaction (API keys, passwords)
- ✅ Prometheus and CloudWatch EMF metric exporters
- ✅ Request counters, error rates, latency histograms

### ✅ T6. Back-pressure & concurrency control — COMPLETED

**Evidence**: Production-ready concurrency management
- ✅ Per-tool concurrency limits and timeouts
- ✅ Global rate limiting with queue depth monitoring
- ✅ Circuit breaker for failing services
- ✅ Comprehensive error handling and recovery

---

## 🚧 NEXT PRIORITIES — Domain Enhancement (P1)

With the complete HTTP infrastructure now in place, the next focus shifts to **domain-specific enhancements** for biomedical research capabilities.

### P1. Hybrid Search Enhancement (Phase 4B.1)

**Goal**: Upgrade existing RAG search with BM25+vector hybrid scoring and quality-aware reranking

**Files**: 
- `src/bio_mcp/mcp/rag_tools.py` (enhance existing)
- `src/bio_mcp/services/rag_service.py` (add hybrid scoring)
- `tests/integration/test_hybrid_search.py` (new)

**Implementation**:
```python
async def rag_search_tool(
    query: str,
    search_mode: str = "hybrid",     # "vector", "bm25", "hybrid"
    filters: dict = None,            # metadata filters  
    rerank_by_quality: bool = True,  # boost by quality scores
    top_k: int = 10
) -> HybridSearchResults
```

**Timeline**: 1-2 weeks  
**Acceptance**: Sub-200ms hybrid search outperforms pure vector search on biomedical queries

### P2. Incremental Sync System (Phase 4B.2)

**Goal**: EDAT watermark-based incremental sync with checkpoint persistence

**Files**:
- `src/bio_mcp/mcp/pubmed_tools.py` (add sync_delta)
- `src/bio_mcp/services/checkpoint_service.py` (new)
- Database migration for sync checkpoints

**Timeline**: 1-2 weeks  
**Acceptance**: Incremental sync processes only new documents since last checkpoint

---

## P3 — Developer experience & tests

### T7. Make targets + local parity

**Files**

* `Makefile`, `docker-compose.yml`, `Dockerfile`

**Steps**

* `make run-http`, `make smoke-http`, `make invoke`
* Docker `HEALTHCHECK` → `/healthz`
* Compose exposes `:8080` and depends on Postgres + Weaviate.

**Acceptance**

* One command brings up a full local stack and passes smoke tests.

---

### T8. Tests: contract, failure injection, idempotency

**Files**

* `tests/http/test_invoke.py`, `tests/http/test_jobs.py`, `tests/http/test_readyz.py`

**Cases**

* Golden I/O per tool over HTTP and stdio.
* PubMed 429 → retry/backoff path surfaces meaningful `error_code`.
* Weaviate 5xx → structured error; no crash.
* Idempotency: duplicate `POST /v1/jobs` returns same `job_id`.

**Acceptance**

* Tests pass locally and in CI.
* Regressions bubble clear error codes, not stack traces.

---

## Branching & PR checklist (for Claude)

* Create feature branches per task: `feat/http-skeleton`, `feat/job-api`, etc.
* Each PR must include:

  * Code + **unit tests** for changed area.
  * **Docs update**: `HTTP_APPROACH.md` or README snippets if behavior changed.
  * **Smoke script**/Make target adjusted.
* Run `make smoke-http` before marking ready for review.

---

## Rollout order (apply sequentially)

1. **T0–T2** (HTTP skeleton, errors, readiness)
2. **T3–T4** (jobs + back-pressure)
3. **T5–T6** (observability, auth/secrets)
4. **T7–T8** (DX & tests)

---

## Quick command snippets (for Claude to use in PRs)

```bash
# new files
git checkout -b feat/http-skeleton
touch src/bio_mcp/http/{__init__.py,app.py,adapters.py,lifecycle.py,registry.py} src/bio_mcp/main_http.py

# deps
pip install fastapi "uvicorn[standard]" anyio httpx

# run
make run-http
make smoke-http
```

---

