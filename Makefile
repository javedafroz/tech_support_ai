.PHONY: up down migrate api web install test lint check-venv e2e-install e2e e2e-ui test-live test-live-ui test-live-install

# Project-root virtualenv (created by `make install`)
VENV_BIN := $(CURDIR)/.venv/bin

check-venv:
	@test -x $(VENV_BIN)/python || (echo "Run 'make install' first to create .venv at the project root." && exit 1)

up:
	docker compose up -d postgres redis minio minio-init

up-all:
	docker compose up -d --build

down:
	docker compose down

install:
	@if command -v uv >/dev/null 2>&1; then \
		uv sync; \
	else \
		python3 -m venv .venv && $(VENV_BIN)/pip install -r requirements-dev.txt; \
	fi
	cd apps/web && npm install

migrate: check-venv
	cd apps/api && $(VENV_BIN)/alembic upgrade head

create-ticket: check-venv
	$(VENV_BIN)/python scripts/create_ticket.py $(ARGS)

zammad-e2e: check-venv
	$(VENV_BIN)/python scripts/zammad_sandbox_e2e.py

api: check-venv
	$(VENV_BIN)/tech-support-api

web:
	cd apps/web && npm run dev

test: check-venv
	$(VENV_BIN)/pytest
	cd apps/web && npm run test

e2e-install:
	cd e2e && npm install
	cd e2e && npx playwright install chromium

e2e: check-venv e2e-install
	cd e2e && npm test

e2e-ui: check-venv e2e-install
	cd e2e && npm run test:ui

test-live-install: check-venv
	$(VENV_BIN)/playwright install chromium

test-live: check-venv
	@echo "Note: API-only mode (no browser). For visible Chromium use: make test-live-ui"
	$(VENV_BIN)/pytest tests/integration -m live -v -s --log-cli-level=INFO --tb=short

test-live-ui: check-venv test-live-install
	INTEGRATION_HEADLESS=false \
	INTEGRATION_SLOW_MO=350 \
	INTEGRATION_UI_PAUSE_MS=2500 \
	$(VENV_BIN)/pytest tests/integration -m live_ui -v -s --log-cli-level=INFO --tb=short

lint: check-venv
	$(VENV_BIN)/ruff check apps/api packages
	cd apps/web && npm run lint
