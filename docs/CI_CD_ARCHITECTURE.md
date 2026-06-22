# Enterprise CI/CD Architecture (FastAPI)

## Target Stack

- FastAPI on Python 3.11
- SQLAlchemy Async + Alembic
- PostgreSQL + Redis
- WebSocket notification services
- Docker + Docker Compose
- Pytest + Ruff
- GitHub Actions for CI/CD

## Environment Model

- `local`: developer machine with `docker-compose.yml` and `.env.local`
- `dev`: shared integration environment with `docker-compose.dev.yml` and `.env.dev`
- `prod`: production environment with `docker-compose.prod.yml` and `.env.prod`

## Recommended Folder Structure

```text
.
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── cd-dev.yml
│       └── cd-prod.yml
├── backend/
│   ├── Dockerfile
│   ├── docker-entrypoint.sh
│   ├── requirements.txt
│   ├── ruff.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   └── core/logging.py
│   └── tests/
├── scripts/
│   └── deploy/
│       ├── deploy.sh
│       ├── health-check.sh
│       └── rollback.sh
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── .pre-commit-config.yaml
└── Makefile
```

## CI Pipeline (`.github/workflows/ci.yml`)

1. Install Python 3.11 and dependencies.
2. Start service containers for PostgreSQL and Redis.
3. Run Ruff checks.
4. Run Alembic migrations (`upgrade head`).
5. Run Pytest test suite.
6. Build and push backend image to GHCR on push events.

## CD Pipeline (`cd-dev.yml`, `cd-prod.yml`)

- Uses SSH to run deployment commands on remote hosts.
- Dev deploy trigger: pushes to `develop`.
- Prod deploy trigger: pushes to `main` and manual workflow dispatch.
- Pulls image, runs `docker compose up -d`, executes migrations, validates readiness health endpoint.

## Alembic Migration Automation

- Runtime migrations are controlled via `RUN_MIGRATIONS=1`.
- Entry point executes `alembic upgrade head` before starting app process.
- CI validates migrations against clean PostgreSQL service.
- CD executes migration step after pulling new image.

## Rollback Strategy

- Each deployment records current image in `.deploy-state/<env>.last_image`.
- Previous image is kept as `.deploy-state/<env>.prev_image`.
- `scripts/deploy/rollback.sh` restores previous image and performs best-effort DB downgrade (`alembic downgrade -1`).
- Health check validation must pass after rollback.

## Health Check Validation

- Application endpoints:
  - `/api/v1/health/live`
  - `/api/v1/health/ready`
- Readiness verifies:
  - DB connectivity (`SELECT 1`)
  - Redis connectivity (`PING`) when `REDIS_URL` is configured
- Docker health checks and deploy scripts rely on `/api/v1/health/ready`.

## Structured Logging

- JSON logs emitted to stdout via `backend/app/core/logging.py`.
- Recommended log shipping:
  - Docker logging driver to central collector, or
  - Sidecar/agent (Fluent Bit, Vector, Datadog Agent).

## Branching and Release Strategy

- `main`: production-ready branch only.
- `develop`: integration branch for dev environment.
- `feature/<ticket-id>-<short-name>`: short-lived feature branches.
- Pull Request requirements:
  - CI green
  - At least one reviewer approval
  - No direct push to `main`

## GitHub Secrets Configuration

Set repository or environment-level secrets:

- Shared image/runtime
  - `GITHUB_TOKEN` (provided by GitHub Actions)
- Dev environment
  - `DEV_SSH_HOST`
  - `DEV_SSH_PORT`
  - `DEV_SSH_USER`
  - `DEV_SSH_PRIVATE_KEY`
  - `DEV_DEPLOY_PATH`
- Prod environment
  - `PROD_SSH_HOST`
  - `PROD_SSH_PORT`
  - `PROD_SSH_USER`
  - `PROD_SSH_PRIVATE_KEY`
  - `PROD_DEPLOY_PATH`

## Operational Best Practices

- Protect `main` and `develop` with required checks.
- Enforce pre-commit locally (`pre-commit install`).
- Keep `.env.*` files out of version control.
- Backup database before prod deployment.
- Use immutable image tags for release traceability.
