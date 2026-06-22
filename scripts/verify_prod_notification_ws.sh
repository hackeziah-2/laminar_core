#!/usr/bin/env sh
# Smoke-test notification WebSocket routing on public prod endpoints.
#
# Usage:
#   ./scripts/verify_prod_notification_ws.sh
#
# Expected:
#   fleet.laminaraviationapps.com  -> 404 until OpenResty WS block is applied
#   api-fleet.laminaraviationapps.com -> 403 (route exists; invalid test token)

set -eu

WS_KEY="dGhlIHNhbXBsZSBub25jZQ=="
WS_HEADERS=(
  -H "Connection: Upgrade"
  -H "Upgrade: websocket"
  -H "Sec-WebSocket-Version: 13"
  -H "Sec-WebSocket-Key: ${WS_KEY}"
)

check_url() {
  label="$1"
  url="$2"
  code=$(curl -sS -o /dev/null -w "%{http_code}" --http1.1 --max-time 8 \
    "${WS_HEADERS[@]}" "$url" 2>/dev/null || echo "000")
  echo "  ${label}: HTTP ${code}"
  case "$code" in
    403|101) echo "       OK — WebSocket route reaches backend (403 = bad/missing token)" ;;
    404) echo "       FAIL — WebSocket upgrade not proxied (add nginx/openresty-fleet-ws.example.conf)" ;;
    000) echo "       FAIL — request timed out or connection refused" ;;
    *) echo "       WARN — unexpected status; inspect response headers manually" ;;
  esac
}

echo "== Notification WebSocket prod smoke test =="
echo ""
check_url "fleet (same-origin frontend)" \
  "https://fleet.laminaraviationapps.com/api/v1/notifications/ws?token=smoke-test"
check_url "api-fleet (dedicated API host)" \
  "https://api-fleet.laminaraviationapps.com/api/v1/notifications/ws?token=smoke-test"
echo ""
echo "REST health:"
for base in \
  "https://fleet.laminaraviationapps.com/api/v1/health" \
  "https://api-fleet.laminaraviationapps.com/api/v1/health"
do
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 8 "$base" 2>/dev/null || echo "000")
  echo "  ${base}: HTTP ${code}"
done
echo ""
echo "Fix fleet 404: add nginx/openresty-fleet-ws.example.conf to the fleet OpenResty vhost, reload."
echo "Alternative: set VITE_WS_URL=wss://api-fleet.laminaraviationapps.com/api/v1 in laminaraviationapp .env.prod and rebuild."
