#!/usr/bin/env sh
# Verify notification WebSocket + Redis subscriber on a running Docker deployment.
# Usage: BACKEND_CONTAINER=laminar_backend_uat CELERY_CONTAINER=laminar_celery_uat sh backend/scripts/verify_notification_ws.sh
set -eu

BACKEND_CONTAINER="${BACKEND_CONTAINER:-laminar_backend_dev}"
CELERY_CONTAINER="${CELERY_CONTAINER:-laminar_celery_dev}"

echo "== Backend subscriber logs =="
docker logs "$BACKEND_CONTAINER" 2>&1 | grep -E "notifications-ws|subscriber" | tail -20 || true

echo ""
echo "== Trigger advisory notification task =="
docker exec -w /app "$BACKEND_CONTAINER" \
  celery -A app.worker.celery_app call \
  app.tasks.advisory_notifications.send_advisory_remaining_30_days_notifications

echo ""
echo "== Post-trigger backend logs =="
docker logs "$BACKEND_CONTAINER" --tail 40 2>&1 | grep -E "notifications-ws|redis publish" || true

echo ""
echo "== Celery worker logs =="
docker logs "$CELERY_CONTAINER" --tail 20 2>&1 | grep -E "advisory|notification" || true
