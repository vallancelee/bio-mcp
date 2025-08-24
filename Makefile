# Bio-MCP Development Makefile
# Provides easy commands for development, testing, and deployment

.PHONY: help install dev test test-unit test-integration test-docker test-coverage test-watch test-ci
.PHONY: lint format type-check security-scan clean build run docker-build docker-run docker-up docker-down
.PHONY: deps-update version bump-patch bump-minor bump-major
.PHONY: manual-test test-health test-server test-logs test-signals test-docker-health test-all-manual
.PHONY: bootstrap up down reset migrate migrate-create migrate-rollback db-reset run-worker quickstart health-check
.PHONY: weaviate-create-v2 weaviate-info weaviate-info-v2 weaviate-recreate-v2 test-weaviate-v2

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m # No Color

# Project variables
PROJECT_NAME := bio-mcp
PYTHON_VERSION := 3.12
UV := uv

help: ## Show this help message
	@echo "$(BLUE)Bio-MCP Development Commands$(NC)"
	@echo "=================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# Installation and Setup
install: ## Install production dependencies
	@echo "$(YELLOW)Installing production dependencies...$(NC)"
	$(UV) sync

dev: install ## Install development dependencies  
	@echo "$(YELLOW)Installing development dependencies...$(NC)"
	$(UV) sync --dev
	@echo "$(GREEN)✓ Development environment ready$(NC)"

bootstrap: ## Complete first-time setup (with services)
	@echo "$(BLUE)🚀 Setting up Bio-MCP development environment...$(NC)"
	@echo "$(YELLOW)1/5: Installing Python dependencies...$(NC)"
	@$(UV) sync --dev
	@echo "$(YELLOW)2/5: Setting up environment file...$(NC)"
	@test -f .env || cp .env.example .env
	@echo "$(YELLOW)3/5: Installing pre-commit hooks...$(NC)"
	@$(UV) run pre-commit install 2>/dev/null || echo "$(YELLOW)Pre-commit hooks not available$(NC)"
	@echo "$(YELLOW)4/5: Creating local data directories...$(NC)"
	@mkdir -p data logs
	@echo "$(YELLOW)5/5: Validating setup...$(NC)"
	@$(UV) run python -c "import bio_mcp; print('✓ Bio-MCP package importable')" 2>/dev/null || echo "$(YELLOW)Package check skipped$(NC)"
	@echo "$(GREEN)✅ Bootstrap complete! Run 'make up' to start services$(NC)"

# Testing Commands
test: ## Run all unit tests (fast)
	@echo "$(YELLOW)Running unit tests...$(NC)"
	$(UV) run --with pytest-asyncio pytest tests/unit -v
	@echo "$(GREEN)✓ Unit tests completed$(NC)"

test-unit: test ## Alias for unit tests

test-integration: ## Run integration tests (requires Docker)
	@echo "$(YELLOW)Running integration tests...$(NC)"
	@command -v docker >/dev/null 2>&1 || (echo "$(RED)Docker required for integration tests$(NC)" && exit 1)
	$(UV) run --with pytest-asyncio pytest tests/integration -v -m "not docker"
	@echo "$(GREEN)✓ Integration tests completed$(NC)"

test-docker: ## Run Docker-specific tests
	@echo "$(YELLOW)Running Docker tests...$(NC)"
	@command -v docker >/dev/null 2>&1 || (echo "$(RED)Docker required$(NC)" && exit 1)
	@docker ps >/dev/null 2>&1 || (echo "$(RED)Docker daemon not running$(NC)" && exit 1)
	$(UV) run --with pytest-asyncio pytest tests/integration -v -m docker -s
	@echo "$(GREEN)✓ Docker tests completed$(NC)"

test-coverage: ## Run tests with coverage report
	@echo "$(YELLOW)Running tests with coverage...$(NC)"
	$(UV) run --with pytest-asyncio --with pytest-cov pytest tests/unit --cov=src/bio_mcp --cov-report=html --cov-report=term
	@echo "$(GREEN)✓ Coverage report generated in htmlcov/$(NC)"

test-watch: ## Run tests in watch mode for development
	@echo "$(YELLOW)Running tests in watch mode (Ctrl+C to stop)...$(NC)"
	$(UV) run --with pytest-asyncio --with pytest-xdist pytest tests/unit -f

test-ci: ## Run full test suite for CI
	@echo "$(YELLOW)Running full CI test suite...$(NC)"
	$(UV) run --with pytest-asyncio pytest tests/unit -v
	@if command -v docker >/dev/null 2>&1 && docker ps >/dev/null 2>&1; then \
		echo "$(YELLOW)Docker available, running integration tests...$(NC)"; \
		$(UV) run --with pytest-asyncio pytest tests/integration -v; \
	else \
		echo "$(YELLOW)Docker not available, skipping integration tests$(NC)"; \
	fi
	@echo "$(GREEN)✓ CI test suite completed$(NC)"

# Code Quality
lint: ## Run linting (Ruff)
	@echo "$(YELLOW)Running linter...$(NC)"
	$(UV) run --with ruff ruff check src/ tests/
	@echo "$(GREEN)✓ Linting completed$(NC)"

format: ## Format code (Ruff)
	@echo "$(YELLOW)Formatting code...$(NC)"
	$(UV) run --with ruff ruff format src/ tests/
	@echo "$(GREEN)✓ Code formatted$(NC)"

type-check: ## Run type checking (MyPy)
	@echo "$(YELLOW)Running type checker...$(NC)"
	$(UV) run --with mypy mypy src/
	@echo "$(GREEN)✓ Type checking completed$(NC)"

check: lint type-check ## Run all code quality checks

security-scan: ## Run security vulnerability scan
	@echo "$(YELLOW)Running security scan...$(NC)"
	$(UV) run --with safety safety check
	@echo "$(GREEN)✓ Security scan completed$(NC)"

# Chunking tests and validation
test-chunking: ## Run chunking-specific tests
	@echo "$(YELLOW)Running chunking tests...$(NC)"
	$(UV) run --with pytest-asyncio pytest tests/unit/services/test_chunking.py -v
	@echo "$(GREEN)✓ Chunking tests completed$(NC)"

test-chunking-perf: ## Run chunking performance tests  
	@echo "$(YELLOW)Running chunking performance tests...$(NC)"
	$(UV) run --with pytest-asyncio pytest tests/performance/test_chunking_performance.py -v
	@echo "$(GREEN)✓ Chunking performance tests completed$(NC)"

validate-chunking: ## Validate chunking on sample data
	@echo "$(YELLOW)Validating chunking strategy...$(NC)"
	$(UV) run python scripts/validate_chunking.py --sample-size 10
	@echo "$(GREEN)✓ Chunking validation completed$(NC)"

benchmark-chunking: ## Benchmark chunking performance
	@echo "$(YELLOW)Running chunking performance benchmark...$(NC)"
	$(UV) run python scripts/benchmark_chunking.py --iterations 3
	@echo "$(GREEN)✓ Chunking benchmark completed$(NC)"

# Development Server
run: ## Run the MCP server locally
	@echo "$(YELLOW)Starting Bio-MCP server...$(NC)"
	$(UV) run python -m bio_mcp.main

run-http: ## Run the HTTP server locally
	@echo "$(YELLOW)Starting Bio-MCP HTTP server...$(NC)"
	@echo "$(BLUE)API will be available at: http://localhost:8000$(NC)"
	@echo "$(BLUE)Web UI will be available at: http://localhost:8000$(NC)"
	UVICORN_LIMIT=200 LOG_LEVEL=info $(UV) run python -m bio_mcp.main_http

run-worker: ## Run the async job worker
	@echo "$(YELLOW)Starting job worker...$(NC)"
	@$(UV) run python -m bio_mcp.http.jobs.worker

# ============================================================================
# WEAVIATE V2 COMMANDS
# ============================================================================

weaviate-create-v2: ## Create DocumentChunk_v2 collection
	@echo "$(YELLOW)Creating DocumentChunk_v2 collection...$(NC)"
	@$(UV) run python -m scripts.create_weaviate_schema
	@echo "$(GREEN)✓ DocumentChunk_v2 collection created$(NC)"

weaviate-info: ## Show Weaviate collection information
	@echo "$(YELLOW)Getting Weaviate collection info...$(NC)"
	@$(UV) run python -m scripts.weaviate_info

weaviate-info-v2: ## Show DocumentChunk_v2 collection information
	@echo "$(YELLOW)Getting DocumentChunk_v2 collection info...$(NC)"
	@$(UV) run python -m scripts.weaviate_info --collection DocumentChunk_v2 --validate

weaviate-recreate-v2: ## Recreate DocumentChunk_v2 collection (WARNING: deletes data)
	@echo "$(RED)⚠️  This will delete DocumentChunk_v2 collection data! Press Ctrl+C to cancel...$(NC)"
	@sleep 3
	@echo "$(YELLOW)Recreating DocumentChunk_v2 collection...$(NC)"
	@$(UV) run python -m scripts.create_weaviate_schema --force
	@echo "$(GREEN)✓ DocumentChunk_v2 collection recreated$(NC)"

test-weaviate-v2: ## Run Weaviate V2 integration tests
	@echo "$(YELLOW)Running Weaviate V2 integration tests...$(NC)"
	@$(UV) run --with pytest-asyncio pytest tests/integration/test_weaviate_v2.py -v
	@echo "$(GREEN)✓ Weaviate V2 tests completed$(NC)"

test-openai: ## Run OpenAI embedding tests (requires API key)
	@echo "$(YELLOW)Running OpenAI embedding tests...$(NC)"
	@test -n "$$OPENAI_API_KEY" || (echo "$(RED)Error: OPENAI_API_KEY environment variable required$(NC)" && exit 1)
	@$(UV) run --with pytest-asyncio pytest tests/integration/test_openai_embeddings.py -v
	@echo "$(GREEN)✓ OpenAI embedding tests completed$(NC)"


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
	@docker-compose exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS postgres;" 2>/dev/null || true
	@docker-compose exec postgres psql -U postgres -c "CREATE DATABASE postgres;" 2>/dev/null || true
	@$(MAKE) migrate
	@echo "$(GREEN)✅ Database reset complete$(NC)"

# ============================================================================
# HEALTH AND TESTING
# ============================================================================

health-check: ## Check if all services are healthy
	@echo "$(YELLOW)Checking service health...$(NC)"
	@docker-compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1 && echo "$(GREEN)✓ PostgreSQL$(NC)" || echo "$(RED)✗ PostgreSQL$(NC)"
	@curl -s http://localhost:8080/v1/.well-known/ready >/dev/null 2>&1 && echo "$(GREEN)✓ Weaviate$(NC)" || echo "$(RED)✗ Weaviate$(NC)"
	@curl -s http://localhost:9000/minio/health/live >/dev/null 2>&1 && echo "$(GREEN)✓ MinIO$(NC)" || echo "$(RED)✗ MinIO$(NC)"

quickstart: up migrate ## Quick setup and test (first-time users)
	@echo "$(BLUE)🎯 Running Bio-MCP Quickstart...$(NC)"
	@echo "$(YELLOW)Step 1: Starting HTTP server (background)...$(NC)"
	@$(UV) run python -m bio_mcp.main_http & SERVER_PID=$$!; \
		sleep 5; \
		echo "$(YELLOW)Step 2: Testing health endpoints...$(NC)"; \
		curl -s localhost:8000/healthz | grep -q "ok" && echo "$(GREEN)✓ Health check passed$(NC)" || echo "$(RED)✗ Health check failed$(NC)"; \
		echo "$(YELLOW)Step 3: Listing available tools...$(NC)"; \
		curl -s localhost:8000/v1/mcp/tools 2>/dev/null | jq -r '.tools[].name' 2>/dev/null | head -3 || echo "$(YELLOW)Tools endpoint not ready$(NC)"; \
		kill $$SERVER_PID 2>/dev/null || true; \
		echo "$(GREEN)🎉 Quickstart complete! Bio-MCP basic setup is working!$(NC)"

smoke-http: ## Basic HTTP health checks
	@echo "$(YELLOW)Running HTTP smoke tests...$(NC)"
	curl -fsS localhost:8080/healthz && echo " - Health OK" || echo " - Health FAILED"
	curl -fsS localhost:8080/readyz && echo " - Readiness OK" || echo " - Readiness FAILED"
	@echo "$(GREEN)✓ HTTP smoke tests completed$(NC)"

invoke-test: ## Test tool invocation via HTTP
	@echo "$(YELLOW)Testing tool invocation...$(NC)"
	curl -s -X POST localhost:8080/v1/mcp/invoke \
	  -H 'content-type: application/json' \
	  -d '{"tool":"ping","params":{"message":"test"}}' | jq .
	@echo "$(GREEN)✓ Tool invocation test completed$(NC)"

# Docker Commands
docker-build: ## Build Docker image
	@echo "$(YELLOW)Building Docker image...$(NC)"
	docker build -t $(PROJECT_NAME):latest .
	@echo "$(GREEN)✓ Docker image built$(NC)"

docker-run: ## Run Docker container
	@echo "$(YELLOW)Running Docker container...$(NC)"
	docker run --rm -it $(PROJECT_NAME):latest

docker-up: ## Start development services with Docker Compose
	@echo "$(YELLOW)Starting development services...$(NC)"
	docker-compose up -d weaviate postgres
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(BLUE)Weaviate: http://localhost:8080$(NC)"
	@echo "$(BLUE)PostgreSQL: localhost:5433$(NC)"

up: ## Start all development services (ONBOARDING alias)
	@echo "$(YELLOW)Starting development services...$(NC)"
	@docker-compose up -d postgres weaviate minio
	@echo "$(YELLOW)Waiting for services to be healthy...$(NC)"
	@sleep 5
	@$(MAKE) health-check || echo "$(YELLOW)Some services may still be starting...$(NC)"
	@echo "$(GREEN)✅ Services ready!$(NC)"
	@echo "$(BLUE)PostgreSQL: localhost:5433$(NC)"
	@echo "$(BLUE)Weaviate: http://localhost:8080 (hybrid: OpenAI + local transformers)$(NC)"
	@echo "$(BLUE)MinIO S3: http://localhost:9000$(NC)"
	@echo "$(BLUE)MinIO Console: http://localhost:9001 (minioadmin/minioadmin)$(NC)"

up-openai: ## Start services with OpenAI-only configuration (requires API key)
	@echo "$(YELLOW)Starting OpenAI-enabled development services...$(NC)"
	@test -n "$$OPENAI_API_KEY" || (echo "$(RED)Error: OPENAI_API_KEY environment variable required$(NC)" && exit 1)
	@docker-compose -f docker-compose.openai.yml up -d postgres weaviate minio
	@echo "$(YELLOW)Waiting for services to be healthy...$(NC)"
	@sleep 5
	@$(MAKE) health-check || echo "$(YELLOW)Some services may still be starting...$(NC)"
	@echo "$(GREEN)✅ OpenAI services ready!$(NC)"
	@echo "$(BLUE)PostgreSQL: localhost:5433$(NC)"
	@echo "$(BLUE)Weaviate: http://localhost:8080 (OpenAI embeddings)$(NC)"
	@echo "$(BLUE)MinIO S3: http://localhost:9000$(NC)"
	@echo "$(BLUE)MinIO Console: http://localhost:9001 (minioadmin/minioadmin)$(NC)"

docker-down: ## Stop development services
	@echo "$(YELLOW)Stopping development services...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

down: ## Stop all development services (ONBOARDING alias)
	@echo "$(YELLOW)Stopping development services...$(NC)"
	@docker-compose down
	@docker-compose -f docker-compose.openai.yml down 2>/dev/null || true
	@echo "$(GREEN)✅ Services stopped$(NC)"

down-openai: ## Stop OpenAI-specific services
	@echo "$(YELLOW)Stopping OpenAI development services...$(NC)"
	@docker-compose -f docker-compose.openai.yml down
	@echo "$(GREEN)✅ OpenAI services stopped$(NC)"

reset: down ## Reset everything (WARNING: destroys data)
	@echo "$(RED)⚠️  This will delete all local data! Press Ctrl+C to cancel...$(NC)"
	@sleep 3
	@docker-compose down -v
	@rm -rf data/* logs/* 2>/dev/null || true
	@echo "$(GREEN)✅ Reset complete$(NC)"

docker-logs: ## Show Docker Compose logs
	docker-compose logs -f

# Build and Release
build: ## Build the package
	@echo "$(YELLOW)Building package...$(NC)"
	$(UV) build
	@echo "$(GREEN)✓ Package built$(NC)"

clean: ## Clean build artifacts
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	rm -rf dist/ build/ *.egg-info htmlcov/ .coverage .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

# Dependency Management
deps-update: ## Update dependencies
	@echo "$(YELLOW)Updating dependencies...$(NC)"
	$(UV) sync --upgrade
	@echo "$(GREEN)✓ Dependencies updated$(NC)"

deps-list: ## List all dependencies
	$(UV) pip list

# Version Management
version: ## Show current version
	@echo "Current version: $$($(UV) run python -c 'from src.bio_mcp import __version__; print(__version__)')"

bump-patch: ## Bump patch version (0.1.0 -> 0.1.1)
	@echo "$(YELLOW)Bumping patch version...$(NC)"
	# This would integrate with your version management tool
	@echo "$(RED)Manual version bump required in src/bio_mcp/__init__.py$(NC)"

bump-minor: ## Bump minor version (0.1.0 -> 0.2.0) 
	@echo "$(YELLOW)Bumping minor version...$(NC)"
	@echo "$(RED)Manual version bump required in src/bio_mcp/__init__.py$(NC)"

bump-major: ## Bump major version (0.1.0 -> 1.0.0)
	@echo "$(YELLOW)Bumping major version...$(NC)"
	@echo "$(RED)Manual version bump required in src/bio_mcp/__init__.py$(NC)"

# Development Workflow Helpers
fresh-start: clean install ## Clean everything and reinstall
	@echo "$(GREEN)✓ Fresh development environment ready$(NC)"

pre-commit: format lint type-check test ## Run all pre-commit checks
	@echo "$(GREEN)✓ Pre-commit checks passed$(NC)"

# Quick development commands
dev-setup: dev docker-up ## Full development setup
	@echo "$(GREEN)✓ Development environment fully set up$(NC)"
	@echo "$(BLUE)Ready to develop! Try 'make test' or 'make run'$(NC)"

# Complete Testing Workflow
test-all: ## Run all tests (unit + integration)
	@echo "$(YELLOW)Running all tests...$(NC)"
	$(UV) run pytest tests/ -v
	@echo "$(GREEN)✓ All tests completed$(NC)"

test-quick: ## Run quick unit tests only
	@echo "$(YELLOW)Running quick unit tests...$(NC)"
	@$(UV) run pytest tests/unit -v --tb=short
	@echo "$(GREEN)✅ Quick tests passed$(NC)"

# Local Deployment
deploy-local: ## Build and deploy locally for manual testing
	@echo "$(YELLOW)Building and deploying locally...$(NC)"
	@echo "1. Cleaning previous build..."
	@$(MAKE) clean
	@echo "2. Building package..."
	@$(MAKE) build
	@echo "3. Starting server (will run for 10 seconds for testing)..."
	@timeout 10s $(UV) run python -m bio_mcp.main & \
	SERVER_PID=$$!; \
	sleep 2; \
	echo "4. Testing health endpoint..."; \
	$(UV) run python -m bio_mcp.health && \
	echo "$(GREEN)✓ Server is healthy$(NC)" || echo "$(RED)✗ Health check failed$(NC)"; \
	echo "5. Server running at PID $$SERVER_PID (will auto-stop)..."; \
	wait $$SERVER_PID 2>/dev/null || true; \
	echo "$(GREEN)✓ Local deployment test complete$(NC)"
	@echo ""
	@echo "$(BLUE)To run server manually:$(NC) make run"
	@echo "$(BLUE)To run with services:$(NC) make docker-up && make run"

# Full workflow
workflow: clean build test-all deploy-local ## Complete build -> test -> deploy workflow
	@echo "$(GREEN)🎉 Complete workflow finished!$(NC)"
	@echo "$(BLUE)Server is ready for use. Run 'make run' to start manually.$(NC)"