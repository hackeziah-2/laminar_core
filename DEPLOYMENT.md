# Laminar Core - Deployment Guide

Complete deployment commands for the Laminar Core application.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed
- Git (for cloning the repository)
- Environment variables configured (optional)

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
docker-compose down -v
```

### Step 4: Build and start all services
```bash
docker-compose up --build -d
```

### Step 5: Wait for services to be healthy (optional check)
```bash
docker-compose ps
```

### Step 6: Run database migrations
```bash
docker-compose exec backend alembic upgrade head
```

### Step 7: Verify deployment
```bash
# Check migration status (optional)
docker-compose exec backend alembic current

# Open API docs in browser
# http://localhost:8000/docs

# Or check with curl
curl http://localhost:8000/docs
```

### One-line deployment (all steps)
```bash
docker-compose down -v && docker-compose up --build -d && docker-compose exec backend alembic upgrade head
```

---

## Initial Setup

### 1. Clone and Navigate
```bash
cd /Users/kevinpaullamadrid/Desktop/Project/laminar_core
```

### 2. Set Environment Variables (Optional)
Create a `.env` file in the root directory if needed:
```bash
# Example .env file
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/laminar_database
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key-change-in-production
DEBUG=False
```

---

## Development Deployment

### Fresh Deployment (Recommended for first time)

```bash
# 1. Stop and remove all containers, volumes, and networks
docker-compose down -v

# 2. Build and start all services
docker-compose up --build -d

# 3. Wait for services to be healthy
docker-compose ps

# 4. Run database migrations
docker-compose exec backend alembic upgrade head

# 5. Check logs to verify everything is running
docker-compose logs -f backend
```

### Quick Start (if volumes already exist)

```bash
# Start all services
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head
```

---

## Database Setup

### Create Fresh Database with Collation Fix

```bash
# Stop and remove database volume
docker-compose down -v db

# Start database (collation fix runs automatically on init)
docker-compose up -d db

# Wait for database to be ready
docker-compose exec db pg_isready -U postgres

# Create application database (if not auto-created)
docker-compose exec db psql -U postgres -c "CREATE DATABASE laminar_database;"
```

### Fix Collation Version (if warning appears)

```bash
# Option 1: Run the fix script
./backend/scripts/fix_collation.sh

# Option 2: Manual fix
docker-compose exec db psql -U postgres -d template1 -c "UPDATE pg_database SET datcollversion = NULL WHERE datname = 'postgres'; ALTER DATABASE postgres REFRESH COLLATION VERSION;"
docker-compose exec db psql -U postgres -d template1 -c "UPDATE pg_database SET datcollversion = NULL WHERE datname = 'laminar_database'; ALTER DATABASE laminar_database REFRESH COLLATION VERSION;"
```

---

## Running Migrations

### Check Migration Status
```bash
docker-compose exec backend alembic current
```

### Run All Migrations
```bash
docker-compose exec backend alembic upgrade head
```

### Create New Migration
```bash
docker-compose exec backend alembic revision --autogenerate -m "migration_description"
```

### Rollback Migration
```bash
# Rollback one migration
docker-compose exec backend alembic downgrade -1

# Rollback to specific revision
docker-compose exec backend alembic downgrade <revision_id>
```

### Check Migration History
```bash
docker-compose exec backend alembic history
```

---

## Starting Services

### Start All Services
```bash
docker-compose up -d
```

### Start Specific Service
```bash
# Start only database
docker-compose up -d db

# Start only backend
docker-compose up -d backend

# Start only celery
docker-compose up -d celery
```

### Stop Services
```bash
# Stop all services
docker-compose stop

# Stop specific service
docker-compose stop backend
```

### Restart Services
```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend
```

---

## Collation Fix

### Automatic Fix (on fresh database)
The collation fix runs automatically when creating a new database volume. If you need to recreate:
```bash
docker-compose down -v db
docker-compose up -d db
```

### Manual Fix (for existing databases)
```bash
# Using the fix script
./backend/scripts/fix_collation.sh

# Or manually
docker-compose exec db psql -U postgres -d template1 << EOF
UPDATE pg_database SET datcollversion = NULL WHERE datname = 'postgres';
ALTER DATABASE postgres REFRESH COLLATION VERSION;
UPDATE pg_database SET datcollversion = NULL WHERE datname = 'laminar_database';
ALTER DATABASE laminar_database REFRESH COLLATION VERSION;
EOF
```

---

## Production Deployment

### 1. Build Production Images
```bash
# Build without cache
docker-compose build --no-cache

# Build specific service
docker-compose build --no-cache backend
```

### 2. Start Production Services
```bash
# Start in detached mode
docker-compose up -d

# Verify all services are running
docker-compose ps
```

### 3. Run Migrations in Production
```bash
docker-compose exec backend alembic upgrade head
```

### 4. Verify Health Checks
```bash
# Check service health
docker-compose ps

# Check backend health
curl http://localhost:8000/docs

# Check database health
docker-compose exec db pg_isready -U postgres
```

### 5. View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

---

## Maintenance Commands

### Database Backup
```bash
# Backup database
docker-compose exec db pg_dump -U postgres laminar_database > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup with custom format
docker-compose exec db pg_dump -U postgres -F c laminar_database > backup_$(date +%Y%m%d_%H%M%S).dump
```

### Database Restore
```bash
# Restore from SQL file
cat backup.sql | docker-compose exec -T db psql -U postgres laminar_database

# Restore from custom format
docker-compose exec db pg_restore -U postgres -d laminar_database backup.dump
```

### Database Connection
```bash
# Connect to database
docker-compose exec db psql -U postgres -d laminar_database

# Execute SQL command
docker-compose exec db psql -U postgres -d laminar_database -c "SELECT version();"
```

### Clean Up
```bash
# Stop and remove containers
docker-compose down

# Stop and remove containers, volumes, and networks
docker-compose down -v

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune
```

### Update Application
```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up --build -d

# Run migrations if needed
docker-compose exec backend alembic upgrade head
```

---

## Troubleshooting

### Check Service Status
```bash
# View all services status
docker-compose ps

# View logs
docker-compose logs backend
docker-compose logs db
docker-compose logs celery
```

### Database Connection Issues
```bash
# Test database connection
docker-compose exec db psql -U postgres -c "SELECT 1;"

# Check database exists
docker-compose exec db psql -U postgres -l

# Check connection from backend
docker-compose exec backend python -c "from app.database import engine; print('DB OK')"
```

### Reset Everything (Nuclear Option)
```bash
# Stop everything
docker-compose down -v

# Remove all containers, images, and volumes
docker system prune -a --volumes

# Start fresh
docker-compose up --build -d
docker-compose exec backend alembic upgrade head
```

### View Resource Usage
```bash
# Container stats
docker stats

# Disk usage
docker system df

# Volume usage
docker volume ls
```

### Enter Container Shell
```bash
# Backend container
docker-compose exec backend /bin/bash

# Database container
docker-compose exec db /bin/sh

# Run Python commands in backend
docker-compose exec backend python -c "print('Hello')"
```

### Check Network Connectivity
```bash
# List networks
docker network ls

# Inspect network
docker network inspect laminar_core_laminar_network
```

---

## Quick Reference

```bash
# Full deployment from scratch
docker-compose down -v
docker-compose up --build -d
docker-compose exec backend alembic upgrade head

# Daily operations
docker-compose up -d                    # Start services
docker-compose logs -f backend         # View logs
docker-compose restart backend         # Restart service
docker-compose down                    # Stop services

# Migrations
docker-compose exec backend alembic upgrade head    # Run migrations
docker-compose exec backend alembic current        # Check status
docker-compose exec backend alembic history        # View history

# Database
docker-compose exec db psql -U postgres -d laminar_database    # Connect to DB
./backend/scripts/fix_collation.sh                              # Fix collation

# Maintenance
docker-compose down -v           # Clean everything
docker-compose logs -f           # View all logs
docker stats                     # Resource usage
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
