import asyncio
import io
import threading
import time
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from app.services import file_upload_service as s


def upload(data=b'a,b\n1,2\n', name='data.csv', mime='text/csv'):
    return UploadFile(file=io.BytesIO(data), filename=name, headers=Headers({'content-type': mime}))


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(s, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(s, 'ensure_uploads_dir', lambda: None)


@pytest.mark.asyncio
async def test_success_and_exact_limit(tmp_path):
    data=b'a,b\n1,2\n'
    result=await s.save_module_upload(upload(data), 'logbooks', max_bytes=len(data), include_checksum=True)
    import hashlib
    assert result['sha256']==hashlib.sha256(data).hexdigest()
    assert (tmp_path/'logbooks'/result['filename']).read_bytes()==data
    assert not list(tmp_path.rglob('*.part'))


@pytest.mark.asyncio
@pytest.mark.parametrize('data,name,mime,status', [
    (b'', 'a.csv', 'text/csv',400), (b'MZ', 'a.exe','application/octet-stream',400),
    (b'a,b', 'a.csv', 'image/png',400), (b'\x00\x01','a.csv','text/csv',400),
    (b'%PDF-1.4\n','a.pdf','application/pdf',400),
    (b'\x89PNG\r\n\x1a\n','a.png','image/png',400),
    (b'PK\x03\x04broken','a.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',400),
    (b'a'*50,'a.csv','text/csv',413),
])
async def test_invalid_cleanup(tmp_path,data,name,mime,status):
    with pytest.raises(HTTPException) as exc:
        await s.save_module_upload(upload(data,name,mime),'logbooks',max_bytes=40)
    assert exc.value.status_code==status
    assert not [p for p in tmp_path.rglob('*') if p.is_file()]


@pytest.mark.asyncio
async def test_disguised_zip_rejected(tmp_path):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z: z.writestr('evil.txt','hello')
    with pytest.raises(HTTPException) as exc:
        await s.save_module_upload(upload(b.getvalue(),'a.docx','application/octet-stream'),'logbooks')
    assert exc.value.status_code==400


@pytest.mark.asyncio
async def test_valid_office(tmp_path):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        z.writestr('[Content_Types].xml','<Types/>')
        z.writestr('xl/workbook.xml','<workbook/>')
    result=await s.save_module_upload(upload(b.getvalue(),'a.xlsx','application/octet-stream'),'logbooks')
    assert result['size']==len(b.getvalue())


@pytest.mark.asyncio
async def test_cancellation_drains_worker_and_cleans(tmp_path):
    started=threading.Event()
    class Slow(io.BytesIO):
        def read(self,n=-1):
            assert 0<n<=s.CHUNK_SIZE
            started.set()
            time.sleep(.03)
            return super().read(n)
    file=upload(b'a'*(2*s.CHUNK_SIZE));file.file=Slow(file.file.getvalue())
    task=asyncio.create_task(s.save_module_upload(file,'logbooks'))
    while not started.is_set(): await asyncio.sleep(.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert file.file.closed
    assert not [p for p in tmp_path.rglob('*') if p.is_file()]


@pytest.mark.asyncio
async def test_read_failure_cleanup(tmp_path):
    class Broken(io.BytesIO):
        def read(self,n=-1): raise OSError('secret filesystem path')
    file=upload();file.file=Broken()
    with pytest.raises(HTTPException) as exc: await s.save_module_upload(file,'logbooks')
    assert exc.value.status_code==500
    assert 'secret' not in exc.value.detail
    assert not [p for p in tmp_path.rglob('*') if p.is_file()]


@pytest.mark.asyncio
async def test_timeout_cleanup(tmp_path,monkeypatch):
    monkeypatch.setattr(s,'upload_timeout_seconds',lambda:.005)
    class Slow(io.BytesIO):
        def read(self,n=-1):
            time.sleep(.02)
            return super().read(n)
    file=upload();file.file=Slow(b'a,b\n')
    with pytest.raises(HTTPException) as exc: await s.save_module_upload(file,'logbooks')
    assert exc.value.status_code==408
    assert not [p for p in tmp_path.rglob('*') if p.is_file()]


@pytest.mark.asyncio
async def test_concurrent_and_traversal(tmp_path):
    results=await asyncio.gather(*(s.save_module_upload(upload(name='../../data.csv'),'logbooks') for _ in range(12)))
    assert len({r['file_path'] for r in results})==12
    for result in results:
        path=tmp_path/'logbooks'/result['filename']
        assert path.is_file() and path.resolve().is_relative_to(tmp_path)
    with pytest.raises(HTTPException): await s.save_module_upload(upload(),'../escape')


@pytest.mark.asyncio
async def test_collision_preserves_original(tmp_path):
    path=tmp_path/'existing.csv';path.write_bytes(b'original')
    with pytest.raises(HTTPException) as exc: await s.save_upload_to_exact_path(upload(),path)
    assert exc.value.status_code==409
    assert path.read_bytes()==b'original'
    assert not list(tmp_path.rglob('*.part'))


def test_sibling_prefix_escape(tmp_path):
    sibling=tmp_path.with_name(tmp_path.name+'_outside');sibling.mkdir()
    path=sibling/'data.csv';path.write_bytes(b'private')
    assert s.resolve_stored_upload_path(str(path)) is None
    (tmp_path/'logbooks').symlink_to(sibling,target_is_directory=True)
    assert s.resolve_stored_upload_path('logbooks/data.csv') is None


@pytest.mark.asyncio
async def test_extension_override_cannot_disguise():
    with pytest.raises(HTTPException): await s.save_module_upload(upload(name='data.exe'),'logbooks',name_override='a.csv')


@pytest.mark.asyncio
async def test_known_size_rejected_before_read():
    file=upload();file.size=100
    with pytest.raises(HTTPException) as exc: await s.save_module_upload(file,'logbooks',max_bytes=10)
    assert exc.value.status_code==413


@pytest.mark.asyncio
async def test_default_50_mib_boundary(tmp_path):
    source=tmp_path/'source.csv'
    with source.open('wb') as output:
        for _ in range(50): output.write(b'x'*(1024*1024))
    result=await s.save_module_upload(UploadFile(filename='limit.csv',file=source.open('rb'),
                                                size=50*1024*1024),'logbooks')
    assert result['size_bytes']==50*1024*1024
    too_large=UploadFile(filename='limit.csv',file=source.open('rb'),size=50*1024*1024+1)
    with pytest.raises(HTTPException) as exc: await s.save_module_upload(too_large,'logbooks')
    assert exc.value.status_code==413


@pytest.mark.asyncio
async def test_symlink_destination_escape(tmp_path):
    outside=tmp_path.with_name(tmp_path.name+'_escape');outside.mkdir()
    (tmp_path/'logbooks').symlink_to(outside,target_is_directory=True)
    with pytest.raises(HTTPException) as exc: await s.save_module_upload(upload(),'logbooks')
    assert exc.value.status_code==400
    assert not list(outside.iterdir())


@pytest.mark.asyncio
async def test_pdf_header_and_eof_alone_are_not_valid():
    with pytest.raises(HTTPException):
        await s.save_module_upload(upload(b'%PDF-1.4\ngarbage\n%%EOF\n','a.pdf','application/pdf'),'logbooks')


@pytest.mark.asyncio
@pytest.mark.parametrize('format,extension,mime',[('PNG','png','image/png'),('JPEG','jpg','image/jpeg'),
    ('GIF','gif','image/gif'),('WEBP','webp','image/webp')])
async def test_valid_images(format,extension,mime):
    from PIL import Image
    data=io.BytesIO();Image.new('RGB',(8,8),'white').save(data,format=format)
    result=await s.save_module_upload(upload(data.getvalue(),'image.'+extension,mime),'logbooks')
    assert result['size_bytes']==len(data.getvalue())
