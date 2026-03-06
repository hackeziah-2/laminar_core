#!/bin/bash
# Fix PostgreSQL collation version warning for existing databases
# Usage: ./scripts/fix_collation.sh

set -e

DB_NAME="${POSTGRES_DB:-laminar_database}"
DB_USER="${POSTGRES_USER:-postgres}"

echo "Fixing PostgreSQL collation version warnings..."

# Optional: explicit compose file (e.g. docker-compose.dev.yml) for unique project/network
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"

# Check if running in Docker or directly
if command -v docker-compose &> /dev/null && docker-compose -f "$COMPOSE_FILE" ps db &> /dev/null; then
    # Running in Docker environment
    echo "Detected Docker environment, using docker-compose -f $COMPOSE_FILE..."
    
    # Fix postgres database
    docker-compose -f "$COMPOSE_FILE" exec -T db psql -U "$DB_USER" -d template1 -c "
        UPDATE pg_database SET datcollversion = NULL WHERE datname = 'postgres';
        ALTER DATABASE postgres REFRESH COLLATION VERSION;
    " || echo "⚠ Could not fix 'postgres' database"
    
    # Fix application database
    docker-compose -f "$COMPOSE_FILE" exec -T db psql -U "$DB_USER" -d template1 -c "
        UPDATE pg_database SET datcollversion = NULL WHERE datname = '$DB_NAME';
        ALTER DATABASE $DB_NAME REFRESH COLLATION VERSION;
    " || echo "⚠ Could not fix '$DB_NAME' database"
    
else
    # Running directly with psql
    echo "Using direct psql connection..."
    
    DB_HOST="${DB_HOST:-localhost}"
    DB_PORT="${DB_PORT:-5432}"
    export PGPASSWORD="${POSTGRES_PASSWORD:-postgres}"
    
    # Fix postgres database
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d template1 -c "
        UPDATE pg_database SET datcollversion = NULL WHERE datname = 'postgres';
        ALTER DATABASE postgres REFRESH COLLATION VERSION;
    " || echo "⚠ Could not fix 'postgres' database"
    
    # Fix application database
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d template1 -c "
        UPDATE pg_database SET datcollversion = NULL WHERE datname = '$DB_NAME';
        ALTER DATABASE $DB_NAME REFRESH COLLATION VERSION;
    " || echo "⚠ Could not fix '$DB_NAME' database"
fi

echo "✓ Collation version fix completed!"
