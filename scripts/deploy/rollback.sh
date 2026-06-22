#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-}"
if [[ -z "${ENVIRONMENT}" ]]; then
  echo "Usage: ./scripts/deploy/rollback.sh <dev|prod>"
  exit 1
fi

if [[ "${ENVIRONMENT}" != "dev" && "${ENVIRONMENT}" != "prod" ]]; then
  echo "Environment must be dev or prod"
  exit 1
fi

COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
ENV_FILE=".env.${ENVIRONMENT}"
PREV_IMAGE_FILE=".deploy-state/${ENVIRONMENT}.prev_image"

if [[ ! -f "${PREV_IMAGE_FILE}" ]]; then
  echo "No previous image recorded for ${ENVIRONMENT}"
  exit 1
fi

APP_IMAGE="$(cat "${PREV_IMAGE_FILE}")"
export APP_IMAGE

echo "Rolling back ${ENVIRONMENT} to ${APP_IMAGE}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T backend alembic downgrade -1 || true
./scripts/deploy/health-check.sh "${ENVIRONMENT}"
echo "Rollback complete"
