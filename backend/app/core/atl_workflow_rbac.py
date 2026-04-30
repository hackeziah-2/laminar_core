"""Role-based ATL work_status transition rules for update operations."""

from typing import Dict, Optional, Set, Tuple

from app.models.aircraft_techinical_log import WorkStatus


_ATL_ALLOWED_STATUS_TRANSITIONS_BY_ROLE: Dict[str, Set[Tuple[WorkStatus, WorkStatus]]] = {
    "Quality Manager": {
        (WorkStatus.PENDING, WorkStatus.COMPLETED),
        (WorkStatus.PENDING, WorkStatus.REJECTED_QUALITY),
    },
}

_CF_INDEX: Dict[str, Set[Tuple[WorkStatus, WorkStatus]]] = {
    role.casefold(): transitions
    for role, transitions in _ATL_ALLOWED_STATUS_TRANSITIONS_BY_ROLE.items()
}


def atl_workflow_skips_transition_rbac(role_name: Optional[str]) -> bool:
    """Admins bypass ATL workflow transition checks."""
    if not role_name or not str(role_name).strip():
        return False
    return str(role_name).strip().casefold() == "admin"


def is_atl_work_status_transition_allowed(
    role_name: Optional[str],
    current_status: Optional[WorkStatus],
    next_status: Optional[WorkStatus],
) -> bool:
    """Return whether the role may change ATL work_status from current to next."""
    if current_status == next_status:
        return True

    if atl_workflow_skips_transition_rbac(role_name):
        return True

    if not role_name or not str(role_name).strip():
        return True

    role_key = str(role_name).strip()
    allowed = _ATL_ALLOWED_STATUS_TRANSITIONS_BY_ROLE.get(role_key)
    if allowed is None:
        allowed = _CF_INDEX.get(role_key.casefold())

    if allowed is None:
        return True

    return (current_status, next_status) in allowed
