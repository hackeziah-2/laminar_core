# Testing Guide

This directory contains unit tests for the Laminar Core application.

## Setup

Install test dependencies (already included in requirements.txt):
```bash
pip install -r requirements.txt
```

## Running Tests

### Inside Docker (Recommended)

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

# Run only unit tests (skip integration)
docker-compose exec backend pytest -m "not integration"

# Stop on first failure
docker-compose exec backend pytest -x

# Run with more detailed output
docker-compose exec backend pytest -vv
```

### Local Development (Outside Docker)

```bash
# Navigate to backend directory
cd backend

# Activate virtual environment (if using one)
# source venv/bin/activate  # Unix/Mac
# venv\Scripts\activate     # Windows

# Run all tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_aircraft.py

# Run specific test
pytest tests/test_aircraft.py::test_list_aircraft_empty

# Run tests with verbose output
pytest -v

# Run only unit tests (skip integration)
pytest -m "not integration"
```

## Test Structure

- `conftest.py` - Shared fixtures and test configuration
- `test_aircraft.py` - Aircraft endpoint tests
- `test_aircraft_technical_log.py` - Aircraft Technical Log endpoint tests
- `test_models.py` - SQLAlchemy model tests
- `test_auth.py` - Authentication endpoint tests

## Test Database

Tests use an in-memory SQLite database by default (configured in `conftest.py`).
This ensures:
- Tests are isolated and don't affect production data
- Tests run quickly with no external dependencies
- Each test gets a fresh database state

For integration tests with PostgreSQL, set the `TEST_DATABASE_URL` environment variable:
```bash
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db"
pytest
```

## Writing New Tests

1. Create test files following the naming pattern `test_*.py`
2. Use the provided fixtures from `conftest.py`:
   - `client` - FastAPI test client
   - `db_session` - Database session
   - `test_aircraft_data` - Sample aircraft data
   - `test_aircraft_technical_log_data` - Sample ATL data

3. Example test:
```python
@pytest.mark.asyncio
async def test_my_endpoint(client: AsyncClient):
    response = client.get("/api/v1/my-endpoint")
    assert response.status_code == 200
```

## Coverage Reports

### Generate Coverage Reports

```bash
# Terminal output (shows missing lines)
docker-compose exec backend pytest --cov=app --cov-report=term-missing

# HTML report (detailed view)
docker-compose exec backend pytest --cov=app --cov-report=html

# XML report (for CI/CD)
docker-compose exec backend pytest --cov=app --cov-report=xml

# All formats
docker-compose exec backend pytest --cov=app --cov-report=term-missing --cov-report=html --cov-report=xml
```

### Viewing Coverage Reports

- **Terminal**: Coverage summary shown after test run
- **HTML**: Generated in `backend/htmlcov/index.html`
  - To view: Copy the file from container or open locally if running tests outside Docker
- **XML**: Generated in `backend/coverage.xml` (useful for CI/CD tools like Jenkins, GitLab CI)

### Coverage Configuration

Coverage settings are configured in `backend/pytest.ini`:
- Minimum coverage threshold: 0% (configurable)
- Excludes: Test files, migrations, and configuration files
