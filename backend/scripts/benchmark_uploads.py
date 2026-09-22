"""Isolated storage + multipart ASGI benchmark (no network, DB, auth or proxy).
Run from backend: python scripts/benchmark_uploads.py --service app/services/file_upload_service.py
Each sample is a fresh subprocess; payload creation is outside timed/traced regions.
"""
import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import importlib.metadata
import uuid
import statistics
import shutil
import subprocess
import sys
import tempfile
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

async def sample(args):
    from fastapi import FastAPI, File, UploadFile
    from httpx import ASGITransport, AsyncClient
    spec = importlib.util.spec_from_file_location('bench_service', args.service)
    service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service)
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        service.UPLOAD_DIR = root / 'uploads'
        service.ensure_uploads_dir = lambda: service.UPLOAD_DIR.mkdir(exist_ok=True)
        size = args.mib * 1024 * 1024
        payload = root / 'data.csv'
        with payload.open('wb') as f:
            block = b'a,b\n' * (256 * 1024)
            for _ in range(args.mib): f.write(block)
        app = FastAPI()
        @app.post('/upload')
        async def upload(file: UploadFile = File(...)):
            return await service.save_module_upload(file, 'bench')
        @app.get('/health')
        async def health(): return {'ok': True}
        spools = []
        if args.mode == 'storage':
            for _ in range(args.concurrency):
                spool = tempfile.SpooledTemporaryFile(max_size=1024*1024)
                with payload.open('rb') as source: shutil.copyfileobj(source, spool, 1024*1024)
                spool.seek(0)
                spools.append(spool)
        database_engine = None
        headers = {}
        if args.mode == 'secured-api':
            os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://test:test@127.0.0.1/test')
            from sqlalchemy import insert, text
            from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
            from app.api.v1 import file_upload as api
            from app.database import Base
            from app.models.account import AccountInformation
            from app.models.role import Role
            from app.models.module import Module
            from app.models.role_permission import RolePermission
            from app.models.user_permission import UserPermission
            from app.models.upload_asset import UploadAsset
            from app.core.security import create_access_token
            database_url = os.getenv('UPLOAD_BENCH_DATABASE_URL')
            schema = 'upload_bench_' + uuid.uuid4().hex if database_url else None
            database_engine = create_async_engine(database_url or 'sqlite+aiosqlite:///' + str(root/'bench.db'),
                execution_options={'schema_translate_map': {None: schema}} if schema else {})
            async with database_engine.begin() as conn:
                if schema: await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                tables = [model.__table__ for model in (Role, Module, AccountInformation, RolePermission, UserPermission, UploadAsset)]
                await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
                await conn.execute(insert(Role).values(id=1,name='Benchmark'))
                await conn.execute(insert(Module).values(id=1,name='Logbook'))
                await conn.execute(insert(RolePermission).values(role_id=1,module_id=1,can_create=True))
                await conn.execute(insert(AccountInformation).values(id=1,username='benchmark',first_name='Test',
                    last_name='User',password='unused',role_id=1,status=True))
            api.AsyncSessionLocal = async_sessionmaker(database_engine,expire_on_commit=False)
            api.storage = service
            app.include_router(api.router)
            headers = {'Authorization': 'Bearer '+create_access_token({'sub':'1'})}
        latencies, health_times = [], []
        done = asyncio.Event()
        async with AsyncClient(transport=ASGITransport(app), base_url='http://bench') as client:
            async def probe():
                while not done.is_set():
                    start = time.perf_counter()
                    await client.get('/health')
                    health_times.append((time.perf_counter() - start) * 1000)
                    await asyncio.sleep(.002)
            async def run_one(index):
                with payload.open('rb') as f:
                    start = time.perf_counter()
                    if args.mode in {'api', 'secured-api'}:
                        route = '/api/v1/logbooks/upload' if args.mode == 'secured-api' else '/upload'
                        response = await client.post(route, headers=headers, files={'file': ('data.csv', f, 'text/csv')})
                        assert response.status_code in {200,201}, response.text
                    else:
                        result = await service.save_module_upload(UploadFile(file=spools[index], filename='data.csv'), 'bench')
                        assert result['size'] == size
                    latencies.append((time.perf_counter() - start) * 1000)
            tracemalloc.start()
            started = time.perf_counter()
            task = asyncio.create_task(probe())
            await asyncio.gather(*(run_one(i) for i in range(args.concurrency)))
            elapsed = time.perf_counter() - started
            done.set()
            await task
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        if database_engine:
            if schema:
                async with database_engine.begin() as conn:
                    await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await database_engine.dispose()
        return dict(mode=args.mode, mib=args.mib, concurrency=args.concurrency,
                    elapsed_ms=elapsed*1000, throughput_mib_s=args.mib*args.concurrency/elapsed,
                    response_ms=statistics.mean(latencies), max_response_ms=max(latencies),
                    peak_python_mib=peak/1024**2,
                    peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024),
                    health_max_ms=max(health_times, default=0))

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--service', required=True)
    p.add_argument('--child', action='store_true')
    p.add_argument('--mib', type=int, default=16)
    p.add_argument('--concurrency', type=int, default=1)
    p.add_argument('--mode', default='storage')
    p.add_argument('--repeats', type=int, default=5)
    p.add_argument('--modes', nargs='+', default=['storage','api'])
    args=p.parse_args()
    if args.child: print(json.dumps(asyncio.run(sample(args))))
    else:
        rows=[]
        for mode in args.modes:
            for concurrency in [1,4,8]:
                for repeat in range(args.repeats):
                    raw=subprocess.check_output([sys.executable,__file__,'--child','--service',str(Path(args.service).resolve()),'--mib',str(args.mib),'--concurrency',str(concurrency),'--mode',mode],text=True)
                    rows.append(dict(repeat=repeat, **json.loads(raw)))
        print(json.dumps({'python':sys.version,'platform':platform.platform(),'versions':{name:importlib.metadata.version(name) for name in ['fastapi','starlette','aiofiles','python-multipart','sqlalchemy','httpx']},'samples':rows},indent=2))
