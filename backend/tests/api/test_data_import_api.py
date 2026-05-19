"""API tests for Excel/CSV import endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from tests.factories.import_files import (
    ad_csv_bytes,
    ad_work_order_csv_bytes,
    aircraft_csv_bytes,
    invalid_extension_bytes,
    ldnd_csv_bytes,
)


# --- Registry ---


def test_list_import_targets(
    client_with_general_information_import_auth: TestClient,
):
    response = client_with_general_information_import_auth.get(
        "/api/v1/excel-data/targets",
    )
    assert response.status_code == 200, response.text
    keys = {t["key"] for t in response.json()}
    assert "aircraft" in keys
    assert "aircraft-technical-log" in keys
    assert "maintenance-ldnd" in keys
    assert "maintenance-ad" in keys
    assert "maintenance-ad-work-orders" in keys


@pytest.mark.asyncio
async def test_aircraft_import_via_dynamic_target_key(
    async_client_with_general_information_import_auth: AsyncClient,
):
    response = await async_client_with_general_information_import_auth.post(
        "/api/v1/excel-data/aircraft/import?dry_run=true",
        files={"file": ("aircraft.csv", aircraft_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "dry-run"


def test_import_unknown_target_not_found(
    client_with_general_information_import_auth: TestClient,
):
    response = client_with_general_information_import_auth.post(
        "/api/v1/excel-data/unknown-table/import?dry_run=true",
        files={"file": ("aircraft.csv", aircraft_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 404
    assert "Unknown import target" in response.json()["detail"]


# --- Aircraft import (/api/v1/excel-data/aircraft/import) ---


@pytest.mark.asyncio
async def test_aircraft_import_dry_run_success(
    async_client_with_general_information_import_auth: AsyncClient,
):
    """1. Success — dry_run validates without persisting."""
    response = await async_client_with_general_information_import_auth.post(
        "/api/v1/excel-data/aircraft/import?dry_run=true",
        files={"file": ("aircraft.csv", aircraft_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dry-run"
    assert body["inserted"] >= 1
    assert body["errors"] == []


def test_aircraft_import_invalid_extension_validation(
    client_with_general_information_import_auth: TestClient,
):
    """2. Validation — unsupported file type."""
    response = client_with_general_information_import_auth.post(
        "/api/v1/excel-data/aircraft/import",
        files={"file": ("data.txt", invalid_extension_bytes(), "text/plain")},
    )
    assert response.status_code == 400
    assert "file" in response.json()["detail"].lower() or "upload" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_aircraft_import_unauthorized(async_client: AsyncClient):
    """5. Unauthorized — no Bearer token."""
    response = await async_client.post(
        "/api/v1/excel-data/aircraft/import",
        files={"file": ("aircraft.csv", aircraft_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 401


def test_aircraft_import_forbidden_without_module_permission(
    client_without_import_permission: TestClient,
):
    """4. RBAC — authenticated but missing can_create on General Information."""
    response = client_without_import_permission.post(
        "/api/v1/excel-data/aircraft/import?dry_run=true",
        files={"file": ("aircraft.csv", aircraft_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 403
    assert "Permission denied" in response.json()["detail"]


def test_aircraft_import_row_validation_error(
    client_with_general_information_import_auth: TestClient,
):
    """2. Validation — missing required columns produces failed status with row errors."""
    bad_csv = b"registration\nONLY-REG\n"
    response = client_with_general_information_import_auth.post(
        "/api/v1/excel-data/aircraft/import?dry_run=true",
        files={"file": ("bad.csv", bad_csv, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dry-run"
    assert len(body["errors"]) >= 1


# --- ATL import (/api/v1/excel-data/aircraft-technical-log/import) ---


def test_atl_import_missing_batch_id_validation(
    client_with_maintenance_import_auth: TestClient,
):
    """2. Validation — batch_id required."""
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/aircraft-technical-log/import",
        data={"aircraft_id": "1"},
        files={"file": ("atl.csv", b"sequence_no\n1\n", "text/csv")},
    )
    assert response.status_code == 400
    assert "batch_id" in response.json()["detail"].lower()


def test_atl_import_aircraft_not_found(
    client_with_maintenance_import_auth: TestClient,
):
    """3. Not found — unknown aircraft_id."""
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/aircraft-technical-log/import",
        data={"aircraft_id": "99999", "batch_id": "1"},
        files={"file": ("atl.csv", b"sequence_no\n1\n", "text/csv")},
    )
    assert response.status_code == 404
    assert "Aircraft" in response.json()["detail"]


def test_atl_import_batch_not_found(
    client_with_maintenance_import_auth: TestClient,
):
    """3. Not found — unknown atl_batch."""
    import asyncio

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="ATL-IMP-AC",
                manufacturer="Cessna",
                model="172",
                msn="ATL-MSN-1",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.commit()
            await session.refresh(ac)
            return ac.id

    aircraft_pk = asyncio.run(_seed_aircraft())

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/aircraft-technical-log/import",
        data={"aircraft_id": str(aircraft_pk), "batch_id": "99999"},
        files={"file": ("atl.csv", b"sequence_no\n1\n", "text/csv")},
    )
    assert response.status_code == 404
    assert "batch" in response.json()["detail"].lower()


# --- AD import (/api/v1/excel-data/maintenance-ad/import) ---


def test_ad_import_missing_aircraft_context(
    client_with_maintenance_import_auth: TestClient,
):
    """Validation — aircraft_id or registration required."""
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ad/import",
        files={"file": ("ad.csv", ad_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 400
    assert "aircraft" in response.json()["detail"].lower()


def test_ad_import_dry_run_success(
    client_with_maintenance_import_auth: TestClient,
):
    """Dry run validates AD rows for a seeded aircraft."""
    import asyncio

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="AD-IMP-AC",
                manufacturer="Cessna",
                model="172",
                msn="AD-MSN-1",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.commit()
            await session.refresh(ac)
            return ac.id

    aircraft_pk = asyncio.run(_seed_aircraft())

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ad/import?dry_run=true",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("ad.csv", ad_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dry-run"
    assert body["inserted"] >= 1
    assert body["errors"] == []


def test_ad_import_dry_run_date_formats(
    client_with_maintenance_import_auth: TestClient,
):
    """Dates accept M/D/YYYY and DD-Mon-YY string formats."""
    import asyncio

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="AD-DATE-AC",
                manufacturer="Cessna",
                model="172",
                msn="AD-DATE-MSN",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.commit()
            await session.refresh(ac)
            return ac.id

    aircraft_pk = asyncio.run(_seed_aircraft())
    rows = [
        {
            "AD Number": "32232",
            "Subject": "TEST AD ONE",
            "Inspection Interval": "Annual",
            "Date of Effectivity": "6/5/2023",
        },
        {
            "AD Number": "32233",
            "Subject": "TEST AD TWO",
            "Inspection Interval": "100 HRS",
            "Date of Effectivity or Compliance Date": "23-Jul-23",
        },
    ]

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ad/import?dry_run=true",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("ad.csv", ad_csv_bytes(rows), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dry-run"
    assert body["inserted"] == 2
    assert body["errors"] == []


def test_ad_import_upserts_on_ad_number(
    client_with_maintenance_import_auth: TestClient,
):
    """Re-importing the same AD Number updates the row (per aircraft), not duplicates."""
    import asyncio

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="AD-UPSERT-AC",
                manufacturer="Cessna",
                model="172",
                msn="AD-UPSERT-MSN",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.commit()
            await session.refresh(ac)
            return ac.id

    aircraft_pk = asyncio.run(_seed_aircraft())
    row = {
        "AD Number": "32232",
        "Subject": "ORIGINAL SUBJECT",
        "Inspection Interval": "Annual",
        "Date of Effectivity": "6/5/2023",
    }
    updated_row = {**row, "Subject": "UPDATED SUBJECT"}

    first = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ad/import",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("ad.csv", ad_csv_bytes([row]), "text/csv")},
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "success"
    assert first.json()["inserted"] == 1

    second = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ad/import?dry_run=true",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("ad.csv", ad_csv_bytes([updated_row]), "text/csv")},
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["updated"] == 1
    assert body["inserted"] == 0


# --- AD work-order import (/api/v1/excel-data/maintenance-ad-work-orders/import) ---


def test_ad_work_order_import_missing_ad_monitoring_context(
    client_with_maintenance_import_auth: TestClient,
):
    """Validation — ad_monitoring_id or ad_monitoring_fk required."""
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ad-work-orders/import",
        files={"file": ("ad-wo.csv", ad_work_order_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 400
    assert "ad_monitoring" in response.json()["detail"].lower()


def test_ad_work_order_import_dry_run_success(
    client_with_maintenance_import_auth: TestClient,
):
    """Dry run validates AD work-order rows for a seeded AD monitoring record."""
    import asyncio

    from app.models.ad_monitoring import ADMonitoring
    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_ad_monitoring() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="AD-WO-AC",
                manufacturer="Cessna",
                model="172",
                msn="AD-WO-MSN",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.flush()
            ad = ADMonitoring(
                aircraft_fk=ac.id,
                ad_number="32232",
                subject="TEST AD",
                inspection_interval="Annual",
            )
            session.add(ad)
            await session.commit()
            await session.refresh(ad)
            return ad.id

    ad_pk = asyncio.run(_seed_ad_monitoring())

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ad-work-orders/import?dry_run=true",
        data={"ad_monitoring_id": str(ad_pk)},
        files={"file": ("ad-wo.csv", ad_work_order_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dry-run"
    assert body["inserted"] >= 1
    assert body["errors"] == []


def test_ad_work_order_import_dry_run_date_formats(
    client_with_maintenance_import_auth: TestClient,
):
    """Dates accept M/D/YYYY and DD-Mon-YY string formats."""
    import asyncio

    from app.models.ad_monitoring import ADMonitoring
    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_ad_monitoring() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="AD-WO-DATE-AC",
                manufacturer="Cessna",
                model="172",
                msn="AD-WO-DATE-MSN",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.flush()
            ad = ADMonitoring(
                aircraft_fk=ac.id,
                ad_number="32233",
                subject="TEST AD",
                inspection_interval="100 HRS",
            )
            session.add(ad)
            await session.commit()
            await session.refresh(ad)
            return ad.id

    ad_pk = asyncio.run(_seed_ad_monitoring())
    rows = [
        {
            "WO Number": "17212-A-000343",
            "Last Done Actt": "6080.1",
            "Last Done Tach": "6079.5",
            "Last Done Date": "6/5/2023",
            "Next Done Actt": "6180.1",
            "Tach": "6179.5",
            "Atl Ref": "ATL-0002225",
        },
        {
            "WO Number": "17212-A-000351",
            "Last Done Actt": "6179.3",
            "Last Done Tach": "6178.7",
            "Last Done Date": "23-Jul-23",
            "Next Done Actt": "6279.3",
            "Tach": "6278.7",
            "Atl Ref": "ATL-0002412",
        },
    ]

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ad-work-orders/import?dry_run=true",
        data={"ad_monitoring_fk": str(ad_pk)},
        files={"file": ("ad-wo.csv", ad_work_order_csv_bytes(rows), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dry-run"
    assert body["inserted"] == 2
    assert body["errors"] == []


def test_ad_work_order_import_upserts_on_work_order_number(
    client_with_maintenance_import_auth: TestClient,
):
    """Re-importing the same WO Number updates the row (per AD), not duplicates."""
    import asyncio

    from app.models.ad_monitoring import ADMonitoring
    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_ad_monitoring() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="AD-WO-UPSERT-AC",
                manufacturer="Cessna",
                model="172",
                msn="AD-WO-UPSERT-MSN",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.flush()
            ad = ADMonitoring(
                aircraft_fk=ac.id,
                ad_number="32234",
                subject="TEST AD",
                inspection_interval="Annual",
            )
            session.add(ad)
            await session.commit()
            await session.refresh(ad)
            return ad.id

    ad_pk = asyncio.run(_seed_ad_monitoring())
    row = {
        "WO Number": "17212-A-000343",
        "Last Done Actt": "6080.1",
        "Last Done Tach": "6079.5",
        "Last Done Date": "6/5/2023",
        "Next Done Actt": "6180.1",
        "Tach": "6179.5",
        "Atl Ref": "ATL-0002225",
    }
    updated_row = {**row, "Atl Ref": "ATL-UPDATED"}

    first = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ad-work-orders/import",
        data={"ad_monitoring_id": str(ad_pk)},
        files={"file": ("ad-wo.csv", ad_work_order_csv_bytes([row]), "text/csv")},
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "success"
    assert first.json()["inserted"] == 1

    second = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ad-work-orders/import?dry_run=true",
        data={"ad_monitoring_id": str(ad_pk)},
        files={"file": ("ad-wo.csv", ad_work_order_csv_bytes([updated_row]), "text/csv")},
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["updated"] == 1
    assert body["inserted"] == 0


# --- LDND import (/api/v1/excel-data/maintenance-ldnd/import) ---


def test_ldnd_import_missing_aircraft_context(
    client_with_maintenance_import_auth: TestClient,
):
    """Validation — aircraft_id or registration required."""
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ldnd/import",
        files={"file": ("ldnd.csv", ldnd_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 400
    assert "aircraft" in response.json()["detail"].lower()


def test_ldnd_import_dry_run_multiple_rows_same_inspection_type(
    client_with_maintenance_import_auth: TestClient,
):
    """Upsert key is aircraft + last_done_tach_done (not inspection_type)."""
    import asyncio

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal
    from tests.factories.import_files import ldnd_csv_bytes

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="LDND-MULTI-AC",
                manufacturer="Cessna",
                model="172",
                msn="LDND-MULTI-MSN",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.commit()
            await session.refresh(ac)
            return ac.id

    aircraft_pk = asyncio.run(_seed_aircraft())
    rows = [
        {
            "Inspection Type": "200",
            "Unit": "HRS",
            "Last Done Tach Due": "5878.4",
            "Last Done Tach Done": "5879.2",
            "Next Due Tach Hours": "5879.2",
            "Performed Date Start": "2023-04-13",
            "Performed Date End": "2023-04-12",
        },
        {
            "Inspection Type": "50",
            "Unit": "HRS",
            "Last Done Tach Due": "5928.4",
            "Last Done Tach Done": "5928.6",
            "Next Due Tach Hours": "5928.6",
            "Performed Date Start": "2023-04-28",
            "Performed Date End": "2023-04-28",
        },
        {
            "Inspection Type": "200",
            "Unit": "HRS",
            "Last Done Tach Due": "6079.4",
            "Last Done Tach Done": "6079.4",
            "Next Due Tach Hours": "6079.4",
            "Performed Date Start": "2023-06-06",
            "Performed Date End": "2023-06-05",
        },
    ]

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ldnd/import?dry_run=true",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("ldnd.csv", ldnd_csv_bytes(rows), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dry-run"
    assert body["inserted"] == 3
    assert body["errors"] == []


def test_ldnd_import_dry_run_success(
    client_with_maintenance_import_auth: TestClient,
):
    """Dry run validates LDND rows for a seeded aircraft."""
    import asyncio

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="LDND-IMP-AC",
                manufacturer="Cessna",
                model="172",
                msn="LDND-MSN-1",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.commit()
            await session.refresh(ac)
            return ac.id

    aircraft_pk = asyncio.run(_seed_aircraft())

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ldnd/import?dry_run=true",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("ldnd.csv", ldnd_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dry-run"
    assert body["inserted"] >= 1
    assert body["errors"] == []


@pytest.mark.no_auth
def test_atl_import_unauthorized(client: TestClient):
    """5. Unauthorized — ATL import without auth."""
    response = client.post(
        "/api/v1/excel-data/aircraft-technical-log/import",
        data={"batch_id": "1", "aircraft_id": "1"},
        files={"file": ("atl.csv", b"sequence_no\n1\n", "text/csv")},
    )
    assert response.status_code == 401
