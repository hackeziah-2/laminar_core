import json
import time
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select, union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import AccountInformation
from app.models.personnel_authorization import PersonnelAuthorization
from app.models.personnel_compliance import PersonnelCompliance, PersonnelComplianceItemType


def _agent_debug_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # region agent log
    try:
        with open(
            "/Users/kevinpaullamadrid/Desktop/Project/laminar_core/.cursor/debug-004053.log",
            "a",
            encoding="utf-8",
        ) as _f:
            _f.write(
                json.dumps(
                    {
                        "sessionId": "004053",
                        "timestamp": int(time.time() * 1000),
                        "hypothesisId": hypothesis_id,
                        "location": location,
                        "message": message,
                        "data": data,
                        "runId": "post-fix",
                    },
                    default=str,
                )
                + "\n"
            )
    except Exception:
        pass
    # endregion


_MATRIX_COMPLIANCE_TYPES = (
    PersonnelComplianceItemType.AUTH_EXPIRY,
    PersonnelComplianceItemType.CAAP_LICENSE,
    PersonnelComplianceItemType.HF_TRAINING,
    PersonnelComplianceItemType.CESSNA,
    PersonnelComplianceItemType.BARON,
    PersonnelComplianceItemType.OTHERS,
)


async def list_personnel_compliance_matrix_2_paged(
    session: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    search: Optional[str] = None,
    sort: str = "",
    designation: Optional[str] = None,
) -> Tuple[
    List[Tuple[AccountInformation, Optional[PersonnelAuthorization]]],
    int,
    Dict[int, Dict[PersonnelComplianceItemType, PersonnelCompliance]],
]:
    """
    One row per account_information_id: union of accounts that have matrix-type
    personnel_compliance rows and/or a latest non-deleted PersonnelAuthorization.
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

    combined_union = union(
        select(latest.c.acc_id.label("account_information_id")),
        select(PersonnelCompliance.account_information_id.label("account_information_id"))
        .where(
            PersonnelCompliance.item_type.in_(_MATRIX_COMPLIANCE_TYPES),
            PersonnelCompliance.is_deleted == False,
        )
        .distinct(),
    ).subquery()

    pa_nd_count = (
        await session.execute(
            select(func.count())
            .select_from(PersonnelAuthorization)
            .where(PersonnelAuthorization.is_deleted == False)
        )
    ).scalar() or 0
    latest_accounts_count = (
        await session.execute(select(func.count()).select_from(latest))
    ).scalar() or 0
    matrix_eligible_count = (
        await session.execute(
            select(func.count())
            .select_from(latest)
            .join(AccountInformation, AccountInformation.id == latest.c.acc_id)
            .where(AccountInformation.is_deleted == False)
        )
    ).scalar() or 0
    union_accounts_active = (
        await session.execute(
            select(func.count())
            .select_from(
                combined_union.join(
                    AccountInformation,
                    AccountInformation.id == combined_union.c.account_information_id,
                )
            )
            .where(AccountInformation.is_deleted == False)
        )
    ).scalar() or 0
    _agent_debug_log(
        "H1-H2-H5",
        "personnel_compliance_matrix_2.py:list_personnel_compliance_matrix_2_paged:counts",
        "baseline PA, PA-only matrix, union(PC+PA) account counts before search/designation",
        {
            "pa_non_deleted_count": pa_nd_count,
            "latest_distinct_accounts_with_pa": latest_accounts_count,
            "matrix_eligible_accounts_pa_only_not_deleted": matrix_eligible_count,
            "matrix_eligible_accounts_union_pc_pa_not_deleted": union_accounts_active,
            "search": (search or "")[:80] if search else None,
            "designation": (designation or "")[:80] if designation else None,
            "phase": "post-fix",
        },
    )

    account_scope = (
        combined_union.join(
            AccountInformation,
            AccountInformation.id == combined_union.c.account_information_id,
        )
        .outerjoin(latest, latest.c.acc_id == AccountInformation.id)
        .outerjoin(PersonnelAuthorization, PersonnelAuthorization.id == latest.c.pa_id)
    )

    stmt = (
        select(AccountInformation, PersonnelAuthorization)
        .select_from(account_scope)
        .where(AccountInformation.is_deleted == False)
        .options(
            selectinload(PersonnelAuthorization.authorization_scope_cessna),
            selectinload(PersonnelAuthorization.authorization_scope_baron),
            selectinload(PersonnelAuthorization.authorization_scope_others),
        )
    )

    count_stmt = (
        select(func.count())
        .select_from(
            combined_union.join(
                AccountInformation,
                AccountInformation.id == combined_union.c.account_information_id,
            )
        )
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
    row_tuples = result.all()
    items: List[Tuple[AccountInformation, Optional[PersonnelAuthorization]]] = [
        (row[0], row[1]) for row in row_tuples
    ]

    _agent_debug_log(
        "H3-H4",
        "personnel_compliance_matrix_2.py:list_personnel_compliance_matrix_2_paged:result",
        "filtered total vs page window",
        {
            "total_after_filters": total,
            "limit": limit,
            "offset": offset,
            "items_in_page": len(items),
            "rows_without_pa": sum(1 for acc, pa in items if pa is None),
            "has_search": bool(search and search.strip()),
            "has_designation": bool(
                designation is not None and str(designation).strip() != ""
            ),
            "phase": "post-fix",
        },
    )

    compliance_by_account: Dict[int, Dict[PersonnelComplianceItemType, PersonnelCompliance]] = {}
    account_ids = [acc.id for acc, _pa in items]
    if account_ids:
        pc_stmt = (
            select(PersonnelCompliance)
            .where(
                PersonnelCompliance.account_information_id.in_(account_ids),
                PersonnelCompliance.item_type.in_(_MATRIX_COMPLIANCE_TYPES),
                PersonnelCompliance.is_deleted == False,
            )
            .options(
                selectinload(PersonnelCompliance.authorization_scope_cessna),
                selectinload(PersonnelCompliance.authorization_scope_baron),
                selectinload(PersonnelCompliance.authorization_scope_others),
            )
        )
        pc_result = await session.execute(pc_stmt)
        for pc in pc_result.scalars().all():
            compliance_by_account.setdefault(pc.account_information_id, {})[
                pc.item_type
            ] = pc

    return items, total, compliance_by_account
