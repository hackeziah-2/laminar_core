Flight Management API 
This scaffold contains a modular FastAPI backend ready for PostgreSQL, Redis, and Celery.
Run locally with Docker Compose.

Quick start:
1. Copy `.env.example` to `.env` and adjust if needed.
2. docker compose up --build
3. API docs: http://localhost:8000/docs (interactive: [/docs](http://localhost:8000/docs#/))

---

## How to Deploy

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed
- Git (for cloning the repository)

### Step 1: Clone and enter the project
```bash
git clone <repository-url>
cd laminar_core
```

### Step 2: Environment variables (optional)
Create a `.env` file in the project root if you need to override defaults:
```bash
# Example .env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/laminar_database
SECRET_KEY=your-secret-key-change-in-production
DEBUG=False
```

### Step 3: Build and start services
```bash
# Build and run all services (db, redis, backend, celery)
docker-compose up --build -d

# Check that services are running
docker-compose ps
```

### Step 4: Run database migrations
```bash
# Apply all migrations (creates/updates tables)
docker-compose exec backend alembic upgrade head

# Optional: verify migration status
docker-compose exec backend alembic current
```

### Step 5: Verify deployment
- **API docs (interactive):** http://localhost:8000/docs#/  
- **Health:** Open the docs URL or `curl http://localhost:8000/docs`  
- **Logs:** `docker-compose logs -f backend`

### Quick deploy (one-shot)
```bash
docker-compose up -d --build && docker-compose exec backend alembic upgrade head
```

### Production notes
- Set a strong `SECRET_KEY` in `.env`.
- Use a managed PostgreSQL and Redis in production if possible.
- Run behind a reverse proxy (e.g. Nginx) with HTTPS.
- See **[DEPLOYMENT.md](DEPLOYMENT.md)** for production deployment, collation fix, and troubleshooting.

---

## Alembic Migrations
Inside `backend/`:
- Initialize (if needed): `alembic init alembic`
- Run migrations: `alembic upgrade head`

The scaffold includes an initial migration in `backend/alembic/versions/`.

**Alembic setup & Docker deployment (step by step):** See **[backend/README_DATABASE.md](backend/README_DATABASE.md)** for:
- **Alembic setup** – config, creating migrations, running migrations (local and Docker)
- **Docker run for deployment** – prerequisites, build, start, verify migrations, access API
- **Clean database** – reset to empty and regenerate tables for a fresh deployment

## Authentication
- Register: POST /api/v1/auth/register
- Token: POST /api/v1/auth/token (use OAuth2 password flow)
- Use `Authorization: Bearer <token>` to access protected endpoints.

## Aircraft Details – Engine ARC & Propeller ARC (Download & View)

On the **Aircraft Details** screen, for **Engine ARC** and **Propeller ARC** (when a file exists), show two actions as in the UI reference:

| Action    | Icon        | Behavior |
|----------|-------------|----------|
| **Download** | Down-arrow (blue) | Opens the file as a download (attachment). |
| **View**     | Eye (blue)        | Opens the file in the browser; use for **modal preview** (especially when the file is an image). |

### API usage

1. **Get aircraft details**  
   `GET /api/v1/aircraft/{aircraft_id}` returns (among others):
   - `engine_arc_download_url` – e.g. `/api/v1/aircraft/1/files/engine-arc`
   - `propeller_arc_download_url` – e.g. `/api/v1/aircraft/1/files/propeller-arc`
   - `engine_arc_is_image` / `propeller_arc_is_image` – `true` when the file is an image (use to show **View** and open in a modal).

2. **Download** (down-arrow button)  
   Use the download URL as-is (no query):  
   - Engine: `{baseUrl}{engine_arc_download_url}`  
   - Propeller: `{baseUrl}{propeller_arc_download_url}`  
   Response is `Content-Disposition: attachment` so the file downloads.

3. **View** (eye button, e.g. modal)  
   Same URL with `?disposition=inline`:  
   - Engine: `{baseUrl}{engine_arc_download_url}?disposition=inline`  
   - Propeller: `{baseUrl}{propeller_arc_download_url}?disposition=inline`  
   Response is `Content-Disposition: inline` so the browser can display it. For images, use this URL as the `src` of an `<img>` inside your modal (or open in a new tab/iframe).

Only show **Download** and **View** when the corresponding `*_download_url` is present (i.e. the aircraft has that file). Optionally show **View** only when `*_is_image` is true if you want the modal only for images.

---

## Document On Board

Documents-on-board can be accessed globally or scoped to a specific aircraft.

### Global endpoints (`/api/v1/documents-on-board/`)
- **List (paginated):** GET `/api/v1/documents-on-board/paged?limit=10&page=1&aircraft_id=&search=&status=&sort=`
- **Get by ID:** GET `/api/v1/documents-on-board/{document_id}`
- **Create:** POST `/api/v1/documents-on-board/` (form: `json_data`, optional `upload_file`)
- **Update:** PUT `/api/v1/documents-on-board/{document_id}` (form: `json_data`, optional `upload_file`)
- **Delete:** DELETE `/api/v1/documents-on-board/{document_id}`

### Document-on-board aircraft (scoped by aircraft)
All operations are scoped to a specific aircraft. Use these when working with documents for one aircraft.

- **List (paginated):** GET `/api/v1/aircraft/{aircraft_id}/documents-on-board/paged?limit=10&page=1&search=&status=&sort=`
- **Get by ID:** GET `/api/v1/aircraft/{aircraft_id}/documents-on-board/{document_id}`
- **Create:** POST `/api/v1/aircraft/{aircraft_id}/documents-on-board/` (form: `json_data`, optional `upload_file`; `aircraft_id` in path overrides body)
- **Update:** PUT `/api/v1/aircraft/{aircraft_id}/documents-on-board/{document_id}` (form: `json_data`, optional `upload_file`)
- **Delete:** DELETE `/api/v1/aircraft/{aircraft_id}/documents-on-board/{document_id}`

Example (aircraft ID 5):
- List: `GET http://localhost:8000/api/v1/aircraft/5/documents-on-board/paged?limit=10&page=1`
- Get: `GET http://localhost:8000/api/v1/aircraft/5/documents-on-board/3`
- Create: `POST http://localhost:8000/api/v1/aircraft/5/documents-on-board/`
- Update: `PUT http://localhost:8000/api/v1/aircraft/5/documents-on-board/3`
- Delete: `DELETE http://localhost:8000/api/v1/aircraft/5/documents-on-board/3`

## AD Monitoring

AD monitoring is scoped by aircraft; work-order AD monitoring has `ad_monitoring_fk` (FK to AD) and can be used globally or scoped under aircraft → ad_monitoring. Interactive API: [http://localhost:8000/docs#/](http://localhost:8000/docs#/).

### Aircraft-scoped AD monitoring – `api/v1/aircraft/{aircraft_fk}/ad_monitoring/` (CRUD)

| Method        | Path |
|---------------|------|
| GET (paged)   | `GET /api/v1/aircraft/{aircraft_fk}/ad_monitoring/paged` |
| GET one       | `GET /api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_id}` |
| POST          | `POST /api/v1/aircraft/{aircraft_fk}/ad_monitoring/` |
| PUT           | `PUT /api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_id}` |
| DELETE        | `DELETE /api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_id}` |

### Work-order AD monitoring (global) – `api/v1/work-order-ad-monitoring/` (CRUD)

Body/query includes `ad_monitoring_fk`. Filter list by `?ad_monitoring_fk=`.

| Method        | Path |
|---------------|------|
| GET (paged)   | `GET /api/v1/work-order-ad-monitoring/paged?ad_monitoring_fk=` |
| GET one       | `GET /api/v1/work-order-ad-monitoring/{work_order_id}` |
| POST          | `POST /api/v1/work-order-ad-monitoring/` |
| PUT           | `PUT /api/v1/work-order-ad-monitoring/{work_order_id}` |
| DELETE        | `DELETE /api/v1/work-order-ad-monitoring/{work_order_id}` |

### Work-order AD monitoring (aircraft-scoped) – `api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/` (CRUD)

| Method        | Path |
|---------------|------|
| GET (paged)   | `GET /api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/paged` |
| GET one       | `GET /api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/{work_order_id}` |
| POST          | `POST /api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/` |
| PUT           | `PUT /api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/{work_order_id}` |
| DELETE        | `DELETE /api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/{work_order_id}` |

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