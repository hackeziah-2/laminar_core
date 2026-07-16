"""Bulk persistence for ATL Excel import."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_audit_fields
from app.models.aircraft_techinical_log import AircraftTechnicalLog, WorkStatus
from app.repository.aircraft_technical_log import _replace_atl_component_parts
from app.repository.excel_import import model_column_names, validated_to_dict
from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogImportSchema
from app.services.atl_import_date_time_reported import (
    apply_date_time_reported_resolution,
    resolve_date_time_reported,
)
from app.services.atl_import_references import AtlImportReferences

MODEL = AircraftTechnicalLog
_MODEL_COLUMNS = model_column_names(MODEL)
_IMPORT_ONLY_KEYS = frozenset(
    {
        "atl_date_time_reported_provided",
        "atl_date_time_reported_issue",
        "component_parts",
    }
)


def _is_patchable_import_value(value: Any) -> bool:
    """True when an imported cell should update an existing DB field (PATCH semantics)."""
    return value not in (None, "")


def _model_payload_from_validated(
    validated: AircraftTechnicalLogImportSchema,
    *,
    patch: bool,
) -> Dict[str, Any]:
    """
    Build a DB column payload from a validated import row.

    When ``patch`` is True (existing ATL), only non-empty imported values are included
    so empty/missing Excel cells do not clear existing database fields.
    """
    data = validated_to_dict(validated)
    payload: Dict[str, Any] = {}
    for key in _MODEL_COLUMNS:
        if key not in data or key in _IMPORT_ONLY_KEYS:
            continue
        value = data[key]
        if patch and not _is_patchable_import_value(value):
            continue
        payload[key] = value
    # Date Time Reported is applied via scenario logic, never via blind setattr.
    payload.pop("atl_date_time_reported", None)
    return payload


async def bulk_upsert_atl_import_rows(
    session: AsyncSession,
    validated_rows: List[Tuple[int, AircraftTechnicalLogImportSchema]],
    *,
    references: AtlImportReferences,
    audit_account_id: Optional[int] = None,
) -> Tuple[int, int]:
    """
    Insert or update all validated ATL rows without per-row SELECT queries.

    Updates use PATCH semantics: only fields with valid non-empty imported values
    are written; empty/NULL/blank Excel cells leave existing DB values unchanged.

    Returns (inserted_count, updated_count).
    """
    inserted = 0
    updated = 0
    parts_targets: List[Tuple[AircraftTechnicalLogImportSchema, AircraftTechnicalLog]] = []

    for _excel_row, validated in validated_rows:
        seq = validated.sequence_no
        existing = references.existing_by_sequence.get(seq)
        reported_provided = bool(
            getattr(validated, "atl_date_time_reported_provided", False)
        )
        resolution = None

        if existing is not None:
            payload = _model_payload_from_validated(validated, patch=True)
            if reported_provided:
                # Resolve against existing origin_* BEFORE payload mutates them.
                resolution = resolve_date_time_reported(
                    existing=existing,
                    imported_dt=validated.atl_date_time_reported,
                )
                # Never overwrite existing origin via Excel payload race.
                payload.pop("origin_date", None)
                payload.pop("origin_time", None)

            for key, value in payload.items():
                setattr(existing, key, value)
            if hasattr(existing, "is_deleted") and existing.is_deleted:
                existing.is_deleted = False

            if reported_provided and resolution is not None:
                apply_date_time_reported_resolution(existing, resolution)

            if audit_account_id is not None:
                await set_audit_fields(existing, audit_account_id, is_create=False)
            updated += 1
            target = existing
        else:
            payload = _model_payload_from_validated(validated, patch=False)
            if reported_provided:
                payload.pop("origin_date", None)
                payload.pop("origin_time", None)
            if payload.get("work_status") is None:
                payload["work_status"] = WorkStatus.FOR_REVIEW
            obj = MODEL(**payload)
            if reported_provided:
                resolution = resolve_date_time_reported(
                    existing=None,
                    imported_dt=validated.atl_date_time_reported,
                )
                apply_date_time_reported_resolution(obj, resolution)
            if audit_account_id is not None:
                await set_audit_fields(obj, audit_account_id, is_create=True)
            session.add(obj)
            references.existing_by_sequence[seq] = obj
            inserted += 1
            target = obj

        if getattr(validated, "component_parts", None) is not None:
            parts_targets.append((validated, target))

    await session.flush()

    for validated, target in parts_targets:
        await _replace_atl_component_parts(
            session=session,
            atl_id=target.id,
            component_parts=list(validated.component_parts),
            audit_account_id=audit_account_id,
        )

    return inserted, updated
