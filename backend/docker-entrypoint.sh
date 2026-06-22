#!/bin/sh
set -e

# Ensure uploads directory exists and is writable by appuser.
mkdir -p /app/uploads
chown -R appuser:appuser /app/uploads

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Running database migrations with Alembic..."
  gosu appuser alembic upgrade head
fi

exec gosu appuser "$@"
