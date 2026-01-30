# Database: Alembic Setup & Docker Deployment

This guide covers **Alembic setup**, **Docker deployment step by step**, and how to **clean the database** and regenerate tables.

---

## Table of Contents

1. [Alembic Setup (Step by Step)](#alembic-setup-step-by-step)
2. [Docker Run for Deployment (Step by Step)](#docker-run-for-deployment-step-by-step)
3. [Clean Database (Reset to Empty)](#clean-database-reset-to-empty)
4. [Generate Tables for Fresh Deployment](#generate-tables-for-fresh-deployment)
5. [Quick Reference](#quick-reference)

---

## Alembic Setup (Step by Step)

### Step 1: Prerequisites

- Python 3.11+ with `backend/` as working directory
- PostgreSQL running (locally or via Docker)
- Dependencies installed: `pip install -r requirements.txt`

### Step 2: Configuration

Alembic is already configured in this project:

| File | Purpose |
|------|---------|
| `alembic.ini` | Main config (script location, logging). Database URL can be set here or in `env.py`. |
| `alembic/env.py` | Runtime config: imports models, sets `target_metadata` from SQLAlchemy `Base`, configures connection from `DATABASE_URL` or `alembic.ini`. |
| `alembic/versions/` | Migration scripts (one file per revision). |

Ensure your database URL is available:

- **Docker:** Backend uses `DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/laminar_database` from `docker-compose.yml`.
- **Local:** Set `DATABASE_URL` in `.env` or in `alembic.ini` under `[postgresql]` / `sqlalchemy.url`, e.g. `postgresql+asyncpg://user:pass@localhost:5432/laminar_database`.

### Step 3: Create a New Migration (Optional)

When you change models and need a new revision:

```bash
# From backend/ directory (or project root with correct DATABASE_URL)
cd backend

# Generate a new migration from model changes
alembic revision --autogenerate -m "description of change"

# Example: add a new column
# alembic revision --autogenerate -m "add_aircraft_fk_to_logbooks"
```

This creates a new file in `alembic/versions/`. Edit it if needed, then run the migration (Step 4).

### Step 4: Run Migrations

**Option A – Inside Docker (recommended for deployment):**

```bash
# From project root
docker compose exec backend alembic upgrade head
```

**Option B – Local (same machine as PostgreSQL):**

```bash
cd backend
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/laminar_database"
alembic upgrade head
```

### Step 5: Useful Alembic Commands

| Command | Description |
|---------|-------------|
| `alembic current` | Show current revision. |
| `alembic history` | List all revisions. |
| `alembic upgrade head` | Apply all pending migrations. |
| `alembic downgrade -1` | Roll back one revision. |
| `alembic downgrade base` | Roll back all migrations (empty schema). |

---

## Docker Run for Deployment (Step by Step)

All steps assume you are in the **project root** (where `docker-compose.yml` is).

### Step 1: Prerequisites

- Docker and Docker Compose installed
- No other process using ports 5432 (PostgreSQL), 6379 (Redis), 8000 (API)

### Step 2: Environment (Optional)

```bash
# Copy example env if you have one
cp .env.example .env

# Edit .env if you need to change:
# - SECRET_KEY
# - DATABASE_URL (default in docker-compose is fine for local)
# - DEBUG
```

### Step 3: Build and Start Containers

```bash
# Stop any existing containers and remove volumes for a clean DB (optional)
docker compose down -v

# Build images and start all services in detached mode
docker compose up --build -d
```

This starts:

- **db** – PostgreSQL 15
- **redis** – Redis 7
- **backend** – FastAPI app (runs `alembic upgrade head` on startup, then uvicorn)
- **celery** – Celery worker

### Step 4: Wait for Services and Verify Migrations

```bash
# Check that containers are running
docker compose ps

# Backend runs migrations automatically; to confirm current revision:
docker compose exec backend alembic current

# If migrations did not run on startup, run them manually:
docker compose exec backend alembic upgrade head
```

### Step 5: Verify API and Database

```bash
# API docs
open http://localhost:8000/docs

# Health / docs (optional)
curl -s http://localhost:8000/docs | head -5

# List tables in PostgreSQL (optional)
docker compose exec db psql -U postgres -d laminar_database -c "\dt"
```

### Step 6: View Logs (Optional)

```bash
# Backend logs
docker compose logs -f backend

# All services
docker compose logs -f
```

---

## Clean Database (Reset to Empty)

Choose one method depending on whether you want to keep the PostgreSQL container or remove everything.

### Option A: Remove Database Volume (Full Reset)

**Use when:** You want a completely empty database and are okay losing all data.

From the **project root** (where `docker-compose.yml` lives):

```bash
# Stop all containers and remove the database volume
docker compose down -v

# Optional: remove the named volume explicitly if it persists
docker volume rm laminar_core_pgdata 2>/dev/null || true
```

- `-v` removes **volumes** (including `pgdata` where PostgreSQL stores data).
- Next time you start the backend, the DB will be empty and migrations will create all tables from scratch.

### Option B: Reset Without Removing Volume (Recreate Database)

**Use when:** You want to wipe data but keep the same volume/container setup.

```bash
# 1. Connect to PostgreSQL and drop/recreate the database
docker compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS laminar_database;"
docker compose exec db psql -U postgres -c "CREATE DATABASE laminar_database;"

# 2. Run migrations to create tables again
docker compose exec backend alembic upgrade head
```

### Option C: Alembic Downgrade (Schema Only)

**Use when:** You want to remove all tables created by Alembic but keep the database and role.

```bash
# From project root
docker compose exec backend alembic downgrade base
```

This runs the **downgrade** for each migration down to no schema. The database `laminar_database` still exists but will have no application tables. Then run `alembic upgrade head` to recreate them.

---

## Generate Tables for Fresh Deployment

After the database is **empty** (or recreated), you need to create all tables. The backend is configured to run migrations automatically on startup when using Docker.

### 1. Start Docker (from project root)

```bash
# Clean start (removes old DB data)
docker compose down -v

# Build and start all services; backend runs migrations on startup
docker compose up --build -d
```

The backend container runs `docker-entrypoint.sh`, which executes:

```text
alembic upgrade head
```

So **tables are created automatically** on first start (or after a clean reset).

### 2. Verify Tables Were Created

```bash
# Check migration version
docker compose exec backend alembic current

# Inspect tables in PostgreSQL (optional)
docker compose exec db psql -U postgres -d laminar_database -c "\dt"
```

### 3. If Migrations Don’t Run on Startup

Run them manually:

```bash
docker compose exec backend alembic upgrade head
```

---

## Quick Reference

| Goal                         | Command |
|-----------------------------|--------|
| **Clean DB + fresh deploy** | `docker compose down -v` then `docker compose up --build -d` |
| **Wipe DB, keep volume**    | Drop/recreate DB (Option B above), then `alembic upgrade head` |
| **Apply migrations only**   | `docker compose exec backend alembic upgrade head` |
| **Current migration**       | `docker compose exec backend alembic current` |
| **See migration history**   | `docker compose exec backend alembic history` |

---

## Notes

- All commands assume you are in the **project root** (parent of `backend/`) when using `docker compose`.
- The backend uses **Alembic** for migrations; table definitions live in `alembic/versions/`.
- For full deployment steps (env vars, production, etc.), see the root **[DEPLOYMENT.md](../DEPLOYMENT.md)**.
