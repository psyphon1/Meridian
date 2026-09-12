# =============================================================================
# Meridian — Autonomous AI PR Reviewer
# Developer task runner (Git Bash / macOS / Linux / CI). Windows users may run
# .\scripts\bootstrap\bootstrap.ps1 once, then `make` from an active venv.
# Every target is documented in docs/PROJECT_STRUCTURE.md §29 ("Makefile Contract").
# =============================================================================

SHELL      := /bin/bash
PY         ?= python
VENV       := .venv
BIN        := $(VENV)/bin
PYTHON     := $(BIN)/python
PIP        := $(PYTHON) -m pip

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: ## Create venv, install Python + frontend dependencies
	$(PY) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	pnpm install

.PHONY: dev
dev: ## Start backing services (api/worker/web run directly in Phase 1)
	docker compose up -d postgres redis

.PHONY: api
api: ## Run the FastAPI API on :8000
	$(PYTHON) -m uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: worker
worker: ## Run the async review worker
	$(PYTHON) -m apps.worker.main

.PHONY: web
web: ## Run the Next.js dashboard on :3000
	pnpm --filter @meridian/web dev

.PHONY: test test-unit test-integration test-security test-e2e
test: ## Run the full test suite
	$(PYTHON) -m pytest
test-unit:
	$(PYTHON) -m pytest tests/unit
test-integration:
	$(PYTHON) -m pytest tests/integration
test-security:
	$(PYTHON) -m pytest tests/security
test-e2e:
	$(PYTHON) -m pytest tests/e2e

.PHONY: lint format typecheck
lint: ## Lint Python + TypeScript
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	pnpm -r --if-present lint
format: ## Auto-fix Python + TypeScript formatting
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .
	pnpm -r --if-present format
typecheck: ## Type-check Python + TypeScript
	@if ls apps packages services 2>/dev/null | grep -q .; then $(PYTHON) -m mypy apps packages services; else echo "No Python source yet — skipping mypy."; fi
	pnpm -r --if-present typecheck

.PHONY: security
security: ## Run SAST (Semgrep)
	$(PIP) install semgrep
	semgrep ci --config=auto

.PHONY: docker-build docker-up docker-down
docker-build: ## Build all app images
	docker compose --profile app build
docker-up: ## Start backing services
	docker compose up -d postgres redis
docker-down: ## Tear down composed services
	docker compose down

.PHONY: index eval benchmark
index: ## Run repository indexing (Phase 2+)
	$(PYTHON) -m services.repository_indexer
eval: ## Run the evaluation harness
	$(PYTHON) -m pytest evals
benchmark: ## Run the regression benchmark
	$(PYTHON) -m scripts.evaluation.benchmark

.PHONY: clean
clean: ## Remove venv and caches
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

