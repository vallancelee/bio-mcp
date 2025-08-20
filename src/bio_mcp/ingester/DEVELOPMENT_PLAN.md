Here’s a drop-in **`DEVELOPMENT_PLAN.md`** you can add at the repo root.

# Development Plan — PubMed Retriever MCP (Catalog + Delta Sync + Backfill)

> Objective: reliably ingest *relevant* PubMed abstracts into persistent stores (Postgres catalog + vector store), on a schedule with checkpoints, with cheap/resumable backfill. Separate client can validate via MCP tools or a REST façade.

---

## ✅ Phase 0 — Repo hygiene & env

* [ ] Create sub-folders:

  ```
  tools/           # seeders, backfills, one-off scripts
  clients/         # separate test clients (CLI / REST façade)
  lib/             # fetch, normalize, persist, scoring, chunking
  ```
* [ ] `.env` add (dev defaults):

  ```
  DB_URL=sqlite:///./bio_mcp.db          # dev, Postgres in prod
  PERSIST_MODE=sql                       # flip to sql+s3 later
  AWS_S3_BUCKET=                          # set when enabling S3
  NCBI_API_KEY=                           # polite E-utilities
  OVERLAP_DAYS=5
  ```
* [ ] Makefile shims:

  ```makefile
  up:        docker compose -f deploy/docker-compose.dev.yml up -d
  seed:      python tools/seed_minicorpus.py
  test:      pytest -q
  sync-demo: python clients/cli.py pubmed.sync_delta --query-key demo --term "$$TERM" --overlap-days 5
  ```

**Acceptance criteria**

* `make up` boots local Weaviate (if you’re indexing now).
* `make seed` populates a tiny corpus (no network).

---

## ✅ Phase 1 — Query Management (compiler + registry) (0.5 day)

* [ ] `config/queries.yaml`

  ```yaml
  - query_key: glp1_obesity_v1
    mode: combined            # clinical + basic
    target: GLP-1 receptor
    drug_synonyms: [semaglutide, tirzepatide]
    indication: Obesity
    notes: "GLP-1 agonists for obesity"
  - query_key: kras_nsclc_v1
    mode: combined
    target: KRAS G12C
    drug_synonyms: [sotorasib, adagrasib]
    indication: non-small cell lung cancer
  ```
* [ ] `lib/query_compiler.py` → builds PubMed `term` per record (clinical+basic).
* [ ] CLI: `tools/print_term.py --query-key glp1_obesity_v1`.

**Acceptance criteria**

* `python tools/print_term.py --query-key glp1_obesity_v1` prints a valid PubMed query string.

---

## ✅ Phase 2 — Fetch & Normalize (esearch/efetch XML→JSON) (1 day)

* [ ] `lib/entrez_client.py`

  * `esearch_delta(term, mindate, maxdate, datetype="edat") -> [pmid]`
  * `efetch_xml(pmids: list[str]) -> xml_str`

* [ ] `lib/normalize_pubmed.py`

  * `xml_to_docs(xml_str) -> List[Doc]  # {pmid,title,abstract,journal,pub_types,mesh,pdat,edat,lr,pmcid,authors}`

* [ ] Respect politeness:

  * ≤ \~3 rps with API key, exponential backoff on 429/5xx.
  * Batch `efetch` in 200–500 PMIDs.

**Acceptance criteria**

* Script: `tools/fetch_once.py --query-key glp1_obesity_v1 --since 2025-01-01` prints N normalized docs to stdout.

---

## ✅ Phase 3 — Persistence (SQL catalog + optional S3 bodies) (1 day)

* [ ] SQL tables (Alembic migration):

  * `pubmed_docs(pmid PK, title, journal, pub_types[], mesh[], pdat, edat, lr, pmcid, evidence_type, quality_json, quality_total, content_hash, version, s3_uri, last_seen_at)`
  * `doc_provenance(pmid, query_key, first_seen_at, PRIMARY KEY (pmid,query_key))`
  * `checkpoints(query_key PK, last_edat, last_scan_at)`

* [ ] Repos:

  * `PostgresOnlyRepo` (today): stores `abstract` in SQL (optional column).
  * `SqlPlusS3Repo` (target): `put_body()` to S3 (`s3://…/pubmed/silver/pmid=<id>/v=<n>/body.json.gz`), then `upsert_meta()` with `s3_uri`.
  * Feature flag: `PERSIST_MODE=sql|sql+s3` (reads are backward-compatible).

* [ ] Deterministic fields:

  * `content_hash = sha256(title|abstract|journal|pub_types|pdat|pmcid)`
  * `version++` on hash or `lr` change.

**Acceptance criteria**

* `tools/persist_smoketest.py` upserts 10 docs; querying SQL shows versions, `s3_uri` when enabled.

---

## ✅ Phase 4 — Tagging & Scoring (0.5 day)

* [ ] `lib/tagging.py` → `classify_evidence(doc) -> clinical|preclinical|basic|other`
* [ ] `lib/scoring.py` → `score_pubmed(doc) -> {design,recency,journal,human,total}`
* [ ] Store `evidence_type`, `quality_total` in SQL and echo into chunk metadata later.

**Acceptance criteria**

* Unit tests cover representative docs (clinical RCT, in-vitro mouse, mechanism).

---

## ✅ Phase 5 — Async Delta Sync (single runner, checkpointed) (1 day)

* [ ] `apps/mcp-server/tools/pubmed.sync_delta` (or REST `/admin/sync`)

  1. Load `query_key` → `last_edat`
  2. Compute window: `[last_edat - overlap_days, now]`
  3. `esearch_delta` → PMIDs
  4. `efetch` + normalize
  5. Tag + score
  6. Persist (S3 + SQL)
  7. (Optional now) chunk + embed + index
  8. Advance checkpoint to `max_edat_seen` iff all succeeded
  9. Return job report

* [ ] **Single runner**: make sync invoked by **one** scheduled job (ECS Scheduled Task / K8s CronJob). MCP replicas do **not** auto-sync.

**Acceptance criteria**

* `clients/cli.py pubmed.sync_delta --query-key glp1_obesity_v1 --term "<compiled term>" --overlap-days 5` returns a report with inserted/updated/skipped and `max_edat_seen`.
* `clients/cli.py corpus.checkpoint.get --query-key glp1_obesity_v1` shows watermark advanced.

---

## ✅ Phase 6 — Backfill (partitioned, resumable, cheap) (1 day)

* [ ] `tools/backfill.py`

  * Args: `--query-key`, `--year-start 2020`, `--year-end 2025`, `--journals "NEJM,Lancet,JAMA"` (optional)
  * Strategy: loop over `year` (or `edat` month) partitions; write partial checkpoints per partition.
  * Use **EPOST** for large PMID sets; batch `efetch` 500; gzip outputs; cache by `content_hash`.
  * Optional: **defer embeddings**; only chunk & index top journals / recent years first.

**Acceptance criteria**

* Can interrupt and resume a backfill run with no duplicates and preserved work.

---

## ✅ Phase 7 — Separate Client & Tests (0.5–1 day)

* [ ] `clients/cli.py` (already drafted): methods for `sync`, `rag.get`/`get`, `ckpt.get/set`, optional `search`.
* [ ] **Contract tests** (`tests/test_contracts.py`):

  * Validate responses against JSON Schemas (from `contracts.md`).
* [ ] **Fixtures** (`tools/fixtures/seed_pubmed.jsonl`):

  * 10–50 mixed records for offline seeding: `make seed`.

**Acceptance criteria**

* `pytest` passes.
* `clients/cli.py` can fetch one abstract and list a page.

---

## (Optional) Phase 8 — Chunk & Index for future search (0.5–1 day)

* [ ] `lib/chunking.py` (section-aware, numeric guard; 250–350 token target)
* [ ] `lib/embeddings` (provider switch: OpenAI or HF local)
* [ ] `lib/weav_store.py` (ensure schema, upsert, hybrid search)
* [ ] `apps/mcp-server/tools/search` (or `rag.search`): oversample K, rerank by quality + section/tier boosts.

**Acceptance criteria**

* `clients/cli.py rag.search --query "weight loss vs placebo"` returns plausible hits.

---

## Ops, Cost & Safety Nets

### Cost controls

* Prefer **ECS Fargate** for MCP (tiny task) over EKS (no \$74 control plane).
* **Avoid NAT** in dev: run public task w/ strict SG to save \~\$32/mo.
* S3 for blobs; keep RDS small: only catalog fields.
* If embedding: start with **OpenAI text-embedding-3-small** or **HF MiniLM**; cache by `content_hash`.

### Reliability

* **Idempotency**: replay-safe at every step (stable UUIDs, upsert rules).
* **Run report** logging:

  ```json
  { "query_key":"glp1_obesity_v1",
    "inserted":37,"updated":12,"skipped":441,"pmids":490,
    "durations_ms":{"fetch":18000,"normalize":2200,"persist":3100},
    "max_edat_seen":"2025-08-17T15:59:02Z","warnings":[] }
  ```
* **Alerts** (later): watermark not advancing N days; consistent 429s; zero docs for a topic.

### Security

* Secrets in **AWS Secrets Manager**; IAM least privilege for S3 + RDS.
* Add `tool` + `email` params on all E-utilities calls (NCBI etiquette).
* No PHI; abstracts are public.

---

## Quick Commands Cheat-Sheet

```bash
# 0) Local services
make up

# 1) Print compiled PubMed term for a query_key
python tools/print_term.py --query-key glp1_obesity_v1

# 2) One-off fetch & normalize (no DB writes)
python tools/fetch_once.py --query-key glp1_obesity_v1 --since 2025-01-01 > /tmp/docs.json

# 3) Seed offline fixtures (no network)
make seed

# 4) Delta sync (advances checkpoint on success)
python clients/cli.py pubmed.sync_delta \
  --query-key glp1_obesity_v1 \
  --term "$(python tools/print_term.py --query-key glp1_obesity_v1)" \
  --overlap-days 5

# 5) Inspect watermark
python clients/cli.py corpus.checkpoint.get --query-key glp1_obesity_v1

# 6) Fetch abstract by PMID
python clients/cli.py rag.get --doc-id pmid:12345678

# 7) Backfill last 5 years (partitioned)
python tools/backfill.py --query-key glp1_obesity_v1 --year-start 2021 --year-end 2025
```

---

## Milestones & Exit Criteria

* **M1 (Day 1):** Seeded corpus; CLI can `get` by PMID; schemas & tests green.
* **M2 (Day 2):** Delta sync from PubMed advances checkpoint; docs persist to SQL (and S3 if enabled).
* **M3 (Day 3–4):** Backfill runs resumably by year; provenance recorded; costs bounded.
* **M4 (Optional):** Chunk/index + search endpoint returns quality-weighted results.

---

## Nice-to-have (later)

* **REST façade** (FastAPI) implementing the OpenAPI you drafted for CI & dashboards.
* **Snowflake external table** on `s3://…/pubmed/bronze` for analytics.
* **Embedding A/B**: `EMBEDDINGS_PROVIDER=openai|hf` + golden queries.
* **Reindex job**: rebuild vectors when embedding model/version changes.

---

**Done.** This plan gets relevant abstracts into durable stores first (your core goal), then adds sync reliability and cheap backfill—while keeping the path open for search and analytics when you’re ready.
