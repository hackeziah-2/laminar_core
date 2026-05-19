"""Orchestrate generic Excel/CSV import (validation, upsert, hooks)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from fastapi import UploadFile
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ValidationError as AppValidationError
from app.repository.excel_import import (
    find_by_unique_fields,
    normalize_unique_fields,
    upsert_validated_row,
    validated_to_dict,
)
from app.services.excel_import.config import ExcelImportConfig
from app.services.excel_import.hooks.registry import get_import_hook
from app.services.excel_import.parsers import make_hashable
from app.services.excel_import.reader import read_upload_records
from app.services.excel_import.row_builder import (
    build_row_for_schema,
    format_row_error,
    schema_field_names,
)


def _map_integrity_error(
    exc: IntegrityError,
    messages: Optional[Dict[str, str]],
) -> str:
    text = str(getattr(exc, "orig", exc)).lower()
    for key, msg in (messages or {}).items():
        if key.lower() in text:
            return msg
    return "Database integrity error"


def _row_signature(validated: BaseModel) -> tuple:
    data = validated_to_dict(validated)
    return tuple(sorted((k, make_hashable(v)) for k, v in data.items()))


class ExcelImportService:
    @staticmethod
    async def run(
        file: UploadFile,
        session: AsyncSession,
        config: ExcelImportConfig,
    ) -> Dict[str, Any]:
        fields = normalize_unique_fields(config.unique_fields)
        for scope_field in ("aircraft_fk", "ad_monitoring_fk"):
            if scope_field in config.inject_fields and scope_field not in fields:
                fields = [scope_field, *fields]
        if not fields:
            raise AppValidationError("At least one unique field is required")

        hook = get_import_hook(config.hook_key)
        schema_fields = schema_field_names(config.schema)
        inject_fields = dict(config.inject_fields)

        records = await read_upload_records(
            file,
            column_mapping=config.column_mapping,
        )
        records = hook.preprocess_records(records)

        inserted = 0
        updated = 0
        errors: List[Dict[str, Any]] = []

        # Pass 1: validate and count
        for idx, row in enumerate(records):
            excel_row = idx + 2
            try:
                row_data = build_row_for_schema(
                    row,
                    schema_fields=schema_fields,
                    inject_fields=inject_fields,
                    hook=hook,
                )
                validated = config.schema(**row_data)
                existing = await find_by_unique_fields(
                    session, config.model, validated, fields
                )
                if existing:
                    updated += 1
                else:
                    inserted += 1
            except Exception as exc:
                errors.append({"row": excel_row, "error": format_row_error(exc)})

        if config.dry_run:
            return {
                "status": "dry-run",
                "inserted": inserted,
                "updated": updated,
                "errors": errors,
            }

        if errors:
            await session.rollback()
            return {
                "status": "failed",
                "inserted": inserted,
                "updated": updated,
                "errors": errors,
            }

        # Pass 2: write
        seen_signatures: set[tuple] = set()
        write_errors: List[Dict[str, Any]] = []

        try:
            with session.no_autoflush:
                for idx, row in enumerate(records):
                    excel_row = idx + 2
                    try:
                        row_data = build_row_for_schema(
                            row,
                            schema_fields=schema_fields,
                            inject_fields=inject_fields,
                            hook=hook,
                        )
                        validated = config.schema(**row_data)
                    except ValidationError as exc:
                        write_errors.append(
                            {"row": excel_row, "error": format_row_error(exc)}
                        )
                        continue

                    sig = _row_signature(validated)
                    if sig in seen_signatures:
                        continue
                    seen_signatures.add(sig)

                    try:
                        _, created = await upsert_validated_row(
                            session,
                            config.model,
                            validated,
                            fields,
                            hook,
                            audit_account_id=config.audit_account_id,
                        )
                    except ValueError as exc:
                        write_errors.append({"row": excel_row, "error": str(exc)})
                        continue

            if write_errors:
                await session.rollback()
                return {
                    "status": "failed",
                    "inserted": inserted,
                    "updated": updated,
                    "errors": write_errors,
                }

            await session.commit()
            await hook.after_commit(
                session,
                context={},
                audit_account_id=config.audit_account_id,
            )

            return {
                "status": "success",
                "inserted": inserted,
                "updated": updated,
                "errors": [],
            }

        except IntegrityError as exc:
            await session.rollback()
            detail = _map_integrity_error(exc, config.integrity_error_messages)
            raise AppValidationError(detail) from exc


async def import_excel_generic(
    file: UploadFile,
    session: AsyncSession,
    model: type,
    schema: type[BaseModel],
    unique_fields: Union[str, List[str]],
    dry_run: bool = False,
    column_mapping: Optional[Dict[str, str]] = None,
    integrity_error_messages: Optional[Dict[str, str]] = None,
    inject_fields: Optional[Dict[str, Any]] = None,
    *,
    audit_account_id: Optional[int] = None,
    hook_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Backward-compatible entry point. Prefer ExcelImportService.run + ExcelImportConfig."""
    if hook_key is None:
        hook_key = _default_hook_key(model)

    config = ExcelImportConfig(
        model=model,
        schema=schema,
        unique_fields=unique_fields,
        hook_key=hook_key,
        dry_run=dry_run,
        column_mapping=column_mapping,
        integrity_error_messages=integrity_error_messages,
        inject_fields=inject_fields or {},
        audit_account_id=audit_account_id,
    )
    try:
        return await ExcelImportService.run(file, session, config)
    except AppValidationError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=exc.message) from exc
    except AppError as exc:
        from fastapi import HTTPException

        status_code = 404 if exc.code == "not_found" else 400
        raise HTTPException(status_code=status_code, detail=exc.message) from exc
    except Exception as exc:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file: {exc}",
        ) from exc


def _default_hook_key(model: type) -> str:
    name = model.__name__
    if name == "Aircraft":
        return "aircraft"
    if name == "AircraftTechnicalLog":
        return "aircraft_technical_log"
    return name.lower()
