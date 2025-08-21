# Bio-MCP Development Makefile
# Provides easy commands for development, testing, and deployment

.PHONY: help install dev test test-unit test-integration test-docker test-coverage test-watch test-ci
.PHONY: lint format type-check security-scan clean build run docker-build docker-run docker-up docker-down
.PHONY: deps-update version bump-patch bump-minor bump-major
.PHONY: manual-test test-health test-server test-logs test-signals test-docker-health test-all-manual

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

# Development Server
run: ## Run the MCP server locally
	@echo "$(YELLOW)Starting Bio-MCP server...$(NC)"
	$(UV) run python -m bio_mcp.main

run-http: ## Run the HTTP server locally
	@echo "$(YELLOW)Starting Bio-MCP HTTP server...$(NC)"
	UVICORN_LIMIT=200 LOG_LEVEL=info $(UV) run python -m bio_mcp.main_http

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

docker-down: ## Stop development services
	@echo "$(YELLOW)Stopping development services...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

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