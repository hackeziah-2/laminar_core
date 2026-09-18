"""Canonical role names and equivalence used by RBAC checks.

Displayed role names stay unchanged. Equivalent roles share access behavior.
"""

from typing import List, Optional, Sequence, Tuple

MAINTENANCE_MANAGER_ROLE = "Maintenance Manager"
MECHANIC_MAINTENANCE_MANAGER_ROLE = "Mechanic - Maintenance Manager"

# Official names that share Maintenance Manager access. Display names stay as stored.
MAINTENANCE_MANAGER_EQUIVALENT_ROLES = frozenset(
    {
        MAINTENANCE_MANAGER_ROLE,
        MECHANIC_MAINTENANCE_MANAGER_ROLE,
    }
)


def normalize_role_name(role_name: Optional[str]) -> str:
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


def _collapsed_role_name(role_name: Optional[str]) -> str:
    return " ".join(normalize_role_name(role_name).replace("-", " ").split())


def is_admin_role(role_name: Optional[str]) -> bool:
    n = normalize_role_name(role_name)
    if not n:
        return False
    return (
        n == "admin"
        or n == "administrator"
        or n.endswith(" admin")
        or n.endswith(" administrator")
    )


def is_maintenance_planner_role(role_name: Optional[str]) -> bool:
    n = normalize_role_name(role_name)
    if not n:
        return False
    return (
        n == "maintenance planner"
        or n == "maint planner"
        or n == "maintenance planning"
        or n.endswith(" maintenance planner")
    )


def is_maintenance_manager_role(role_name: Optional[str]) -> bool:
    n = normalize_role_name(role_name)
    if not n:
        return False
    collapsed = _collapsed_role_name(role_name)
    return (
        n == "maintenance manager"
        or n == "maint manager"
        or n.endswith(" maintenance manager")
        or collapsed == "maintenance manager"
        or collapsed == "mechanic maintenance manager"
        or collapsed.endswith(" maintenance manager")
    )


def is_technical_publication_role(role_name: Optional[str]) -> bool:
    n = normalize_role_name(role_name)
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
    n = normalize_role_name(role_name)
    if not n:
        return False
    return (
        n == "quality manager"
        or n == "qa manager"
        or n.endswith(" quality manager")
    )


def canonical_access_role(role_name: Optional[str]) -> Optional[str]:
    """Return the RBAC identity used by guards; display name is unchanged."""
    if not role_name or not str(role_name).strip():
        return None
    if is_maintenance_manager_role(role_name):
        return MAINTENANCE_MANAGER_ROLE
    return str(role_name).strip()


def equivalent_role_names(role_name: Optional[str]) -> Tuple[str, ...]:
    """Official role names that share this role's access."""
    if is_maintenance_manager_role(role_name):
        return tuple(sorted(MAINTENANCE_MANAGER_EQUIVALENT_ROLES))
    stripped = str(role_name).strip() if role_name else ""
    if not stripped:
        return ()
    return (stripped,)


def expand_equivalent_role_names(role_names: Sequence[str]) -> List[str]:
    """Expand lookup lists so equivalent roles receive the same notifications/access."""
    expanded: List[str] = []
    seen = set()
    for name in role_names:
        if not name or not str(name).strip():
            continue
        for alias in equivalent_role_names(name):
            key = alias.casefold()
            if key in seen:
                continue
            seen.add(key)
            expanded.append(alias)
    return expanded


def roles_have_equivalent_access(left: Optional[str], right: Optional[str]) -> bool:
    left_key = canonical_access_role(left)
    right_key = canonical_access_role(right)
    if not left_key or not right_key:
        return False
    return left_key.casefold() == right_key.casefold()
