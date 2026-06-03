"""ATL edit RBAC for Operation / Technical Logbook."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_account
from app.core.atl_edit_rbac import (
    ATL_EDIT_FORBIDDEN_MESSAGE,
    can_edit_atl_for_role_and_status,
    is_maintenance_planner_renew_only_update,
    is_maintenance_manager_workflow_only_update,
    validate_atl_edit_allowed_for_account,
)
from app.main import app
from app.models.aircraft_techinical_log import WorkStatus
from app.models.role import Role
from tests.conftest import TestSessionLocal


def test_can_edit_atl_matrix():
    assert can_edit_atl_for_role_and_status("Admin", WorkStatus.COMPLETED)
    assert can_edit_atl_for_role_and_status(
        "Maintenance Planner", WorkStatus.FOR_REVIEW
    )
    assert not can_edit_atl_for_role_and_status(
        "Maintenance Planner", WorkStatus.APPROVED
    )
    assert can_edit_atl_for_role_and_status(
        "Maintenance Manager", WorkStatus.REJECTED_MAINTENANCE
    )
    assert not can_edit_atl_for_role_and_status(
        "Maintenance Manager", WorkStatus.COMPLETED
    )
    assert can_edit_atl_for_role_and_status(
        "Quality Manager", WorkStatus.COMPLETED
    )
    assert not can_edit_atl_for_role_and_status("Mechanic", WorkStatus.PENDING)


def test_validate_raises_standard_message():
    with pytest.raises(ValueError, match=ATL_EDIT_FORBIDDEN_MESSAGE):
        validate_atl_edit_allowed_for_account(
            role_name="Maintenance Planner",
            current_status=WorkStatus.APPROVED,
            update_data={"remarks": "nope"},
        )


def test_maintenance_planner_renew_only_update():
    assert is_maintenance_planner_renew_only_update(
        "Maintenance Planner",
        WorkStatus.REJECTED_QUALITY,
        {"work_status": WorkStatus.PENDING},
    )


def test_maintenance_manager_workflow_only_update():
    assert is_maintenance_manager_workflow_only_update(
        "Maintenance Manager",
        WorkStatus.FOR_REVIEW,
        {"work_status": WorkStatus.APPROVED},
    )


def test_maintenance_planner_cannot_update_approved_atl(client: TestClient):
    async def seed_role() -> int:
        async with TestSessionLocal() as session:
            role = Role(name="Maintenance Planner", description="ATL RBAC")
            session.add(role)
            await session.commit()
            await session.refresh(role)
            return role.id

    planner_role_id = asyncio.run(seed_role())

    async def override_account():
        acc = type("Acc", (), {})()
        acc.id = 8810
        acc.status = True
        acc.role_id = planner_role_id
        return acc

    app.dependency_overrides[get_current_active_account] = override_account

    log_data = {
        "aircraft_fk": 1,
        "sequence_no": "ATL-MP-001",
        "nature_of_flight": "TR",
        "origin_station": "ORG",
        "origin_date": "2025-01-17",
        "origin_time": "10:00:00",
        "destination_station": "DST",
        "destination_date": "2025-01-17",
        "destination_time": "12:00:00",
        "number_of_landings": 1,
        "hobbs_meter_start": 1.0,
        "hobbs_meter_end": 2.0,
        "hobbs_meter_total": 1.0,
        "tachometer_start": 1.0,
        "tachometer_end": 2.0,
        "tachometer_total": 1.0,
        "work_status": "APPROVED",
        "component_parts": [],
    }

    create_response = client.post("/api/v1/aircraft-technical-log/", json=log_data)
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json={"remarks": "should be blocked"},
    )
    assert update_response.status_code == 403
    assert update_response.json()["detail"] == ATL_EDIT_FORBIDDEN_MESSAGE

    app.dependency_overrides.pop(get_current_active_account, None)


def test_quality_manager_can_update_completed_atl(client: TestClient):
    async def seed_role() -> int:
        async with TestSessionLocal() as session:
            role = Role(name="Quality Manager", description="ATL RBAC")
            session.add(role)
            await session.commit()
            await session.refresh(role)
            return role.id

    qm_role_id = asyncio.run(seed_role())

    async def override_account():
        acc = type("Acc", (), {})()
        acc.id = 8814
        acc.status = True
        acc.role_id = qm_role_id
        return acc

    app.dependency_overrides[get_current_active_account] = override_account

    log_data = {
        "aircraft_fk": 1,
        "sequence_no": "ATL-QM-COMP",
        "nature_of_flight": "TR",
        "origin_station": "ORG",
        "origin_date": "2025-01-17",
        "origin_time": "10:00:00",
        "destination_station": "DST",
        "destination_date": "2025-01-17",
        "destination_time": "12:00:00",
        "number_of_landings": 1,
        "hobbs_meter_start": 1.0,
        "hobbs_meter_end": 2.0,
        "hobbs_meter_total": 1.0,
        "tachometer_start": 1.0,
        "tachometer_end": 2.0,
        "tachometer_total": 1.0,
        "work_status": "COMPLETED",
        "component_parts": [],
    }

    create_response = client.post("/api/v1/aircraft-technical-log/", json=log_data)
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/v1/aircraft-technical-log/{log_id}",
        json={"remarks": "qm edit ok"},
    )
    assert update_response.status_code == 200

    app.dependency_overrides.pop(get_current_active_account, None)
