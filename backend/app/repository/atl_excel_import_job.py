from typing import Any, Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.atl_excel_import_job import AtlExcelImportJob


async def get_import_job(session: AsyncSession, job_id: str) -> Optional[AtlExcelImportJob]:
    return await session.get(AtlExcelImportJob, job_id)


async def patch_import_job(session: AsyncSession, job_id: str, **values: Any) -> None:
    await session.execute(
        update(AtlExcelImportJob).where(AtlExcelImportJob.job_id == job_id).values(**values)
    )


async def create_import_job(
    session: AsyncSession,
    *,
    job_id: str,
    temp_file_path: str,
    aircraft_fk: int,
    atl_batch_fk: int,
    started_by: Optional[int],
    total_rows: int = 0,
    status: str = "PENDING",
    message: Optional[str] = None,
) -> AtlExcelImportJob:
    row = AtlExcelImportJob(
        job_id=job_id,
        temp_file_path=temp_file_path,
        aircraft_fk=aircraft_fk,
        atl_batch_fk=atl_batch_fk,
        started_by=started_by,
        total_rows=total_rows,
        status=status,
        message=message,
        processed_rows=0,
        failed_rows=0,
        errors=[],
    )
    session.add(row)
    await session.flush()
    return row
