#!/bin/sh
set -e

# Ensure uploads directory exists and is writable by appuser (fixes file upload in Docker)
mkdir -p /app/uploads
chown -R appuser:appuser /app/uploads

echo "Running database migrations..."
exec gosu appuser sh -c 'alembic upgrade head && exec "$@"' _ "$@"
