#!/bin/bash
set -e

# Fix collation version warning in PostgreSQL 15+
# This script resets and refreshes collation versions for all databases
# to prevent the warning: "database has no actual collation version,
# but a version was recorded"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname template1 <<-EOSQL
    -- Reset collation version for postgres database (if it exists)
    DO \$\$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'postgres') THEN
            UPDATE pg_database SET datcollversion = NULL WHERE datname = 'postgres';
            ALTER DATABASE postgres REFRESH COLLATION VERSION;
            RAISE NOTICE 'Fixed collation version for postgres database';
        END IF;
    END
    \$\$;
    
    -- Reset and refresh collation version for the application database
    DO \$\$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_database WHERE datname = '$POSTGRES_DB') THEN
            UPDATE pg_database SET datcollversion = NULL WHERE datname = '$POSTGRES_DB';
            ALTER DATABASE "$POSTGRES_DB" REFRESH COLLATION VERSION;
            RAISE NOTICE 'Fixed collation version for $POSTGRES_DB database';
        END IF;
    END
    \$\$;
EOSQL
