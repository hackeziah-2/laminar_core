#!/bin/sh
set -e

# Ensure uploads directory exists and is writable by appuser (fixes file upload in Docker)
mkdir -p /app/uploads
chown -R appuser:appuser /app/uploads

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Running database migrations..."
  exec gosu appuser sh -c 'alembic upgrade head && exec "$@"' _ "$@"
else
  exec gosu appuser sh -c 'exec "$@"' _ "$@"
fi
