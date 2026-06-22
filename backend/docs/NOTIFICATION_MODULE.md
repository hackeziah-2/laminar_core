# Notification Module

Enterprise in-app notification backend for the Laminar React + FastAPI stack.

## Architecture Overview

```text
Business Module (e.g. ATL)
        │
        ▼
events/notification_events.publish_notification_event()
        │
        ▼
services/notification_service.NotificationService
        │
        ├── repository/notification.py  (PostgreSQL persistence)
        └── websocket/notification_manager.py  (realtime push)
        │
        ▼
React Notification Bell (REST + WebSocket)
```

### Responsibilities

| Layer | Responsibility |
|-------|----------------|
| `api/v1/notification.py` | JWT-protected REST + WebSocket endpoints |
| `services/notification_service.py` | Business rules, response mapping, realtime orchestration |
| `repository/notification.py` | SQLAlchemy queries, pagination, archive semantics |
| `events/notification_events.py` | Decoupled entry point for other modules |
| `websocket/notification_manager.py` | Per-user connection registry and push delivery |
| `models/notification.py` | ORM model and status transitions |

## Database

Table: `notifications`

- `uuid` — public identifier (`PublicUuidMixin`); unique, auto-generated
- `recipient_account_id` → `account_information.id` (authenticated users)
- `sender_account_id` → `account_information.id` (nullable)
- `status`: `UNREAD`, `READ`, `ARCHIVED`
- `metadata` JSONB for extensible payloads
- Composite index: `(recipient_account_id, status, created_at)`

Archived rows are excluded from list/count queries. Clear-all sets `status = ARCHIVED` and `archived_at = ph_now()` — no hard deletes.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/notifications?status=all\|unread\|read&page=1&limit=20` | Paginated list |
| GET | `/api/v1/notifications/unread-count` | Bell badge count |
| PATCH | `/api/v1/notifications/{id}/read` | Mark one as read |
| PATCH | `/api/v1/notifications/read-all` | Mark all as read |
| PATCH | `/api/v1/notifications/{id}/archive` | Archive one |
| PATCH | `/api/v1/notifications/clear-all` | Soft-archive all |
| WS | `/api/v1/notifications/ws?token=<JWT>` | Realtime events |

### Example list response

```json
{
  "items": [
    {
      "id": 1,
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "sender_initials": "MQ",
      "title": "Maintenance reminder",
      "message": "Aircraft N12345 — inspection window opens in 48 hours.",
      "module_name": "Maintenance",
      "type": "REMINDER",
      "severity": "WARNING",
      "status": "UNREAD",
      "reference_id": 123,
      "reference_type": "AIRCRAFT",
      "created_at": "2026-06-16T09:30:00+08:00",
      "time_ago": "2 min ago"
    }
  ],
  "page": 1,
  "limit": 20,
  "total": 1,
  "total_pages": 1,
  "unread_count": 1
}
```

### WebSocket events

```json
{
  "event": "new_notification",
  "data": {
    "id": 123,
    "title": "Maintenance reminder",
    "message": "Aircraft inspection due.",
    "unread_count": 3
  }
}
```

```json
{
  "event": "unread_count_updated",
  "data": { "unread_count": 0 }
}
```

## Integration Example (ATL Approval)

```python
from app.events.notification_events import publish_notification_event
from app.enums.notification import NotificationType, NotificationSeverity

await publish_notification_event(
    session,
    recipient_account_id=manager.id,
    sender_account=current_user,
    title="ATL Submitted",
    message=f"ATL #{atl.sequence_no} is awaiting approval.",
    module_name="ATL",
    notification_type=NotificationType.APPROVAL,
    severity=NotificationSeverity.INFO,
    reference_id=atl.id,
    reference_type="ATL",
)
```

Frontend navigation: use `module_name`, `reference_type`, and `reference_id` from the notification payload.

## Migrations

```bash
cd backend
alembic upgrade head
```

Revision: `o0p1q2r3s4t5_add_notifications_table.py`, `p1q2r3s4t5u6_add_public_uuid_to_notifications.py`

### Reusing `PublicUuidMixin` on new models

```python
from app.database import Base, TimestampMixin, PublicUuidMixin

class MyNewModel(Base, TimestampMixin, PublicUuidMixin):
    __tablename__ = "my_new_models"
    id = Column(Integer, primary_key=True, index=True)
    # uuid column is inherited from PublicUuidMixin
```

## Run Application

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Run Tests

### Local / CI (pytest)

```bash
cd backend
pytest tests/test_notification_repository.py \
       tests/test_notification_service.py \
       tests/test_notifications_api.py \
       tests/test_notification_permissions.py \
       tests/test_notification_websocket.py \
       tests/test_notification_broker.py \
       tests/test_advisory_notification_service.py \
       tests/test_atl_notification_events.py \
       tests/test_fleet_daily_update_notification_events.py -v
```

Or all tests:

```bash
pytest tests -v
```

### Per environment (Docker)

From the repo root, with the target stack already running:

```bash
./scripts/test_notifications.sh dev
./scripts/test_notifications.sh uat
./scripts/test_notifications.sh prod
```

Each run:

1. Confirms backend, celery, celery-beat, and nginx containers are up
2. Runs the full notification pytest suite inside the backend container
3. Checks nginx WebSocket proxy config and Redis subscriber logs
4. Smoke-triggers the advisory Celery task and hits `/api/v1/health`

Quick WebSocket / Celery smoke only (override containers for uat/prod):

```bash
BACKEND_CONTAINER=laminar_backend_uat CELERY_CONTAINER=laminar_celery_uat \
  sh backend/scripts/verify_notification_ws.sh
```

## Security

- All REST endpoints require `get_current_active_account` (JWT).
- Queries are always scoped to `recipient_account_id = current_account.id`.
- Cross-user access returns `404 Not Found` (no information leakage).

## Production WebSocket (HTTPS domains)

Realtime notifications require a working WebSocket upgrade path end-to-end:

```text
Browser  →  OpenResty (fleet / api-fleet)  →  docker nginx (:8082)  →  gunicorn workers
```

### Symptom

- REST works (`GET /api/v1/notifications/unread-count` returns 401/200).
- WebSocket on `wss://fleet.laminaraviationapps.com/api/v1/notifications/ws` returns **HTTP 404**.
- WebSocket on `wss://api-fleet.laminaraviationapps.com/api/v1/notifications/ws` returns **HTTP 403** with an invalid token (route exists).

The prod frontend is served from `fleet.laminaraviationapps.com` and builds the WebSocket URL from the same origin unless `VITE_WS_URL` is set.

### Fix (choose one)

**Option A — OpenResty on fleet (no frontend rebuild)**

Add the block in `nginx/openresty-fleet-ws.example.conf` to the OpenResty vhost for `fleet.laminaraviationapps.com`, then reload OpenResty. Upstream port must match `NGINX_PORT` in `.env.prod` (default **8082**).

**Option B — Frontend `VITE_WS_URL`**

In **laminaraviationapp** `.env.prod`:

```env
VITE_APP_URL=https://fleet.laminaraviationapps.com
VITE_API_URL=/api/v1/
VITE_WS_URL=wss://api-fleet.laminaraviationapps.com/api/v1
```

Rebuild and redeploy the frontend. See `docs/frontend-env-prod.example`.

### Verify

```bash
chmod +x scripts/verify_prod_notification_ws.sh
./scripts/verify_prod_notification_ws.sh

# Docker stack (on the server)
./scripts/test_notifications.sh prod
```

After a successful fix, `fleet` and `api-fleet` WebSocket smoke tests should return **403** (not 404) when called without a valid JWT.

## Future Channels

The service layer is the integration point for email/SMS/push. Add a strategy interface under `services/` without changing repository contracts or API shapes.
