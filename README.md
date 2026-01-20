Flight Management API 
This scaffold contains a modular FastAPI backend ready for PostgreSQL, Redis, and Celery.
Run locally with Docker Compose.

Quick start:
1. Copy `.env.example` to `.env` and adjust if needed.
2. docker compose up --build
3. API docs: http://localhost:8000/docs


## Alembic Migrations
Inside `backend/`:
- Initialize (if needed): `alembic init alembic`
- Run migrations: `alembic upgrade head`

The scaffold includes an initial migration in `backend/alembic/versions/`.

## Authentication
- Register: POST /api/v1/auth/register
- Token: POST /api/v1/auth/token (use OAuth2 password flow)
- Use `Authorization: Bearer <token>` to access protected endpoints.

## Testing

### Running Tests

#### Inside Docker (Recommended)
```bash
# Run all tests
docker-compose exec backend pytest

# Run with coverage report
docker-compose exec backend pytest --cov=app --cov-report=html

# Run specific test file
docker-compose exec backend pytest tests/test_aircraft.py

# Run specific test
docker-compose exec backend pytest tests/test_aircraft.py::test_list_aircraft_empty

# Verbose output
docker-compose exec backend pytest -v
```

#### Local Development (Outside Docker)
```bash
# Navigate to backend directory
cd backend

# Activate virtual environment (if using one)
# source venv/bin/activate  # Unix/Mac
# venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# View coverage report
# HTML report: open htmlcov/index.html in browser
```

### Test Coverage

Tests are configured to generate coverage reports:
- **Terminal**: Shows coverage summary and missing lines
- **HTML**: Detailed report in `htmlcov/index.html`
- **XML**: For CI/CD integration

### Test Structure

- `backend/tests/test_aircraft.py` - Aircraft endpoint tests
- `backend/tests/test_aircraft_technical_log.py` - Aircraft Technical Log tests
- `backend/tests/test_models.py` - SQLAlchemy model tests
- `backend/tests/test_auth.py` - Authentication tests
- `backend/tests/conftest.py` - Shared fixtures and configuration

For more details, see `backend/tests/README.md`.

<!-- docker-compose up --build        -->