# ONBOARDING.md

Welcome! This guide gets you productive on **bio-mcp** in a couple of hours. It covers environment setup, running the stack locally, smoke tests, a repo tour, and common workflows.

> **TL;DR - Get productive in 5 minutes:**
>
> * `make bootstrap && make up`
> * `make quickstart` (tests everything works)
> * `make run-http` in one terminal, `make run-worker` in another
> * `uv run python clients/cli.py ping --message "hello"`

---

## 1) Prerequisites

* **Python**: 3.12+
* **Docker** & **Docker Compose**
* **Make** (GNU make)
* **Git**
* (Optional) **Poetry** if you prefer it locally

If you’re on macOS:

```bash
brew install python@3.12 make
# Docker Desktop from https://www.docker.com/
```

---

## 2) First-time setup

1. **Clone**

```bash
git clone <your-org>/bio-mcp.git
cd bio-mcp
```

2. **Environment**

```bash
cp .env.example .env
# Edit as needed. Values in .env are safe defaults for local dev.
```

3. **Install tools & hooks**

```bash
make bootstrap
```

This sets up Python deps, pre-commit hooks (ruff/black/mypy), and local tooling.

---

## 3) Start local dependencies

We run Postgres, Weaviate, and S3-compatible storage via Docker.

```bash
make up    # docker compose up -d
```

This brings up:

* **PostgreSQL** (db) on port 5433
* **Weaviate** (vector DB) on port 8080 with text modules enabled  
* **MinIO** S3-compatible storage on ports 9000 (API) and 9001 (Console)

> To view logs: `docker compose logs -f weaviate postgres minio`

---

## 4) Run the application (API + Worker)

Open two terminals.

**Terminal A — API (HTTP server)**

```bash
make run-http
```

* Serves on `http://localhost:8000`
* Health: `/healthz`, `/readyz`

**Terminal B — Worker (SQS/job consumer)**

```bash
make run-worker
```

* Long-running jobs (e.g., `pubmed.sync`) are processed here when enqueued.

> If you don’t need jobs yet, you can skip the worker.

---

## 5) Smoke tests

Verify the stack is healthy:

```bash
make quickstart
```

This command:
* Starts all services
* Runs database migrations
* Tests the HTTP API endpoints
* Shows available MCP tools
* Confirms everything is working

List MCP tools (via CLI client):

```bash
uv run python clients/cli.py list-tools
```

Test a tool (recommended first test):

```bash
uv run python clients/cli.py ping --message "hello world"
```

Search PubMed:

```bash
uv run python clients/cli.py rag.search --query "glioblastoma" --top-k 3
```

Test async job processing:

```bash
uv run python clients/cli.py pubmed.sync --query "cancer" --max-results 10
```

This will sync PubMed results to your local database and vector store.

---

## 6) Repo tour

```
src/bio_mcp/
  http/           # FastAPI app, routes, health/readiness, adapters
  mcp/            # MCP tools exposed by the service
  clients/        # DB, Weaviate, S3/MinIO, PubMed, etc.
  services/       # Orchestration: archive, normalize, chunk, embed, index
  pipelines/      # Jobs, workers (SQS), sync/ingest loops
  models/         # Document, Chunk, typed schemas
migrations/       # Alembic migrations for Postgres
tests/            # unit, contract, integration (LocalStack/MinIO)
infra/terraform/  # ECS, S3, SQS, EventBridge, IAM, ALB
```

**Primary flows**

* **Ingest (PubMed):** `clients.pubmed_*` → `clients.s3_storage` (archive) → `services.normalize_pubmed` → `models.Document` → `services.chunking` → `services.embed_index` → Weaviate
* **Query:** `rag.search` tool (or HTTP endpoint) → Weaviate hybrid/vector search → results (chunks)
* **Jobs:** HTTP `POST /v1/jobs` → SQS → worker consumes → updates `jobs` table

---

## 7) Common developer tasks

### Run tests

```bash
make test       # all tests
make test-unit  # unit only
make test-int   # integration (brings up services)
```

### Lint & type check

```bash
make lint
make typecheck
```

### DB migrations

```bash
make migrate     # apply migrations
make makemigration name="add_documents_table"  # create new migration
```

### Reset local state (dangerous)

```bash
make down        # stop services
make clean       # remove volumes (db/index/buckets) if defined
make up          # start fresh
```

---

## 8) Feature development workflow

1. **Create a branch**: `git checkout -b feat/<short-desc>`
2. **Write code + tests** in `src/` and `tests/`
3. **Run locally**: `make up`, `make run-http`, `make run-worker`
4. **Smoke test**: `make smoke-http`
5. **Open PR** with:

   * Tests green (CI runs unit/contract/integration)
   * Updated docs if interface changed
   * No secrets in code/logs

**PR checklist**

* Logging is **structured JSON**; includes `trace_id`/`job_id` where relevant
* Idempotency respected (S3/DB pointers, jobs)
* Back-pressure and pagination considered
* `/readyz` remains accurate

---

## 9) Configuration reference (local)

Key `.env` entries (local defaults should work):

```
BIO_MCP_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/postgres
BIO_MCP_WEAVIATE_URL=http://localhost:8080
BIO_MCP_S3_ENDPOINT=http://localhost:9000
BIO_MCP_S3_ACCESS_KEY=minioadmin
BIO_MCP_S3_SECRET_KEY=minioadmin
BIO_MCP_ARCHIVE_BUCKET=bio-mcp-archive
BIO_MCP_ARCHIVE_PREFIX=pubmed
BIO_MCP_LOG_LEVEL=INFO
BIO_MCP_API_PORT=8000
```

> MinIO credentials are pre-configured in `.env.example`. Access the MinIO console at http://localhost:9001 with minioadmin/minioadmin to view stored data.

---

## 10) Troubleshooting

* **/readyz is 503**: Run `make health-check` to verify all services. Try `make down && make up` to restart.
* **CLI tools not working**: Ensure services are running with `make up` and try `make quickstart`.
* **Port conflicts**: If ports 5433, 8000, 8080, 9000, 9001 are in use, stop conflicting services or modify docker-compose.yml ports.
* **Vector search returns empty**: Run a sync first: `uv run python clients/cli.py pubmed.sync --query "test" --max-results 5`
* **MinIO errors**: Check MinIO is running with `make health-check`. Access console at http://localhost:9001.
* **Rate limits from PubMed**: Add your API key to `.env`: `BIO_MCP_PUBMED_API_KEY=your_key_here`
