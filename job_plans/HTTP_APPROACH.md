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

### Repo‑specific wiring

From the repo’s README, preferred **env var names** and **tool surface** are:

* **Env vars** (use these exact keys):

  * `BIO_MCP_DATABASE_URL` – Postgres
  * `BIO_MCP_WEAVIATE_URL` – Weaviate HTTP endpoint
  * `BIO_MCP_PUBMED_API_KEY` – NCBI key
  * `BIO_MCP_OPENAI_API_KEY` – OpenAI key (if used for embeddings)
  * `BIO_MCP_LOG_LEVEL` (e.g., INFO)
  * `BIO_MCP_JSON_LOGS` (true/false)
  * Optional: `BIO_MCP_CORPUS_FOCUS`, `BIO_MCP_COMPANY_TRACKING`, `BIO_MCP_MARKET_FOCUS`

* **Tools exposed** (per README):

  * `pubmed.search`, `pubmed.get`, `pubmed.sync`, `pubmed.sync.incremental`
  * `corpus.checkpoint.create`, `.get`, `.list`, `.delete`
  * `rag.search`, `rag.get`

> Source: repo README, sections *Available Tools* and *Configuration*. (Adjust only if the code diverges.)

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

`GET /v1/mcp/tools` → `["pubmed.search", "pubmed.get", "pubmed.sync", "rag.search", "corpus.checkpoint.list"]`

### 3.3 Jobs (for long‑running operations)

* `POST /v1/jobs` with `{ "tool": "pubmed.sync", "params": {...}, "idempotency_key": "..." }`
* `GET /v1/jobs/{id}` → `{ "state": "queued|running|succeeded|failed", "result": {...}, "error": {...} }`

### 3.4 Health

* `GET /healthz` → liveness (process up).
* `GET /readyz` → readiness (database ping, weaviate ping, schema/migrations check).

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

### Concrete registry for this repo

Create a central registry function that maps the **tool names above** to **actual code callables**. If function names differ, update the dotted paths in one place.

```python
# src/bio_mcp/http/registry.py
from typing import Dict, Callable, Any
import importlib

# Map tool name -> dotted path to callable
_TOOL_MAP = {
    # PubMed
    "pubmed.search": "bio_mcp.mcp.pubmed_tools.search",
    "pubmed.get": "bio_mcp.mcp.pubmed_tools.get",
    "pubmed.sync": "bio_mcp.mcp.pubmed_tools.sync",
    "pubmed.sync.incremental": "bio_mcp.mcp.pubmed_tools.sync_incremental",
    # RAG
    "rag.search": "bio_mcp.mcp.rag_tools.search",
    "rag.get": "bio_mcp.mcp.rag_tools.get",
    # Corpus checkpoints
    "corpus.checkpoint.create": "bio_mcp.mcp.corpus_tools.create_checkpoint",
    "corpus.checkpoint.list": "bio_mcp.mcp.corpus_tools.list_checkpoints",
    "corpus.checkpoint.get": "bio_mcp.mcp.corpus_tools.get_checkpoint",
    "corpus.checkpoint.delete": "bio_mcp.mcp.corpus_tools.delete_checkpoint",
}

def build_registry() -> Dict[str, Callable[[dict], Any]]:
    reg: Dict[str, Callable[[dict], Any]] = {}
    for tool, path in _TOOL_MAP.items():
        module_name, func_name = path.rsplit(".", 1)
        mod = importlib.import_module(module_name)
        fn = getattr(mod, func_name)
        reg[tool] = fn
    return reg
```

> **Note:** If any function names differ (e.g., `sync_full` vs `sync`), adjust `_TOOL_MAP` only—no other code changes required.

---

## 5) Concurrency & back‑pressure

* **Global limit**: uvicorn `limit_concurrency=200` (tune per CPU/RAM).
* **Per‑tool caps**: e.g., `pubmed.sync` 5, `rag.search` 50.
* **Database pool**: max connections \~20; match to concurrency.
* On overload: return **429** with `Retry‑After`.

---

## 6) Long‑running jobs

* Avoid LB timeouts by moving `pubmed.sync`/bulk ingest into the **job API**.
* Persist **job rows** (id, tool, params hash, idempotency\_key, state, progress, result\_ref, timestamps).
* Workers: in‑process task queue (background tasks) or a tiny side worker container; store progress checkpoints.
* **Idempotency**: dedupe by `idempotency_key` + tool + params hash.

### Job schema (SQL sketch)

```sql
CREATE TABLE jobs (
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
CREATE UNIQUE INDEX IF NOT EXISTS jobs_idem ON jobs (tool, params_hash, COALESCE(idempotency_key, ''));
```

---

## 7) Health & readiness

* `/livez`: always 200 when process is alive.
* `/healthz`: simple OK—used by container healthcheck.
* `/readyz`: returns 200 only when:

  1. DB reachable **and** required tables exist (migrations applied),
  2. Weaviate reachable **and** required classes exist.
* Cache readiness results for \~5s to reduce probe amplification.

### Repo‑specific readiness

Use repo env names and dependency URLs:

* Read DB URL from `BIO_MCP_DATABASE_URL`
* Read vector store URL from `BIO_MCP_WEAVIATE_URL`

Example wiring snippet:

```python
import os
DB_URL = os.getenv("BIO_MCP_DATABASE_URL", "")
WEAVIATE_URL = os.getenv("BIO_MCP_WEAVIATE_URL", "")
```

---

## 8) Observability

* **Logs**: structured JSON (`ts, level, trace_id, tool, route, status, latency_ms`).
* **Metrics**: per‑tool request count, error rate, latency histogram.
* **Tracing**: OTEL spans around tool invocation and downstream calls.

---

## 9) Security

* Default VPC‑only.
* For public: bearer tokens / OIDC; per‑tenant rate limits.
* Secrets: AWS Secrets Manager; redact from logs.

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

### Secret/env mapping for this repo

Use **these exact env names** in task definition:

```hcl
environment = [
  { name = "BIO_MCP_DATABASE_URL", value = var.database_url },
  { name = "BIO_MCP_WEAVIATE_URL", value = var.weaviate_url },
  { name = "BIO_MCP_PUBMED_API_KEY", value = data.aws_secretsmanager_secret_version.pubmed_api_key.secret_string },
  { name = "BIO_MCP_OPENAI_API_KEY", value = data.aws_secretsmanager_secret_version.openai_api_key.secret_string },
  { name = "BIO_MCP_LOG_LEVEL", value = "INFO" },
  { name = "BIO_MCP_JSON_LOGS", value = "true" }
]
```

---

## 11) Testing strategy

* Contract tests: each tool via stdio and HTTP.
* Load tests: RPS against `/v1/mcp/invoke`.
* Chaos: DB/Weaviate down; assert errors and retries.
* Migration test: empty DB → run `alembic upgrade`; `/readyz` gates until complete.

---

## 12) Migration & rollout plan

1. Add HTTP alongside stdio; feature flag.
2. Local docker‑compose parity; new Make targets (`run-http`, `smoke-http`).
3. Staging ECS deploy; verify health, job API.
4. Add dashboards; set alarms.
5. Gradual traffic ramp; keep stdio forever for MCP clients.

---

## 13) Known risks & mitigations

* **Protocol mismatch**: HTTP wrapper is not MCP session; keep stdio entrypoint.
* **Long ops**: use job API.
* **Blocking code**: wrap sync in `to_thread`.
* **Readiness**: check schema/migrations, not just ping.
* **Overload**: semaphores + 429.

---

## 14) Example stubs

**Async‑safe invocation**

```python
import inspect, anyio

async def invoke(fn, params):
    if inspect.iscoroutinefunction(fn):
        return await fn(params)
    return await anyio.to_thread.run_sync(fn, params)
```

**Error envelope**

```python
def error(code, msg, trace_id, tool):
    return {"ok": False, "error_code": code, "message": msg, "trace_id": trace_id, "tool": tool}
```

**Health readiness**

```python
@app.get("/readyz")
async def readyz():
    ok = await db_ready() and await weaviate_ready() and await schema_ready()
    return {"ok": ok}
```

---

## 15) Makefile targets

```
run-http:
	python -m bio_mcp.main_http

smoke-http:
	curl -fsS localhost:8080/healthz && curl -fsS localhost:8080/readyz

invoke:
	curl -s -X POST localhost:8080/v1/mcp/invoke \
	  -H 'content-type: application/json' \
	  -d '{"tool":"pubmed.search","params":{"q":"glioblastoma","limit":3}}' | jq .
```

---

## 16) Acceptance checklist

* [ ] `/healthz` returns 200.
* [ ] `/readyz` waits for DB + Weaviate + migrations.
* [ ] Tools callable via `/v1/mcp/invoke` with parity.
* [ ] Back‑pressure returns 429.
* [ ] Job API completes `pubmed.sync`.
* [ ] Structured logs + metrics emitted.
* [ ] Terraform deployed behind ALB.
* [ ] Doc linked from README.
