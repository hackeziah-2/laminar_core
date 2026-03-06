# Laminar Core - Deployment Guide

Complete deployment commands for the Laminar Core application.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed
- Git (for cloning the repository)
- Environment variables configured (optional)

## Deployment Checklist

Ensure each environment uses:

| Requirement | How it's satisfied |
|-------------|--------------------|
| **Unique container names** | Each compose file uses env-specific names (e.g. `laminar_backend_dev`, `laminar_backend_prod`, `laminar_backend_uat`). |
| **Unique network** | Each compose file defines its own network: `laminar_network_dev`, `laminar_network_prod`, `laminar_network_uat`. |
| **Unique host ports** | Set different ports per environment in `.env.dev`, `.env.uat`, `.env.prod` (e.g. `FASTAPI_PORT`, `NGINX_PORT`, `POSTGRES_PORT`, `REDIS_PORT`). |
| **Explicit compose file** | Always use `-f docker-compose.<env>.yml` (e.g. `-f docker-compose.dev.yml`, `-f docker-compose.prod.yml`). |
| **Explicit env file** | Each compose file references an env file (e.g. `.env.dev`). For CLI override, use `--env-file .env.<env>`. |
| **Single Dockerfile (dev/uat/prod)** | One `backend/Dockerfile`; default CMD is production-safe (uvicorn, no `--reload`). Dev compose overrides with `uvicorn ... --reload`; UAT/Prod override with `gunicorn`. |

### CORS and frontend (laminaraviationapp)

- **Backend CORS:** FastAPI in `backend/app/main.py` allows origins for dev (`:3000`), UAT (`:3011`), and prod (`:3002`) on `120.89.33.51`. Override via `ALLOWED_ORIGINS` (comma-separated) or `VITE_APP_URL` if needed.
- **Frontend API URLs:** In the **laminaraviationapp** repo, set env so the frontend calls the correct API:
  - **UAT:** `VITE_APP_URL=http://120.89.33.51:3011`, `VITE_API_URL=http://120.89.33.51:8100/api/v1/` (or use NGINX: `http://120.89.33.51:8080/api/v1/`).
  - **Prod:** `VITE_APP_URL=http://120.89.33.51:3002`, `VITE_API_URL=http://120.89.33.51:8200/api/v1/` (or use NGINX: `http://120.89.33.51:8082/api/v1/`).
- **Reference files:** See `docs/frontend-env-uat.example` and `docs/frontend-env-prod.example`; copy contents to laminaraviationapp as `.env.uat` and `.env.prod`.
- **NGINX:** UAT and prod NGINX configs proxy `/api/v1/` to the backend; host ports are `NGINX_PORT` from `.env.uat` (e.g. 8080) and `.env.prod` (e.g. 8082).

---

## How to run the server (every environment)

Use **one** of the following according to the environment you want to run. Each uses its own compose file and env file so dev, UAT, and prod can run side-by-side without conflicts.

### Development

```bash
# From project root
cp .env.example .env.dev   # edit .env.dev if needed (ports, SECRET_KEY, etc.)
docker-compose -f docker-compose.dev.yml --env-file .env.dev up --build -d
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

- **API:** http://localhost:8000/docs (or the port set in `.env.dev` as `FASTAPI_PORT`)
- **Logs:** `docker-compose -f docker-compose.dev.yml logs -f backend`
- **Stop:** `docker-compose -f docker-compose.dev.yml down`

### UAT

```bash
cp .env.example .env.uat   # set UAT ports and config (e.g. FASTAPI_PORT=8001)
docker-compose -f docker-compose.uat.yml --env-file .env.uat up --build -d
docker-compose -f docker-compose.uat.yml exec backend alembic upgrade head
```

- **API:** http://localhost:`FASTAPI_PORT`/docs (port from `.env.uat`)
- **Logs:** `docker-compose -f docker-compose.uat.yml logs -f backend`
- **Stop:** `docker-compose -f docker-compose.uat.yml down`

### Production

```bash
# Use strong SECRET_KEY and production values in .env.prod
docker-compose -f docker-compose.prod.yml --env-file .env.prod up --build -d
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

- **API:** http://localhost:`FASTAPI_PORT`/docs (port from `.env.prod`, or your public URL)
- **Logs:** `docker-compose -f docker-compose.prod.yml logs -f backend`
- **Stop:** `docker-compose -f docker-compose.prod.yml down`

---

## Table of Contents

1. [Deployment Steps (Command Summary)](#deployment-steps-command-summary)
2. [Initial Setup](#initial-setup)
3. [Development Deployment](#development-deployment)
4. [Database Setup](#database-setup)
5. [Running Migrations](#running-migrations)
6. [Starting Services](#starting-services)
7. [Collation Fix](#collation-fix)
8. [Production Deployment](#production-deployment)
9. [Maintenance Commands](#maintenance-commands)
10. [Troubleshooting](#troubleshooting)
11. [CORS and frontend (laminaraviationapp)](#cors-and-frontend-laminaraviationapp)

---

## Deployment Steps (Command Summary)

Run these commands in order for a full deployment from scratch.

### Step 1: Clone the repository
```bash
git clone <repository-url>
cd laminar_core
```

### Step 2: (Optional) Create `.env` file
```bash
# Create .env in project root with:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/laminar_database
# SECRET_KEY=your-secret-key-change-in-production
# DEBUG=False
```

### Step 3: Stop any existing containers and volumes
```bash
# Use the compose file and env file for your environment (dev / uat / prod)
docker-compose -f docker-compose.dev.yml --env-file .env.dev down -v
```

### Step 4: Build and start all services
```bash
docker-compose -f docker-compose.dev.yml --env-file .env.dev up --build -d
```

### Step 5: Wait for services to be healthy (optional check)
```bash
docker-compose -f docker-compose.dev.yml ps
```

### Step 6: Run database migrations
```bash
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

### Step 7: Verify deployment
```bash
# Check migration status (optional)
docker-compose -f docker-compose.dev.yml exec backend alembic current

# Open API docs in browser
# http://localhost:8000/docs

# Or check with curl
curl http://localhost:8000/docs
```

### One-line deployment (all steps)
```bash
docker-compose -f docker-compose.dev.yml --env-file .env.dev down -v && docker-compose -f docker-compose.dev.yml --env-file .env.dev up --build -d && docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

---

## Initial Setup

### 1. Clone and Navigate
```bash
cd /Users/kevinpaullamadrid/Desktop/Project/laminar_core
```

### 2. Set Environment Variables (Optional)
Create an env file per environment so ports and config stay unique:
- **Development:** copy `.env.example` to `.env.dev`, set `FASTAPI_PORT`, `NGINX_PORT`, `POSTGRES_PORT`, `REDIS_PORT` (e.g. 8000, 80, 5432, 6379).
- **UAT:** `.env.uat` with different ports (e.g. 8001, 81, 5433, 6380).
- **Production:** `.env.prod` with your production ports and secrets.

Example `.env.dev`:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/laminar_database
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key-change-in-production
DEBUG=False
FASTAPI_PORT=8000
NGINX_PORT=80
POSTGRES_PORT=5432
REDIS_PORT=6379
```

---

## Development Deployment

### Fresh Deployment (Recommended for first time)

```bash
# Use explicit compose and env file for dev
COMPOSE_FILE=docker-compose.dev.yml
ENV_FILE=.env.dev

# 1. Stop and remove all containers, volumes, and networks
docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE down -v

# 2. Build and start all services
docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE up --build -d

# 3. Wait for services to be healthy
docker-compose -f $COMPOSE_FILE ps

# 4. Run database migrations
docker-compose -f $COMPOSE_FILE exec backend alembic upgrade head

# 5. Check logs to verify everything is running
docker-compose -f $COMPOSE_FILE logs -f backend
```

### Quick Start (if volumes already exist)

```bash
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

---

## Database Setup

### Create Fresh Database with Collation Fix

```bash
# Use the compose/env for your environment (e.g. dev)
docker-compose -f docker-compose.dev.yml --env-file .env.dev down -v db
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d db
docker-compose -f docker-compose.dev.yml exec db pg_isready -U postgres
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -c "CREATE DATABASE laminar_database;"
```

### Fix Collation Version (if warning appears)

```bash
# Option 1: Run the fix script (uses docker-compose if available)
./backend/scripts/fix_collation.sh

# Option 2: Manual fix (use your compose file)
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -d template1 -c "UPDATE pg_database SET datcollversion = NULL WHERE datname = 'postgres'; ALTER DATABASE postgres REFRESH COLLATION VERSION;"
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -d template1 -c "UPDATE pg_database SET datcollversion = NULL WHERE datname = 'laminar_database'; ALTER DATABASE laminar_database REFRESH COLLATION VERSION;"
```

---

## Running Migrations

Use the same `-f docker-compose.<env>.yml` as your running stack (e.g. `docker-compose.dev.yml` for dev).

### Check Migration Status
```bash
docker-compose -f docker-compose.dev.yml exec backend alembic current
```

### Run All Migrations
```bash
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

### Create New Migration
```bash
docker-compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "migration_description"
```

### Rollback Migration
```bash
docker-compose -f docker-compose.dev.yml exec backend alembic downgrade -1
# Or: docker-compose -f docker-compose.dev.yml exec backend alembic downgrade <revision_id>
```

### Check Migration History
```bash
docker-compose -f docker-compose.dev.yml exec backend alembic history
```

---

## Starting Services

Always pass the compose file (and optionally env file) for your environment.

### Start All Services
```bash
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d
```

### Start Specific Service
```bash
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d db
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d backend
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d celery
```

### Stop Services
```bash
docker-compose -f docker-compose.dev.yml stop
# Or: docker-compose -f docker-compose.dev.yml stop backend
```

### Restart Services
```bash
docker-compose -f docker-compose.dev.yml restart
# Or: docker-compose -f docker-compose.dev.yml restart backend
```

---

## Collation Fix

### Automatic Fix (on fresh database)
The collation fix runs automatically when creating a new database volume. If you need to recreate:
```bash
docker-compose -f docker-compose.dev.yml --env-file .env.dev down -v db
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d db
```

### Manual Fix (for existing databases)
```bash
./backend/scripts/fix_collation.sh
# Or manually (use your compose file):
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -d template1 << EOF
UPDATE pg_database SET datcollversion = NULL WHERE datname = 'postgres';
ALTER DATABASE postgres REFRESH COLLATION VERSION;
UPDATE pg_database SET datcollversion = NULL WHERE datname = 'laminar_database';
ALTER DATABASE laminar_database REFRESH COLLATION VERSION;
EOF
```

---

## Production Deployment

Use **explicit compose and env file** so production uses unique containers, network, and ports:

```bash
COMPOSE_FILE=docker-compose.prod.yml
ENV_FILE=.env.prod
```

### 1. Build Production Images
```bash
docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE build --no-cache
# Or single service: docker-compose -f $COMPOSE_FILE build --no-cache backend
```

### 2. Start Production Services
```bash
docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d
docker-compose -f $COMPOSE_FILE ps
```

### 3. Run Migrations in Production
```bash
docker-compose -f $COMPOSE_FILE exec backend alembic upgrade head
```

### 4. Verify Health Checks
```bash
docker-compose -f $COMPOSE_FILE ps
curl http://localhost:${FASTAPI_PORT:-8000}/docs   # use port from .env.prod
docker-compose -f $COMPOSE_FILE exec db pg_isready -U postgres
```

### 5. View Logs
```bash
docker-compose -f $COMPOSE_FILE logs -f
docker-compose -f $COMPOSE_FILE logs -f backend
docker-compose -f $COMPOSE_FILE logs --tail=100 backend
```

---

## Maintenance Commands

Use `-f docker-compose.<env>.yml` for your environment (e.g. `docker-compose.prod.yml` for production).

### Database Backup
```bash
docker-compose -f docker-compose.prod.yml exec db pg_dump -U postgres laminar_database > backup_$(date +%Y%m%d_%H%M%S).sql
docker-compose -f docker-compose.prod.yml exec db pg_dump -U postgres -F c laminar_database > backup_$(date +%Y%m%d_%H%M%S).dump
```

### Database Restore
```bash
cat backup.sql | docker-compose -f docker-compose.prod.yml exec -T db psql -U postgres laminar_database
docker-compose -f docker-compose.prod.yml exec db pg_restore -U postgres -d laminar_database backup.dump
```

### Database Connection
```bash
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -d laminar_database
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -d laminar_database -c "SELECT version();"
```

### Clean Up
```bash
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml down -v
docker image prune -a
docker volume prune
```

### Update Application
```bash
git pull
docker-compose -f docker-compose.prod.yml --env-file .env.prod up --build -d
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## Troubleshooting

Use the same compose file as the stack you're debugging (e.g. `-f docker-compose.dev.yml`).

### Check Service Status
```bash
docker-compose -f docker-compose.dev.yml ps
docker-compose -f docker-compose.dev.yml logs backend
docker-compose -f docker-compose.dev.yml logs db
docker-compose -f docker-compose.dev.yml logs celery
```

### Database Connection Issues
```bash
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -c "SELECT 1;"
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -l
docker-compose -f docker-compose.dev.yml exec backend python -c "from app.database import engine; print('DB OK')"
```

### Reset Everything (Nuclear Option)
```bash
docker-compose -f docker-compose.dev.yml down -v
docker system prune -a --volumes
docker-compose -f docker-compose.dev.yml --env-file .env.dev up --build -d
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

### View Resource Usage
```bash
docker stats
docker system df
docker volume ls
```

### Enter Container Shell
```bash
docker-compose -f docker-compose.dev.yml exec backend /bin/bash
docker-compose -f docker-compose.dev.yml exec db /bin/sh
docker-compose -f docker-compose.dev.yml exec backend python -c "print('Hello')"
```

### Check Network Connectivity
```bash
docker network ls
# Dev project name is laminar_core_dev; network is laminar_core_dev_laminar_network_dev
docker network inspect laminar_core_dev_laminar_network_dev
```

---

## Quick Reference

Use explicit compose and env file for your environment (dev example below; for prod use `docker-compose.prod.yml` and `.env.prod`).

```bash
# Full deployment from scratch (dev)
docker-compose -f docker-compose.dev.yml --env-file .env.dev down -v
docker-compose -f docker-compose.dev.yml --env-file .env.dev up --build -d
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head

# Daily operations
docker-compose -f docker-compose.dev.yml --env-file .env.dev up -d
docker-compose -f docker-compose.dev.yml logs -f backend
docker-compose -f docker-compose.dev.yml restart backend
docker-compose -f docker-compose.dev.yml down

# Migrations
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
docker-compose -f docker-compose.dev.yml exec backend alembic current
docker-compose -f docker-compose.dev.yml exec backend alembic history

# Database
docker-compose -f docker-compose.dev.yml exec db psql -U postgres -d laminar_database
# Fix collation (uses COMPOSE_FILE=docker-compose.dev.yml by default; set for prod/uat if needed)
./backend/scripts/fix_collation.sh

# Maintenance
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml logs -f
docker stats
```

---

## Access Points

After deployment, access the application at:

- **API Documentation**: http://localhost:8000/docs
- **Database**: localhost:5432
- **Redis**: localhost:6379
- **Backend API**: http://localhost:8000

---

## Notes

- Always backup the database before running migrations in production
- Use `docker-compose ps` to verify all services are healthy before proceeding
- Check logs if services fail to start: `docker-compose logs <service_name>`
- The collation fix script runs automatically on fresh database initialization
- Keep your `SECRET_KEY` secure and never commit it to version control
