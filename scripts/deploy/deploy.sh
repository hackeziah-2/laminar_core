#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-}"
APP_IMAGE="${2:-}"

if [[ -z "${ENVIRONMENT}" || -z "${APP_IMAGE}" ]]; then
  echo "Usage: ./scripts/deploy/deploy.sh <dev|prod> <app-image>"
  exit 1
fi

if [[ "${ENVIRONMENT}" != "dev" && "${ENVIRONMENT}" != "prod" ]]; then
  echo "Environment must be dev or prod"
  exit 1
fi

COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
ENV_FILE=".env.${ENVIRONMENT}"
DEPLOY_STATE_DIR=".deploy-state"
mkdir -p "${DEPLOY_STATE_DIR}"

if [[ -f "${DEPLOY_STATE_DIR}/${ENVIRONMENT}.last_image" ]]; then
  cp "${DEPLOY_STATE_DIR}/${ENVIRONMENT}.last_image" "${DEPLOY_STATE_DIR}/${ENVIRONMENT}.prev_image"
fi
echo "${APP_IMAGE}" > "${DEPLOY_STATE_DIR}/${ENVIRONMENT}.last_image"

export APP_IMAGE

echo "Pulling image: ${APP_IMAGE}"
docker pull "${APP_IMAGE}"

echo "Running compose update for ${ENVIRONMENT}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d

echo "Running migrations"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T backend alembic upgrade head

echo "Validating health checks"
./scripts/deploy/health-check.sh "${ENVIRONMENT}"

echo "Deployment succeeded for ${ENVIRONMENT}"
