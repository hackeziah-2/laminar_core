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


<!-- docker-compose up --build        -->