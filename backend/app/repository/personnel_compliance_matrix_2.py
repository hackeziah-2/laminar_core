from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import AccountInformation
from app.models.personnel_authorization import PersonnelAuthorization


async def list_personnel_compliance_matrix_2_paged(
    session: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
    designation: Optional[str] = None,
) -> Tuple[List[PersonnelAuthorization], int]:
    """
    One row per account_information_id: use the latest non-deleted PersonnelAuthorization
    (by updated_at desc nulls last, then id desc) to merge multiple authorizations per person.
    """
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

    latest = (
        select(ranked.c.pa_id, ranked.c.acc_id).where(ranked.c.rn == 1).subquery()
    )

    stmt = (
        select(PersonnelAuthorization)
        .join(latest, latest.c.pa_id == PersonnelAuthorization.id)
        .join(AccountInformation, AccountInformation.id == latest.c.acc_id)
        .where(AccountInformation.is_deleted == False)
        .options(
            selectinload(PersonnelAuthorization.account_information),
            selectinload(PersonnelAuthorization.authorization_scope_cessna),
            selectinload(PersonnelAuthorization.authorization_scope_baron),
            selectinload(PersonnelAuthorization.authorization_scope_others),
        )
    )

    count_stmt = (
        select(func.count())
        .select_from(latest)
        .join(AccountInformation, AccountInformation.id == latest.c.acc_id)
        .where(AccountInformation.is_deleted == False)
    )

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
        name_filter = or_(
            AccountInformation.first_name.ilike(q),
            AccountInformation.last_name.ilike(q),
            AccountInformation.middle_name.ilike(q),
            concat_last_first.ilike(q),
            concat_first_last.ilike(q),
        )
        stmt = stmt.where(name_filter)
        count_stmt = count_stmt.where(name_filter)

    if designation is not None and str(designation).strip() != "":
        stmt = stmt.where(AccountInformation.designation == designation.strip())
        count_stmt = count_stmt.where(AccountInformation.designation == designation.strip())

    sortable = {
        "id": PersonnelAuthorization.id,
        "account_information_id": PersonnelAuthorization.account_information_id,
        "account_information_id__auth_stamp": AccountInformation.auth_stamp,
        "authorization_no": AccountInformation.auth_stamp,
        "auth_initial_doi": PersonnelAuthorization.auth_initial_doi,
        "auth_issue_date": PersonnelAuthorization.auth_issue_date,
        "auth_expiry_date": PersonnelAuthorization.auth_expiry_date,
        "date_of_expiration": PersonnelAuthorization.auth_expiry_date,
        "caap_lic_expiry": PersonnelAuthorization.caap_license_expiry,
        "caap_license_expiry": PersonnelAuthorization.caap_license_expiry,
        "hf_training_expiry": PersonnelAuthorization.human_factors_training_expiry,
        "human_factors_training_expiry": PersonnelAuthorization.human_factors_training_expiry,
        "type_training_expiry_cessna": PersonnelAuthorization.type_training_expiry_cessna,
        "type_training_expiry_baron": PersonnelAuthorization.type_training_expiry_baron,
        "created_at": PersonnelAuthorization.created_at,
        "updated_at": PersonnelAuthorization.updated_at,
        "account_information.last_name": AccountInformation.last_name,
        "account_information.first_name": AccountInformation.first_name,
        "account_information__last_name": AccountInformation.last_name,
        "account_information__first_name": AccountInformation.first_name,
    }
    sortable_by_lower = {k.lower(): v for k, v in sortable.items()}
    date_columns_nullslast = {
        PersonnelAuthorization.auth_initial_doi,
        PersonnelAuthorization.auth_issue_date,
        PersonnelAuthorization.auth_expiry_date,
        PersonnelAuthorization.caap_license_expiry,
        PersonnelAuthorization.human_factors_training_expiry,
        PersonnelAuthorization.type_training_expiry_cessna,
        PersonnelAuthorization.type_training_expiry_baron,
        PersonnelAuthorization.created_at,
        PersonnelAuthorization.updated_at,
    }

    if sort:
        order_parts = []
        for part in sort.split(","):
            part = part.strip()
            if not part:
                continue
            desc = part.startswith("-")
            key = part.lstrip("-").strip().lower()
            if key in ("full_name", "name", "account_information__full_name"):
                col_last = AccountInformation.last_name
                col_first = AccountInformation.first_name
                order_parts.append(col_last.desc() if desc else col_last.asc())
                order_parts.append(col_first.desc() if desc else col_first.asc())
                continue
            col = sortable_by_lower.get(key)
            if col is not None:
                if col in date_columns_nullslast:
                    order_parts.append(col.desc().nullslast() if desc else col.asc().nullslast())
                else:
                    order_parts.append(col.desc() if desc else col.asc())
        if order_parts:
            stmt = stmt.order_by(*order_parts)
    else:
        stmt = stmt.order_by(
            AccountInformation.last_name.asc(),
            AccountInformation.first_name.asc(),
        )

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total
