#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-}"
if [[ -z "${ENVIRONMENT}" ]]; then
  echo "Usage: ./scripts/deploy/health-check.sh <dev|prod|local>"
  exit 1
fi

if [[ "${ENVIRONMENT}" == "local" ]]; then
  ENV_FILE=".env.local"
else
  ENV_FILE=".env.${ENVIRONMENT}"
fi

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

FASTAPI_PORT="${FASTAPI_PORT:-8000}"
HEALTH_URL="http://127.0.0.1:${FASTAPI_PORT}/api/v1/health/ready"

echo "Checking ${HEALTH_URL}"
for attempt in {1..30}; do
  if curl -fsS "${HEALTH_URL}" >/dev/null; then
    echo "Health check passed"
    exit 0
  fi
  sleep 2
done

echo "Health check failed after retries"
exit 1
