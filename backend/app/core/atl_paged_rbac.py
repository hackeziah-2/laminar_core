"""RBAC: which aircraft_technical_log.work_status values each role may see on GET .../paged."""

from functools import wraps
from typing import Dict, Optional, Tuple

from sqlalchemy import false, or_

from app.models.aircraft_techinical_log import AircraftTechnicalLog, WorkStatus
from app.models.role import Role

# Role names match seeded `roles.json` (and DB `roles.name`).
_ATL_PAGED_WORK_STATUSES_BY_ROLE: Dict[str, Tuple[WorkStatus, ...]] = {
    "Maintenance Planner": (
        WorkStatus.FOR_REVIEW,
        WorkStatus.AWAITING_ATTACHMENT,
        WorkStatus.COMPLETED,
        WorkStatus.PENDING,
        WorkStatus.FOR_REVIEW,
        WorkStatus.APPROVED,
        WorkStatus.REJECTED_MAINTENANCE,
        WorkStatus.REJECTED_QUALITY
    ),
    "Maintenance Manager": (
        WorkStatus.FOR_REVIEW,
        WorkStatus.APPROVED,
    ),
    "Technical Publication": (
        WorkStatus.AWAITING_ATTACHMENT,
        WorkStatus.PENDING,
    ),
    "Quality Manager": (
        WorkStatus.PENDING,
        WorkStatus.COMPLETED,
    ),
    "Mechanic": (
        WorkStatus.FOR_REVIEW,
        WorkStatus.AWAITING_ATTACHMENT,
        WorkStatus.COMPLETED,
        WorkStatus.PENDING,
        WorkStatus.FOR_REVIEW,
        WorkStatus.APPROVED,
    ),
}

_CF_INDEX: Dict[str, Tuple[WorkStatus, ...]] = {
    k.casefold(): v for k, v in _ATL_PAGED_WORK_STATUSES_BY_ROLE.items()
}


def _is_maintenance_planner_role(role_name: Optional[str]) -> bool:
    if not role_name or not str(role_name).strip():
        return False
    return str(role_name).strip().casefold() == "maintenance planner"


def atl_paged_list_skips_work_status_rbac(role_name: Optional[str]) -> bool:
    """Admin sees all ATL rows regardless of work_status (no IN filter)."""
    if not role_name or not str(role_name).strip():
        return False
    return str(role_name).strip().casefold() == "admin"


def allowed_work_statuses_for_atl_paged_list(role_name: Optional[str]) -> Tuple[WorkStatus, ...]:
    """
    Return work_status values the role may list. Empty tuple = no access (fail-safe).
    Unknown role, blank name, or missing role yields ().
    """
    if not role_name or not str(role_name).strip():
        return ()
    stripped = str(role_name).strip()
    if stripped in _ATL_PAGED_WORK_STATUSES_BY_ROLE:
        return _ATL_PAGED_WORK_STATUSES_BY_ROLE[stripped]
    return _CF_INDEX.get(stripped.casefold(), ())


def atl_rbac_filter():
    """Decorate an async function that returns (stmt, count_stmt); applies work_status RBAC and runs both queries."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            session = kwargs.get("session")
            current_account = kwargs.get("current_account")
            work_status = kwargs.get("work_status")

            role_name = None
            if current_account and current_account.role_id:
                role = await session.get(Role, current_account.role_id)
                if role and not role.is_deleted:
                    role_name = role.name

            skip = atl_paged_list_skips_work_status_rbac(role_name)
            allowed = allowed_work_statuses_for_atl_paged_list(role_name)

            stmt, count_stmt = await func(*args, **kwargs)

            def apply_rbac(s):
                if skip:
                    if work_status:
                        return s.where(AircraftTechnicalLog.work_status == work_status)
                    return s

                if not allowed:
                    return s.where(false())

                if work_status:
                    if work_status not in allowed:
                        return s.where(false())
                    return s.where(AircraftTechnicalLog.work_status == work_status)

                if _is_maintenance_planner_role(role_name):
                    return s.where(
                        or_(
                            AircraftTechnicalLog.work_status.in_(list(allowed)),
                            AircraftTechnicalLog.work_status.is_(None),
                        )
                    )
                return s.where(AircraftTechnicalLog.work_status.in_(list(allowed)))

            stmt = apply_rbac(stmt)
            count_stmt = apply_rbac(count_stmt)

            limit = kwargs.get("limit", 0)
            offset = kwargs.get("offset", 0)

            total = (await session.execute(count_stmt)).scalar()

            stmt = stmt.limit(limit).offset(offset)
            result = await session.execute(stmt)
            items = result.scalars().all()

            return items, total

        return wrapper

    return decorator
