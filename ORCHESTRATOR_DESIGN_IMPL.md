# DESIGN & IMPLEMENTATION PLAN — Bio-MCP Orchestrator (“Biotech Analyst”)

This is a copy-ready plan for Claude to implement the orchestrator that plans and executes MCP tool calls (PubMed + ClinicalTrials.gov today; extensible to company.\* later). It emphasizes determinism, auditability, and fast “cache-then-network” answers.

---

## 1) Objectives & Success Criteria

**Objectives**

* Interpret user questions → plan minimal tool calls → answer with citations and a `checkpoint_id`.
* Support **lazy load**: fetch live from PubMed/CT.gov on cache misses, persist to S3/PG (and later vectors).
* Return useful partial results under a strict latency budget.

**Success Criteria**

* P50 end-to-end latency ≤ **2.5s**; P95 ≤ **5s** on common queries.
* Answers include **tables/summaries + PMIDs/NCTs** and a `checkpoint_id`.
* Deterministic outputs given same inputs + corpus snapshot; no broken tool contracts.
* Telemetry: one trace per question; spans per tool call with `cache_hit`, `rows`, `latency_ms`.

**Non-Goals (this phase)**

* No multi-agent choreography inside MCP.
* No paid data vendors.
* No embeddings on the hot path (enqueue write-behind if needed).

---

## 2) Architecture (Components & Flow)

```
User Query
   │
   ▼
[Frame Parser]  → intent, entities, filters, fetch_policy
   │
   ▼
[Planner] → tiny DAG (steps, dependencies, budgets)
   │
   ▼
[Async Executor]
   ├─ Token-bucket rate limiter per source
   ├─ Cache-then-network tool clients (PG/S3 first; live fetch on miss)
   ├─ Persist results (S3 raw, PG normalized; enqueue embeddings if needed)
   └─ Collect span metrics, errors, partials
   │
   ▼
[Synthesizer]
   ├─ Tables/summaries + citations
   └─ checkpoint_id (tool versions + inputs + source watermarks + blob URIs)
```

**Core modules**

* `orchestrator/frame.py` — parse query → `Frame`
* `orchestrator/plan.py` — rule-based plan builder → `Plan`
* `orchestrator/exec.py` — async DAG executor + rate limits + budgets
* `orchestrator/synth.py` — render answer & citations
* `orchestrator/registry.py` — tool registry (p95, rate caps, versions)
* `orchestrator/checkpoints.py` — deterministic `checkpoint_id`
* `clients/pubmed_client.py`, `clients/ctgov_client.py` — cache-then-network adapters

---

## 3) Data Contracts (Claude must keep these stable)

### 3.1 Frame (input to planner)

```json
{
  "intent": "one_of: [recent_pubs_by_topic, indication_phase_trials, trials_with_pubs]",
  "entities": { "company": null, "ticker": null, "indication": "Alzheimer Disease", "trial_nct": null, "topic": "GLP-1" },
  "filters": { "phase": ["3"], "status": ["Recruiting","Active, not recruiting"], "published_within_days": 180 },
  "fetch_policy": "cache_then_network",
  "time_budget_ms": 5000
}
```

### 3.2 Plan (tiny DAG)

```yaml
version: 1
budget_ms: 5000
steps:
  - id: find_trials
    tool: ctgov.search
    args: { condition: "Alzheimer Disease", phase: ["3"], status: ["Recruiting","Active, not recruiting"] }
    out: { ncts: "$.results[*].nct_id" }

  - id: pubs_by_nct
    needs: [find_trials]
    parallel_map_over: "$.find_trials.ncts"
    tool: pubmed.search
    args: { query_template: "NCT{nct}[SI] AND (\"{TODAY-180}\"[EDAT]:\"{TODAY}\"[EDAT])", top_k: 10 }
    out: { pmids: "$.results[*].pmid" }

  - id: hydrate
    needs: [pubs_by_nct]
    tool: pubmed.get
    args: { pmids: "$.pubs_by_nct[*].pmids" }
```

### 3.3 Tool registry (used by planner/executor)

```json
{
  "pubmed.search": { "version": "v1", "p95_ms": 300, "rps_cap": 2 },
  "pubmed.get":    { "version": "v1", "p95_ms": 150, "rps_cap": 3 },
  "ctgov.search":  { "version": "v1", "p95_ms": 400, "rps_cap": 2 }
}
```

### 3.4 Fetch policy enum

`"cache_only" | "cache_then_network" | "network_only"` (default: `cache_then_network`)

---

## 4) Execution Semantics

* **Concurrency**: parallelize independent steps; `parallel_map_over` lists (e.g., multiple NCTs).
* **Rate limiting**: token bucket per source (`pubmed`, `ctgov`). Conservative defaults: 2 RPS each; exponential backoff on 429/5xx.
* **Budgets**: wave-by-wave execution within `budget_ms`; drop remaining steps when budget exhausted and synthesize partials.
* **Cache-then-network**: query PG/S3 first; on miss, live fetch → S3 raw (`/raw/{source}/...`), PG upserts; read-back to continue plan.
* **Idempotency**: S3 keys include `content_sha256`; PG uses `ON CONFLICT` upserts; stable Weaviate IDs (if used) via UUIDv5.
* **Errors**: annotate step result with `error_code/message`; continue other branches; surface partials with a short “data still loading” note.

---

## 5) Implementation Plan (Milestones)

### M0 — Scaffolding (½ day)

* Files/folders per module above.
* Unit test harness; basic logger + OTel setup; config via `pydantic-settings`.

### M1 — Frame Parser (1–2 days)

* Heuristics (regex + keyword maps) for:

  * indications (MeSH synonyms map you already use),
  * phases (`phase 2/3`, `Phase III`),
  * companies/tickers (for now, treat as free text; CT.gov sponsor used directly),
  * time windows (`last N days`, `past 6 months`).
* Output `Frame` with defaults: `fetch_policy="cache_then_network"`, `time_budget_ms=5000`.

### M2 — Rule-based Planner (1–2 days)

* Map `intent` → plan templates:

  * `indication_phase_trials` → `ctgov.search` only.
  * `recent_pubs_by_topic` → `pubmed.search` → `pubmed.get`.
  * `trials_with_pubs` → `ctgov.search` → map NCTs → `pubmed.search(NCT[SI])` → `pubmed.get`.
* Fill args from `Frame`; enforce per-tool p95-aware order and budgets.

### M3 — Async Executor + Rate Limits (2 days)

* Topological execution by waves; `asyncio.gather` per wave.
* Token bucket per source; exponential backoff (jitter).
* Step result projection via JSONPath-like mini-selector in `out`.
* Global timer enforcing `budget_ms`.

### M4 — Cache-then-Network Tool Clients (2–3 days)

* Wrap existing `pubmed.*` / `ctgov.*`:

  * **Read path**: PG/S3 check → (maybe) live API → persist (S3 raw, PG normalized) → return.
  * Return structured payloads the orchestrator expects (`results[*].pmid`, etc.).
* Add config flags: `persist`, `embed_on_write` (default false).

### M5 — Synthesizer (1–2 days)

* Table builders for trials and publications.
* Inline citations (PMID/NCT).
* Clean partials (“—” for missing cells).
* Copy-ready markdown output.

### M6 — Checkpoints & Telemetry (1 day)

* `checkpoint_id = hash(tool_versions, registry_version, normalized_inputs, source_watermarks, blob_uris)`
* OTel spans:

  * attrs: `tool`, `args_hash`, `cache_hit`, `rows`, `latency_ms`, `error_code`
* Metrics counters/histograms per tool and overall.

### M7 — Tests & Fixtures (2 days)

* **Unit**: frame parsing, plan building, token bucket, projection.
* **Integration**: fake adapters (golden JSON), PG upserts, S3 writes (localstack or temp dir).
* **End-to-end**: three demo queries; assert shape, citations, and `checkpoint_id`.

### M8 — Perf polish (1 day)

* Concurrency tuning; JSON streaming parsers for PubMed; ensure P95 under budgets.

---

## 6) Code Skeletons (Claude can start from here)

### 6.1 Types

```python
# orchestrator/types.py
from typing import Any, Literal, Dict, List, Optional, TypedDict

FetchPolicy = Literal["cache_only","cache_then_network","network_only"]

class Frame(TypedDict, total=False):
    intent: str
    entities: Dict[str, Any]
    filters: Dict[str, Any]
    fetch_policy: FetchPolicy
    time_budget_ms: int

class PlanStep(TypedDict, total=False):
    id: str
    tool: str
    needs: List[str]
    args: Dict[str, Any]
    parallel_map_over: Optional[str]
    out: Dict[str, str]

class Plan(TypedDict):
    version: int
    budget_ms: int
    steps: List[PlanStep]
```

### 6.2 Orchestrate

```python
# orchestrator/orchestrate.py
import asyncio, time
from .frame import parse_frame
from .plan import plan_from_frame
from .exec import execute_plan
from .synth import synthesize
from .checkpoints import build_checkpoint

async def orchestrate(query: str, registry: dict, now=None) -> dict:
    frame = parse_frame(query)
    plan  = plan_from_frame(frame, registry)
    ctx   = await execute_plan(plan, frame, registry)
    answer = synthesize(query, ctx)
    ckpt   = build_checkpoint(plan, frame, ctx)
    return {"answer": answer, "checkpoint_id": ckpt, "trace": ctx.get("_trace", {})}
```

### 6.3 Executor (wave runner)

```python
# orchestrator/exec.py
import asyncio, time
from .rate import TokenBucket
from .clients import get_client_for_tool
from .jsonproj import project

async def execute_plan(plan, frame, registry):
    start = time.perf_counter()
    ctx = {"_trace": {"steps": []}}
    waves = topo_sort(plan["steps"])
    buckets = {"pubmed": TokenBucket(rps=2), "ctgov": TokenBucket(rps=2)}

    for wave in waves:
        if ms_left(plan, start) <= 0: break
        tasks = [run_step(s, ctx, frame, registry, buckets, start, plan["budget_ms"]) for s in wave]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for s, r in zip(wave, results):
            ctx[s["id"]] = r if not isinstance(r, Exception) else {"error": str(r)}
    return ctx

async def run_step(step, ctx, frame, registry, buckets, start, budget_ms):
    args = render_args(step["args"], ctx, frame)
    client = get_client_for_tool(step["tool"], registry, buckets)
    res = await client.call(args, fetch_policy=frame.get("fetch_policy","cache_then_network"), time_left_ms=time_left(start,budget_ms))
    # persist side effects handled inside client (S3/PG upserts)
    return project(step.get("out",{}), res)
```

---

## 7) Config & Ops

* **Config** via `settings.yml` or env:

  * `time_budget_ms`, per-source `rps_cap`, backoff, fetch policy defaults.
* **Feature flags**:

  * `ORCH_ENABLE_LAZY_LOAD=true`
  * `ORCH_EMBED_ON_WRITE=false`
* **Logging**: structured (tool, args\_hash, cache\_hit, rows, ms, error\_code, checkpoint\_id).

---

## 8) Testing Strategy

* **Fixtures**:

  * Minimal CT.gov JSON (NCT+phase/status/sponsor).
  * Minimal PubMed JSON/XML with `[SI]` linking to that NCT; 2–3 PMIDs.
* **Unit**:

  * Parser: “Phase 3 Alzheimer’s last year” → correct `Frame`.
  * Planner: `Frame` → expected `Plan` steps.
  * Token bucket: respects rps.
  * Projection: JSON projection correctness.
* **Integration**:

  * Fake adapters return canned JSON; ensure S3/PG upserts idempotent.
* **E2E**:

  * The three demo queries produce expected tables + citations + a non-empty `checkpoint_id`.

---

## 9) Risks & Mitigations

* **Source throttling (429)** → token buckets + exponential backoff + circuit breaker to `cache_only`.
* **Affiliation/company noise** → (defer; not in this phase).
* **Cold start latency** → two-phase answering (partial tables first), sane top\_k caps, parallel map with limits.
* **Nondeterminism** → freeze `registry.json` per release; record source watermarks in checkpoint.

---

## 10) Rollout & Acceptance

**Ready to ship when:**

* E2E demo queries run cold → persist → warm runs are fast (<1s).
* Spans show cache hits vs live fetches; DLQs empty (if any).
* `checkpoint_id` resolves to blob URIs + tool versions.

**Post-ship**

* Add `company.*` tools into planner templates.
* Turn on background embedding queue for newly ingested PubMed docs.

---

## 11) Work Breakdown (tickets Claude can pick up)

1. `orch-001` Frame parser with tests.
2. `orch-002` Planner templates for 3 intents + tests.
3. `orch-003` Token bucket & executor wave runner.
4. `orch-004` PubMed client (cache-then-network) + tests.
5. `orch-005` CT.gov client (cache-then-network) + tests.
6. `orch-006` Synthesizer (tables, citations).
7. `orch-007` Checkpoint builder + OTel spans.
8. `orch-008` E2E demo flows + fixtures.
9. `orch-009` Perf tuning & configization.
