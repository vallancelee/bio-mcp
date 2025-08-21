# HTTP\_APPROACH.md

A pragmatic plan to expose the bio‑mcp server over HTTP while preserving stdio MCP for compatibility. Optimized for cloud ops (health checks, autoscaling, observability) with a thin adapter that maps existing tool functions to HTTP endpoints.

---

## 1) Objectives

* **Ops‑friendly**: native HTTP surface with `/healthz` and `/readyz`, ALB/NLB health checks, and autoscaling.
* **Non‑intrusive**: reuse existing MCP tool implementations; no rewrite of business logic.
* **Safe at scale**: concurrency caps, back‑pressure, job pattern for long‑running tasks, structured errors.
* **Dual transport**: keep stdio entrypoint for MCP‑native clients while adding HTTP for cloud.

---

## 2) Architecture (delta from today)

```
[Clients (agents, workers)]
          │
          ▼
   HTTP Adapter (FastAPI)
    • /v1/mcp/invoke
    • /v1/mcp/tools
    • /v1/jobs, /v1/jobs/{id}
    • /healthz, /readyz
          │
          ▼
   Tool Registry  ─────────► Services ─────────► Clients (DB, Weaviate, PubMed, LLM)
          ▲                                 (pooled connections)
          │
   stdio MCP main.py (unchanged for local / MCP‑native)
```

### Key modules to add

* `bio_mcp/http/app.py`: FastAPI app, routes, health/readiness, wiring.
* `bio_mcp/http/adapters.py`: tool registry → HTTP endpoints.
* `bio_mcp/http/lifecycle.py`: startup/shutdown hooks, dependency pings.
* `bio_mcp/main_http.py`: uvicorn entrypoint.

---

## 3) API surface (v1)

### 3.1 Invoke a tool

`POST /v1/mcp/invoke`

```json
{
  "tool": "pubmed.search",
  "params": { "q": "glioblastoma", "limit": 3 },
  "idempotency_key": "<optional-guid>"
}
```

**Response**

```json
{ "ok": true, "tool": "pubmed.search", "result": { /* tool-specific */ }, "trace_id": "..." }
```

### 3.2 List tools

`GET /v1/mcp/tools` → `["pubmed.search", "pubmed.get", ...]`

### 3.3 Jobs (for long‑running operations)

* `POST /v1/jobs` with `{ "tool": "pubmed.sync", "params": {...}, "idempotency_key": "..." }`
* `GET /v1/jobs/{id}` → `{ "state": "queued|running|succeeded|failed", "result": {...}, "error": {...} }`
* Optional `GET /v1/jobs/stream/{id}` (SSE) for progress.

### 3.4 Health

* `GET /healthz` → liveness (process up).
* `GET /readyz` → readiness (DB ping, Weaviate ping, schema/migrations check).

> **Versioning**: Prefix routes with `/v1/`. Bump on breaking changes.

---

## 4) Adapter design (async‑safe)

* Detect coroutine vs sync functions; wrap sync calls with `anyio.to_thread.run_sync`.
* Per‑tool Pydantic models for **inputs/outputs**; OpenAPI auto‑docs.
* Standard error envelope:

```json
{
  "ok": false,
  "error_code": "WEAVIATE_TIMEOUT",
  "message": "...",
  "trace_id": "...",
  "tool": "pubmed.sync"
}
```

---

## 5) Concurrency & back‑pressure

* **Global limit**: uvicorn `limit_concurrency=200` (tune per CPU/RAM).
* **Per‑tool caps** (semaphores): e.g., `rag.search` 50, `pubmed.sync` 8.
* **DB pool**: set max pool size and overflow; match to concurrency.
* On overload: return **429** with `Retry‑After`.

---

## 6) Long‑running jobs

* Avoid LB timeouts by moving `pubmed.sync`/bulk ingest into the **job API**.
* Persist **job rows** (id, tool, params hash, idempotency\_key, state, progress, result\_ref, timestamps).
* Workers: in‑process task queue (background tasks) or a tiny side worker container; store progress checkpoints.
* **Idempotency**: dedupe by `idempotency_key` + tool + params hash.

---

## 7) Health & readiness

* `/livez`: always 200 when process is alive.
* `/healthz`: simple OK—used by container healthcheck.
* `/readyz`: returns 200 only when:

  1. DB reachable **and** required tables exist (migrations applied),
  2. Weaviate reachable **and** required classes exist.
* Cache readiness results for \~5s to reduce probe amplification.

---

## 8) Observability

* **Structured JSON logs** with fields: `ts, level, trace_id, tool, route, status, latency_ms, tenant_id`.
* **Tracing** (optional initially): OTEL spans around tool invocations and dependency calls.
* **Metrics**: per‑tool `requests_total`, `latency_ms` histogram, `errors_total`, `inflight`, `429_total`.

---

## 9) Security

* Default private (VPC‑only). If public:

  * Bearer tokens or OIDC; per‑tenant **rate limiting** & quotas.
  * Do **not** expose `/v1/mcp/tools` without auth.
* Secrets via AWS Secrets Manager/SSM; never log secret values.

---

## 10) Deployment (ECS Fargate + ALB)

* Container listens on `:8080`; add Docker `HEALTHCHECK` hitting `/healthz`.
* ALB target group health check path `/healthz`; idle timeout ≥ 120s unless all long ops use jobs.
* ECS service **deregistration delay** ≥ app shutdown grace (30–60s).
* Autoscaling on CPU/RAM + `5xx` alarms.

**Terraform excerpts**

* Task definition: container port 8080, awslogs, healthCheck `curl http://localhost:8080/healthz`.
* Target group: HTTP:8080, health check `/healthz`.
* Listener rule: route `/`, `/v1/*`, `/healthz`, `/readyz` to TG.

---

## 11) Testing strategy

* **Contract tests**: golden inputs/outputs per tool over HTTP and stdio.
* **Load tests**: realistic RPS, verify back‑pressure and latency SLOs.
* **Failure injection**: DB/Weaviate timeouts, PubMed rate limits, verify retries & error envelopes.
* **Migration test**: start with empty DB; run `alembic upgrade` (pre‑deploy job or on startup gate) and assert `/readyz` gates until done.

---

## 12) Migration & rollout plan

1. Land HTTP code paths behind feature flags; keep stdio intact.
2. Local `docker‑compose` parity; add `make run-http`, `make smoke-http`.
3. Deploy to staging ECS; verify health, readiness, and job API.
4. Backfill dashboards (logs, metrics); set alarms.
5. Gradual traffic ramp; keep stdio path for MCP clients indefinitely.

---

## 13) Known risks & mitigations

* **Protocol mismatch**: HTTP wrapper is not MCP session; keep stdio entrypoint.
* **Long requests**: move to job API; set ALB idle timeout appropriately.
* **Blocking code**: wrap sync I/O via `anyio.to_thread.run_sync` or make tools async.
* **Readiness flapping**: cache checks; verify schema/migrations, not just pings.
* **Overload**: per‑tool semaphores + 429; size DB/Weaviate pools conservatively.

---

## 14) Minimal stubs (illustrative)

**Adapter invocation boundary**

```python
import inspect, anyio

async def invoke(fn, params):
    if inspect.iscoroutinefunction(fn):
        return await fn(params)
    return await anyio.to_thread.run_sync(fn, params)
```

**Error envelope helper**

```python
def err(code, msg, trace_id, tool):
    return {"ok": False, "error_code": code, "message": msg, "trace_id": trace_id, "tool": tool}
```

**Health wiring sketch**

```python
@app.get("/readyz")
async def readyz():
    ok = await db_ready() and await weaviate_ready() and await schema_ready()
    return ({"ok": True}, 200) if ok else ({"ok": False}, 503)
```

---

## 15) Makefile targets

```
run-http:
	UVICORN_LIMIT=200 LOG_LEVEL=info python -m bio_mcp.main_http

smoke-http:
	curl -fsS localhost:8080/healthz && curl -fsS localhost:8080/readyz

invoke:
	curl -s -X POST localhost:8080/v1/mcp/invoke \
	  -H 'content-type: application/json' \
	  -d '{"tool":"pubmed.search","params":{"q":"glioblastoma","limit":3}}' | jq .
```

---

## 16) Acceptance checklist

* [ ] `/healthz` returns 200; Docker/ECS healthchecks pass.
* [ ] `/readyz` gates until DB + Weaviate + schema ready.
* [ ] All tools callable via `/v1/mcp/invoke`; parity with stdio behavior.
* [ ] Back‑pressure returns 429 with `Retry‑After`.
* [ ] Job API completes `pubmed.sync` end‑to‑end with idempotency.
* [ ] Structured logs + basic latency/error metrics emitted.
* [ ] Terraform deployed behind ALB with sane timeouts.
* [ ] Documentation (this file) linked from README.
