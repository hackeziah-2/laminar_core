"""RBAC: which aircraft_technical_log.work_status values each role may see on GET .../paged."""

from typing import Dict, Optional, Tuple

from app.models.aircraft_techinical_log import WorkStatus

# Role names match seeded `roles.json` (and DB `roles.name`).
_ATL_PAGED_WORK_STATUSES_BY_ROLE: Dict[str, Tuple[WorkStatus, ...]] = {
    "Maintenance Planner": (
        WorkStatus.APPROVED,
        WorkStatus.AWAITING_ATTACHMENT,
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
}

_CF_INDEX: Dict[str, Tuple[WorkStatus, ...]] = {
    k.casefold(): v for k, v in _ATL_PAGED_WORK_STATUSES_BY_ROLE.items()
}


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
