from fastapi import APIRouter, UploadFile, File, Depends, Form, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.schemas.aircraft_schema import AircraftImportSchema
from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema
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
        integrity_error_messages={
            "registration": "Aircraft with this registration already exists",
            "msn": "Aircraft with this MSN already exists",
        },
    )


def _parse_aircraft_id(value: str | int | None) -> int | None:
    """Parse aircraft_id from form (may be empty string or int)."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


@router.post(
    "/aircraft-technical-log/import",
    summary="Import Aircraft Technical Log from Excel or CSV",
    description="Upload a file and provide aircraft by aircraft_id or registration. All ATL rows are imported for that aircraft. Use dry_run=true to validate without saving.",
)
async def import_atl_endpoint(
    file: UploadFile = File(..., description="Excel (.xlsx, .xls) or CSV file with aircraft technical log data"),
    aircraft_id: str | None = Form(None, description="Aircraft ID to assign to all imported ATL rows"),
    registration: str | None = Form(None, description="Aircraft registration; used to look up aircraft_id if aircraft_id not provided"),
    dry_run: bool = Query(False, description="If true, validate only and return counts without writing"),
    session: AsyncSession = Depends(get_session),
):
    aid = _parse_aircraft_id(aircraft_id)
    reg = str(registration).strip() if registration else ""

    if aid is not None:
        result = await session.execute(
            select(Aircraft).where(Aircraft.id == aid).where(Aircraft.is_deleted.is_(False))
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Aircraft with this ID not found")
        resolved_id = aid
    elif reg:
        result = await session.execute(
            select(Aircraft).where(Aircraft.registration.ilike(reg)).where(Aircraft.is_deleted.is_(False))
        )
        aircraft = result.scalar_one_or_none()
        if aircraft is None:
            raise HTTPException(status_code=404, detail=f"Aircraft with registration '{reg}' not found")
        resolved_id = aircraft.id
    else:
        raise HTTPException(status_code=400, detail="Provide either aircraft_id or registration")

    return await import_excel_generic(
        file=file,
        session=session,
        model=AircraftTechnicalLog,
        schema=AircraftTechnicalLogImportSchema,
        unique_fields=["sequence_no", "aircraft_fk"],
        dry_run=dry_run,
        inject_fields={"aircraft_fk": resolved_id},
        column_mapping={
            "sequence no": "sequence_no",
            "sequence number": "sequence_no",
            "sequence_no": "sequence_no",
        },
        integrity_error_messages={
            "aircraft_fk": "Aircraft with this ID does not exist",
            "sequence_no": "ATL with this sequence number for this aircraft already exists",
        },
    )
