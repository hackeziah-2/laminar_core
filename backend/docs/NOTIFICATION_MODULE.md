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

```bash
cd backend
pytest tests/test_notification_repository.py \
       tests/test_notification_service.py \
       tests/test_notifications_api.py \
       tests/test_notification_permissions.py \
       tests/test_notification_websocket.py -v
```

Or all tests:

```bash
pytest tests -v
```

## Security

- All REST endpoints require `get_current_active_account` (JWT).
- Queries are always scoped to `recipient_account_id = current_account.id`.
- Cross-user access returns `404 Not Found` (no information leakage).

## Future Channels

The service layer is the integration point for email/SMS/push. Add a strategy interface under `services/` without changing repository contracts or API shapes.
