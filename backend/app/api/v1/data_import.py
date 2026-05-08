from typing import Optional, Union

from fastapi import APIRouter, UploadFile, File, Depends, Form, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account
from app.database import get_session
from app.models.account import AccountInformation
from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from app.models.atl_batch import AtlBatch
from app.schemas.aircraft_schema import AircraftImportSchema
from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema
from app.services import import_excel_generic

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
    current_account: AccountInformation = Depends(get_current_active_account),
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
        audit_account_id=current_account.id,
    )


def _parse_form_optional_int(value: Union[str, int, None]) -> Optional[int]:
    """Parse optional int from multipart form (empty string or int)."""
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
    description="Upload a file; set aircraft via aircraft_id or registration. Required form field batch_id (atl_batch.id) tags this import: rows match on aircraft_fk + sequence_no + atl_batch_fk — existing rows are updated, others inserted. dry_run=true validates only.",
)
async def import_atl_endpoint(
    file: UploadFile = File(..., description="Excel (.xlsx, .xls) or CSV file with aircraft technical log data"),
    aircraft_id: Optional[str] = Form(None, description="Aircraft ID to assign to all imported ATL rows (stored as aircraft_fk)"),
    registration: Optional[str] = Form(None, description="Aircraft registration; used to look up aircraft_id if aircraft_id not provided"),
    batch_id: str = Form(..., description="ATL batch primary key (multipart form); applied as atl_batch_fk on every row for audit grouping"),
    dry_run: bool = Query(False, description="If true, validate only and return counts without writing"),
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(get_current_active_account),
):
    aid = _parse_form_optional_int(aircraft_id)
    resolved_batch_id = _parse_form_optional_int(batch_id)
    reg = str(registration).strip() if registration else ""

    if resolved_batch_id is None:
        raise HTTPException(status_code=400, detail="batch_id is required and must be a valid integer (atl_batch.id)")

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

    b = await session.execute(
        select(AtlBatch).where(AtlBatch.id == resolved_batch_id).where(AtlBatch.is_deleted.is_(False))
    )
    if b.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="ATL batch not found")

    inject_fields: dict = {"aircraft_fk": resolved_id, "atl_batch_fk": resolved_batch_id}

    return await import_excel_generic(
        file=file,
        session=session,
        model=AircraftTechnicalLog,
        schema=AircraftTechnicalLogImportSchema,
        unique_fields=["aircraft_fk", "sequence_no", "atl_batch_fk"],
        dry_run=dry_run,
        inject_fields=inject_fields,
        column_mapping={
            "sequence no": "sequence_no",
            "sequence no.": "sequence_no",
            "sequence number": "sequence_no",
            "seq no": "sequence_no",
            "seq no.": "sequence_no",

            "nature of flight": "nature_of_flight",
            "next inspection due": "next_inspection_due",
            "tach time due": "tach_time_due",
            "no of lnd": "number_of_landings",
            "number of landings": "number_of_landings",

            "origin station": "origin_station",
            "origin date": "origin_date",
            "origin time": "origin_time",
            "destination station": "destination_station",
            "destination date": "destination_date",
            "destination time": "destination_time",

            "hobbs start": "hobbs_meter_start",
            "hobbs end": "hobbs_meter_end",
            "hobbs total": "hobbs_meter_total",
            "tach start": "tachometer_start",
            "tach end": "tachometer_end",
            "tach total": "tachometer_total",

            "airframe prev time": "airframe_prev_time",
            "airframe flight time": "airframe_flight_time",
            "airframe total time": "airframe_total_time",
            "run time": "airframe_run_time",
            "airframe run time": "airframe_run_time",
            "aftt": "airframe_aftt",

            "engine prev time": "engine_prev_time",
            "engine flight time": "engine_flight_time",
            "engine total time": "engine_total_time",
            "engine run time": "engine_run_time",
            "engine tsn": "engine_tsn",
            "engine tso": "engine_tso",
            "engine tbo": "engine_tbo",

            "propeller prev time": "propeller_prev_time",
            "propeller flight time": "propeller_flight_time",
            "propeller total time": "propeller_total_time",
            "propeller run time": "propeller_run_time",
            # typo in RP-12 fleet export template ("Propellee RUN TIME")
            "propellee run time": "propeller_run_time",
            "propeller tsn": "propeller_tsn",
            "propeller tso": "propeller_tso",
            "propeller tbo": "propeller_tbo",

            "life time limit engine": "life_time_limit_engine",
            "life time limit propeller": "life_time_limit_propeller",

            "fuel qty left uplift qty": "fuel_qty_left_uplift_qty",
            "fuel qty right uplift qty": "fuel_qty_right_uplift_qty",
            "fuel qty left prior departure": "fuel_qty_left_prior_departure",
            "fuel qty right prior departure": "fuel_qty_right_prior_departure",
            "fuel qty left after on blks": "fuel_qty_left_after_on_blks",
            "fuel qty right after on blks": "fuel_qty_right_after_on_blks",
            "oil qty uplift qty": "oil_qty_uplift_qty",
            "oil qty prior departure": "oil_qty_prior_departure",
            "oil qty after on blks": "oil_qty_after_on_blks",

            "remarks": "remarks",
            "action taken": "actions_taken",
            "remark person": "remark_person",
            "actiontaken person": "actiontaken_person",
            "pilot fk": "pilot_fk",
            "maintenance fk": "maintenance_fk",
            "pilot accepted by": "pilot_accepted_by",
            "pilot accept date": "pilot_accept_date",
            "pilot accept time": "pilot_accept_time",
            "rts signed by": "rts_signed_by",
            "rts date": "rts_date",
            "rts time": "rts_time",
            "date time reported": "date_time_reported",
            "date time released": "date_time_released",
            "white atl": "white_atl",
            "dfp": "dfp",
            "work status": "work_status",

            "part remove part no.": "removed_part_no",
            "part remove serial no.": "removed_serial_no",
            "part remove remaining time": "part_removed_remaining_time",
            "part install remaining time": "part_installed_remaining_time",
            "part install part no.": "installed_part_no",
            "part install serial no.": "installed_serial_no",
            "part description": "part_description",
            "part remark": "part_remark",
            "part qty": "part_qty",
            "part unit": "part_unit",
            "part nomenclature": "part_nomenclature",
            "ata chapter": "ata_chapter",
        },
        integrity_error_messages={
            "aircraft_fk": "Aircraft with this ID does not exist",
            "sequence_no": "ATL upsert conflict for sequence_no / batch / aircraft",
            "atl_batch_fk": "ATL batch does not exist",
        },
        audit_account_id=current_account.id,
    )
