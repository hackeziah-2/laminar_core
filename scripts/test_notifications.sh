#!/usr/bin/env sh
# Run notification test suite and deployment smoke checks for dev, uat, or prod.
#
# Usage:
#   ./scripts/test_notifications.sh dev
#   ./scripts/test_notifications.sh uat
#   ./scripts/test_notifications.sh prod
#
# Requires: Docker Compose stack for the target environment already running.

set -eu

ENV_NAME="${1:-dev}"
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

case "$ENV_NAME" in
  dev)
    COMPOSE_FILE="docker-compose.dev.yml"
    BACKEND_CONTAINER="laminar_backend_dev"
    CELERY_CONTAINER="laminar_celery_dev"
    BEAT_CONTAINER="laminar_celery_beat_dev"
    NGINX_CONTAINER="laminar_nginx_dev"
    ;;
  uat)
    COMPOSE_FILE="docker-compose.uat.yml"
    BACKEND_CONTAINER="laminar_backend_uat"
    CELERY_CONTAINER="laminar_celery_uat"
    BEAT_CONTAINER="laminar_celery_beat_uat"
    NGINX_CONTAINER="laminar_nginx_uat"
    ;;
  prod)
    COMPOSE_FILE="docker-compose.prod.yml"
    BACKEND_CONTAINER="laminar_backend_prod"
    CELERY_CONTAINER="laminar_celery_prod"
    BEAT_CONTAINER="laminar_celery_beat_prod"
    NGINX_CONTAINER="laminar_nginx_prod"
    ;;
  *)
    echo "Unknown environment: $ENV_NAME (use dev, uat, or prod)" >&2
    exit 1
    ;;
esac

NOTIFICATION_TESTS="
tests/test_notification_repository.py
tests/test_notification_service.py
tests/test_notification_permissions.py
tests/test_notification_websocket.py
tests/test_notification_broker.py
tests/test_notifications_api.py
tests/test_advisory_notification_service.py
tests/test_atl_notification_events.py
tests/test_fleet_daily_update_notification_events.py
"

echo "=========================================="
echo " Notification tests — environment: $ENV_NAME"
echo "=========================================="

cd "$ROOT_DIR"

echo ""
echo "== 1) Container health =="
for name in "$BACKEND_CONTAINER" "$CELERY_CONTAINER" "$BEAT_CONTAINER" "$NGINX_CONTAINER"; do
  if docker ps --format '{{.Names}}' | grep -qx "$name"; then
    echo "  OK  $name"
  else
    echo "  MISSING  $name"
    echo "Start stack: docker compose -f $COMPOSE_FILE up -d"
    exit 1
  fi
done

echo ""
echo "== 2) Pytest notification suite =="
docker exec -w /app "$BACKEND_CONTAINER" \
  pytest $NOTIFICATION_TESTS --no-cov -q

echo ""
echo "== 3) Redis notification subscriber =="
if docker logs "$BACKEND_CONTAINER" 2>&1 | grep -q "notifications-ws.*subscriber connected"; then
  echo "  OK  subscriber connected (see backend logs)"
else
  echo "  WARN  subscriber connected log not found — restart backend if stack was updated recently"
  docker logs "$BACKEND_CONTAINER" 2>&1 | grep "notifications-ws" | tail -5 || true
fi

echo ""
echo "== 4) Nginx WebSocket route =="
if docker exec "$NGINX_CONTAINER" grep -q "notifications/ws" /etc/nginx/conf.d/default.conf 2>/dev/null; then
  echo "  OK  /api/v1/notifications/ws proxy configured"
else
  echo "  FAIL  WebSocket location missing in nginx config"
  exit 1
fi

echo ""
echo "== 5) Celery advisory notification task (smoke) =="
docker exec -w /app "$BACKEND_CONTAINER" \
  celery -A app.worker.celery_app call \
  app.tasks.advisory_notifications.send_advisory_remaining_30_days_notifications

sleep 2
docker logs "$CELERY_CONTAINER" --tail 15 2>&1 | grep -E "advisory|succeeded|notification" | tail -5 || true
docker logs "$BACKEND_CONTAINER" --tail 20 2>&1 | grep -E "notifications-ws|redis publish" | tail -5 || true

echo ""
echo "== 6) API health =="
docker exec "$BACKEND_CONTAINER" python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

echo ""
echo "=========================================="
echo " Notification tests completed for: $ENV_NAME"
echo "=========================================="
