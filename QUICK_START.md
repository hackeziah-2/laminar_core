# Quick Start Commands

## 🚀 Start the Application

### First Time Setup (Fresh Start)
```bash
# Stop and remove everything (clean slate)
docker-compose down -v

# Build and start all services
docker-compose up --build -d

# Wait a few seconds for services to be ready, then run migrations
docker-compose exec backend alembic upgrade head

# Check logs
docker-compose logs -f backend
```

### Regular Start (Existing Setup)
```bash
# Start all services
docker-compose up -d

# Run migrations (if needed)
docker-compose exec backend alembic upgrade head
```

### Quick Start (Everything in One)
```bash
docker-compose up -d && docker-compose exec backend alembic upgrade head
```

---

## 📊 Check Status

```bash
# Check all services status
docker-compose ps

# View logs for all services
docker-compose logs -f

# View backend logs only
docker-compose logs -f backend

# Check if backend is healthy
curl http://localhost:8000/docs
```

---

## 🛑 Stop the Application

```bash
# Stop all services (keeps data)
docker-compose stop

# Stop and remove containers (keeps volumes/data)
docker-compose down

# Stop and remove everything including data
docker-compose down -v
```

---

## 🔄 Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend
docker-compose restart db
docker-compose restart celery
```

---

## 📝 Common Commands

### View Logs
```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Database Commands
```bash
# Connect to database
docker-compose exec db psql -U postgres -d laminar_database

# Run migrations
docker-compose exec backend alembic upgrade head

# Check migration status
docker-compose exec backend alembic current
```

### Access Points
- **API Docs**: http://localhost:8000/docs
- **API**: http://localhost:8000
- **Database**: localhost:5432
- **Redis**: localhost:6379

---

## 🧪 Running Tests

### Quick Test Commands

```bash
# Run all tests
docker-compose exec backend pytest

# Run with coverage
docker-compose exec backend pytest --cov=app --cov-report=html

# Run specific test file
docker-compose exec backend pytest tests/test_aircraft.py

# Run specific test
docker-compose exec backend pytest tests/test_aircraft.py::test_list_aircraft_empty

# Verbose output
docker-compose exec backend pytest -v

# Run tests matching a pattern
docker-compose exec backend pytest -k "aircraft" -v
```

### Test Coverage Reports

```bash
# Generate HTML coverage report
docker-compose exec backend pytest --cov=app --cov-report=html

# View coverage report (after running tests)
# The HTML report is generated in backend/htmlcov/index.html
# You can access it via: docker-compose exec backend ls htmlcov/

# Generate terminal coverage summary
docker-compose exec backend pytest --cov=app --cov-report=term-missing
```

### Local Testing (Without Docker)

If you prefer to run tests locally:

```bash
# Navigate to backend
cd backend

# Install/update dependencies
pip install -r requirements.txt

# Run tests
pytest

# With coverage
pytest --cov=app --cov-report=html
```

### Test Types

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test API endpoints with test database
- **Model Tests**: Test SQLAlchemy models and relationships

All tests use an in-memory SQLite database by default, isolated from the production database.

---

## 🐛 Troubleshooting

### If services fail to start
```bash
# Check logs
docker-compose logs backend
docker-compose logs db

# Rebuild and restart
docker-compose up --build -d

# Check service health
docker-compose ps
```

### If migrations fail
```bash
# Check current migration status
docker-compose exec backend alembic current

# View migration history
docker-compose exec backend alembic history

# Force upgrade
docker-compose exec backend alembic upgrade head
```

### Complete Reset (Nuclear Option)
```bash
# Stop everything and remove all data
docker-compose down -v

# Start fresh
docker-compose up --build -d
docker-compose exec backend alembic upgrade head
```
