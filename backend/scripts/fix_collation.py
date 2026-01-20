#!/usr/bin/env python3
"""Script to fix PostgreSQL collation version warning.

This script refreshes the collation version for PostgreSQL databases
to resolve the warning: 'database has no actual collation version,
but a version was recorded'.

Usage:
    python scripts/fix_collation.py
"""
import asyncio
import os
import sys

import asyncpg
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine


async def fix_collation_async(db_url: str) -> None:
    """Fix collation version using asyncpg."""
    try:
        # Connect to template1 to fix other databases
        base_url = db_url.replace('+asyncpg', '')
        # Extract connection parameters but connect to template1
        template_url = base_url.rsplit('/', 1)[0] + '/template1'
        conn = await asyncpg.connect(template_url)
        
        # Fix for postgres database
        try:
            await conn.execute(
                "ALTER DATABASE postgres REFRESH COLLATION VERSION"
            )
            print("✓ Refreshed collation version for 'postgres' database")
        except Exception as e:
            print(f"⚠ Warning fixing 'postgres' database: {e}")
        
        # Get the database name from URL
        db_name = os.getenv("POSTGRES_DB", "laminar_database")
        
        # Fix for application database
        try:
            await conn.execute(
                f"ALTER DATABASE {db_name} REFRESH COLLATION VERSION"
            )
            print(f"✓ Refreshed collation version for '{db_name}' database")
        except Exception as e:
            print(f"⚠ Warning fixing '{db_name}' database: {e}")
        
        await conn.close()
        print("✓ Collation versions refreshed successfully!")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


def fix_collation_sync(db_url: str) -> None:
    """Fix collation version using psycopg2 (sync)."""
    try:
        # Use psycopg2 URL format, connect to template1 to fix other databases
        sync_url = db_url.replace('+asyncpg', '').replace('postgresql+asyncpg', 'postgresql')
        template_url = sync_url.rsplit('/', 1)[0] + '/template1'
        
        engine = create_engine(template_url)
        
        with engine.connect() as conn:
            # Fix for postgres database
            try:
                conn.execute(text("ALTER DATABASE postgres REFRESH COLLATION VERSION"))
                conn.commit()
                print("✓ Refreshed collation version for 'postgres' database")
            except Exception as e:
                print(f"⚠ Warning fixing 'postgres' database: {e}")
            
            # Get the database name from URL
            db_name = os.getenv("POSTGRES_DB", "laminar_database")
            
            # Fix for application database
            try:
                conn.execute(text(f"ALTER DATABASE {db_name} REFRESH COLLATION VERSION"))
                conn.commit()
                print(f"✓ Refreshed collation version for '{db_name}' database")
            except Exception as e:
                print(f"⚠ Warning fixing '{db_name}' database: {e}")
        
        print("✓ Collation versions refreshed successfully!")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


async def main() -> None:
    """Main function."""
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/laminar_database"
    )
    
    print("Fixing PostgreSQL collation version warnings...")
    print(f"Database URL: {db_url.split('@')[1] if '@' in db_url else db_url}")
    
    # Try async first, fall back to sync
    try:
        await fix_collation_async(db_url)
    except ImportError:
        print("asyncpg not available, using sync method...")
        fix_collation_sync(db_url)
    except Exception as e:
        print(f"Async method failed: {e}")
        print("Trying sync method...")
        fix_collation_sync(db_url)


if __name__ == "__main__":
    asyncio.run(main())
