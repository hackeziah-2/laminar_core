"""Mechanic - Maintenance Manager has the same access as Maintenance Manager."""

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_account_permission
from app.core.atl_edit_rbac import (
    can_edit_atl_for_role_and_status,
    is_maintenance_manager_workflow_only_update,
    validate_atl_edit_allowed_for_account,
)
from app.core.atl_paged_rbac import (
    allowed_work_statuses_for_atl_paged_list,
    atl_paged_list_skips_work_status_rbac,
)
from app.core.atl_workflow_rbac import is_atl_work_status_transition_allowed
from app.core.role_identity import (
    MAINTENANCE_MANAGER_ROLE,
    MECHANIC_MAINTENANCE_MANAGER_ROLE,
    canonical_access_role,
    expand_equivalent_role_names,
    is_maintenance_manager_role,
    roles_have_equivalent_access,
)
from app.models.aircraft_techinical_log import WorkStatus
from app.repository.user_repository import get_active_accounts_by_roles
from tests.factories.rbac import seed_account, seed_module, seed_role, seed_role_permission

ROLES_SEED_PATH = Path(__file__).resolve().parents[1] / "seeds" / "roles.json"
PERMISSION_ACTIONS = ("can_read", "can_create", "can_update", "can_delete", "can_approve")
MM_ROLES = (MAINTENANCE_MANAGER_ROLE, MECHANIC_MAINTENANCE_MANAGER_ROLE)


def _load_seeded_roles() -> list[dict]:
    with ROLES_SEED_PATH.open() as handle:
        return json.load(handle)


def _seed_role(roles: list[dict], name: str) -> dict:
    for role in roles:
        if role["name"] == name:
            return role
    raise AssertionError(f"Role {name!r} missing from seeds/roles.json")


def test_seeded_mechanic_maintenance_manager_matches_maintenance_manager_permissions():
    roles = _load_seeded_roles()
    manager = _seed_role(roles, MAINTENANCE_MANAGER_ROLE)
    mechanic_manager = _seed_role(roles, MECHANIC_MAINTENANCE_MANAGER_ROLE)

    assert mechanic_manager["name"] == MECHANIC_MAINTENANCE_MANAGER_ROLE
    assert manager["permissions"] == mechanic_manager["permissions"]


def test_seeded_other_roles_are_unchanged():
    roles = _load_seeded_roles()
    by_name = {role["name"]: role["permissions"] for role in roles}

    assert set(by_name) == {
        "Admin",
        "Mechanic",
        "Maintenance Planner",
        "Maintenance Manager",
        "Mechanic - Maintenance Manager",
        "Technical Publication",
        "Quality Manager",
    }
    assert by_name["Mechanic"] == [
        {
            "module": "General Information",
            "read": True,
            "create": False,
            "update": False,
            "delete": False,
        },
        {
            "module": "Operation",
            "read": True,
            "create": False,
            "update": False,
            "delete": False,
        },
    ]
    assert by_name["Maintenance Planner"] != by_name["Maintenance Manager"]
    assert by_name["Admin"] != by_name["Maintenance Manager"]


def test_role_identity_treats_mechanic_maintenance_manager_as_maintenance_manager():
    assert is_maintenance_manager_role(MECHANIC_MAINTENANCE_MANAGER_ROLE) is True
    assert is_maintenance_manager_role(MAINTENANCE_MANAGER_ROLE) is True
    assert is_maintenance_manager_role("Mechanic") is False
    assert canonical_access_role(MECHANIC_MAINTENANCE_MANAGER_ROLE) == MAINTENANCE_MANAGER_ROLE
    assert canonical_access_role(MAINTENANCE_MANAGER_ROLE) == MAINTENANCE_MANAGER_ROLE
    assert canonical_access_role("Mechanic") == "Mechanic"
    assert roles_have_equivalent_access(
        MAINTENANCE_MANAGER_ROLE, MECHANIC_MAINTENANCE_MANAGER_ROLE
    )
    assert set(expand_equivalent_role_names([MAINTENANCE_MANAGER_ROLE])) == set(MM_ROLES)


@pytest.mark.parametrize("role_name", MM_ROLES)
def test_atl_paged_rbac_is_identical_for_maintenance_manager_roles(role_name: str):
    assert atl_paged_list_skips_work_status_rbac(role_name) is True
    assert allowed_work_statuses_for_atl_paged_list(role_name) == (
        allowed_work_statuses_for_atl_paged_list(MAINTENANCE_MANAGER_ROLE)
    )


def test_atl_edit_and_workflow_rbac_are_identical_for_maintenance_manager_roles():
    update_data = {"work_status": WorkStatus.APPROVED}
    for status in WorkStatus:
        manager_can_edit = can_edit_atl_for_role_and_status(
            MAINTENANCE_MANAGER_ROLE, status
        )
        mechanic_can_edit = can_edit_atl_for_role_and_status(
            MECHANIC_MAINTENANCE_MANAGER_ROLE, status
        )
        assert mechanic_can_edit is manager_can_edit

        manager_workflow = is_maintenance_manager_workflow_only_update(
            MAINTENANCE_MANAGER_ROLE, WorkStatus.FOR_REVIEW, update_data
        )
        mechanic_workflow = is_maintenance_manager_workflow_only_update(
            MECHANIC_MAINTENANCE_MANAGER_ROLE, WorkStatus.FOR_REVIEW, update_data
        )
        assert mechanic_workflow is manager_workflow

        for next_status in WorkStatus:
            manager_transition = is_atl_work_status_transition_allowed(
                MAINTENANCE_MANAGER_ROLE, status, next_status
            )
            mechanic_transition = is_atl_work_status_transition_allowed(
                MECHANIC_MAINTENANCE_MANAGER_ROLE, status, next_status
            )
            assert mechanic_transition is manager_transition


def test_mechanic_role_does_not_inherit_maintenance_manager_access():
    assert atl_paged_list_skips_work_status_rbac("Mechanic") is False
    assert not can_edit_atl_for_role_and_status("Mechanic", WorkStatus.APPROVED)
    assert can_edit_atl_for_role_and_status(
        MECHANIC_MAINTENANCE_MANAGER_ROLE, WorkStatus.APPROVED
    )


def test_validate_atl_edit_allows_same_workflow_for_both_manager_roles():
    for role_name in MM_ROLES:
        validate_atl_edit_allowed_for_account(
            role_name=role_name,
            current_status=WorkStatus.FOR_REVIEW,
            update_data={"work_status": WorkStatus.APPROVED},
        )


@pytest.mark.asyncio
async def test_module_permission_checks_match_for_both_manager_roles(
    db_session: AsyncSession,
):
    roles = _load_seeded_roles()
    manager_seed = _seed_role(roles, MAINTENANCE_MANAGER_ROLE)
    accounts = {}
    modules = {}

    for role_name in MM_ROLES:
        role_id = await seed_role(db_session, name=role_name)
        for perm in manager_seed["permissions"]:
            module_name = perm["module"]
            if module_name not in modules:
                modules[module_name] = await seed_module(db_session, module_name)
            await seed_role_permission(
                db_session,
                role_id=role_id,
                module_id=modules[module_name],
                can_read=bool(perm.get("read", False)),
                can_create=bool(perm.get("create", False)),
                can_update=bool(perm.get("update", False)),
                can_delete=bool(perm.get("delete", False)),
                can_approve=bool(perm.get("approve", False)),
            )
        account_id = await seed_account(
            db_session,
            role_id=role_id,
            username=f"user_{role_name.replace(' ', '_').replace('-', '_')}",
        )
        accounts[role_name] = account_id
    await db_session.commit()

    from app.models.account import AccountInformation

    all_modules = {perm["module"] for perm in manager_seed["permissions"]}
    all_modules.add("System Settings")
    all_modules.add("Regulatory Compliance")
    for extra in ("System Settings", "Regulatory Compliance"):
        if extra not in modules:
            modules[extra] = await seed_module(db_session, extra)
    await db_session.commit()

    for module_name in all_modules:
        for action in PERMISSION_ACTIONS:
            results = []
            for role_name in MM_ROLES:
                account = await db_session.get(AccountInformation, accounts[role_name])
                try:
                    await ensure_account_permission(
                        db_session, account, module_name, action
                    )
                    results.append("allowed")
                except HTTPException as exc:
                    results.append(exc.status_code)
            assert results[0] == results[1], (
                f"{module_name}.{action} diverged: {dict(zip(MM_ROLES, results))}"
            )


@pytest.mark.asyncio
async def test_notification_lookup_for_maintenance_manager_includes_equivalent_role(
    db_session: AsyncSession,
):
    manager_role_id = await seed_role(db_session, name=MAINTENANCE_MANAGER_ROLE)
    mechanic_role_id = await seed_role(
        db_session, name=MECHANIC_MAINTENANCE_MANAGER_ROLE
    )
    manager_id = await seed_account(db_session, role_id=manager_role_id, username="mm_user")
    mechanic_id = await seed_account(
        db_session, role_id=mechanic_role_id, username="mechanic_mm_user"
    )
    await db_session.commit()

    found = await get_active_accounts_by_roles(db_session, [MAINTENANCE_MANAGER_ROLE])
    assert {account.id for account in found} == {manager_id, mechanic_id}

    found_from_alias = await get_active_accounts_by_roles(
        db_session, [MECHANIC_MAINTENANCE_MANAGER_ROLE]
    )
    assert {account.id for account in found_from_alias} == {manager_id, mechanic_id}
