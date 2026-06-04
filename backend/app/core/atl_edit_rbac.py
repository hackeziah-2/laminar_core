"""ATL edit RBAC by role and work_status (Operation / Technical Logbook)."""

from typing import FrozenSet, Optional, Set, Tuple

from app.models.aircraft_techinical_log import WorkStatus

ATL_EDIT_FORBIDDEN_MESSAGE = (
    "You do not have permission to edit this ATL record in its current work status."
)

ATL_LOCKED_STATUSES: FrozenSet[WorkStatus] = frozenset(
    {WorkStatus.COMPLETED, WorkStatus.APPROVED}
)

_MAINTENANCE_PLANNER_ALLOWED: FrozenSet[WorkStatus] = frozenset(
    {
        WorkStatus.FOR_REVIEW,
        WorkStatus.AWAITING_ATTACHMENT,
        WorkStatus.REJECTED_MAINTENANCE,
        WorkStatus.PENDING,
    }
)

_TECHNICAL_PUBLICATION_ALLOWED: FrozenSet[WorkStatus] = frozenset(
    {WorkStatus.AWAITING_ATTACHMENT, WorkStatus.PENDING}
)

_MAINTENANCE_MANAGER_ALLOWED: FrozenSet[WorkStatus] = frozenset(
    {
        WorkStatus.PENDING,
        WorkStatus.REJECTED_MAINTENANCE,
        WorkStatus.APPROVED,
    }
)

_QUALITY_MANAGER_ALLOWED: FrozenSet[WorkStatus] = frozenset(
    {
        WorkStatus.APPROVED,
        WorkStatus.REJECTED_QUALITY,
        WorkStatus.COMPLETED,
    }
)

# Logbook Renew — work_status-only (not full form edit).
_MAINTENANCE_PLANNER_RENEW_TRANSITIONS: Set[Tuple[WorkStatus, WorkStatus]] = {
    (WorkStatus.REJECTED_QUALITY, WorkStatus.PENDING),
    (WorkStatus.REJECTED_MAINTENANCE, WorkStatus.FOR_REVIEW),
}

# Approve / Reject on FOR_REVIEW — work_status-only.
_MAINTENANCE_MANAGER_WORKFLOW_TRANSITIONS: Set[Tuple[WorkStatus, WorkStatus]] = {
    (WorkStatus.FOR_REVIEW, WorkStatus.APPROVED),
    (WorkStatus.FOR_REVIEW, WorkStatus.REJECTED_MAINTENANCE),
}


def _normalize_role_name(role_name: Optional[str]) -> str:
    if not role_name or not str(role_name).strip():
        return ""
    return (
        str(role_name)
        .strip()
        .lower()
        .replace("_", " ")
        .replace(".", "")
        .replace("'", "")
        .replace('"', "")
    )


def is_admin_role(role_name: Optional[str]) -> bool:
    n = _normalize_role_name(role_name)
    if not n:
        return False
    return (
        n == "admin"
        or n == "administrator"
        or n.endswith(" admin")
        or n.endswith(" administrator")
    )


def is_maintenance_planner_role(role_name: Optional[str]) -> bool:
    n = _normalize_role_name(role_name)
    if not n:
        return False
    return (
        n == "maintenance planner"
        or n == "maint planner"
        or n == "maintenance planning"
        or n.endswith(" maintenance planner")
    )


def is_maintenance_manager_role(role_name: Optional[str]) -> bool:
    n = _normalize_role_name(role_name)
    if not n:
        return False
    return (
        n == "maintenance manager"
        or n == "maint manager"
        or n.endswith(" maintenance manager")
    )


def is_technical_publication_role(role_name: Optional[str]) -> bool:
    n = _normalize_role_name(role_name)
    if not n:
        return False
    has_phrase = "technical publication" in n or "tech publication" in n
    return (
        has_phrase
        or n == "technical publication"
        or n == "tech publication"
        or n == "oem technical publication"
        or n == "oem tech publication"
        or n.endswith(" technical publication")
    )


def is_quality_manager_role(role_name: Optional[str]) -> bool:
    n = _normalize_role_name(role_name)
    if not n:
        return False
    return (
        n == "quality manager"
        or n == "qa manager"
        or n.endswith(" quality manager")
    )


def _allowed_statuses_for_role(role_name: Optional[str]) -> Optional[FrozenSet[WorkStatus]]:
    if is_admin_role(role_name):
        return None
    if is_maintenance_planner_role(role_name):
        return _MAINTENANCE_PLANNER_ALLOWED
    if is_technical_publication_role(role_name):
        return _TECHNICAL_PUBLICATION_ALLOWED
    if is_maintenance_manager_role(role_name):
        return _MAINTENANCE_MANAGER_ALLOWED
    if is_quality_manager_role(role_name):
        return _QUALITY_MANAGER_ALLOWED
    return frozenset()


def can_bypass_locked_status_edit(role_name: Optional[str]) -> bool:
    return (
        is_admin_role(role_name)
        or is_maintenance_manager_role(role_name)
        or is_quality_manager_role(role_name)
    )


def can_edit_atl_for_role_and_status(
    role_name: Optional[str],
    current_status: Optional[WorkStatus],
) -> bool:
    if is_admin_role(role_name):
        return True
    if current_status is None:
        return False

    allowed = _allowed_statuses_for_role(role_name)
    if allowed is None:
        return True
    if not allowed:
        return False
    if current_status not in allowed:
        return False
    if current_status in ATL_LOCKED_STATUSES and not can_bypass_locked_status_edit(
        role_name
    ):
        return False
    return True


def is_maintenance_planner_renew_only_update(
    role_name: Optional[str],
    current_status: Optional[WorkStatus],
    update_data: dict,
) -> bool:
    if not is_maintenance_planner_role(role_name):
        return False
    if "work_status" not in update_data:
        return False
    if any(key != "work_status" for key in update_data):
        return False
    next_status = update_data["work_status"]
    if not isinstance(next_status, WorkStatus):
        return False
    return (current_status, next_status) in _MAINTENANCE_PLANNER_RENEW_TRANSITIONS


def is_maintenance_manager_workflow_only_update(
    role_name: Optional[str],
    current_status: Optional[WorkStatus],
    update_data: dict,
) -> bool:
    if not is_maintenance_manager_role(role_name):
        return False
    if "work_status" not in update_data:
        return False
    if any(key != "work_status" for key in update_data):
        return False
    next_status = update_data["work_status"]
    if not isinstance(next_status, WorkStatus):
        return False
    return (current_status, next_status) in _MAINTENANCE_MANAGER_WORKFLOW_TRANSITIONS


def validate_atl_edit_allowed_for_account(
    *,
    role_name: Optional[str],
    current_status: Optional[WorkStatus],
    update_data: dict,
) -> None:
    """Raise ValueError with HTTP 403 detail message when edit is not permitted."""
    if can_edit_atl_for_role_and_status(role_name, current_status):
        return

    if is_maintenance_planner_role(role_name) and is_maintenance_planner_renew_only_update(
        role_name, current_status, update_data
    ):
        return

    if is_maintenance_manager_role(role_name) and is_maintenance_manager_workflow_only_update(
        role_name, current_status, update_data
    ):
        return

    raise ValueError(ATL_EDIT_FORBIDDEN_MESSAGE)


# Backward-compatible aliases for tests / imports
MAINTENANCE_PLANNER_ATL_EDIT_ALLOWED = _MAINTENANCE_PLANNER_ALLOWED
MAINTENANCE_PLANNER_ATL_EDIT_BLOCKED = frozenset(
    s for s in WorkStatus if s not in _MAINTENANCE_PLANNER_ALLOWED
)
MAINTENANCE_PLANNER_ATL_EDIT_DENIED_MESSAGE = ATL_EDIT_FORBIDDEN_MESSAGE
MAINTENANCE_MANAGER_ATL_EDIT_ALLOWED = _MAINTENANCE_MANAGER_ALLOWED
MAINTENANCE_MANAGER_ATL_EDIT_DENIED_MESSAGE = ATL_EDIT_FORBIDDEN_MESSAGE


def is_maintenance_planner_atl_edit_blocked(
    current_status: Optional[WorkStatus],
) -> bool:
    return not can_edit_atl_for_role_and_status("Maintenance Planner", current_status)


def is_maintenance_manager_atl_edit_blocked(
    current_status: Optional[WorkStatus],
) -> bool:
    return not can_edit_atl_for_role_and_status("Maintenance Manager", current_status)
