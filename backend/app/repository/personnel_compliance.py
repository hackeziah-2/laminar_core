from typing import List, Optional, Tuple

from fastapi import HTTPException, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import set_audit_fields
from app.models.audit_log import AuditAction
from app.services.audit_trail_service import create_audit_log, serialize_audit_data
from app.models.account import AccountInformation
from app.models.personnel_authorization import PersonnelAuthorization
from app.models.personnel_compliance import PersonnelCompliance, PersonnelComplianceItemType
from app.schemas.personnel_compliance_schema import (
    PersonnelComplianceCreate,
    PersonnelComplianceUpdate,
    PersonnelComplianceRead,
)


def _latest_personnel_authorization_subquery():
    ranked = (
        select(
            PersonnelAuthorization.id.label("pa_id"),
            PersonnelAuthorization.account_information_id.label("acc_id"),
            func.row_number()
            .over(
                partition_by=PersonnelAuthorization.account_information_id,
                order_by=(
                    PersonnelAuthorization.updated_at.desc().nullslast(),
                    PersonnelAuthorization.id.desc(),
                ),
            )
            .label("rn"),
        ).where(PersonnelAuthorization.is_deleted == False)
    ).subquery()
    return select(ranked.c.pa_id, ranked.c.acc_id).where(ranked.c.rn == 1).subquery()


async def validate_personnel_compliance_duplicate(
    session: AsyncSession,
    data: PersonnelComplianceCreate,
) -> None:
    item_type = data.item_type.name
    result = await session.execute(
        select(PersonnelCompliance.id).where(
            and_(
                PersonnelCompliance.account_information_id == data.account_information_id,
                PersonnelCompliance.item_type == data.item_type,
                PersonnelCompliance.is_withhold == False,
                PersonnelCompliance.is_deleted == False,
            )
        ).limit(1)
    )

    if result.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'Entry Already Exists "{item_type}"'
        )


async def list_personnel_compliances(
    session: AsyncSession,
    limit: int = 0,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
    designation: Optional[str] = None,
    item_type: Optional[PersonnelComplianceItemType] = None,
) -> Tuple[List[Tuple[PersonnelCompliance, Optional[PersonnelAuthorization]]], int]:
    latest_pa = _latest_personnel_authorization_subquery()
    stmt = (
        select(PersonnelCompliance, PersonnelAuthorization)
        .options(
            selectinload(PersonnelCompliance.account_information),
            selectinload(PersonnelCompliance.authorization_scope_cessna),
            selectinload(PersonnelCompliance.authorization_scope_baron),
            selectinload(PersonnelCompliance.authorization_scope_others),
        )
        .outerjoin(latest_pa, latest_pa.c.acc_id == PersonnelCompliance.account_information_id)
        .outerjoin(PersonnelAuthorization, PersonnelAuthorization.id == latest_pa.c.pa_id)
        .where(PersonnelCompliance.is_deleted == False)
    )
    need_join = False
    if search and search.strip():
        need_join = True
    if designation is not None and str(designation).strip() != "":
        need_join = True
    sort_lower = (sort or "").lower()
    if "account_information_id__auth_stamp" in sort_lower:
        need_join = True
    if "auth_initial_doi" in sort_lower:
        need_join = True
    for _part in (sort or "").split(","):
        _n = _part.lstrip("-").strip().lower()
        if _n in (
            "full_name",
            "account_information__full_name",
            "account_information.last_name",
            "account_information.first_name",
            "account_information__last_name",
            "account_information__first_name",
        ):
            need_join = True
            break

    if need_join:
        stmt = stmt.join(PersonnelCompliance.account_information)
    if search and search.strip():
        q = f"%{search.strip()}%"
        concat_last_first = func.concat(
            func.coalesce(AccountInformation.last_name, ""),
            ", ",
            func.coalesce(AccountInformation.first_name, ""),
        )
        concat_first_last = func.concat(
            func.coalesce(AccountInformation.first_name, ""),
            " ",
            func.coalesce(AccountInformation.last_name, ""),
        )
        stmt = stmt.where(
            or_(
                AccountInformation.first_name.ilike(q),
                AccountInformation.last_name.ilike(q),
                AccountInformation.middle_name.ilike(q),
                concat_last_first.ilike(q),
                concat_first_last.ilike(q),
            )
        )
    if designation is not None and str(designation).strip() != "":
        stmt = stmt.where(AccountInformation.designation == designation.strip())
    if item_type is not None:
        stmt = stmt.where(PersonnelCompliance.item_type == item_type)

    sortable = {
        "id": PersonnelCompliance.id,
        "account_information_id": PersonnelCompliance.account_information_id,
        "account_information_id__auth_stamp": AccountInformation.auth_stamp,
        "item_type": PersonnelCompliance.item_type,
        "auth_issue_date": PersonnelCompliance.auth_issue_date,
        "expiry_date": PersonnelCompliance.expiry_date,
        "date_of_expiration": PersonnelCompliance.expiry_date,
        "created_at": PersonnelCompliance.created_at,
        "updated_at": PersonnelCompliance.updated_at,
        "account_information.last_name": AccountInformation.last_name,
        "account_information.first_name": AccountInformation.first_name,
        "account_information__last_name": AccountInformation.last_name,
        "account_information__first_name": AccountInformation.first_name,
    }
    sortable_by_lower = {k.lower(): v for k, v in sortable.items()}
    date_columns_nullslast = {
        PersonnelCompliance.expiry_date,
        PersonnelCompliance.auth_issue_date,
    }
    auth_initial_doi_sort = func.coalesce(
        PersonnelAuthorization.auth_initial_doi,
        AccountInformation.auth_initial_doi,
    )
    if sort:
        order_parts = []
        for part in sort.split(","):
            desc = part.startswith("-")
            name = part.lstrip("-").strip()
            if name.lower() == "auth_initial_doi":
                order_parts.append(
                    auth_initial_doi_sort.desc().nullslast()
                    if desc
                    else auth_initial_doi_sort.asc().nullslast()
                )
                continue
            if name.lower() in ("full_name", "account_information__full_name"):
                col_last = AccountInformation.last_name
                col_first = AccountInformation.first_name
                if desc:
                    order_parts.append(col_last.desc().nullslast())
                    order_parts.append(col_first.desc().nullslast())
                else:
                    order_parts.append(col_last.asc().nullsfirst())
                    order_parts.append(col_first.asc().nullsfirst())
                continue
            col = sortable_by_lower.get(name.lower())
            if col is not None:
                if col in date_columns_nullslast:
                    order_parts.append(
                        col.desc().nullslast() if desc else col.asc().nullslast()
                    )
                else:
                    order_parts.append(col.desc() if desc else col.asc())
        if order_parts:
            stmt = stmt.order_by(*order_parts)
    else:
        stmt = stmt.order_by(PersonnelCompliance.expiry_date.desc().nullslast())

    count_stmt = (
        select(func.count())
        .select_from(PersonnelCompliance)
        .where(PersonnelCompliance.is_deleted == False)
    )
    if need_join:
        count_stmt = count_stmt.join(PersonnelCompliance.account_information)
    if search and search.strip():
        q = f"%{search.strip()}%"
        concat_last_first = func.concat(
            func.coalesce(AccountInformation.last_name, ""),
            ", ",
            func.coalesce(AccountInformation.first_name, ""),
        )
        concat_first_last = func.concat(
            func.coalesce(AccountInformation.first_name, ""),
            " ",
            func.coalesce(AccountInformation.last_name, ""),
        )
        count_stmt = count_stmt.where(
            or_(
                AccountInformation.first_name.ilike(q),
                AccountInformation.last_name.ilike(q),
                AccountInformation.middle_name.ilike(q),
                concat_last_first.ilike(q),
                concat_first_last.ilike(q),
            )
        )
    if designation is not None and str(designation).strip() != "":
        count_stmt = count_stmt.where(AccountInformation.designation == designation.strip())
    if item_type is not None:
        count_stmt = count_stmt.where(PersonnelCompliance.item_type == item_type)

    total = (await session.execute(count_stmt)).scalar()
    total = int(total or 0)
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = [(row[0], row[1]) for row in result.all()]
    return items, total


async def get_personnel_compliance(
    session: AsyncSession,
    compliance_id: int,
) -> Optional[PersonnelCompliance]:
    result = await session.execute(
        select(PersonnelCompliance)
        .options(
            selectinload(PersonnelCompliance.account_information),
            selectinload(PersonnelCompliance.authorization_scope_cessna),
            selectinload(PersonnelCompliance.authorization_scope_baron),
            selectinload(PersonnelCompliance.authorization_scope_others),
        )
        .where(PersonnelCompliance.id == compliance_id)
        .where(PersonnelCompliance.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def create_personnel_compliance(
    session: AsyncSession,
    data: PersonnelComplianceCreate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> PersonnelComplianceRead:
    await validate_personnel_compliance_duplicate(session, data)
    obj = PersonnelCompliance(**data.dict())
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=True)
    await session.commit()
    await session.refresh(obj)
    result = await session.execute(
        select(PersonnelCompliance)
        .options(
            selectinload(PersonnelCompliance.account_information),
            selectinload(PersonnelCompliance.authorization_scope_cessna),
            selectinload(PersonnelCompliance.authorization_scope_baron),
            selectinload(PersonnelCompliance.authorization_scope_others),
        )
        .where(PersonnelCompliance.id == obj.id)
        .where(PersonnelCompliance.is_deleted == False)
    )
    loaded = result.scalar_one()

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=loaded.id,
            action=AuditAction.CREATE,
            old_data=None,
            new_data=loaded,
            current_user=audit_user,
            request=audit_request,
        )

    return PersonnelComplianceRead.from_orm(loaded)


async def update_personnel_compliance(
    session: AsyncSession,
    compliance_id: int,
    data: PersonnelComplianceUpdate,
    *,
    audit_account_id: Optional[int] = None,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> Optional[PersonnelComplianceRead]:
    result = await session.execute(
        select(PersonnelCompliance)
        .options(
            selectinload(PersonnelCompliance.account_information),
            selectinload(PersonnelCompliance.authorization_scope_cessna),
            selectinload(PersonnelCompliance.authorization_scope_baron),
            selectinload(PersonnelCompliance.authorization_scope_others),
        )
        .where(PersonnelCompliance.id == compliance_id)
        .where(PersonnelCompliance.is_deleted == False)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return None

    old_data_snapshot = serialize_audit_data(obj)
    update_data = data.dict(exclude_unset=True)
    # Do not write None onto NOT NULL columns when clients send explicit nulls.
    skip_none_for = {"account_information_id", "item_type", "is_withhold"}
    for k, v in update_data.items():
        if v is None and k in skip_none_for:
            continue
        setattr(obj, k, v)
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=False)
    await session.commit()
    await session.refresh(obj)
    await session.refresh(
        obj,
        [
            "account_information",
            "authorization_scope_cessna",
            "authorization_scope_baron",
            "authorization_scope_others",
        ],
    )

    if audit_module_name and audit_table_name:
        await create_audit_log(
            db=session,
            module_name=audit_module_name,
            table_name=audit_table_name,
            record_id=obj.id,
            action=AuditAction.UPDATE,
            old_data=old_data_snapshot,
            new_data=obj,
            current_user=audit_user,
            request=audit_request,
        )

    return PersonnelComplianceRead.from_orm(obj)


async def soft_delete_personnel_compliance(
    session: AsyncSession,
    compliance_id: int,
    *,
    audit_module_name: Optional[str] = None,
    audit_table_name: Optional[str] = None,
    audit_user: Optional[AccountInformation] = None,
    audit_request: Optional[Request] = None,
) -> bool:
    obj = await session.get(PersonnelCompliance, compliance_id)
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
            record_id=compliance_id,
            action=AuditAction.DELETE,
            old_data=old_data_snapshot,
            new_data=None,
            current_user=audit_user,
            request=audit_request,
        )

    return True
