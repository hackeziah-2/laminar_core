"""Upload-focused tests run without production services or application startup.
pytest --confcutdir=tests/uploads tests/uploads -o addopts=''
"""
import os
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://test:test@127.0.0.1/test')
