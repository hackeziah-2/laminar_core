from typing import Any, Dict, List, Optional, Tuple
from datetime import date, time

from fastapi import HTTPException, Request
from sqlalchemy import select, or_, cast, String, Numeric, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.database import set_audit_fields
from app.core.atl_derived_times import ATL_AUTO_FIELD_KEYS, persist_atl_auto_fields_to_row
from app.core.atl_paged_rbac import atl_rbac_filter
from app.models.aircraft_techinical_log import (
    AircraftTechnicalLog,
    ComponentPartsRecord,
    TypeEnum,
    WorkStatus,
)
from app.models.atl_batch import AtlBatch
from app.models.aircraft import Aircraft
from app.models.account import AccountInformation
from app.models.audit_log import AuditAction
from app.services.audit_trail_service import create_audit_log, serialize_audit_data
from app.core.atl_edit_rbac import validate_atl_edit_allowed_for_account
from app.core.atl_workflow_rbac import is_atl_work_status_transition_allowed
from app.models.role import Role
from app.schemas.aircraft_technical_log_schema import (
    AircraftTechnicalLogCreate,
    AircraftTechnicalLogUpdate,
    AircraftTechnicalLogBulkWorkStatusUpdateResponse,
    AircraftTechnicalLogBulkWorkStatusUpdateItem,
    AircraftTechnicalLogBulkDeleteResponse,
    AircraftTechnicalLogBulkDeleteItem,
    ComponentPartsRecordCreate,
)

def _sequence_no_digits_only(sequence_no: str) -> str:
    """Normalize to number-only: strip optional leading 'ATL-', then whitespace. '001' or 'ATL-001' -> '001'. Stored value is digits only."""
    if not sequence_no or not str(sequence_no).strip():
        return sequence_no
    s = str(sequence_no).strip()
    if s.upper().startswith("ATL-"):
        s = s[4:].lstrip()
    return s


def _sequence_no_as_numeric():
    """SQL: sequence_no as Numeric for ORDER BY / comparisons. Handles '10001.0' (PostgreSQL INTEGER cast rejects it)."""
    return cast(AircraftTechnicalLog.sequence_no, Numeric)


_ATL_SORT_FIELD_ALIASES = {
    "sequenceno": "sequence_no",
    "aircraftregistration": "aircraft_registration",
    "registration": "aircraft_registration",
    "acreg": "aircraft_registration",
    "workstatus": "work_status",
    "createdat": "created_at",
    "updatedat": "updated_at",
    "origindate": "origin_date",
    "destinationdate": "destination_date",
    "originstation": "origin_station",
    "destinationstation": "destination_station",
    "airframeruntime": "airframe_run_time",
    "airframeaftt": "airframe_aftt",
    "engineruntime": "engine_run_time",
    "enginetsn": "engine_tsn",
    "enginetso": "engine_tso",
    "enginetbo": "engine_tbo",
    "propellerruntime": "propeller_run_time",
    "propellertsn": "propeller_tsn",
    "propellertso": "propeller_tso",
    "propellertbo": "propeller_tbo",
    "lifetimelimitengine": "life_time_limit_engine",
    "lifetimelimitpropeller": "life_time_limit_propeller",
}


def _resolve_atl_sort_field_name(field_name: str) -> str:
    """Map camelCase / case variants to snake_case sort keys."""
    stripped = field_name.strip()
    if not stripped:
        return stripped
    return _ATL_SORT_FIELD_ALIASES.get(stripped.casefold(), stripped)


def _normalize_atl_paged_sort(sort: Optional[str]) -> Optional[str]:
    """
    Normalize sort query for ATL paged endpoints.

    Accepts:
    - asc / desc (sequence_no only; matches /aircraft/{id}/atl/paged)
    - sequence_no / -sequence_no (and camelCase sequenceNo)
    - sequence_no:asc / sequence_no:desc
    - sequence_no asc / sequence_no desc (space-separated)
    """
    if sort is None:
        return None
    raw = str(sort).strip()
    if not raw:
        return None

    lower = raw.casefold()
    if lower in ("asc", "ascending"):
        return "sequence_no"
    if lower in ("desc", "descending"):
        return "-sequence_no"

    normalized_segments: List[str] = []
    for segment in raw.split(","):
        segment = segment.strip()
        if not segment:
            continue

        seg_lower = segment.casefold()
        if seg_lower in ("asc", "ascending"):
            normalized_segments.append("sequence_no")
            continue
        if seg_lower in ("desc", "descending"):
            normalized_segments.append("-sequence_no")
            continue

        if ":" in segment:
            field_part, _, dir_part = segment.partition(":")
            field_part = field_part.strip()
            dir_part = dir_part.strip().casefold()
            field_key = _resolve_atl_sort_field_name(field_part.lstrip("-"))
            if field_part.startswith("-") or dir_part in ("desc", "descending"):
                normalized_segments.append(f"-{field_key}")
            else:
                normalized_segments.append(field_key)
            continue

        if " " in segment:
            tokens = segment.split()
            field_token = tokens[0].strip()
            dir_token = tokens[-1].strip().casefold() if len(tokens) > 1 else ""
            field_key = _resolve_atl_sort_field_name(field_token.lstrip("-"))
            if field_token.startswith("-") or dir_token in ("desc", "descending"):
                normalized_segments.append(f"-{field_key}")
            else:
                normalized_segments.append(field_key)
            continue

        if segment.startswith("-"):
            normalized_segments.append(
                f"-{_resolve_atl_sort_field_name(segment[1:])}"
            )
        else:
            normalized_segments.append(_resolve_atl_sort_field_name(segment))

    return ",".join(normalized_segments) if normalized_segments else None


def _atl_paged_sortable_fields(*, include_aircraft: bool = False) -> dict:
    """Whitelisted ORDER BY columns for ATL paged list endpoints."""
    fields = {
        "created_at": AircraftTechnicalLog.created_at,
        "updated_at": AircraftTechnicalLog.updated_at,
        "sequence_no": _sequence_no_as_numeric(),
        "work_status": AircraftTechnicalLog.work_status,
        "origin_date": AircraftTechnicalLog.origin_date,
        "destination_date": AircraftTechnicalLog.destination_date,
        "origin_station": AircraftTechnicalLog.origin_station,
        "destination_station": AircraftTechnicalLog.destination_station,
        "airframe_run_time": AircraftTechnicalLog.airframe_run_time,
        "airframe_aftt": AircraftTechnicalLog.airframe_aftt,
        "engine_run_time": AircraftTechnicalLog.engine_run_time,
        "engine_tsn": AircraftTechnicalLog.engine_tsn,
        "engine_tso": AircraftTechnicalLog.engine_tso,
        "engine_tbo": AircraftTechnicalLog.engine_tbo,
        "propeller_run_time": AircraftTechnicalLog.propeller_run_time,
        "propeller_tsn": AircraftTechnicalLog.propeller_tsn,
        "propeller_tso": AircraftTechnicalLog.propeller_tso,
        "propeller_tbo": AircraftTechnicalLog.propeller_tbo,
        "life_time_limit_engine": AircraftTechnicalLog.life_time_limit_engine,
        "life_time_limit_propeller": AircraftTechnicalLog.life_time_limit_propeller,
    }
    if include_aircraft:
        fields["aircraft_registration"] = Aircraft.registration
    return fields


def _atl_paged_sort_needs_aircraft_join(sort: Optional[str]) -> bool:
    normalized_sort = _normalize_atl_paged_sort(sort)
    if not normalized_sort:
        return False
    for field in normalized_sort.split(","):
        field = field.strip()
        if not field:
            continue
        field_name = _resolve_atl_sort_field_name(field.lstrip("-"))
        if field_name == "aircraft_registration":
            return True
    return False


def _apply_atl_paged_sort(stmt, sort: Optional[str], *, aircraft_joined: bool = False):
    """Apply ORDER BY to ATL list stmt; default to numeric sequence_no desc."""
    needs_aircraft_join = _atl_paged_sort_needs_aircraft_join(sort)
    if needs_aircraft_join and not aircraft_joined:
        stmt = stmt.join(Aircraft, AircraftTechnicalLog.aircraft_fk == Aircraft.id)
        stmt = stmt.where(Aircraft.is_deleted == False)
        aircraft_joined = True

    sortable_fields = _atl_paged_sortable_fields(include_aircraft=aircraft_joined)
    normalized_sort = _normalize_atl_paged_sort(sort)
    order_clauses = []

    if normalized_sort:
        for field in normalized_sort.split(","):
            field = field.strip()
            if not field:
                continue
            desc_order = field.startswith("-")
            field_name = _resolve_atl_sort_field_name(field.lstrip("-"))
            column = sortable_fields.get(field_name)
            if column is None:
                continue
            order_clauses.append(column.desc() if desc_order else column.asc())

    if order_clauses:
        order_clauses.append(AircraftTechnicalLog.id.desc())
        return stmt.order_by(*order_clauses)

    return stmt.order_by(_sequence_no_as_numeric().desc(), AircraftTechnicalLog.id.desc())


def generate_range(start_id: str, end_id: str) -> list[str]:
    """
    Generate a list of sequence numbers between start_id and end_id (exclusive). Number-only.
    Example: 0001 -> 0008 returns 0002 to 0007. Accepts digits-only or leading ATL- (stripped).
    """
    start_id = _sequence_no_digits_only(start_id)
    end_id = _sequence_no_digits_only(end_id)
    if not start_id or not end_id:
        return []
    try:
        start_num = int(start_id)
        end_num = int(end_id)
    except ValueError:
        return []
    width = max(len(start_id), len(end_id))
    return [str(i).zfill(width) for i in range(start_num + 1, end_num)]


async def _get_previous_meter_starts(
    session: AsyncSession,
    aircraft_fk: int,
    sequence_no: str,
    atl_batch_fk: Optional[int] = None,
) -> tuple[float, float]:
    """Return hobbs/tach start defaults from the previous ATL in the same aircraft + batch stream."""
    prev_atl = await get_previous_atl(
        session, aircraft_fk, sequence_no, atl_batch_fk=atl_batch_fk
    )
    if not prev_atl:
        return 0.0, 0.0
    return (
        float(prev_atl.hobbs_meter_end or 0.0),
        float(prev_atl.tachometer_end or 0.0),
    )


def _atl_update_payload_from_schema(log_in: AircraftTechnicalLogUpdate) -> dict:
    ex = {"component_parts"}
    if hasattr(log_in, "model_dump"):
        return log_in.model_dump(exclude_unset=True, exclude=ex)  # type: ignore[call-arg]
    return log_in.dict(exclude_unset=True, exclude=ex)  # type: ignore[call-arg]


def _component_part_to_dict(part_data: ComponentPartsRecordCreate) -> dict:
    if hasattr(part_data, "model_dump"):
        return part_data.model_dump(exclude_unset=True)  # type: ignore[union-attr]
    return part_data.dict(exclude_unset=True)


async def _validate_atl_batch_fk(
    session: AsyncSession,
    atl_batch_fk: Optional[int],
) -> None:
    if atl_batch_fk is None:
        return
    batch = await session.get(AtlBatch, atl_batch_fk)
    if not batch or batch.is_deleted:
        raise HTTPException(status_code=400, detail="ATL batch not found")


async def _atl_exists_same_aircraft_sequence_batch(
    session: AsyncSession,
    *,
    aircraft_fk: int,
    sequence_no: str,
    atl_batch_fk: Optional[int],
) -> bool:
    """True if a non-deleted ATL exists for this aircraft, sequence, and batch (NULL batch matches NULL only)."""
    q = (
        select(AircraftTechnicalLog.id)
        .where(AircraftTechnicalLog.sequence_no == sequence_no)
        .where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
    )
    if atl_batch_fk is None:
        q = q.where(AircraftTechnicalLog.atl_batch_fk.is_(None))
    else:
        q = q.where(AircraftTechnicalLog.atl_batch_fk == atl_batch_fk)
    return (await session.scalar(q)) is not None


def _clean_atl_update_data(update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize sequence, enums, strip client auto_*, coerce work_status / nature_of_flight."""
    if "sequence_no" in update_data and update_data["sequence_no"]:
        update_data["sequence_no"] = _sequence_no_digits_only(str(update_data["sequence_no"]))

    if "nature_of_flight" in update_data:
        nf = update_data["nature_of_flight"]
        if nf is None:
            update_data["nature_of_flight"] = None
        elif isinstance(nf, str):
            s = nf.strip()
            if not s or s == "-":
                update_data["nature_of_flight"] = None
            else:
                update_data["nature_of_flight"] = TypeEnum(
                    s.upper().replace(" ", "_")
                )
        elif isinstance(nf, TypeEnum):
            pass

    if "work_status" in update_data:
        ws = update_data["work_status"]
        if ws is not None and isinstance(ws, str):
            update_data["work_status"] = WorkStatus(ws)
        # None or already WorkStatus: keep

    for field in ATL_AUTO_FIELD_KEYS:
        update_data.pop(field, None)

    return update_data


async def _resolve_account_role_name(
    session: AsyncSession,
    current_account: Optional[AccountInformation],
) -> Optional[str]:
    if not current_account or not current_account.role_id:
        return None
    role = await session.get(Role, current_account.role_id)
    if role and not role.is_deleted:
        return role.name
    return None


async def _validate_atl_edit_rbac(
    *,
    session: AsyncSession,
    obj: AircraftTechnicalLog,
    update_data: dict,
    current_account: Optional[AccountInformation],
) -> None:
    role_name = await _resolve_account_role_name(session, current_account)
    try:
        validate_atl_edit_allowed_for_account(
            role_name=role_name,
            current_status=obj.work_status,
            update_data=update_data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


async def _validate_work_status_transition(
    *,
    session: AsyncSession,
    obj: AircraftTechnicalLog,
    update_data: dict,
    current_account: Optional[AccountInformation],
) -> None:
    if "work_status" not in update_data:
        return
    role_name = await _resolve_account_role_name(session, current_account)
    next_status = update_data["work_status"]
    if not is_atl_work_status_transition_allowed(
        role_name=role_name,
        current_status=obj.work_status,
        next_status=next_status,
    ):
        current_value = obj.work_status.value if obj.work_status else "NULL"
        next_value = next_status.value if next_status else "NULL"
        raise HTTPException(
            status_code=403,
            detail=(
                f"Role '{role_name}' cannot change work_status "
                f"from '{current_value}' to '{next_value}'."
            ),
        )


async def _apply_meter_start_defaults_if_needed(
    *,
    session: AsyncSession,
    obj: AircraftTechnicalLog,
    update_data: dict,
) -> None:
    target_aircraft_fk = update_data.get("aircraft_fk", obj.aircraft_fk)
    target_sequence_no = update_data.get("sequence_no", obj.sequence_no)
    should_refresh = (
        target_aircraft_fk != obj.aircraft_fk
        or target_sequence_no != obj.sequence_no
        or obj.hobbs_meter_start is None
        or obj.tachometer_start is None
    )
    if not should_refresh:
        return
    need_hobbs = "hobbs_meter_start" not in update_data
    need_tach = "tachometer_start" not in update_data
    if not need_hobbs and not need_tach:
        return
    target_atl_batch_fk = (
        update_data["atl_batch_fk"]
        if "atl_batch_fk" in update_data
        else obj.atl_batch_fk
    )
    prev_hobbs_start, prev_tach_start = await _get_previous_meter_starts(
        session,
        target_aircraft_fk,
        str(target_sequence_no) if target_sequence_no is not None else "",
        atl_batch_fk=target_atl_batch_fk,
    )
    if need_hobbs:
        update_data["hobbs_meter_start"] = prev_hobbs_start
    if need_tach:
        update_data["tachometer_start"] = prev_tach_start


async def _replace_atl_component_parts(
    *,
    session: AsyncSession,
    atl_id: int,
    component_parts: List[ComponentPartsRecordCreate],
    audit_account_id: Optional[int] = None,
) -> None:
    existing_res = await session.execute(
        select(ComponentPartsRecord).where(ComponentPartsRecord.atl_fk == atl_id)
    )
    for part in existing_res.scalars().all():
        await session.delete(part)
    await session.flush()
    for part_data in component_parts:
        data = _component_part_to_dict(part_data)
        data.pop("atl_fk", None)
        row = ComponentPartsRecord(atl_fk=atl_id, **data)
        if audit_account_id is not None:
            await set_audit_fields(row, audit_account_id, is_create=True)
        session.add(row)


async def create_aircraft_technical_log(
    session: AsyncSession,
    data: AircraftTechnicalLogCreate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> AircraftTechnicalLog:
    """Create a new Aircraft Technical Log entry with optional gap-fill (skipped when first ATL for aircraft/batch stream). Sequence numbers stored as number only (e.g. 001). Persists auto_* via compute_auto_fields before insert."""
    sequence_no = _sequence_no_digits_only(data.sequence_no)
    if await _atl_exists_same_aircraft_sequence_batch(
        session,
        aircraft_fk=data.aircraft_fk,
        sequence_no=sequence_no,
        atl_batch_fk=data.atl_batch_fk,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Sequence No. {sequence_no} already exists for this aircraft and ATL batch. Please use a different Sequence No.",
        )

    # Prepare log data dictionary (server owns auto_*; always recomputed in persist)
    log_data = data.dict(exclude={'component_parts'})
    for k in ATL_AUTO_FIELD_KEYS:
        log_data.pop(k, None)
    # nature_of_flight: empty string or "" -> NULL in DB; otherwise preserve from payload
    nf = log_data.get('nature_of_flight')
    if nf is None or (isinstance(nf, str) and (not str(nf).strip() or str(nf).strip() == "-")):
        log_data['nature_of_flight'] = None
    elif isinstance(nf, str):
        log_data['nature_of_flight'] = TypeEnum(nf)
    if data.nature_of_flight is not None:
        log_data['nature_of_flight'] = data.nature_of_flight
    else:
        log_data['nature_of_flight'] = None  # ensure NULL when empty/omitted

    # work_status: explicit FOR_REVIEW when omitted (matches intended lifecycle; avoids NULL so RBAC/list filters apply)
    ws = log_data.get('work_status')
    if ws is not None:
        if isinstance(ws, str):
            log_data['work_status'] = WorkStatus(ws)
        else:
            log_data['work_status'] = ws
    else:
        log_data['work_status'] = WorkStatus.FOR_REVIEW

    await _validate_atl_batch_fk(session, log_data.get("atl_batch_fk"))

    # Latest sequence in the same aircraft + batch stream (NULL batch only groups NULL atl_batch_fk rows)
    latest_stmt = (
        select(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.aircraft_fk == data.aircraft_fk)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
    )
    if data.atl_batch_fk is None:
        latest_stmt = latest_stmt.where(AircraftTechnicalLog.atl_batch_fk.is_(None))
    else:
        latest_stmt = latest_stmt.where(AircraftTechnicalLog.atl_batch_fk == data.atl_batch_fk)
    latest_stmt = latest_stmt.order_by(_sequence_no_as_numeric().desc()).limit(1)
    latest_result = await session.execute(latest_stmt)
    latest_atl = latest_result.scalar_one_or_none()
    latest_sequence_no = latest_atl.sequence_no if latest_atl else None

    # Auto-populate hobbs_meter_start and tachometer_start from the previous ATL by sequence_no.
    if log_data.get('hobbs_meter_start') is None or log_data.get('tachometer_start') is None:
        prev_hobbs_start, prev_tach_start = await _get_previous_meter_starts(
            session, data.aircraft_fk, sequence_no, atl_batch_fk=data.atl_batch_fk
        )
        if log_data.get('hobbs_meter_start') is None:
            log_data['hobbs_meter_start'] = prev_hobbs_start
        if log_data.get('tachometer_start') is None:
            log_data['tachometer_start'] = prev_tach_start

    # Create the main ATL entry (use model, not schema); store sequence_no as number only
    entry = AircraftTechnicalLog(**{**log_data, 'sequence_no': sequence_no})
    # Persist NULL when empty/omitted; otherwise use validated value
    entry.nature_of_flight = data.nature_of_flight if data.nature_of_flight is not None else None
    aircraft_row = await session.get(Aircraft, data.aircraft_fk)
    await persist_atl_auto_fields_to_row(session, entry, aircraft_row)
    session.add(entry)
    await session.flush()

    # Generate missing sequence IDs only when there is existing data (skip when first ATL for aircraft)
    if latest_sequence_no is not None:
        try:
            missing_sequences = generate_range(latest_sequence_no, sequence_no)
        except (ValueError, IndexError):
            missing_sequences = []
        if missing_sequences:
            for seq_no in missing_sequences:
                if await _atl_exists_same_aircraft_sequence_batch(
                    session,
                    aircraft_fk=data.aircraft_fk,
                    sequence_no=seq_no,
                    atl_batch_fk=data.atl_batch_fk,
                ):
                    continue
                gap_entry = AircraftTechnicalLog(
                    sequence_no=seq_no,
                    aircraft_fk=data.aircraft_fk,
                    atl_batch_fk=data.atl_batch_fk,
                    work_status=WorkStatus.FOR_REVIEW,
                )
                prev_hobbs, prev_tach = await _get_previous_meter_starts(
                    session, data.aircraft_fk, seq_no, atl_batch_fk=data.atl_batch_fk
                )
                gap_entry.hobbs_meter_start = prev_hobbs
                gap_entry.tachometer_start = prev_tach
                # await persist_atl_auto_fields_to_row(session, gap_entry, aircraft_row) Range auto complete
                if audit_account_id is not None:
                    await set_audit_fields(gap_entry, audit_account_id, is_create=True)
                session.add(gap_entry)
                await session.flush()

    # Create component parts if provided
    if data.component_parts:
        for part_data in data.component_parts:
            pdata = (
                part_data.model_dump()
                if hasattr(part_data, "model_dump")
                else part_data.dict()
            )
            pdata.pop("atl_fk", None)
            part = ComponentPartsRecord(atl_fk=entry.id, **pdata)
            session.add(part)
            if audit_account_id is not None:
                await set_audit_fields(part, audit_account_id, is_create=True)

    if audit_account_id is not None:
        await set_audit_fields(entry, audit_account_id, is_create=True)

    await session.commit()
    await session.refresh(entry)
    await session.refresh(entry, ['aircraft', 'component_parts'])

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=entry.id,
            action=AuditAction.CREATE,
            old_data=None,
            new_data=entry,
            current_user=audit_user,
            request=audit_request,
        )

    return entry

def _normalize_atl_search(search: str) -> str:
    """Normalize ATL sequence search: strip and optionally remove leading 'ATL-' so 'ATL-24451' or '24451' both match."""
    s = str(search).strip()
    if not s:
        return s
    if s.upper().startswith("ATL-"):
        s = s[4:].strip() or s
    return s


async def search_atl_by_sequence_no(
    session: AsyncSession,
    search: str,
    aircraft_fk: Optional[int] = None,
    limit: int = 50,
) -> List[AircraftTechnicalLog]:
    """Search Aircraft Technical Log by ATL Sequence Number. Optionally filter by aircraft. Returns list with aircraft loaded. Accepts 'ATL-24451' or '24451'."""
    if not search or not str(search).strip():
        return []
    normalized = _normalize_atl_search(search)
    q = f"%{normalized}%"
    stmt = (
        select(AircraftTechnicalLog)
        .options(
            selectinload(AircraftTechnicalLog.aircraft),
            selectinload(AircraftTechnicalLog.atl_batch),
        )
        .where(AircraftTechnicalLog.is_deleted == False)
        .where(AircraftTechnicalLog.sequence_no.ilike(q))
        .order_by(_sequence_no_as_numeric().asc())
        .limit(limit)
    )
    if aircraft_fk is not None:
        stmt = stmt.where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_aircraft_technical_log(
    session: AsyncSession,
    id: int
) -> Optional[AircraftTechnicalLog]:
    """Get an Aircraft Technical Log entry by ID."""
    result = await session.execute(
        select(AircraftTechnicalLog)
        .options(
            selectinload(AircraftTechnicalLog.aircraft),
            selectinload(AircraftTechnicalLog.atl_batch),
            selectinload(AircraftTechnicalLog.component_parts)
        )
        .where(AircraftTechnicalLog.id == id)
        .where(AircraftTechnicalLog.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None
    return obj


async def update_aircraft_technical_log(
    session: AsyncSession,
    log_id: int,
    log_in: AircraftTechnicalLogUpdate,
    *,
    audit_account_id: Optional[int] = None,
    current_account: Optional[AccountInformation] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[AircraftTechnicalLog]:
    """Update an Aircraft Technical Log entry. Re-persists auto_* via compute_auto_fields after field updates."""
    obj = await session.get(AircraftTechnicalLog, log_id)
    if not obj or obj.is_deleted:
        return None

    old_data_snapshot = serialize_audit_data(obj)
    update_data = _atl_update_payload_from_schema(log_in)
    update_data = _clean_atl_update_data(update_data)

    await _validate_atl_edit_rbac(
        session=session,
        obj=obj,
        update_data=update_data,
        current_account=current_account,
    )
    await _validate_work_status_transition(
        session=session,
        obj=obj,
        update_data=update_data,
        current_account=current_account,
    )
    await _apply_meter_start_defaults_if_needed(
        session=session,
        obj=obj,
        update_data=update_data,
    )

    if "atl_batch_fk" in update_data:
        await _validate_atl_batch_fk(session, update_data.get("atl_batch_fk"))

    for field, value in update_data.items():
        setattr(obj, field, value)

    aircraft_row = (
        await session.get(Aircraft, obj.aircraft_fk) if obj.aircraft_fk is not None else None
    )
    await persist_atl_auto_fields_to_row(session, obj, aircraft_row)

    if log_in.component_parts is not None:
        await _replace_atl_component_parts(
            session=session,
            atl_id=log_id,
            component_parts=log_in.component_parts,
            audit_account_id=audit_account_id,
        )

    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=False)
    session.add(obj)
    await session.commit()

    result = await session.execute(
        select(AircraftTechnicalLog)
        .options(
            selectinload(AircraftTechnicalLog.aircraft),
            selectinload(AircraftTechnicalLog.atl_batch),
            selectinload(AircraftTechnicalLog.component_parts),
        )
        .where(AircraftTechnicalLog.id == log_id)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
    )
    reloaded = result.scalar_one_or_none()

    if reloaded and audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=reloaded.id,
            action=AuditAction.UPDATE,
            old_data=old_data_snapshot,
            new_data=reloaded,
            current_user=audit_user or current_account,
            request=audit_request,
        )

    return reloaded


async def bulk_update_aircraft_technical_log_work_status(
    session: AsyncSession,
    *,
    atl_ids: List[int],
    work_status: WorkStatus,
    atomic: bool = False,
    audit_account_id: Optional[int] = None,
    current_account: Optional[AccountInformation] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> AircraftTechnicalLogBulkWorkStatusUpdateResponse:
    """Bulk update ATL work_status with optional atomic rollback behavior."""
    unique_ids = list(dict.fromkeys(atl_ids))
    if not unique_ids:
        raise HTTPException(status_code=400, detail="ids must not be empty")

    result_items: List[AircraftTechnicalLogBulkWorkStatusUpdateItem] = []
    updated_count = 0
    touched_rows: List[Tuple[AircraftTechnicalLog, Optional[Dict[str, Any]]]] = []

    rows_result = await session.execute(
        select(AircraftTechnicalLog).where(AircraftTechnicalLog.id.in_(unique_ids))
    )
    row_map = {
        row.id: row
        for row in rows_result.scalars().all()
    }

    for atl_id in unique_ids:
        obj = row_map.get(atl_id)
        if not obj or obj.is_deleted:
            if atomic:
                await session.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"ATL id {atl_id} not found",
                )
            result_items.append(
                AircraftTechnicalLogBulkWorkStatusUpdateItem(
                    id=atl_id,
                    success=False,
                    message="ATL not found",
                )
            )
            continue

        try:
            await _validate_work_status_transition(
                session=session,
                obj=obj,
                update_data={"work_status": work_status},
                current_account=current_account,
            )
            old_data_snapshot = serialize_audit_data(obj)
            obj.work_status = work_status
            if audit_account_id is not None:
                await set_audit_fields(obj, audit_account_id, is_create=False)
            session.add(obj)
            touched_rows.append((obj, old_data_snapshot))
            updated_count += 1
            result_items.append(
                AircraftTechnicalLogBulkWorkStatusUpdateItem(
                    id=atl_id,
                    success=True,
                    message="Updated",
                )
            )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            if atomic:
                await session.rollback()
                raise HTTPException(status_code=exc.status_code, detail=detail)
            result_items.append(
                AircraftTechnicalLogBulkWorkStatusUpdateItem(
                    id=atl_id,
                    success=False,
                    message=detail,
                )
            )
        except Exception as exc:
            if atomic:
                await session.rollback()
                raise HTTPException(status_code=500, detail=str(exc))
            result_items.append(
                AircraftTechnicalLogBulkWorkStatusUpdateItem(
                    id=atl_id,
                    success=False,
                    message=str(exc),
                )
            )

    if touched_rows:
        await session.commit()
    else:
        await session.rollback()

    if touched_rows and audit_module_name and audit_table_name:
        for obj, old_data_snapshot in touched_rows:
            await create_audit_log(
                db=session,
                module_name=audit_module_name,
                table_name=audit_table_name,
                record_id=obj.id,
                action=AuditAction.BULK_UPDATE,
                old_data=old_data_snapshot,
                new_data=obj,
                current_user=audit_user or current_account,
                request=audit_request,
            )

    return AircraftTechnicalLogBulkWorkStatusUpdateResponse(
        updated_count=updated_count,
        failed_count=len(unique_ids) - updated_count,
        results=result_items,
    )


async def get_previous_atl(
    session: AsyncSession,
    aircraft_fk: int,
    sequence_no: str,
    *,
    atl_batch_fk: Optional[int] = None,
    null_batch_only_when_batch_unset: bool = True,
) -> Optional[AircraftTechnicalLog]:
    """Immediate predecessor (highest sequence_no strictly less than given) for aircraft (+ batch scope)."""
    sequence_no = _sequence_no_digits_only(sequence_no)
    try:
        sequence_no_int = int(sequence_no)
    except (TypeError, ValueError):
        return None
    stmt = (
        select(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
        .where(_sequence_no_as_numeric() < sequence_no_int)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
    )
    if atl_batch_fk is not None:
        stmt = stmt.where(AircraftTechnicalLog.atl_batch_fk == atl_batch_fk)
    elif null_batch_only_when_batch_unset:
        stmt = stmt.where(AircraftTechnicalLog.atl_batch_fk.is_(None))
    stmt = stmt.order_by(_sequence_no_as_numeric().desc()).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def fetch_predecessors_for_atl(
    session: AsyncSession,
    aircraft_fk: int,
    sequence_no: str,
    *,
    atl_batch_fk: Optional[int] = None,
) -> List[AircraftTechnicalLog]:
    """All predecessors for one ATL stream in ascending numeric sequence (single query)."""
    sequence_no = _sequence_no_digits_only(sequence_no)
    try:
        sequence_no_int = int(sequence_no)
    except (TypeError, ValueError):
        return []
    stmt = (
        select(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
        .where(_sequence_no_as_numeric() < sequence_no_int)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
    )
    if atl_batch_fk is None:
        stmt = stmt.where(AircraftTechnicalLog.atl_batch_fk.is_(None))
    else:
        stmt = stmt.where(AircraftTechnicalLog.atl_batch_fk == atl_batch_fk)
    stmt = stmt.order_by(_sequence_no_as_numeric().asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_atls_for_scope_ordered(
    session: AsyncSession,
    aircraft_fk: int,
    *,
    atl_batch_fk: Optional[int] = None,
) -> List[AircraftTechnicalLog]:
    """All non-deleted ATLs for aircraft (+ optional batch), ascending by numeric sequence_no."""
    stmt = (
        select(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
    )
    if atl_batch_fk is None:
        stmt = stmt.where(AircraftTechnicalLog.atl_batch_fk.is_(None))
    else:
        stmt = stmt.where(AircraftTechnicalLog.atl_batch_fk == atl_batch_fk)
    stmt = stmt.order_by(_sequence_no_as_numeric().asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_atl_paged(
    session: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    search: Optional[str] = None,
    nature_of_flight: Optional[str] = None,
    sort_sequence: str = "asc",
    aircraft_fk: Optional[int] = None,
) -> Tuple[List[AircraftTechnicalLog], int]:
    """List ATL entries for /api/v1/aircraft/{aircraft_id}/atl/paged: search by sequence_no, filter by nature_of_flight, sort by sequence_no, always filter by aircraft_fk when provided."""
    # Exclude soft-deleted ATL (is_deleted = True must not be included); exclude ATLs whose aircraft is soft-deleted
    stmt = (
        select(AircraftTechnicalLog)
        .options(
            selectinload(AircraftTechnicalLog.aircraft),
            selectinload(AircraftTechnicalLog.atl_batch),
            selectinload(AircraftTechnicalLog.component_parts)
        )
        .join(Aircraft, AircraftTechnicalLog.aircraft_fk == Aircraft.id)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
        .where(Aircraft.is_deleted.is_(False))
    )
    if aircraft_fk is not None:
        stmt = stmt.where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
    if search and str(search).strip():
        q = f"%{_sequence_no_digits_only(search.strip())}%"
        stmt = stmt.where(AircraftTechnicalLog.sequence_no.ilike(q))
    if nature_of_flight and str(nature_of_flight).strip():
        try:
            nf = TypeEnum(nature_of_flight.strip().upper().replace(" ", "_"))
            stmt = stmt.where(AircraftTechnicalLog.nature_of_flight == nf)
        except ValueError:
            pass
    if sort_sequence.lower() == "desc":
        stmt = stmt.order_by(_sequence_no_as_numeric().desc())
    else:
        stmt = stmt.order_by(_sequence_no_as_numeric().asc())

    count_stmt = (
        select(func.count())
        .select_from(AircraftTechnicalLog)
        .join(Aircraft, AircraftTechnicalLog.aircraft_fk == Aircraft.id)
        .where(AircraftTechnicalLog.is_deleted.is_(False))
        .where(Aircraft.is_deleted.is_(False))
    )
    if aircraft_fk is not None:
        count_stmt = count_stmt.where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)
    if search and str(search).strip():
        q = f"%{_sequence_no_digits_only(search.strip())}%"
        count_stmt = count_stmt.where(AircraftTechnicalLog.sequence_no.ilike(q))
    if nature_of_flight and str(nature_of_flight).strip():
        try:
            nf = TypeEnum(nature_of_flight.strip().upper().replace(" ", "_"))
            count_stmt = count_stmt.where(AircraftTechnicalLog.nature_of_flight == nf)
        except ValueError:
            pass

    total = (await session.execute(count_stmt)).scalar()
    total = int(total) if total is not None else 0
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


def _build_aircraft_technical_logs_list_statements(
    search: Optional[str] = None,
    aircraft_fk: Optional[int] = None,
    atl_batch_fk: Optional[int] = None,
    sort: Optional[str] = "-sequence_no",
) -> Tuple:
    """Build list/count statements shared by ATL paged endpoints."""
    stmt = (
        select(AircraftTechnicalLog)
        .options(
            selectinload(AircraftTechnicalLog.aircraft),
            selectinload(AircraftTechnicalLog.atl_batch),
            selectinload(AircraftTechnicalLog.component_parts)
        )
        .where(AircraftTechnicalLog.is_deleted == False)
    )

    # Filter by aircraft
    if aircraft_fk:
        stmt = stmt.where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)

    if atl_batch_fk is not None:
        stmt = stmt.where(AircraftTechnicalLog.atl_batch_fk == atl_batch_fk)

    aircraft_joined = False

    # Search functionality; sequence_no stored as number only, so strip ATL- from search for that field
    if search:
        q = f"%{search}%"
        q_seq = f"%{_sequence_no_digits_only(search)}%"
        # Join Aircraft table for registration search
        stmt = stmt.join(Aircraft, AircraftTechnicalLog.aircraft_fk == Aircraft.id)
        stmt = stmt.where(Aircraft.is_deleted == False)
        aircraft_joined = True
        stmt = stmt.where(
            or_(
                AircraftTechnicalLog.sequence_no.ilike(q_seq),
                AircraftTechnicalLog.origin_station.ilike(q),
                AircraftTechnicalLog.destination_station.ilike(q),
                cast(AircraftTechnicalLog.nature_of_flight, String).ilike(q),
                Aircraft.registration.ilike(q),
            )
        )

    stmt = _apply_atl_paged_sort(stmt, sort, aircraft_joined=aircraft_joined)

    # Total count query (same filters, no ORDER BY)
    count_stmt = (
        select(func.count())
        .select_from(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.is_deleted == False)
    )

    if aircraft_fk:
        count_stmt = count_stmt.where(
            AircraftTechnicalLog.aircraft_fk == aircraft_fk
        )

    if atl_batch_fk is not None:
        count_stmt = count_stmt.where(
            AircraftTechnicalLog.atl_batch_fk == atl_batch_fk
        )

    if search:
        q = f"%{search}%"
        q_seq = f"%{_sequence_no_digits_only(search)}%"
        # Join Aircraft table for registration search in count query
        count_stmt = count_stmt.join(
            Aircraft, AircraftTechnicalLog.aircraft_fk == Aircraft.id
        )
        count_stmt = count_stmt.where(Aircraft.is_deleted == False)
        count_stmt = count_stmt.where(
            or_(
                AircraftTechnicalLog.sequence_no.ilike(q_seq),
                AircraftTechnicalLog.origin_station.ilike(q),
                AircraftTechnicalLog.destination_station.ilike(q),
                cast(AircraftTechnicalLog.nature_of_flight, String).ilike(q),
                Aircraft.registration.ilike(q),
            )
        )

    return stmt, count_stmt


async def list_aircraft_technical_logs(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    aircraft_fk: Optional[int] = None,
    atl_batch_fk: Optional[int] = None,
    work_status: Optional[WorkStatus] = None,
    sort: Optional[str] = "-sequence_no",
) -> Tuple[List[AircraftTechnicalLog], int]:
    """List Aircraft Technical Log entries with pagination."""
    stmt, count_stmt = _build_aircraft_technical_logs_list_statements(
        search=search,
        aircraft_fk=aircraft_fk,
        atl_batch_fk=atl_batch_fk,
        sort=sort,
    )

    if work_status:
        stmt = stmt.where(AircraftTechnicalLog.work_status == work_status)
        count_stmt = count_stmt.where(AircraftTechnicalLog.work_status == work_status)

    total = (await session.execute(count_stmt)).scalar()
    total = int(total) if total is not None else 0

    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total


@atl_rbac_filter()
async def list_aircraft_technical_logs_manage(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    aircraft_fk: Optional[int] = None,
    atl_batch_fk: Optional[int] = None,
    work_status: Optional[WorkStatus] = None,
    sort: Optional[str] = "-sequence_no",
    current_account: Optional[AccountInformation] = None,
) -> Tuple[List[AircraftTechnicalLog], int]:
    """List ATL entries for the manage paged endpoint with RBAC applied by decorator."""
    stmt, count_stmt = _build_aircraft_technical_logs_list_statements(
        search=search,
        aircraft_fk=aircraft_fk,
        atl_batch_fk=atl_batch_fk,
        sort=sort,
    )
    return stmt, count_stmt


async def get_latest_aircraft_technical_log(
    session: AsyncSession,
    aircraft_fk: Optional[int] = None,
    atl_batch_fk: Optional[int] = None,
) -> Optional[AircraftTechnicalLog]:
    """Get the latest ATL for aircraft (+ optional batch) by highest numeric sequence_no."""
    stmt = (
        select(AircraftTechnicalLog)
        .options(
            selectinload(AircraftTechnicalLog.aircraft),
            selectinload(AircraftTechnicalLog.atl_batch),
            selectinload(AircraftTechnicalLog.component_parts)
        )
        .where(AircraftTechnicalLog.is_deleted == False)
    )

    if aircraft_fk is not None:
        stmt = stmt.where(AircraftTechnicalLog.aircraft_fk == aircraft_fk)

    if atl_batch_fk is not None:
        stmt = stmt.where(AircraftTechnicalLog.atl_batch_fk == atl_batch_fk)

    stmt = stmt.order_by(_sequence_no_as_numeric().desc()).limit(1)
    
    result = await session.execute(stmt)
    obj = result.scalar_one_or_none()
    
    if not obj:
        return None

    return obj


async def soft_delete_aircraft_technical_log(
    session: AsyncSession,
    log_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    """Soft delete an Aircraft Technical Log entry."""
    obj = await session.get(AircraftTechnicalLog, log_id)
    if not obj or obj.is_deleted:
        return False

    old_data_snapshot = serialize_audit_data(obj)
    obj.soft_delete()
    session.add(obj)
    await session.commit()

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=log_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True


async def bulk_soft_delete_aircraft_technical_logs(
    session: AsyncSession,
    *,
    atl_ids: List[int],
    atomic: bool = False,
    audit_account_id: Optional[int] = None,
) -> AircraftTechnicalLogBulkDeleteResponse:
    """Bulk soft-delete ATL entries with optional atomic rollback behavior."""
    unique_ids = list(dict.fromkeys(atl_ids))
    if not unique_ids:
        raise HTTPException(status_code=400, detail="ids must not be empty")

    result_items: List[AircraftTechnicalLogBulkDeleteItem] = []
    deleted_count = 0
    touched_rows: List[AircraftTechnicalLog] = []

    rows_result = await session.execute(
        select(AircraftTechnicalLog).where(AircraftTechnicalLog.id.in_(unique_ids))
    )
    row_map = {row.id: row for row in rows_result.scalars().all()}

    for atl_id in unique_ids:
        obj = row_map.get(atl_id)
        if not obj or obj.is_deleted:
            if atomic:
                await session.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"ATL id {atl_id} not found",
                )
            result_items.append(
                AircraftTechnicalLogBulkDeleteItem(
                    id=atl_id,
                    success=False,
                    message="ATL not found",
                )
            )
            continue

        obj.soft_delete()
        if audit_account_id is not None:
            await set_audit_fields(obj, audit_account_id, is_create=False)
        session.add(obj)
        touched_rows.append(obj)
        deleted_count += 1
        result_items.append(
            AircraftTechnicalLogBulkDeleteItem(
                id=atl_id,
                success=True,
                message="Deleted",
            )
        )

    if touched_rows:
        await session.commit()
    else:
        await session.rollback()

    return AircraftTechnicalLogBulkDeleteResponse(
        deleted_count=deleted_count,
        failed_count=len(unique_ids) - deleted_count,
        results=result_items,
    )
