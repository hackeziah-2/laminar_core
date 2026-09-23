import asyncio
import io
import threading
import time
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import UploadFile
from app.services.excel_import import reader


@pytest.mark.asyncio
async def test_parser_does_not_block_event_loop(monkeypatch):
    original=reader.pd.read_csv
    main_thread=threading.get_ident()
    def slow(*args,**kwargs):
        assert threading.get_ident()!=main_thread
        time.sleep(.08)
        return original(*args,**kwargs)
    monkeypatch.setattr(reader.pd,'read_csv',slow)
    ticks=0
    async def heartbeat():
        nonlocal ticks
        for _ in range(10):
            ticks+=1
            await asyncio.sleep(.005)
    rows,_=await asyncio.gather(reader.read_upload_records(
        UploadFile(filename='a.csv',file=io.BytesIO(b'a,b\n1,2\n'))),heartbeat())
    assert rows==[{'a':1,'b':2}]
    assert ticks==10


def test_csv_sample_read_is_bounded(tmp_path,monkeypatch):
    path=tmp_path/'data.csv';path.write_text('a,b\n1,2\n')
    def forbidden(*args): raise AssertionError('Unbounded read_bytes')
    monkeypatch.setattr(type(path),'read_bytes',forbidden)
    assert list(reader._read_csv_dataframe_from_path(path).columns)==['a','b']


@pytest.mark.parametrize('claimed',[True,False])
def test_worker_claims_pending_job_once(monkeypatch,claimed):
    from app import database
    from app.tasks.file_upload import process_atl_import
    from app.services import atl_excel_import_job_runner as runner
    session=AsyncMock()
    result=MagicMock();result.rowcount=1 if claimed else 0
    session.execute.return_value=result
    factory=MagicMock();factory.return_value.__aenter__=AsyncMock(return_value=session)
    factory.return_value.__aexit__=AsyncMock(return_value=False)
    monkeypatch.setattr(database,'AsyncSessionLocal',factory)
    dispose=AsyncMock();fake_engine=MagicMock();fake_engine.dispose=dispose
    monkeypatch.setattr(database,'engine',fake_engine)
    process=AsyncMock();monkeypatch.setattr(runner,'process_atl_excel_import_job',process)
    process_atl_import.run('job-1')
    assert process.await_count==int(claimed)
    assert session.commit.await_count==1
    dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancelled_queued_parse_removes_temp_file(tmp_path,monkeypatch):
    path=tmp_path/'input.csv';path.write_bytes(b'a,b\n1,2\n')
    monkeypatch.setattr(reader,'_stream_upload_to_temp_path',AsyncMock(return_value=path))
    gate=asyncio.Semaphore(0)
    reader._parse_slots[asyncio.get_running_loop()]=gate
    task=asyncio.create_task(reader.read_upload_records(UploadFile(filename='a.csv',file=io.BytesIO())))
    await asyncio.sleep(.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert not path.exists()
