SHELL := /bin/bash
COMPOSE_LOCAL := docker compose -f docker-compose.yml --env-file .env.local
COMPOSE_DEV := docker compose -f docker-compose.dev.yml --env-file .env.dev
COMPOSE_PROD := docker compose -f docker-compose.prod.yml --env-file .env.prod

.PHONY: help lint test test-fast ci precommit-install local-up local-down dev-up dev-down prod-up prod-down migrate-local migrate-dev migrate-prod health-local health-dev health-prod rollback-dev rollback-prod

help:
	@echo "Available targets:"
	@echo "  lint            - Run Ruff checks"
	@echo "  test            - Run pytest"
	@echo "  ci              - Run lint + tests"
	@echo "  local-up/down   - Start/stop local stack"
	@echo "  dev-up/down     - Start/stop dev stack"
	@echo "  prod-up/down    - Start/stop prod stack"
	@echo "  migrate-*       - Run alembic upgrade head per env"
	@echo "  health-*        - Run readiness check per env"
	@echo "  rollback-dev    - Rollback dev migration by 1"
	@echo "  rollback-prod   - Rollback prod migration by 1"

lint:
	cd backend && python -m ruff check app tests

test:
	cd backend && python -m pytest -q

test-fast:
	cd backend && python -m pytest -q -m "not integration"

ci: lint test

precommit-install:
	pre-commit install

local-up:
	$(COMPOSE_LOCAL) up -d --build

local-down:
	$(COMPOSE_LOCAL) down

dev-up:
	$(COMPOSE_DEV) up -d --build

dev-down:
	$(COMPOSE_DEV) down

prod-up:
	$(COMPOSE_PROD) up -d

prod-down:
	$(COMPOSE_PROD) down

migrate-local:
	$(COMPOSE_LOCAL) exec backend alembic upgrade head

migrate-dev:
	$(COMPOSE_DEV) exec backend alembic upgrade head

migrate-prod:
	$(COMPOSE_PROD) exec backend alembic upgrade head

health-local:
	curl -fsS "http://localhost:$${FASTAPI_PORT:-8000}/api/v1/health/ready"

health-dev:
	curl -fsS "http://localhost:$${FASTAPI_PORT:-8000}/api/v1/health/ready"

health-prod:
	curl -fsS "http://localhost:$${FASTAPI_PORT:-8000}/api/v1/health/ready"

rollback-dev:
	$(COMPOSE_DEV) exec backend alembic downgrade -1

rollback-prod:
	$(COMPOSE_PROD) exec backend alembic downgrade -1
