#!/bin/bash
set -e

# Script to fix collation version warning for existing databases
# Usage: ./fix-collation.sh

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD:-postgres}"

export PGPASSWORD="$DB_PASSWORD"

echo "Fixing collation version warnings..."

# Fix for postgres database
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres <<-EOSQL
    ALTER DATABASE postgres REFRESH COLLATION VERSION;
EOSQL

# Fix for application database
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d laminar_database <<-EOSQL
    ALTER DATABASE laminar_database REFRESH COLLATION VERSION;
EOSQL

echo "Collation versions refreshed successfully!"
