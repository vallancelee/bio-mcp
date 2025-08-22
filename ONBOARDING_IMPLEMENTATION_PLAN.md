# Onboarding Implementation Plan

## Executive Summary

This plan addresses gaps between the documented onboarding experience and actual implementation, focusing on getting developers productive within 30 minutes. The goal is to enable: setup → run → test → contribute workflow with minimal friction.

## Current State Analysis

### Issues Identified

1. **Port Conflicts**: Mixed use of ports between dev (docker-compose.yml) and test environments
2. **Missing Infrastructure**: No S3/object storage in local dev setup
3. **Command Misalignment**: ONBOARDING.md references non-existent Make targets
4. **No Quick Win**: No immediate success path after setup
5. **Worker Complexity**: Unclear how to run async job processing
6. **Database Migrations**: No easy commands for schema management

### Port Allocation Strategy

```
Development Ports (docker-compose.yml):
- PostgreSQL: 5432 (host) → 5432 (container)
- Weaviate: 8080 (host) → 8080 (container)
- MinIO S3: 9000 (host) → 9000 (container)
- MinIO Console: 9001 (host) → 9001 (container)
- HTTP API: 8000 (host application)
- Worker: (no port - internal)

Integration Test Ports (tests/integration/):
- PostgreSQL: (testcontainers - dynamic)
- Weaviate: 8090 (host) → 8080 (container)
- MinIO: (testcontainers - dynamic)
```

## Implementation Tasks

### Phase 1: Infrastructure Setup (Priority: HIGH)

#### 1.1 Docker Compose Improvements

**File**: `docker-compose.yml`

```yaml
# Add MinIO for S3-compatible storage
minio:
  image: minio/minio:latest
  container_name: bio-mcp-minio
  ports:
    - "9000:9000"
    - "9001:9001"
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin
  command: server /data --console-address ":9001"
  volumes:
    - minio_data:/data
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval: 30s
    timeout: 20s
    retries: 3

# Update Weaviate to use standard port for dev
weaviate:
  ports:
    - "8080:8080"  # Standard port for local dev
    - "50051:50051"  # gRPC port
```

**File**: `docker-compose.override.yml` (new)
```yaml
# Override file for local development customization
# Users can modify this without affecting the base configuration
version: '3.8'
services:
  weaviate:
    ports:
      - "${WEAVIATE_PORT:-8080}:8080"
```

#### 1.2 Environment Configuration

**File**: `.env.example` updates
```bash
# S3/Object Storage Configuration
BIO_MCP_S3_ENDPOINT="http://localhost:9000"
BIO_MCP_S3_ACCESS_KEY="minioadmin"
BIO_MCP_S3_SECRET_KEY="minioadmin"
BIO_MCP_S3_BUCKET="bio-mcp-data"
BIO_MCP_S3_REGION="us-east-1"

# Archive Configuration
BIO_MCP_ARCHIVE_BUCKET="bio-mcp-archive"
BIO_MCP_ARCHIVE_PREFIX="pubmed"
BIO_MCP_ARCHIVE_COMPRESSION="zstd"

# Job Queue Configuration (for worker)
BIO_MCP_JOBS_ENABLED="true"
BIO_MCP_JOBS_POLL_INTERVAL="5"
BIO_MCP_WORKER_CONCURRENCY="2"

# API Server Configuration
BIO_MCP_API_HOST="0.0.0.0"
BIO_MCP_API_PORT="8000"
```

### Phase 2: Makefile Enhancements (Priority: HIGH)

**File**: `Makefile` additions

```makefile
# ============================================================================
# ONBOARDING COMMANDS - Primary developer workflow
# ============================================================================

bootstrap: ## Complete first-time setup (aliased from dev-setup)
	@echo "$(BLUE)🚀 Setting up Bio-MCP development environment...$(NC)"
	@echo "$(YELLOW)1/5: Installing Python dependencies...$(NC)"
	@$(UV) sync --dev
	@echo "$(YELLOW)2/5: Setting up environment file...$(NC)"
	@test -f .env || cp .env.example .env
	@echo "$(YELLOW)3/5: Installing pre-commit hooks...$(NC)"
	@$(UV) run pre-commit install 2>/dev/null || true
	@echo "$(YELLOW)4/5: Creating local data directories...$(NC)"
	@mkdir -p data logs
	@echo "$(YELLOW)5/5: Validating setup...$(NC)"
	@$(UV) run python -c "import bio_mcp; print('✓ Bio-MCP package importable')"
	@echo "$(GREEN)✅ Bootstrap complete! Run 'make up' to start services$(NC)"

up: ## Start all development services (Docker)
	@echo "$(YELLOW)Starting development services...$(NC)"
	@docker-compose up -d postgres weaviate minio
	@echo "$(YELLOW)Waiting for services to be healthy...$(NC)"
	@sleep 5
	@$(MAKE) health-check
	@echo "$(GREEN)✅ Services ready!$(NC)"
	@echo "$(BLUE)PostgreSQL: localhost:5432$(NC)"
	@echo "$(BLUE)Weaviate: http://localhost:8080$(NC)"
	@echo "$(BLUE)MinIO S3: http://localhost:9000$(NC)"
	@echo "$(BLUE)MinIO Console: http://localhost:9001 (admin/minioadmin)$(NC)"

down: ## Stop all development services
	@echo "$(YELLOW)Stopping development services...$(NC)"
	@docker-compose down
	@echo "$(GREEN)✅ Services stopped$(NC)"

reset: down ## Reset everything (WARNING: destroys data)
	@echo "$(RED)⚠️  This will delete all local data! Press Ctrl+C to cancel...$(NC)"
	@sleep 3
	@docker-compose down -v
	@rm -rf data/* logs/*
	@echo "$(GREEN)✅ Reset complete$(NC)"

# ============================================================================
# DATABASE COMMANDS
# ============================================================================

migrate: ## Run database migrations
	@echo "$(YELLOW)Running database migrations...$(NC)"
	@$(UV) run alembic upgrade head
	@echo "$(GREEN)✅ Migrations applied$(NC)"

migrate-create: ## Create a new migration (usage: make migrate-create name="add_users_table")
	@test -n "$(name)" || (echo "$(RED)Error: name parameter required$(NC)" && exit 1)
	@echo "$(YELLOW)Creating migration: $(name)...$(NC)"
	@$(UV) run alembic revision --autogenerate -m "$(name)"
	@echo "$(GREEN)✅ Migration created$(NC)"

migrate-rollback: ## Rollback last migration
	@echo "$(YELLOW)Rolling back last migration...$(NC)"
	@$(UV) run alembic downgrade -1
	@echo "$(GREEN)✅ Rollback complete$(NC)"

db-reset: ## Reset database (drop and recreate)
	@echo "$(RED)⚠️  This will delete all database data! Press Ctrl+C to cancel...$(NC)"
	@sleep 3
	@docker-compose exec postgres psql -U biomcp -c "DROP DATABASE IF EXISTS biomcp;"
	@docker-compose exec postgres psql -U biomcp -c "CREATE DATABASE biomcp;"
	@$(MAKE) migrate
	@echo "$(GREEN)✅ Database reset complete$(NC)"

# ============================================================================
# APPLICATION COMMANDS
# ============================================================================

run-worker: ## Run the async job worker
	@echo "$(YELLOW)Starting job worker...$(NC)"
	@$(UV) run python -m bio_mcp.http.jobs.worker

run-all: ## Run HTTP server and worker (requires 2 terminals)
	@echo "$(BLUE)Starting all services...$(NC)"
	@echo "$(YELLOW)Open a new terminal and run: make run-worker$(NC)"
	@$(MAKE) run-http

quickstart: up migrate ## Quick setup and test (first-time users)
	@echo "$(BLUE)🎯 Running Bio-MCP Quickstart...$(NC)"
	@echo "$(YELLOW)Step 1: Starting HTTP server (background)...$(NC)"
	@$(UV) run python -m bio_mcp.main_http &
	@SERVER_PID=$$!
	@sleep 3
	@echo "$(YELLOW)Step 2: Testing health endpoints...$(NC)"
	@curl -s localhost:8000/healthz | grep -q "ok" && echo "$(GREEN)✓ Health check passed$(NC)" || echo "$(RED)✗ Health check failed$(NC)"
	@echo "$(YELLOW)Step 3: Listing available tools...$(NC)"
	@curl -s localhost:8000/v1/mcp/tools | jq -r '.tools[].name' | head -5
	@echo "$(YELLOW)Step 4: Testing a simple tool call...$(NC)"
	@curl -s -X POST localhost:8000/v1/mcp/invoke \
		-H 'Content-Type: application/json' \
		-d '{"tool":"ping","params":{"message":"Hello Bio-MCP!"}}' | jq .
	@kill $$SERVER_PID 2>/dev/null || true
	@echo "$(GREEN)🎉 Quickstart complete! Bio-MCP is working!$(NC)"
	@echo ""
	@echo "$(BLUE)Next steps:$(NC)"
	@echo "  1. Run the HTTP server: $(GREEN)make run-http$(NC)"
	@echo "  2. Run the worker: $(GREEN)make run-worker$(NC)"
	@echo "  3. Try the CLI: $(GREEN)uv run python clients/cli.py --help$(NC)"

health-check: ## Check if all services are healthy
	@echo "$(YELLOW)Checking service health...$(NC)"
	@docker-compose exec -T postgres pg_isready -U biomcp >/dev/null 2>&1 && echo "$(GREEN)✓ PostgreSQL$(NC)" || echo "$(RED)✗ PostgreSQL$(NC)"
	@curl -s http://localhost:8080/v1/.well-known/ready >/dev/null 2>&1 && echo "$(GREEN)✓ Weaviate$(NC)" || echo "$(RED)✗ Weaviate$(NC)"
	@curl -s http://localhost:9000/minio/health/live >/dev/null 2>&1 && echo "$(GREEN)✓ MinIO$(NC)" || echo "$(RED)✗ MinIO$(NC)"

logs: ## Tail logs from all services
	docker-compose logs -f

logs-api: ## Tail API server logs
	tail -f logs/bio-mcp-api.log

logs-worker: ## Tail worker logs
	tail -f logs/bio-mcp-worker.log

# ============================================================================
# TESTING COMMANDS
# ============================================================================

test-quick: ## Run quick unit tests only
	@echo "$(YELLOW)Running quick unit tests...$(NC)"
	@$(UV) run pytest tests/unit -v --tb=short
	@echo "$(GREEN)✅ Quick tests passed$(NC)"

test-tool: ## Test a specific tool (usage: make test-tool tool=rag.search)
	@test -n "$(tool)" || (echo "$(RED)Error: tool parameter required$(NC)" && exit 1)
	@echo "$(YELLOW)Testing tool: $(tool)...$(NC)"
	@$(UV) run python clients/cli.py $(tool) --help

# ============================================================================
# DEVELOPMENT WORKFLOW ALIASES
# ============================================================================

start: up migrate run-http ## Complete start (services + migrations + API)

stop: down ## Stop everything

restart: down up ## Restart all services

status: health-check ## Check system status

clean-all: clean reset ## Clean everything (code + data)
```

### Phase 3: Quick Start Scripts (Priority: HIGH)

#### 3.1 Bootstrap Script

**File**: `scripts/bootstrap.sh`
```bash
#!/bin/bash
set -e

echo "🚀 Bio-MCP Development Setup"
echo "============================"

# Check prerequisites
echo "Checking prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3.12+ required"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ Docker required"; exit 1; }
command -v uv >/dev/null 2>&1 || { echo "❌ UV required (pip install uv)"; exit 1; }

# Setup environment
echo "Setting up environment..."
cp -n .env.example .env 2>/dev/null || echo "✓ .env already exists"

# Install dependencies
echo "Installing dependencies..."
uv sync --dev

# Start services
echo "Starting Docker services..."
docker-compose up -d

# Wait for services
echo "Waiting for services to be ready..."
sleep 10

# Run migrations
echo "Running database migrations..."
uv run alembic upgrade head

# Create S3 buckets
echo "Setting up S3 buckets..."
docker-compose exec minio mc config host add local http://localhost:9000 minioadmin minioadmin
docker-compose exec minio mc mb local/bio-mcp-data --ignore-existing
docker-compose exec minio mc mb local/bio-mcp-archive --ignore-existing

echo "✅ Setup complete!"
echo ""
echo "Quick test: make quickstart"
echo "Start API: make run-http"
echo "Start worker: make run-worker"
```

#### 3.2 End-to-End Test Script

**File**: `scripts/e2e_test.py`
```python
#!/usr/bin/env python3
"""Quick end-to-end test to verify the system works."""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
from rich.console import Console

console = Console()

async def test_health():
    """Test health endpoints."""
    async with httpx.AsyncClient() as client:
        # Test healthz
        response = await client.get("http://localhost:8000/healthz")
        assert response.status_code == 200
        console.print("✅ Health check passed")
        
        # Test readyz
        response = await client.get("http://localhost:8000/readyz")
        assert response.status_code == 200
        console.print("✅ Readiness check passed")

async def test_list_tools():
    """List available MCP tools."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/v1/mcp/tools")
        assert response.status_code == 200
        tools = response.json()["tools"]
        console.print(f"✅ Found {len(tools)} tools")
        return tools

async def test_invoke_tool():
    """Test invoking a simple tool."""
    async with httpx.AsyncClient() as client:
        # Test ping tool
        response = await client.post(
            "http://localhost:8000/v1/mcp/invoke",
            json={"tool": "ping", "params": {"message": "test"}}
        )
        assert response.status_code == 200
        result = response.json()
        console.print(f"✅ Tool invocation successful: {result}")

async def test_job_creation():
    """Test creating an async job."""
    async with httpx.AsyncClient() as client:
        # Create a job
        response = await client.post(
            "http://localhost:8000/v1/jobs",
            json={
                "tool": "pubmed.sync",
                "params": {"query": "cancer", "max_results": 10}
            }
        )
        if response.status_code == 200:
            job = response.json()
            console.print(f"✅ Job created: {job['job_id']}")
            return job["job_id"]
        else:
            console.print("⚠️  Jobs API not available (worker not running?)")
            return None

async def main():
    """Run all tests."""
    console.print("[bold blue]Bio-MCP End-to-End Test[/bold blue]")
    console.print("=" * 40)
    
    try:
        await test_health()
        tools = await test_list_tools()
        await test_invoke_tool()
        job_id = await test_job_creation()
        
        console.print("\n[bold green]🎉 All tests passed![/bold green]")
        console.print("\nYour Bio-MCP installation is working correctly!")
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Test failed: {e}[/bold red]")
        console.print("\nTroubleshooting:")
        console.print("1. Ensure services are running: make up")
        console.print("2. Check logs: make logs")
        console.print("3. Verify API is running: make run-http")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
```

### Phase 4: Documentation Updates (Priority: MEDIUM)

#### 4.1 Updated ONBOARDING.md Structure

```markdown
# Quick Start (5 minutes)

## Prerequisites
- Python 3.12+
- Docker & Docker Compose
- UV package manager (`pip install uv`)

## Setup
```bash
# 1. Clone and enter directory
git clone <repo> && cd bio-mcp

# 2. One-command setup
make bootstrap

# 3. Start services
make up

# 4. Run quick test
make quickstart
```

## You're Done! 🎉

The system is now running. Try:
- View API docs: http://localhost:8000/docs
- List tools: `curl localhost:8000/v1/mcp/tools | jq`
- Test a tool: `uv run python clients/cli.py ping --message "hello"`

## Running the Full Stack

### Terminal 1: API Server
```bash
make run-http
```

### Terminal 2: Worker (for async jobs)
```bash
make run-worker
```

### Terminal 3: Your development
```bash
# Make changes and test
make test-quick
```
```

#### 4.2 Developer Workflow Documentation

**File**: `docs/DEVELOPER_WORKFLOW.md`
```markdown
# Developer Workflow

## Daily Development

### Starting your day
```bash
# Get latest code
git pull

# Start services
make up

# Run migrations
make migrate

# Start development
make run-http  # Terminal 1
make run-worker  # Terminal 2 (if needed)
```

### Making changes
1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes
3. Test: `make test-quick`
4. Lint: `make lint`
5. Full test: `make test-all`

### Before committing
```bash
make pre-commit  # Runs format, lint, type-check, test
```

## Common Tasks

### Adding a new MCP tool
1. Define schema in `src/bio_mcp/tool_definitions.py`
2. Implement in `src/bio_mcp/mcp/<domain>_tools.py`
3. Register in `src/bio_mcp/http/registry.py`
4. Test: `make test-tool tool=<your.tool>`

### Database changes
```bash
# After modifying models
make migrate-create name="describe_your_change"

# Review generated migration
# Apply it
make migrate
```

### Debugging
```bash
# View logs
make logs          # All services
make logs-api      # API server only
make logs-worker   # Worker only

# Check service health
make health-check

# Reset if needed
make reset  # WARNING: Deletes all data
```
```

### Phase 5: CI/CD Integration (Priority: LOW)

#### 5.1 GitHub Actions Workflow

**File**: `.github/workflows/onboarding-test.yml`
```yaml
name: Test Onboarding Experience

on:
  pull_request:
    paths:
      - 'ONBOARDING.md'
      - 'Makefile'
      - 'docker-compose.yml'
      - 'scripts/bootstrap.sh'

jobs:
  test-onboarding:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install UV
        run: pip install uv
      
      - name: Test bootstrap
        run: make bootstrap
      
      - name: Test services
        run: |
          make up
          sleep 10
          make health-check
      
      - name: Test quickstart
        run: make quickstart
      
      - name: Cleanup
        run: make down
```

## Success Metrics

### Target Onboarding Times
- **5 minutes**: Services running, basic test passing
- **15 minutes**: First tool invocation working
- **30 minutes**: Understanding codebase, ready to contribute
- **1 hour**: First meaningful code change

### Key Performance Indicators
1. Time to first successful tool call: < 10 minutes
2. Number of manual steps required: < 5
3. Documentation clarity score: > 90%
4. Error recovery paths documented: 100%

## Implementation Schedule

### Week 1: Foundation
- [ ] Update Makefile with new targets
- [ ] Add MinIO to docker-compose.yml
- [ ] Create bootstrap script
- [ ] Update .env.example

### Week 2: Developer Experience
- [ ] Create quickstart command
- [ ] Add e2e test script
- [ ] Update ONBOARDING.md
- [ ] Create developer workflow docs

### Week 3: Polish
- [ ] Add CI tests for onboarding
- [ ] Create troubleshooting guide
- [ ] Add progress indicators to scripts
- [ ] Video walkthrough (optional)

## Testing the Onboarding

### Test Scenarios
1. **Fresh developer**: No prior knowledge, follows ONBOARDING.md
2. **Experienced developer**: Familiar with similar projects
3. **Windows developer**: Using WSL2
4. **Mac developer**: Using Docker Desktop
5. **Linux developer**: Native Docker

### Validation Checklist
- [ ] All commands in ONBOARDING.md work
- [ ] No undefined environment variables
- [ ] All ports are accessible
- [ ] Error messages are helpful
- [ ] Recovery paths are clear

## Rollback Plan

If issues arise:
1. Keep old commands as aliases
2. Document both paths temporarily
3. Gradual migration over 2 weeks
4. Monitor developer feedback

## Conclusion

This implementation plan will transform the onboarding experience from a complex, error-prone process to a smooth, confidence-building introduction to the Bio-MCP project. The focus on quick wins and progressive disclosure ensures developers feel productive immediately while gradually learning the full system.