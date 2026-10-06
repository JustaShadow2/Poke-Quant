# PokeQuant developer tasks.
# Local Python is managed by uv into ./.venv ; runtime target is 3.12 (docker/).

PY := .venv/bin/python
UV := uv
export UV_CACHE_DIR := $(PWD)/.dev/uv-cache
export TMPDIR := $(PWD)/.dev/tmp
API_DIR := apps/api
WEB_DIR := apps/web

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- setup
.PHONY: setup
setup: ## Create local venv and install the API package (editable, with dev extras)
	mkdir -p .dev/uv-cache .dev/tmp data/artifacts
	@if [ ! -x .venv/bin/python ]; then $(UV) venv .venv --python 3.9; fi
	$(UV) pip install --python $(PY) -e "$(API_DIR)[dev]"

# ---------------------------------------------------------------- quality
.PHONY: fmt
fmt: ## Auto-format (ruff)
	$(PY) -m ruff format $(API_DIR)
	$(PY) -m ruff check --fix $(API_DIR)

.PHONY: lint
lint: ## Lint (ruff)
	$(PY) -m ruff check $(API_DIR)
	$(PY) -m ruff format --check $(API_DIR)

.PHONY: typecheck
typecheck: ## Static type check (mypy)
	cd $(API_DIR) && ../../$(PY) -m mypy pokequant

.PHONY: test
test: ## Run the Python test suite
	cd $(API_DIR) && ../../$(PY) -m pytest

.PHONY: check
check: lint typecheck test ## Lint + typecheck + test

# ---------------------------------------------------------------- data / ml (offline capable)
.PHONY: migrate
migrate: ## Apply DB migrations (needs DATABASE_URL / running Postgres)
	cd $(API_DIR) && ../../$(PY) -m pokequant.cli db upgrade

.PHONY: seed
seed: ## Seed asset classes, categories and the curated instrument catalog
	cd $(API_DIR) && ../../$(PY) -m pokequant.cli seed

.PHONY: synth
synth: ## Generate calibrated synthetic price history (offline)
	cd $(API_DIR) && ../../$(PY) -m pokequant.cli synth --days 900

.PHONY: ingest
ingest: ## Run a daily ingestion + snapshot pass (uses live providers if keys set)
	cd $(API_DIR) && ../../$(PY) -m pokequant.cli ingest

.PHONY: features
features: ## Build point-in-time features
	cd $(API_DIR) && ../../$(PY) -m pokequant.cli features build

.PHONY: train
train: ## Train baseline + GBM forecasters and register them
	cd $(API_DIR) && ../../$(PY) -m pokequant.cli train --horizon d90

.PHONY: vision-train
vision-train: ## Train the card-grading CNN on synthetic data
	cd $(API_DIR) && ../../$(PY) -m pokequant.cli vision-train

.PHONY: forecast
forecast: ## Batch-forecast all instruments with the production model
	cd $(API_DIR) && ../../$(PY) -m pokequant.cli forecast run

.PHONY: phase2
phase2: ## Run Phase 2 batch: calibrate + explain + score + risk
	cd $(API_DIR) && ../../$(PY) -m pokequant.cli phase2

.PHONY: drift-check
drift-check: ## Run drift detection on the production model
	cd $(API_DIR) && ../../$(PY) -m pokequant.cli drift-check

.PHONY: retrain
retrain: ## Check drift and retrain if needed
	cd $(API_DIR) && ../../$(PY) -m pokequant.cli retrain

.PHONY: bootstrap
bootstrap: migrate seed synth features train vision-train forecast phase2 ## Full offline end-to-end pipeline

# ---------------------------------------------------------------- run
.PHONY: api
api: ## Run the API (uvicorn, reload)
	cd $(API_DIR) && ../../$(PY) -m uvicorn pokequant.api.app:app --reload --port 8000

.PHONY: web-install
web-install: ## Install frontend deps
	cd $(WEB_DIR) && npm install

.PHONY: web
web: ## Run the Next.js dev server
	cd $(WEB_DIR) && NEXT_TELEMETRY_DISABLED=1 npm run dev

.PHONY: web-typecheck
web-typecheck: ## Type-check the frontend (tsc --noEmit)
	cd $(WEB_DIR) && npm run typecheck

.PHONY: web-build
web-build: ## Production build of the frontend
	cd $(WEB_DIR) && NEXT_TELEMETRY_DISABLED=1 npm run build

.PHONY: verify
verify: check web-typecheck web-build ## Backend check + frontend typecheck/build

# ---------------------------------------------------------------- docker
.PHONY: up
up: ## Start the full stack (db + api + web) via docker compose
	docker compose up --build

.PHONY: down
down: ## Stop the stack
	docker compose down -v
