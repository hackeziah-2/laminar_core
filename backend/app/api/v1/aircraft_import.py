from fastapi import APIRouter, UploadFile, File, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.aircraft import Aircraft
from app.schemas.aircraft_schema import AircraftImportSchema
from app.services.import_data_excel import import_excel_generic

router = APIRouter(
    prefix="/api/v1/excel-data",
    tags=["excel-data"],
)


@router.post(
    "/aircraft/import",
    summary="Import aircraft from Excel or CSV",
    description="Upload a .xlsx, .xls, or .csv file with aircraft rows. Columns are matched by name (case-insensitive). Use dry_run=true to validate without saving.",
)
async def import_aircraft_endpoint(
    file: UploadFile = File(..., description="Excel (.xlsx, .xls) or CSV file with aircraft data"),
    dry_run: bool = Query(False, description="If true, validate only and return counts without writing"),
    session: AsyncSession = Depends(get_session),
):
    return await import_excel_generic(
        file=file,
        session=session,
        model=Aircraft,
        schema=AircraftImportSchema,
        unique_fields=["registration", "msn"],
        dry_run=dry_run,
    )
