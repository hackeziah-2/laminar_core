"""Unit tests for ATL paged list work_status RBAC mapping."""
from app.core.atl_paged_rbac import (
    allowed_work_statuses_for_atl_paged_list,
    atl_paged_list_skips_work_status_rbac,
)
from app.models.aircraft_techinical_log import WorkStatus


def test_rbac_maintenance_planner_statuses():
    allowed = allowed_work_statuses_for_atl_paged_list("Maintenance Planner")
    assert set(allowed) == {
        WorkStatus.FOR_REVIEW,
        WorkStatus.AWAITING_ATTACHMENT,
        WorkStatus.COMPLETED,
        WorkStatus.PENDING,
        WorkStatus.APPROVED,
        WorkStatus.REJECTED_MAINTENANCE,
        WorkStatus.REJECTED_QUALITY,
    }


def test_rbac_maintenance_manager_statuses():
    allowed = allowed_work_statuses_for_atl_paged_list("Maintenance Manager")
    assert set(allowed) == {WorkStatus.FOR_REVIEW, WorkStatus.APPROVED}


def test_rbac_technical_publication_statuses():
    allowed = allowed_work_statuses_for_atl_paged_list("Technical Publication")
    assert set(allowed) == {WorkStatus.AWAITING_ATTACHMENT, WorkStatus.PENDING}


def test_rbac_quality_manager_statuses():
    allowed = allowed_work_statuses_for_atl_paged_list("Quality Manager")
    assert set(allowed) == {WorkStatus.PENDING, WorkStatus.COMPLETED}


def test_rbac_unknown_role_returns_empty():
    assert allowed_work_statuses_for_atl_paged_list("Nonexistent Role For RBAC Test") == ()


def test_rbac_admin_not_in_status_map_but_skips_filter():
    assert allowed_work_statuses_for_atl_paged_list("Admin") == ()
    assert atl_paged_list_skips_work_status_rbac("Admin") is True
    assert atl_paged_list_skips_work_status_rbac("admin") is True
    assert atl_paged_list_skips_work_status_rbac("Maintenance Manager") is False


def test_rbac_case_insensitive_role_name():
    allowed = allowed_work_statuses_for_atl_paged_list("quality manager")
    assert WorkStatus.PENDING in allowed


def test_rbac_blank_role_name_returns_empty():
    assert allowed_work_statuses_for_atl_paged_list("") == ()
    assert allowed_work_statuses_for_atl_paged_list(None) == ()
