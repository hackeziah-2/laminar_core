"""API tests for Excel/CSV import endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import select

from tests.factories.import_files import (
    ad_csv_bytes,
    ad_work_order_csv_bytes,
    ad_work_order_csv_bytes_with_headers,
    ad_work_order_tsv_bytes,
    aircraft_csv_bytes,
    cpcp_csv_bytes,
    invalid_extension_bytes,
    ldnd_csv_bytes,
    tcc_csv_bytes,
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
    assert "maintenance-tcc" in keys
    assert "maintenance-cpcp" in keys


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


def test_atl_import_persists_values_without_recomputation(
    client_with_maintenance_import_auth: TestClient,
):
    """ATL import saves file values only; no auto_* or TSO/TBO backfill from prior rows."""
    import asyncio

    from app.models.aircraft import Aircraft
    from app.models.aircraft_techinical_log import AircraftTechnicalLog
    from app.models.atl_batch import AtlBatch
    from tests.conftest import TestSessionLocal

    async def _seed() -> tuple[int, int]:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="ATL-IMP-BF",
                model="172",
                msn="ATL-MSN-BF",
                base="Base",
                ownership="Owner",
                status="Active",
                airframe_aftt=10.0,
                engine_life_time_limit=1000.0,
                engine_tso=100.0,
                propeller_life_time_limit=600.0,
                propeller_tso=50.0,
            )
            session.add(ac)
            await session.flush()
            batch = AtlBatch(name="Import BF", description="pytest")
            session.add(batch)
            await session.commit()
            await session.refresh(ac)
            await session.refresh(batch)
            return ac.id, batch.id

    aircraft_id, batch_id = asyncio.run(_seed())
    csv_body = (
        b"SEQ NO.,TACH START,TACH END,ENGINE TSO,ENGINE TBO\n"
        b"001,1,2,111,888\n"
        b"002,2,3.5,222,777\n"
    )
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/aircraft-technical-log/import",
        data={"aircraft_id": str(aircraft_id), "batch_id": str(batch_id)},
        files={"file": ("atl.csv", csv_body, "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"

    async def _check_rows() -> None:
        from decimal import Decimal

        from sqlalchemy import Numeric, cast

        async with TestSessionLocal() as session:
            rows = (
                await session.execute(
                    select(AircraftTechnicalLog)
                    .where(AircraftTechnicalLog.aircraft_fk == aircraft_id)
                    .where(AircraftTechnicalLog.atl_batch_fk == batch_id)
                    .order_by(cast(AircraftTechnicalLog.sequence_no, Numeric).asc())
                )
            ).scalars().all()
            assert len(rows) == 2

            first, second = rows
            assert float(first.tachometer_start) == 1.0
            assert float(first.tachometer_end) == 2.0
            assert float(first.engine_tso) == 111.0
            assert float(first.engine_tbo) == 888.0
            assert first.auto_airframe_run_time is None
            assert first.auto_engine_tso is None

            assert float(second.tachometer_start) == 2.0
            assert float(second.tachometer_end) == 3.5
            assert float(second.engine_tso) == 222.0
            assert float(second.engine_tbo) == 777.0
            assert second.auto_airframe_run_time is None
            assert second.auto_engine_tso is None

    asyncio.run(_check_rows())


def test_atl_import_preserves_high_precision_decimals(
    client_with_maintenance_import_auth: TestClient,
):
    """ATL import stores exact decimal digits from spreadsheet text (no rounding)."""
    import asyncio
    from decimal import Decimal

    from app.models.aircraft import Aircraft
    from app.models.aircraft_techinical_log import AircraftTechnicalLog
    from app.models.atl_batch import AtlBatch
    from tests.conftest import TestSessionLocal

    async def _seed() -> tuple[int, int]:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="ATL-PREC-AC",
                model="172",
                msn="ATL-PREC-MSN",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.flush()
            batch = AtlBatch(name="Import precision", description="pytest")
            session.add(batch)
            await session.commit()
            await session.refresh(ac)
            await session.refresh(batch)
            return ac.id, batch.id

    aircraft_id, batch_id = asyncio.run(_seed())
    csv_body = (
        b"SEQ NO.,TACH END,ENGINE TSO,PROPELLER TSN,AIRFRAME AFTT\n"
        b"001,123.4567,45.10,80.5,502.5000\n"
    )
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/aircraft-technical-log/import",
        data={"aircraft_id": str(aircraft_id), "batch_id": str(batch_id)},
        files={"file": ("atl.csv", csv_body, "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"

    async def _check_precision() -> None:
        async with TestSessionLocal() as session:
            row = (
                await session.execute(
                    select(AircraftTechnicalLog)
                    .where(AircraftTechnicalLog.aircraft_fk == aircraft_id)
                    .where(AircraftTechnicalLog.atl_batch_fk == batch_id)
                )
            ).scalar_one()
            assert Decimal(str(row.tachometer_end)) == Decimal("123.4567")
            assert Decimal(str(row.engine_tso)) == Decimal("45.10")
            assert Decimal(str(row.propeller_tsn)) == Decimal("80.5")
            assert Decimal(str(row.airframe_aftt)) == Decimal("502.5000")

    asyncio.run(_check_precision())


ATL_LIST_DETAIL_TIME_FIELDS = (
    "airframe_aftt",
    "airframe_run_time",
    "engine_run_time",
    "engine_tsn",
    "engine_tso",
    "engine_tbo",
    "propeller_run_time",
    "propeller_tsn",
    "propeller_tso",
    "propeller_tbo",
)


def test_atl_import_list_and_detail_return_identical_time_fields(
    client_with_maintenance_import_auth: TestClient,
):
    """After import, paged list and detail GET must return the same persisted time columns."""
    import asyncio

    from app.models.aircraft import Aircraft
    from app.models.atl_batch import AtlBatch
    from tests.conftest import TestSessionLocal

    async def _seed() -> tuple[int, int]:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="ATL-IMP-LD",
                model="172",
                msn="ATL-MSN-LD",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.flush()
            batch = AtlBatch(name="Import list/detail", description="pytest")
            session.add(batch)
            await session.commit()
            await session.refresh(ac)
            await session.refresh(batch)
            return ac.id, batch.id

    aircraft_id, batch_id = asyncio.run(_seed())
    csv_body = (
        b"SEQ NO.,TACH START,TACH END,AIRFRAME RUN TIME,AFTT,"
        b"ENGINE RUN TIME,ENGINE TSN,ENGINE TSO,ENGINE TBO,"
        b"PROPELLER RUN TIME,PROPELLER TSN,PROPELLER TSO,PROPELLER TBO\n"
        b"001,10,12.5,2.5,502.5,2.5,1200.50,300.25,699.75,2.5,800,150.5,449.5\n"
    )
    import_response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/aircraft-technical-log/import",
        data={"aircraft_id": str(aircraft_id), "batch_id": str(batch_id)},
        files={"file": ("atl.csv", csv_body, "text/csv")},
    )
    assert import_response.status_code == 200, import_response.text
    assert import_response.json()["status"] == "success"

    paged_response = client_with_maintenance_import_auth.get(
        f"/api/v1/aircraft-technical-log/paged"
        f"?aircraft_fk={aircraft_id}&atl_batch_fk={batch_id}&limit=10&page=1"
    )
    assert paged_response.status_code == 200, paged_response.text
    items = paged_response.json()["items"]
    assert len(items) == 1, items
    list_row = items[0]

    detail_response = client_with_maintenance_import_auth.get(
        f"/api/v1/aircraft-technical-log/{list_row['id']}"
    )
    assert detail_response.status_code == 200, detail_response.text
    detail_row = detail_response.json()

    for field in ATL_LIST_DETAIL_TIME_FIELDS:
        assert list_row[field] == detail_row[field], field

    recompute_response = client_with_maintenance_import_auth.get(
        f"/api/v1/aircraft-technical-log/{list_row['id']}?recompute=true"
    )
    assert recompute_response.status_code == 200, recompute_response.text
    assert recompute_response.json()["auto_airframe_run_time"] == 2.5


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


@pytest.mark.parametrize(
    "header_labels",
    [
        {
            "AD NUMBER": "ad_number",
            "SUBJECT": "subject",
            "INSPECTION INTERVAL": "inspection_interval",
            "DATE OF EFFECTIVITY": "compli_date",
        },
        {
            "ad number": "ad_number",
            "subject": "subject",
            "inspection interval": "inspection_interval",
            "date of effectivity or compliance date": "compli_date",
        },
        {
            "ad_number": "ad_number",
            "subject": "subject",
            "inspection_interval": "inspection_interval",
            "compli_date": "compli_date",
        },
    ],
)
def test_ad_import_accepts_header_casing(
    client_with_maintenance_import_auth: TestClient,
    header_labels: dict,
):
    """AD import accepts uppercase, lowercase, and snake_case headers."""
    import asyncio
    import csv
    import io

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="AD-CASE-AC",
                model="172",
                msn="AD-CASE-MSN",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.commit()
            await session.refresh(ac)
            return ac.id

    aircraft_pk = asyncio.run(_seed_aircraft())
    default_values = {
        "ad_number": "32236",
        "subject": "TEST AD",
        "inspection_interval": "Annual",
        "compli_date": "6/5/2023",
    }
    row = {header: default_values[field] for header, field in header_labels.items()}
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(header_labels.keys()))
    writer.writeheader()
    writer.writerow(row)

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-ad/import?dry_run=true",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("ad.csv", buf.getvalue().encode("utf-8"), "text/csv")},
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


def test_ad_work_order_import_tab_separated_headers(
    client_with_maintenance_import_auth: TestClient,
):
    """Tab-separated files with canonical headers import correctly."""
    import asyncio

    from app.models.ad_monitoring import ADMonitoring
    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_ad_monitoring() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="AD-WO-TSV-AC",
                model="172",
                msn="AD-WO-TSV-MSN",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.flush()
            ad = ADMonitoring(
                aircraft_fk=ac.id,
                ad_number="32237",
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
        files={
            "file": (
                "ad-wo.csv",
                ad_work_order_tsv_bytes(),
                "text/csv",
            )
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dry-run"
    assert body["inserted"] >= 1
    assert body["errors"] == []


@pytest.mark.parametrize(
    "header_labels",
    [
        {
            "WO NUMBER": "work_order_number",
            "LAST DONE AFTT": "last_done_aftt",
            "LAST DONE TACH": "last_done_tach",
            "LAST DONE DATE": "last_done_date",
            "NEXT DUE AFTT": "next_due_aftt",
            "NEXT DUE TACH": "next_due_tach",
            "ATL REF": "atl_ref",
        },
        {
            "wo number": "work_order_number",
            "last done aftt": "last_done_aftt",
            "last done tach": "last_done_tach",
            "last done date": "last_done_date",
            "next due aftt": "next_due_aftt",
            "next due tach": "next_due_tach",
            "atl ref": "atl_ref",
        },
        {
            "wo_number": "work_order_number",
            "last_done_aftt": "last_done_aftt",
            "last_done_tach": "last_done_tach",
            "last_done_date": "last_done_date",
            "next_due_aftt": "next_due_aftt",
            "next_due_tach": "next_due_tach",
            "atl_ref": "atl_ref",
        },
    ],
)
def test_ad_work_order_import_accepts_header_casing(
    client_with_maintenance_import_auth: TestClient,
    header_labels: dict,
):
    """AD work-order import accepts uppercase, lowercase, and snake_case headers."""
    import asyncio

    from app.models.ad_monitoring import ADMonitoring
    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_ad_monitoring() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="AD-WO-CASE-AC",
                model="172",
                msn="AD-WO-CASE-MSN",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.flush()
            ad = ADMonitoring(
                aircraft_fk=ac.id,
                ad_number="32235",
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
        files={
            "file": (
                "ad-wo.csv",
                ad_work_order_csv_bytes_with_headers(headers=header_labels),
                "text/csv",
            )
        },
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
            "WO NUMBER": "17212-A-000343",
            "LAST DONE AFTT": "6080.1",
            "LAST DONE TACH": "6079.5",
            "LAST DONE DATE": "6/5/2023",
            "NEXT DUE AFTT": "6180.1",
            "NEXT DUE TACH": "6179.5",
            "ATL REF": "ATL-0002225",
        },
        {
            "WO NUMBER": "17212-A-000351",
            "LAST DONE AFTT": "6179.3",
            "LAST DONE TACH": "6178.7",
            "LAST DONE DATE": "23-Jul-23",
            "NEXT DUE AFTT": "6279.3",
            "NEXT DUE TACH": "6278.7",
            "ATL REF": "ATL-0002412",
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
        "WO NUMBER": "17212-A-000343",
        "LAST DONE AFTT": "6080.1",
        "LAST DONE TACH": "6079.5",
        "LAST DONE DATE": "6/5/2023",
        "NEXT DUE AFTT": "6180.1",
        "NEXT DUE TACH": "6179.5",
        "ATL REF": "ATL-0002225",
    }
    updated_row = {**row, "ATL REF": "ATL-UPDATED"}

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


# --- TCC import (/api/v1/excel-data/maintenance-tcc/import) ---


def test_tcc_import_missing_aircraft_context(
    client_with_maintenance_import_auth: TestClient,
):
    """Validation — aircraft_id or registration required."""
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-tcc/import",
        files={"file": ("tcc.csv", tcc_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 400
    assert "aircraft" in response.json()["detail"].lower()


def test_tcc_import_dry_run_success(
    client_with_maintenance_import_auth: TestClient,
):
    """Dry run validates TCC rows for a seeded aircraft."""
    import asyncio

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="TCC-IMP-AC",
                model="172",
                msn="TCC-MSN-1",
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
        "/api/v1/excel-data/maintenance-tcc/import?dry_run=true",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("tcc.csv", tcc_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dry-run"
    assert body["inserted"] >= 1
    assert body["updated"] == 0
    assert body["errors"] == []


def test_tcc_import_dry_run_sequence_no_column_maps_to_atl_sequence(
    client_with_maintenance_import_auth: TestClient,
):
    """Excel column 'Sequence No.' maps to the same field as ATL Ref (sequence → atl_ref on save)."""
    import asyncio

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="TCC-SEQ-COL-AC",
                model="172",
                msn="TCC-SEQ-MSN",
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
            "Category": "AIRFRAME",
            "Part Number": "PN-SEQ",
            "Description": "Row with Sequence No. header",
            "Sequence No.": "10001",
        }
    ]
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-tcc/import?dry_run=true",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("tcc.csv", tcc_csv_bytes(rows), "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["errors"] == []


def test_tcc_import_inspection_servicing_category_alias(
    client_with_maintenance_import_auth: TestClient,
):
    """Category INSPECTION/SERVICING normalizes to Inspection Servicing."""
    import asyncio

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="TCC-CAT-AC",
                model="172",
                msn="TCC-CAT-MSN",
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
            "Category": "INSPECTION/SERVICING",
            "Part Number": "PN-1",
            "Description": "Test item",
        }
    ]

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-tcc/import?dry_run=true",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("tcc.csv", tcc_csv_bytes(rows), "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["errors"] == []


def test_tcc_import_persist_without_part_number(
    client_with_maintenance_import_auth: TestClient,
):
    """Persist import rows when part_number is blank (NOT NULL column uses empty string)."""
    import asyncio

    from sqlalchemy import select

    from app.models.aircraft import Aircraft
    from app.models.tcc_maintenance import TCCMaintenance
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="TCC-PERSIST-AC",
                model="172",
                msn="TCC-PERSIST-MSN",
                base="Base",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.commit()
            await session.refresh(ac)
            return ac.id

    aircraft_pk = asyncio.run(_seed_aircraft())
    rows = [{"Category": "AIRFRAME", "Description": "Wing"}]

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-tcc/import",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("tcc.csv", tcc_csv_bytes(rows), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["inserted"] == 1
    assert body["errors"] == []

    async def _assert_row() -> None:
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(TCCMaintenance).where(TCCMaintenance.aircraft_fk == aircraft_pk)
            )
            items = result.scalars().all()
            assert len(items) == 1
            assert items[0].part_number == ""
            assert items[0].description == "Wing"

    asyncio.run(_assert_row())


def test_tcc_import_preserves_excel_row_order(
    client_with_maintenance_import_auth: TestClient,
):
    """Imported TCC rows keep Excel order via display_order (A→C→B, not alphabetical)."""
    import asyncio
    from unittest.mock import AsyncMock, patch

    from sqlalchemy import select

    from app.models.aircraft import Aircraft
    from app.models.tcc_maintenance import TCCMaintenance
    from app.services.tcc_computation import COMPUTED_TCC_COLUMN_KEYS
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="TCC-ORDER-AC",
                model="172",
                msn="TCC-ORDER-MSN",
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
        {"Category": "AIRFRAME", "Description": "A", "Part Number": "PN-A"},
        {"Category": "AIRFRAME", "Description": "C", "Part Number": "PN-C"},
        {"Category": "AIRFRAME", "Description": "B", "Part Number": "PN-B"},
    ]

    # TCC after_upsert looks up latest ATL with Postgres-only regex; stub for SQLite tests.
    with patch(
        "app.services.excel_import.hooks.maintenance_tcc.build_computed_tcc_field_values",
        new_callable=AsyncMock,
        return_value={k: None for k in COMPUTED_TCC_COLUMN_KEYS},
    ):
        response = client_with_maintenance_import_auth.post(
            "/api/v1/excel-data/maintenance-tcc/import",
            data={"aircraft_id": str(aircraft_pk)},
            files={"file": ("tcc.csv", tcc_csv_bytes(rows), "text/csv")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success", body
    assert body["inserted"] == 3
    assert body["errors"] == []

    async def _assert_db_and_list_order() -> None:
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(TCCMaintenance)
                .where(TCCMaintenance.aircraft_fk == aircraft_pk)
                .order_by(TCCMaintenance.display_order.asc())
            )
            items = result.scalars().all()
            assert [i.description for i in items] == ["A", "C", "B"]
            assert [i.display_order for i in items] == [1, 2, 3]

            from app.repository.tcc_maintenance import list_tcc_maintenances

            listed, total = await list_tcc_maintenances(
                session, limit=10, offset=0, aircraft_fk=aircraft_pk
            )
            assert total == 3
            assert [i.description for i in listed] == ["A", "C", "B"]
            assert [i.display_order for i in listed] == [1, 2, 3]

    asyncio.run(_assert_db_and_list_order())


def test_tcc_import_schema_sanitizes_pandas_nat_and_nan():
    """Empty Excel date/number cells (NaT/nan) must become None, not DB errors."""
    import math

    import pandas as pd

    from app.schemas.tcc_maintenance_schema import TCCMaintenanceImportSchema

    row = TCCMaintenanceImportSchema(
        aircraft_fk=1,
        category="POWERPLANT",
        part_number="PN-1",
        description="Fuel hose",
        last_done_date=pd.NaT,
        last_done_tach=float("nan"),
        last_done_aftt=float("nan"),
        component_limit_hours=float("nan"),
    )
    assert row.last_done_date is None
    assert row.last_done_tach is None
    assert row.last_done_aftt is None
    assert row.component_limit_hours is None
    assert not (row.component_limit_years is not None and math.isnan(row.component_limit_years))


# --- CPCP import (/api/v1/excel-data/maintenance-cpcp/import) ---


def test_cpcp_import_missing_aircraft_context(
    client_with_maintenance_import_auth: TestClient,
):
    """Validation — aircraft_id or registration required."""
    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-cpcp/import",
        files={"file": ("cpcp.csv", cpcp_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 400
    assert "aircraft" in response.json()["detail"].lower()


def test_cpcp_import_dry_run_success(
    client_with_maintenance_import_auth: TestClient,
):
    """Dry run validates CPCP rows for a seeded aircraft."""
    import asyncio

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="CPCP-IMP-AC",
                model="172",
                msn="CPCP-MSN-1",
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
        "/api/v1/excel-data/maintenance-cpcp/import?dry_run=true",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("cpcp.csv", cpcp_csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dry-run"
    assert body["inserted"] >= 1
    assert body["updated"] == 0
    assert body["errors"] == []


def test_cpcp_import_dry_run_date_formats(
    client_with_maintenance_import_auth: TestClient,
):
    """Dates accept M/D/YYYY and DD-Mon-YY string formats."""
    import asyncio

    from app.models.aircraft import Aircraft
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="CPCP-DATE-AC",
                model="172",
                msn="CPCP-DATE-MSN",
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
            "Inspection Operation": "Wing spar inspection",
            "Description": "First row",
            "Interval Hours": "120",
            "Interval Months": "6",
            "Last Done Tach": "1000.0",
            "Last Done AFTT": "1002.0",
            "Last Done Date": "6/5/2023",
            "Sequence No.": "10001",
        },
        {
            "Inspection Operation": "Tail section inspection",
            "Description": "Second row",
            "Interval Hours": "200",
            "Interval Months": "12",
            "Last Done Tach": "1200.5",
            "Last Done AFTT": "1201.0",
            "Last Done Date": "23-Jul-23",
            "Sequence No.": "10002",
        },
    ]

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-cpcp/import?dry_run=true",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("cpcp.csv", cpcp_csv_bytes(rows), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dry-run"
    assert body["inserted"] == 2
    assert body["errors"] == []


def test_cpcp_import_preserves_excel_row_order(
    client_with_maintenance_import_auth: TestClient,
):
    """Imported CPCP rows keep Excel order via display_order (A→C→B, not alphabetical)."""
    import asyncio

    from sqlalchemy import select

    from app.models.aircraft import Aircraft
    from app.models.cpcp_monitoring import CPCPMonitoring
    from app.repository.cpcp_monitoring import list_cpcp_monitorings
    from tests.conftest import TestSessionLocal

    async def _seed_aircraft() -> int:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="CPCP-ORDER-AC",
                model="172",
                msn="CPCP-ORDER-MSN",
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
            "Inspection Operation": "Op A",
            "Description": "A",
            "Interval Hours": "100",
            "Interval Months": "6",
        },
        {
            "Inspection Operation": "Op C",
            "Description": "C",
            "Interval Hours": "200",
            "Interval Months": "12",
        },
        {
            "Inspection Operation": "Op B",
            "Description": "B",
            "Interval Hours": "150",
            "Interval Months": "9",
        },
    ]

    response = client_with_maintenance_import_auth.post(
        "/api/v1/excel-data/maintenance-cpcp/import",
        data={"aircraft_id": str(aircraft_pk)},
        files={"file": ("cpcp.csv", cpcp_csv_bytes(rows), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success", body
    assert body["inserted"] == 3
    assert body["errors"] == []

    async def _assert_db_and_list_order() -> None:
        async with TestSessionLocal() as session:
            result = await session.execute(
                select(CPCPMonitoring)
                .where(CPCPMonitoring.aircraft_id == aircraft_pk)
                .order_by(CPCPMonitoring.display_order.asc())
            )
            items = result.scalars().all()
            assert [i.description for i in items] == ["A", "C", "B"]
            assert [i.display_order for i in items] == [1, 2, 3]

            listed, total = await list_cpcp_monitorings(
                session, limit=10, offset=0, aircraft_id=aircraft_pk
            )
            assert total == 3
            assert [i.description for i in listed] == ["A", "C", "B"]
            assert [i.display_order for i in listed] == [1, 2, 3]

    asyncio.run(_assert_db_and_list_order())


@pytest.mark.no_auth
def test_atl_import_unauthorized(client: TestClient):
    """5. Unauthorized — ATL import without auth."""
    response = client.post(
        "/api/v1/excel-data/aircraft-technical-log/import",
        data={"batch_id": "1", "aircraft_id": "1"},
        files={"file": ("atl.csv", b"sequence_no\n1\n", "text/csv")},
    )
    assert response.status_code == 401
