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

## P0 — Must land first

### T0. Create HTTP skeleton (FastAPI + uvicorn)

**Files**

* `src/bio_mcp/http/app.py`
* `src/bio_mcp/http/adapters.py`
* `src/bio_mcp/http/lifecycle.py`
* `src/bio_mcp/http/registry.py`
* `src/bio_mcp/main_http.py`

**Steps**

1. Implement `registry.build_registry()` mapping tool names → callables:

   * `pubmed.search|get|sync|sync_incremental`
   * `rag.search|get`
   * `corpus.checkpoint.create|list|get|delete`
2. Adapter endpoint:

   * `POST /v1/mcp/invoke {tool, params, idempotency_key?}` → `{ok,result,trace_id,tool}`
   * `GET /v1/mcp/tools` → list
3. Health endpoints:

   * `/healthz` (liveness)
   * `/readyz` (DB ping + Weaviate ping + schema/migrations check stub)
4. `main_http.py` runs uvicorn on `0.0.0.0:8080` with sensible `limit_concurrency`.

**Acceptance**

* `make run-http` starts server.
* `curl :8080/healthz` → 200; `curl :8080/v1/mcp/tools` lists tools.
* Invoking a fast tool (e.g., `rag.get` with dummy id) round-trips.

---

### T1. Async-safe invocation & error envelope

**Files**

* `adapters.py` (update)
* `http/app.py` (add error helpers)

**Steps**

1. Detect `async` vs sync tool functions; wrap sync with `anyio.to_thread.run_sync`.
2. Return standardized errors:

   ```json
   {"ok": false, "error_code": "WEAVIATE_TIMEOUT", "message": "...", "trace_id": "...", "tool": "rag.search"}
   ```
3. Generate a `trace_id` per request (UUID4) and include in logs + responses.

**Acceptance**

* A forced error (e.g., invalid params) returns the envelope with `ok:false`.
* Logs contain `trace_id`, `tool`, `latency_ms`.

---

### T2. Readiness that gates on real dependencies

**Files**

* `lifecycle.py`, `app.py`
* Optionally `clients/` ping helpers

**Steps**

1. DB check: connect using `BIO_MCP_DATABASE_URL`; run `SELECT 1`.
2. Weaviate check: GET `${BIO_MCP_WEAVIATE_URL}/v1/.well-known/ready`.
3. Schema/migration check:

   * Confirm Alembic head applied (inspect alembic version table).
   * Confirm required Weaviate classes exist.
4. Cache readiness for \~5s to avoid probe storms.

**Acceptance**

* With DB/Weaviate down, `/readyz` returns **503**.
* After dependencies up + migrated, `/readyz` returns **200**.

---

## P1 — Reliability under load

### T3. Job API for long-running tools (e.g., `pubmed.sync`)

**Files**

* `http/app.py` (routes: `POST /v1/jobs`, `GET /v1/jobs/{id}`)
* `services/` (job runner/background task)
* DB migration for job table

**Steps**

1. Add table:

   ```
   jobs(id uuid pk, tool text, params_hash text, idempotency_key text null,
        state text check in ('queued','running','succeeded','failed'),
        progress jsonb, result_ref text, error text, created_at, updated_at)
   unique (tool, params_hash, coalesce(idempotency_key,''))
   ```
2. `POST /v1/jobs` enqueues; returns `job_id`.
3. Background runner executes tool with periodic `progress` updates.
4. Store result (or ref) and final state; retries safe via idempotency key.

**Acceptance**

* Kicking off `pubmed.sync` returns a job id quickly.
* Polling job shows state transitions; final result stored.
* Re-posting same request with same idempotency key **does not** duplicate work.

---

### T4. Back-pressure & per-tool concurrency

**Files**

* `app.py` (dependency-injected semaphores)
* Config (env) for limits: `BIO_MCP_MAX_CONCURRENCY`, per-tool overrides

**Steps**

1. Global concurrency cap (uvicorn) + per-tool semaphores:

   * `rag.search`: e.g., 50
   * `pubmed.sync`: e.g., 8
2. If semaphore exhausted → return **429** with `Retry-After`.

**Acceptance**

* Synthetic load that exceeds limits yields 429, not 5xx or timeouts.
* DB/Weaviate pools are not saturated (monitor connections).

---

## P2 — Ops hardening

### T5. Structured JSON logging & basic metrics

**Files**

* Logging config (JSON)
* Optional: Prometheus/CloudWatch EMF emitter

**Steps**

1. Emit JSON logs with fields:

   * `ts, level, trace_id, tool, route, status, latency_ms, tenant_id?`
2. Add counters/histograms:

   * `requests_total{tool}`, `errors_total{tool}`, `latency_ms{tool}`, `inflight{tool}`.

**Acceptance**

* Logs are machine-parseable.
* Metrics visible locally (or exported).

---

### T6. Auth posture & secrets hygiene

**Files**

* `app.py` (auth middleware)
* Terraform task definition (secrets)
* README updates

**Steps**

1. Default VPC-only; if public, require bearer tokens or OIDC on `/v1/*`.
2. Don’t expose `/v1/mcp/tools` without auth in public mode.
3. Pull secrets from AWS Secrets Manager/SSM in task definition (no plaintext env in TF).

**Acceptance**

* Requests without auth (public mode) are rejected with 401/403.
* Secrets never appear in logs/env dumps.

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

