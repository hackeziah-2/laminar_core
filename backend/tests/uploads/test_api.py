import asyncio
import os
import uuid
import io
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select, func, event, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.api.v1 import file_upload as api
from app.core.security import create_access_token
from app.database import Base
from app.models.account import AccountInformation
from app.models.module import Module
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission
from app.models.upload_asset import UploadAsset
from app.services import file_upload_service as storage


def auth(account=1):
    return {'Authorization': 'Bearer '+create_access_token({'sub':str(account)})}


@pytest.fixture
async def env(tmp_path, monkeypatch):
    database_url=os.getenv('UPLOAD_TEST_DATABASE_URL')
    schema='upload_test_'+uuid.uuid4().hex if database_url else None
    engine=create_async_engine(database_url or 'sqlite+aiosqlite:///'+str(tmp_path/'test.db'),
        execution_options={'schema_translate_map': {None: schema}} if schema else {})
    tables=[x.__table__ for x in (Role, Module, AccountInformation, RolePermission, UserPermission, UploadAsset)]
    async with engine.begin() as conn:
        if schema: await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        await conn.run_sync(lambda c: Base.metadata.create_all(c,tables=tables))
        await conn.execute(insert(Role).values(id=1,name='Uploader'))
        await conn.execute(insert(Module).values(id=1,name='Logbook'))
        await conn.execute(insert(RolePermission).values(role_id=1,module_id=1,can_create=True))
        for i in range(1,5):
            await conn.execute(insert(AccountInformation).values(id=i,username=f'user{i}',first_name='Test',
                last_name='User',password='unused',role_id=1 if i!=3 else None,status=i!=4))
    factory=async_sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(api,'AsyncSessionLocal',factory)
    root=tmp_path/'uploads';root.mkdir()
    monkeypatch.setattr(storage,'UPLOAD_DIR',root)
    monkeypatch.setattr(storage,'ensure_uploads_dir',lambda:None)
    app=FastAPI();app.include_router(api.router)
    async with AsyncClient(transport=ASGITransport(app),base_url='http://test') as client:
        yield client, factory, root, engine
    if schema:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    await engine.dispose()


async def send(client,data=b'a,b\n1,2\n',account=1,name='data.csv',**kw):
    return await client.post('/api/v1/logbooks/upload',headers=auth(account),
                             files={'file':(name,data,'text/csv')},**kw)


@pytest.mark.asyncio
async def test_success_dedup_and_owner_isolation(env):
    client,factory,root,_=env
    first=await send(client);second=await send(client);other=await send(client,account=2)
    assert first.status_code==second.status_code==other.status_code==201
    assert first.json()==second.json()
    assert other.json()['file_path']!=first.json()['file_path']
    assert set(first.json())=={'file_path','filename','size_bytes','content_type','original_filename','stored_filename','size'}
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(UploadAsset))==2
    assert len([p for p in root.rglob('*') if p.is_file()])==2


@pytest.mark.asyncio
async def test_auth_before_body(env):
    client,_,root,_=env
    async def forbidden_body():
        raise AssertionError('Unauthenticated body consumed')
        yield b''
    response=await client.post('/api/v1/logbooks/upload',content=forbidden_body(),
                              headers={'Content-Type':'multipart/form-data; boundary=x'})
    assert response.status_code==401
    for account,status in [(3,403),(4,403),(999,401)]:
        assert (await send(client,account=account)).status_code==status
    assert not list(root.rglob('*'))


@pytest.mark.asyncio
async def test_no_db_connection_during_copy(env,monkeypatch):
    client,_,_,engine=env
    checked_out=0
    @event.listens_for(engine.sync_engine,'checkout')
    def checkout(*args):
        nonlocal checked_out
        checked_out+=1
    @event.listens_for(engine.sync_engine,'checkin')
    def checkin(*args):
        nonlocal checked_out
        checked_out-=1
    original=storage.save_module_upload
    async def inspect(*args,**kwargs):
        assert checked_out==0
        return await original(*args,**kwargs)
    monkeypatch.setattr(storage,'save_module_upload',inspect)
    assert (await send(client)).status_code==201


@pytest.mark.asyncio
async def test_concurrent_duplicates(env):
    client,factory,root,_=env
    responses=await asyncio.gather(*(send(client) for _ in range(8)))
    assert {r.status_code for r in responses}=={201}
    assert len({r.json()['file_path'] for r in responses})==1
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(UploadAsset))==1
    assert len([p for p in root.rglob('*') if p.is_file()])==1


@pytest.mark.asyncio
async def test_metadata_failure_removes_file(env,monkeypatch):
    client,_,root,_=env
    async def fail(*args): raise RuntimeError('database failed')
    monkeypatch.setattr(api,'_register',fail)
    with pytest.raises(RuntimeError): await send(client)
    assert not [p for p in root.rglob('*') if p.is_file()]


@pytest.mark.asyncio
async def test_limit_and_invalid_filename(env,monkeypatch):
    client,_,root,_=env
    monkeypatch.setattr(storage,'max_upload_bytes',lambda:8)
    assert (await send(client,b'a,b\n1,2\n')).status_code==201
    assert (await send(client,b'a,b\n1,2\n3')).status_code==413
    assert (await send(client,params={'name':'../../attack.csv'})).status_code==400
    assert (await send(client,name='../../safe.csv')).status_code==201
    assert (await client.post('/api/v1/unknown/upload',headers=auth(),files={'file':('a.csv',b'a','text/csv')})).status_code==400


@pytest.mark.asyncio
async def test_stream_size_limit_without_content_length(env,monkeypatch):
    client,_,root,_=env
    monkeypatch.setattr(storage,'max_upload_bytes',lambda:8)
    monkeypatch.setattr(storage,'CHUNK_SIZE',64)
    async def body():
        yield b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.csv"\r\n\r\n'
        yield b'a'*100
        yield b'\r\n--x--\r\n'
    response=await client.post('/api/v1/logbooks/upload',content=body(),
        headers={**auth(),'content-type':'multipart/form-data; boundary=x'})
    assert response.status_code==413
    assert not [p for p in root.rglob('*') if p.is_file()]


@pytest.mark.asyncio
async def test_interrupted_multipart_closes_spool(env,monkeypatch):
    client,_,root,_=env
    from starlette import formparsers
    original=formparsers.SpooledTemporaryFile
    spools=[]
    def create(*args,**kwargs):
        file=original(*args,**kwargs);spools.append(file);return file
    monkeypatch.setattr(formparsers,'SpooledTemporaryFile',create)
    async def body():
        yield b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.csv"\r\n\r\na,b\n'
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await client.post('/api/v1/logbooks/upload',content=body(),headers={**auth(),'content-type':'multipart/form-data; boundary=x'})
    assert spools and all(f.closed for f in spools)
    assert not [p for p in root.rglob('*') if p.is_file()]


@pytest.mark.asyncio
async def test_truncated_multipart_rejected(env):
    client,_,root,_=env
    data=b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.csv"\r\n\r\na,b\n\r\n--x\r\n'
    response=await client.post('/api/v1/logbooks/upload',content=data,
        headers={**auth(),'content-type':'multipart/form-data; boundary=x'})
    assert response.status_code==400
    assert not [p for p in root.rglob('*') if p.is_file()]


@pytest.mark.asyncio
async def test_transaction_file_cleanup(env):
    _,factory,root,_=env
    from starlette.datastructures import UploadFile
    async with factory() as session:
        relative=await storage.persist_optional_upload(UploadFile(filename='a.csv',file=io.BytesIO(b'a,b\n')),
                                                      'logbooks',session=session)
        path=root/relative.removeprefix('uploads/')
        assert path.exists()
        await session.rollback()
        assert not path.exists()
        assert not list(root.rglob('*.pending'))
    async with factory() as session:
        relative=await storage.persist_optional_upload(UploadFile(filename='a.csv',file=io.BytesIO(b'a,b\n')),
                                                      'logbooks',session=session)
        path=root/relative.removeprefix('uploads/')
        await session.commit()
        assert path.exists()
        assert not list(root.rglob('*.pending'))


@pytest.mark.asyncio
async def test_session_close_cleans_uncommitted_file(env):
    _,factory,root,_=env
    from starlette.datastructures import UploadFile
    async with factory() as session:
        await storage.persist_optional_upload(UploadFile(filename='a.csv',file=io.BytesIO(b'a,b\n')),
                                              'logbooks',session=session)
    assert not [p for p in root.rglob('*') if p.is_file()]


@pytest.mark.asyncio
async def test_committed_metadata_survives_lost_ack(env,monkeypatch):
    client,factory,root,_=env
    register=api._register
    async def ambiguous(*args):
        await register(*args)
        raise OSError('lost commit acknowledgement')
    monkeypatch.setattr(api,'_register',ambiguous)
    with pytest.raises(OSError): await send(client)
    async with factory() as session:
        asset=(await session.scalars(select(UploadAsset))).one()
    assert (root/asset.file_path.removeprefix('uploads/')).is_file()


@pytest.mark.asyncio
async def test_admission_limit(env):
    client,_,root,_=env
    gate=asyncio.Semaphore(0)
    api._slots[asyncio.get_running_loop()]=gate
    response=await send(client)
    assert response.status_code==503
    assert response.headers['retry-after']=='2'
    assert not list(root.rglob('*'))


@pytest.mark.asyncio
async def test_attachment_copy_releases_reads_and_preserves_object(env,monkeypatch):
    _,factory,root,engine=env
    from starlette.datastructures import UploadFile
    checked_out=0
    @event.listens_for(engine.sync_engine,'checkout')
    def checkout(*args):
        nonlocal checked_out
        checked_out+=1
    @event.listens_for(engine.sync_engine,'checkin')
    def checkin(*args):
        nonlocal checked_out
        checked_out-=1
    original=storage.save_module_upload
    async def inspect(*args,**kwargs):
        assert checked_out==0
        return await original(*args,**kwargs)
    monkeypatch.setattr(storage,'save_module_upload',inspect)
    async with factory() as session:
        account=await session.get(AccountInformation,1)
        await storage.persist_optional_upload(UploadFile(filename='a.csv',file=io.BytesIO(b'a,b\n')),
                                              'logbooks',session=session)
        assert account.first_name=='Test'
        account.first_name='Updated'
        await session.commit()
    async with factory() as session:
        assert (await session.get(AccountInformation,1)).first_name=='Updated'


@pytest.mark.asyncio
async def test_duplicate_restores_missing_file(env):
    client,_,root,_=env
    first=await send(client)
    path=root/first.json()['file_path'].removeprefix('uploads/')
    path.unlink()
    second=await send(client)
    assert first.json()==second.json()
    assert path.read_bytes()==b'a,b\n1,2\n'


@pytest.mark.asyncio
async def test_download_requires_module_read_permission(env,monkeypatch):
    from app import main
    from sqlalchemy import update
    client,factory,root,_=env
    saved=(await send(client)).json()
    monkeypatch.setattr(main,'UPLOAD_DIR',root)
    app=FastAPI()
    app.add_api_route('/api/v1/{module_folder}/download',main.download_file_by_name,methods=['GET'])
    async with AsyncClient(transport=ASGITransport(app),base_url='http://test') as download:
        params={'name':saved['filename']}
        assert (await download.get('/api/v1/logbooks/download',params=params)).status_code==401
        assert (await download.get('/api/v1/logbooks/download',params=params,headers=auth())).status_code==403
        async with factory() as session:
            await session.execute(update(RolePermission).values(can_read=True))
            await session.commit()
        response=await download.get('/api/v1/logbooks/download',params=params,headers=auth())
        assert response.status_code==200 and response.content==b'a,b\n1,2\n'


@pytest.mark.asyncio
async def test_reconcile_only_stale_marked_files(env,monkeypatch):
    client,factory,root,engine=env
    from app.services import upload_reconciliation as recovery
    from app.services.upload_transaction import marker
    import time
    # This focused schema contains the upload registry; legacy enum migrations
    # are deliberately outside the fixture. Keep recovery's discovery scoped to it.
    from types import SimpleNamespace
    monkeypatch.setattr(recovery, 'Base', SimpleNamespace(metadata=SimpleNamespace(
        tables={'upload_assets': UploadAsset.__table__})))
    monkeypatch.setattr(recovery,'AsyncSessionLocal',factory)
    saved=(await send(client)).json()
    committed=root/saved['file_path'].removeprefix('uploads/')
    orphan=root/'logbooks/orphan.csv';orphan.write_bytes(b'a,b\n')
    legacy=root/'logbooks/legacy.csv';legacy.write_bytes(b'legacy')
    fresh=root/'logbooks/fresh.csv';fresh.write_bytes(b'a,b\n');marker(fresh).touch()
    part=root/'logbooks/.upload-old.part';part.write_bytes(b'partial')
    old=time.time()-48*3600
    for path in [committed,orphan]:
        marker(path).touch();os.utime(marker(path),(old,old))
    os.utime(part,(old,old))
    assert await recovery.reconcile_uploads()==2
    assert committed.exists() and legacy.exists() and fresh.exists()
    assert not orphan.exists() and not part.exists()
