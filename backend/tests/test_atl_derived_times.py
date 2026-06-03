"""Regression tests for ATL derived time computations."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import Numeric, cast, select

from app.core.atl_derived_times import (
    ATL_AUTO_FIELD_KEYS,
    backfill_atl_auto_fields_for_scope,
    persist_atl_auto_fields_to_row,
    resolve_auto_fields,
)
from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import AircraftTechnicalLog
from tests.conftest import TestSessionLocal


async def _persist_auto_columns_for_all_atl_rows(aircraft_id: int) -> None:
    """Backfill auto_* DB columns for raw SQLAlchemy seeds (mirrors create/update persist)."""
    async with TestSessionLocal() as session:
        ac = await session.get(Aircraft, aircraft_id)
        stmt = (
            select(AircraftTechnicalLog)
            .where(AircraftTechnicalLog.aircraft_fk == aircraft_id)
            .where(AircraftTechnicalLog.is_deleted.is_(False))
            .order_by(cast(AircraftTechnicalLog.sequence_no, Numeric).asc())
        )
        rows = (await session.execute(stmt)).scalars().all()
        for row in rows:
            await persist_atl_auto_fields_to_row(session, row, ac)
        await session.commit()


def test_resolve_auto_fields_handles_deep_predecessor_chain_without_recursion(
    client_with_atl_auth: TestClient,
):
    """Regression: bulk-imported ATLs can have 1000+ predecessors; recursive resolve caused RecursionError on GET."""
    last_atl_id = None

    async def _seed() -> None:
        nonlocal last_atl_id
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="TEST-ATL-DEEP",
                manufacturer="Cessna",
                model="172",
                msn="TEST-MSN-DEEP",
                base="Base",
                ownership="Owner",
                status="Active",
                airframe_aftt=0.0,
            )
            session.add(ac)
            await session.flush()
            aircraft_id = ac.id

            rows = []
            for seq in range(1, 1101):
                rows.append(
                    AircraftTechnicalLog(
                        aircraft_fk=ac.id,
                        sequence_no=str(seq),
                        tachometer_start=float(seq),
                        tachometer_end=float(seq) + 1.0,
                    )
                )
            session.add_all(rows)
            await session.commit()
            last_atl_id = rows[-1].id

    asyncio.run(_seed())
    assert last_atl_id is not None

    response = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/{last_atl_id}"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sequence_no"] == "1100"
    assert body["auto_airframe_run_time"] == 1.0


def test_get_atl_uses_stored_auto_fields_without_predecessor_queries(
    client_with_atl_auth: TestClient,
):
    """GET should read persisted auto_* when present (no get_previous_atl / batch fetch)."""
    last_atl_id = None

    async def _seed() -> None:
        nonlocal last_atl_id
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="TEST-ATL-STORED",
                manufacturer="Cessna",
                model="172",
                msn="TEST-MSN-STORED",
                base="Base",
                ownership="Owner",
                status="Active",
                airframe_aftt=100.0,
            )
            session.add(ac)
            await session.flush()
            for seq in ("001", "002", "003"):
                session.add(
                    AircraftTechnicalLog(
                        aircraft_fk=ac.id,
                        sequence_no=seq,
                        tachometer_start=float(seq),
                        tachometer_end=float(seq) + 1.0,
                    )
                )
            await session.commit()
            await backfill_atl_auto_fields_for_scope(session, ac.id)
            await session.commit()
            stmt = (
                select(AircraftTechnicalLog)
                .where(AircraftTechnicalLog.aircraft_fk == ac.id)
                .where(AircraftTechnicalLog.sequence_no == "003")
            )
            last_atl_id = (await session.execute(stmt)).scalar_one().id

    asyncio.run(_seed())
    assert last_atl_id is not None

    with patch(
        "app.repository.aircraft_technical_log.get_previous_atl",
        new_callable=AsyncMock,
    ) as mock_prev, patch(
        "app.repository.aircraft_technical_log.fetch_predecessors_for_atl",
        new_callable=AsyncMock,
    ) as mock_fetch:
        response = client_with_atl_auth.get(
            f"/api/v1/aircraft-technical-log/{last_atl_id}"
        )
        assert response.status_code == 200, response.text
        mock_prev.assert_not_called()
        mock_fetch.assert_not_called()

    with patch(
        "app.repository.aircraft_technical_log.get_previous_atl",
        new_callable=AsyncMock,
    ) as mock_prev, patch(
        "app.repository.aircraft_technical_log.fetch_predecessors_for_atl",
        new_callable=AsyncMock,
    ) as mock_fetch:
        response = client_with_atl_auth.get(
            f"/api/v1/aircraft-technical-log/{last_atl_id}?recompute=true"
        )
        assert response.status_code == 200, response.text
        assert mock_prev.called or mock_fetch.called


def test_batch_resolve_matches_chain_for_three_row_sequence(
    client_with_atl_auth: TestClient,
):
    """Batch predecessor fetch should match sequential resolve for a short chain."""

    async def _run() -> None:
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="TEST-ATL-BATCH",
                manufacturer="Cessna",
                model="172",
                msn="TEST-MSN-BATCH",
                base="Base",
                ownership="Owner",
                status="Active",
                airframe_aftt=10.0,
                engine_tsn=100.0,
                engine_tso=20.0,
                propeller_tsn=50.0,
                propeller_tso=10.0,
            )
            session.add(ac)
            await session.flush()
            session.add_all(
                [
                    AircraftTechnicalLog(
                        aircraft_fk=ac.id,
                        sequence_no="001",
                        airframe_aftt=11.0,
                        tachometer_start=1.0,
                        tachometer_end=2.0,
                    ),
                    AircraftTechnicalLog(
                        aircraft_fk=ac.id,
                        sequence_no="002",
                        tachometer_start=2.0,
                        tachometer_end=4.0,
                    ),
                    AircraftTechnicalLog(
                        aircraft_fk=ac.id,
                        sequence_no="003",
                        tachometer_start=4.0,
                        tachometer_end=5.5,
                    ),
                ]
            )
            await session.commit()
            stmt = (
                select(AircraftTechnicalLog)
                .where(AircraftTechnicalLog.aircraft_fk == ac.id)
                .order_by(cast(AircraftTechnicalLog.sequence_no, Numeric).asc())
            )
            rows = (await session.execute(stmt)).scalars().all()
            target = rows[-1]
            forced = await resolve_auto_fields(
                session, target, ac, {}, force_recompute=True
            )
            assert round(forced["auto_airframe_run_time"], 2) == 1.5
            assert round(forced["auto_airframe_aftt"], 2) == 11.5

    asyncio.run(_run())


def test_atl_paged_computes_runtime_and_component_totals_from_tach_and_aircraft_baselines(
    client_with_atl_auth: TestClient,
    test_aircraft_data: dict,
):
    """Derived values should use tach delta and aircraft TSN/TSO baselines when previous ATL values are zero."""
    aircraft_payload = {
        **test_aircraft_data,
        "msn": "TEST-MSN-ATL-DERIVED",
        "registration": "TEST-ATL-DERIVED",
        "engine_life_time_limit": 1000.0,
        "engine_tsn": 2500.0,
        "engine_tso": 500.0,
        "propeller_life_time_limit": 1500.0,
        "propeller_tsn": 1200.0,
        "propeller_tso": 300.0,
    }
    aircraft_response = client_with_atl_auth.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(aircraft_payload)},
        files={},
    )
    assert aircraft_response.status_code == 200, aircraft_response.text
    aircraft_id = aircraft_response.json()["id"]

    async def seed_previous_atl() -> None:
        async with TestSessionLocal() as session:
            previous = AircraftTechnicalLog(
                aircraft_fk=aircraft_id,
                sequence_no="001",
                airframe_aftt=100.0,
                engine_tsn=0.0,
                engine_tso=0.0,
                propeller_tsn=0.0,
                propeller_tso=0.0,
                tachometer_start=100.0,
                tachometer_end=101.0,
            )
            session.add(previous)
            await session.commit()

    asyncio.run(seed_previous_atl())

    current_payload = {
        "aircraft_fk": aircraft_id,
        "sequence_no": "ATL-002",
        "nature_of_flight": "TR",
        "origin_station": "TEST-ORG",
        "origin_date": "2025-01-18",
        "origin_time": "10:00:00",
        "destination_station": "TEST-DEST",
        "destination_date": "2025-01-18",
        "destination_time": "12:00:00",
        "number_of_landings": 1,
        "hobbs_meter_start": 101.0,
        "hobbs_meter_end": 103.5,
        "hobbs_meter_total": 2.5,
        "tachometer_start": 101.0,
        "tachometer_end": 103.5,
        "tachometer_total": 2.5,
        "component_parts": [],
    }
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=current_payload,
    )
    assert create_response.status_code == 201, create_response.text

    paged_response = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/paged?aircraft_fk={aircraft_id}&limit=10&page=1"
    )
    assert paged_response.status_code == 200, paged_response.text
    items = paged_response.json()["items"]
    row = next(item for item in items if item["sequence_no"] == "002")

    assert row["auto_airframe_run_time"] == 2.5
    assert row["auto_airframe_aftt"] == 102.5
    assert row["auto_engine_run_time"] == 2.5
    assert row["auto_run_time"] == 2.5
    assert row["auto_engine_tsn"] == 2502.5
    assert row["auto_engine_tso"] == 502.5
    assert row["auto_engine_tbo"] == 497.5
    assert row["auto_propeller_run_time"] == 2.5
    assert row["auto_propeller_tsn"] == 1202.5
    assert row["auto_propeller_tso"] == 302.5
    assert row["auto_propeller_tbo"] == 1197.5


def test_atl_paged_uses_aircraft_airframe_aftt_when_previous_aftt_is_missing(
    client_with_atl_auth: TestClient,
    test_aircraft_data: dict,
):
    """Airframe AFTT should fall back to Aircraft Details baseline when no previous ATL AFTT exists."""
    aircraft_payload = {
        **test_aircraft_data,
        "msn": "TEST-MSN-ATL-AFTT-BASE",
        "registration": "TEST-ATL-AFTT-BASE",
        "airframe_aftt": 200.0,
    }
    aircraft_response = client_with_atl_auth.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(aircraft_payload)},
        files={},
    )
    assert aircraft_response.status_code == 200, aircraft_response.text
    aircraft_id = aircraft_response.json()["id"]

    current_payload = {
        "aircraft_fk": aircraft_id,
        "sequence_no": "ATL-001",
        "nature_of_flight": "TR",
        "origin_station": "TEST-ORG",
        "origin_date": "2025-01-18",
        "origin_time": "10:00:00",
        "destination_station": "TEST-DEST",
        "destination_date": "2025-01-18",
        "destination_time": "12:00:00",
        "number_of_landings": 1,
        "hobbs_meter_start": 101.0,
        "hobbs_meter_end": 103.5,
        "hobbs_meter_total": 2.5,
        "tachometer_start": 101.0,
        "tachometer_end": 103.5,
        "tachometer_total": 2.5,
        "component_parts": [],
    }
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=current_payload,
    )
    assert create_response.status_code == 201, create_response.text

    paged_response = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/paged?aircraft_fk={aircraft_id}&limit=10&page=1"
    )
    assert paged_response.status_code == 200, paged_response.text
    items = paged_response.json()["items"]
    row = next(item for item in items if item["sequence_no"] == "001")

    assert row["auto_airframe_run_time"] == 2.5
    assert row["auto_airframe_aftt"] == 202.5


def test_atl_paged_uses_aircraft_propeller_tsn_tso_when_previous_values_are_missing(
    client_with_atl_auth: TestClient,
    test_aircraft_data: dict,
):
    """Propeller TSN/TSO should fall back to Aircraft Details values when there is no previous ATL."""
    aircraft_payload = {
        **test_aircraft_data,
        "msn": "TEST-MSN-ATL-PROP-BASE",
        "registration": "TEST-ATL-PROP-BASE",
        "propeller_tsn": 500.0,
        "propeller_tso": 100.0,
    }
    aircraft_response = client_with_atl_auth.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(aircraft_payload)},
        files={},
    )
    assert aircraft_response.status_code == 200, aircraft_response.text
    aircraft_id = aircraft_response.json()["id"]

    current_payload = {
        "aircraft_fk": aircraft_id,
        "sequence_no": "ATL-001",
        "nature_of_flight": "TR",
        "origin_station": "TEST-ORG",
        "origin_date": "2025-01-18",
        "origin_time": "10:00:00",
        "destination_station": "TEST-DEST",
        "destination_date": "2025-01-18",
        "destination_time": "12:00:00",
        "number_of_landings": 1,
        "hobbs_meter_start": 101.0,
        "hobbs_meter_end": 103.5,
        "hobbs_meter_total": 2.5,
        "tachometer_start": 101.0,
        "tachometer_end": 103.5,
        "tachometer_total": 2.5,
        "component_parts": [],
    }
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=current_payload,
    )
    assert create_response.status_code == 201, create_response.text

    paged_response = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/paged?aircraft_fk={aircraft_id}&limit=10&page=1"
    )
    assert paged_response.status_code == 200, paged_response.text
    items = paged_response.json()["items"]
    row = next(item for item in items if item["sequence_no"] == "001")

    assert row["auto_propeller_run_time"] == 2.5
    assert row["auto_propeller_tsn"] == 502.5
    assert row["auto_propeller_tso"] == 102.5


def test_atl_paged_uses_aircraft_engine_and_propeller_tso_when_previous_tso_is_zero(
    client_with_atl_auth: TestClient,
    test_aircraft_data: dict,
):
    """Engine/propeller TSO should fall back to Aircraft Details when the previous ATL TSO is zero."""
    aircraft_payload = {
        **test_aircraft_data,
        "msn": "TEST-MSN-ATL-TSO-FALLBACK",
        "registration": "TEST-ATL-TSO-FALLBACK",
        "engine_tso": 500.0,
        "propeller_tso": 300.0,
    }
    aircraft_response = client_with_atl_auth.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(aircraft_payload)},
        files={},
    )
    assert aircraft_response.status_code == 200, aircraft_response.text
    aircraft_id = aircraft_response.json()["id"]

    async def seed_previous_atl() -> None:
        async with TestSessionLocal() as session:
            previous = AircraftTechnicalLog(
                aircraft_fk=aircraft_id,
                sequence_no="001",
                engine_tso=0.0,
                propeller_tso=0.0,
                tachometer_start=100.0,
                tachometer_end=101.0,
            )
            session.add(previous)
            await session.commit()

    asyncio.run(seed_previous_atl())

    current_payload = {
        "aircraft_fk": aircraft_id,
        "sequence_no": "ATL-002",
        "nature_of_flight": "TR",
        "origin_station": "TEST-ORG",
        "origin_date": "2025-01-18",
        "origin_time": "10:00:00",
        "destination_station": "TEST-DEST",
        "destination_date": "2025-01-18",
        "destination_time": "12:00:00",
        "number_of_landings": 1,
        "hobbs_meter_start": 101.0,
        "hobbs_meter_end": 103.5,
        "hobbs_meter_total": 2.5,
        "tachometer_start": 101.0,
        "tachometer_end": 103.5,
        "tachometer_total": 2.5,
        "component_parts": [],
    }
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=current_payload,
    )
    assert create_response.status_code == 201, create_response.text

    paged_response = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/paged?aircraft_fk={aircraft_id}&limit=10&page=1"
    )
    assert paged_response.status_code == 200, paged_response.text
    items = paged_response.json()["items"]
    row = next(item for item in items if item["sequence_no"] == "002")

    assert row["auto_engine_run_time"] == 2.5
    assert row["auto_propeller_run_time"] == 2.5
    assert row["auto_engine_tso"] == 502.5
    assert row["auto_propeller_tso"] == 302.5


def test_atl_paged_keeps_tso_cumulative_from_previous_computed_values_for_later_sequences(
    client_with_atl_auth: TestClient,
    test_aircraft_data: dict,
):
    """Later rows should build on the previous computed TSO, not reset to Aircraft Details each time."""
    aircraft_payload = {
        **test_aircraft_data,
        "msn": "TEST-MSN-ATL-TSO-CUMULATIVE",
        "registration": "TEST-ATL-TSO-CUMULATIVE",
        "engine_tso": 500.0,
        "propeller_tso": 300.0,
    }
    aircraft_response = client_with_atl_auth.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(aircraft_payload)},
        files={},
    )
    assert aircraft_response.status_code == 200, aircraft_response.text
    aircraft_id = aircraft_response.json()["id"]

    async def seed_rows() -> None:
        async with TestSessionLocal() as session:
            session.add_all(
                [
                    AircraftTechnicalLog(
                        aircraft_fk=aircraft_id,
                        sequence_no="001",
                        engine_tso=0.0,
                        propeller_tso=0.0,
                        tachometer_start=100.0,
                        tachometer_end=101.0,
                    ),
                    AircraftTechnicalLog(
                        aircraft_fk=aircraft_id,
                        sequence_no="002",
                        engine_tso=0.0,
                        propeller_tso=0.0,
                        tachometer_start=101.0,
                        tachometer_end=103.0,
                    ),
                    AircraftTechnicalLog(
                        aircraft_fk=aircraft_id,
                        sequence_no="003",
                        tachometer_start=103.0,
                        tachometer_end=104.5,
                    ),
                ]
            )
            await session.commit()

    asyncio.run(seed_rows())
    asyncio.run(_persist_auto_columns_for_all_atl_rows(aircraft_id))

    paged_response = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/paged?aircraft_fk={aircraft_id}&limit=10&page=1&sort=sequence_no"
    )
    assert paged_response.status_code == 200, paged_response.text
    items = {item["sequence_no"]: item for item in paged_response.json()["items"]}

    assert items["001"]["auto_engine_tso"] == 501.0
    assert items["001"]["auto_propeller_tso"] == 301.0
    assert items["002"]["auto_engine_tso"] == 503.0
    assert items["002"]["auto_propeller_tso"] == 303.0
    assert items["003"]["auto_engine_tso"] == 504.5
    assert items["003"]["auto_propeller_tso"] == 304.5


def test_atl_paged_defaults_to_sequence_number_descending(
    client_with_atl_auth: TestClient,
    test_aircraft_data: dict,
):
    """Default paged ordering should follow descending numeric sequence_no (newest first)."""
    aircraft_payload = {
        **test_aircraft_data,
        "msn": "TEST-MSN-ATL-ASC",
        "registration": "TEST-ATL-ASC",
    }
    aircraft_response = client_with_atl_auth.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(aircraft_payload)},
        files={},
    )
    assert aircraft_response.status_code == 200, aircraft_response.text
    aircraft_id = aircraft_response.json()["id"]

    async def seed_atls() -> None:
        async with TestSessionLocal() as session:
            session.add_all(
                [
                    AircraftTechnicalLog(
                        aircraft_fk=aircraft_id,
                        sequence_no="002",
                        airframe_aftt=10.0,
                        tachometer_start=1.0,
                        tachometer_end=2.0,
                    ),
                    AircraftTechnicalLog(
                        aircraft_fk=aircraft_id,
                        sequence_no="010",
                        tachometer_start=2.0,
                        tachometer_end=4.5,
                    ),
                ]
            )
            await session.commit()

    asyncio.run(seed_atls())
    asyncio.run(_persist_auto_columns_for_all_atl_rows(aircraft_id))

    paged_response = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/paged?aircraft_fk={aircraft_id}&limit=10&page=1"
    )
    assert paged_response.status_code == 200, paged_response.text

    items = paged_response.json()["items"]
    assert [item["sequence_no"] for item in items] == ["010", "002"]

    row_010 = next(item for item in items if item["sequence_no"] == "010")
    assert row_010["auto_airframe_run_time"] == 2.5
    assert row_010["auto_airframe_aftt"] == 12.5


def test_aircraft_technical_log_paged_sorts_sequence_numbers_numerically_ascending(
    client_with_atl_auth: TestClient,
    test_aircraft_data: dict,
):
    """Paged ATL order should follow numeric sequence ascending, not string order."""
    aircraft_payload = {
        **test_aircraft_data,
        "msn": "TEST-MSN-ATL-ORDER",
        "registration": "TEST-ATL-ORDER",
    }
    aircraft_response = client_with_atl_auth.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(aircraft_payload)},
        files={},
    )
    assert aircraft_response.status_code == 200, aircraft_response.text
    aircraft_id = aircraft_response.json()["id"]

    base_payload = {
        "aircraft_fk": aircraft_id,
        "nature_of_flight": "TR",
        "origin_station": "TEST-ORG",
        "origin_date": "2025-01-18",
        "origin_time": "10:00:00",
        "destination_station": "TEST-DEST",
        "destination_date": "2025-01-18",
        "destination_time": "12:00:00",
        "number_of_landings": 1,
        "hobbs_meter_start": 100.0,
        "hobbs_meter_end": 101.0,
        "hobbs_meter_total": 1.0,
        "tachometer_start": 100.0,
        "tachometer_end": 101.0,
        "tachometer_total": 1.0,
        "component_parts": [],
    }

    for sequence_no in ("ATL-10", "ATL-2", "ATL-11"):
        response = client_with_atl_auth.post(
            "/api/v1/aircraft-technical-log/",
            json={**base_payload, "sequence_no": sequence_no},
        )
        assert response.status_code == 201, response.text

    paged_response = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/paged?aircraft_fk={aircraft_id}&limit=10&page=1&sort=sequence_no"
    )
    assert paged_response.status_code == 200, paged_response.text
    sequence_numbers = [item["sequence_no"] for item in paged_response.json()["items"]]

    assert sequence_numbers == ["2", "10", "11"]


def test_atl_paged_uses_previous_sequence_in_numeric_ascending_order_for_auto_comp_base(
    client_with_atl_auth: TestClient,
    test_aircraft_data: dict,
):
    """The previous base row for computed fields should use numeric sequence ordering, not string ordering."""
    aircraft_payload = {
        **test_aircraft_data,
        "msn": "TEST-MSN-ATL-SEQUENCE",
        "registration": "TEST-ATL-SEQUENCE",
        "engine_tsn": 100.0,
        "engine_tso": 20.0,
        "propeller_tsn": 50.0,
        "propeller_tso": 10.0,
    }
    aircraft_response = client_with_atl_auth.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(aircraft_payload)},
        files={},
    )
    assert aircraft_response.status_code == 200, aircraft_response.text
    aircraft_id = aircraft_response.json()["id"]

    async def seed_rows() -> None:
        async with TestSessionLocal() as session:
            session.add_all(
                [
                    AircraftTechnicalLog(
                        aircraft_fk=aircraft_id,
                        sequence_no="001",
                        airframe_aftt=10.0,
                        engine_tsn=101.0,
                        engine_tso=21.0,
                        propeller_tsn=51.0,
                        propeller_tso=11.0,
                        tachometer_start=1.0,
                        tachometer_end=2.0,
                    ),
                    AircraftTechnicalLog(
                        aircraft_fk=aircraft_id,
                        sequence_no="002",
                        airframe_aftt=20.0,
                        engine_tsn=102.0,
                        engine_tso=22.0,
                        propeller_tsn=52.0,
                        propeller_tso=12.0,
                        tachometer_start=2.0,
                        tachometer_end=3.0,
                    ),
                    AircraftTechnicalLog(
                        aircraft_fk=aircraft_id,
                        sequence_no="009",
                        airframe_aftt=90.0,
                        engine_tsn=109.0,
                        engine_tso=29.0,
                        propeller_tsn=59.0,
                        propeller_tso=19.0,
                        tachometer_start=9.0,
                        tachometer_end=10.0,
                    ),
                ]
            )
            await session.commit()

    asyncio.run(seed_rows())

    current_payload = {
        "aircraft_fk": aircraft_id,
        "sequence_no": "ATL-010",
        "nature_of_flight": "TR",
        "origin_station": "TEST-ORG",
        "origin_date": "2025-01-19",
        "origin_time": "10:00:00",
        "destination_station": "TEST-DEST",
        "destination_date": "2025-01-19",
        "destination_time": "12:00:00",
        "number_of_landings": 1,
        "hobbs_meter_start": 10.0,
        "hobbs_meter_end": 11.5,
        "hobbs_meter_total": 1.5,
        "tachometer_start": 10.0,
        "tachometer_end": 11.5,
        "tachometer_total": 1.5,
        "component_parts": [],
    }
    create_response = client_with_atl_auth.post(
        "/api/v1/aircraft-technical-log/",
        json=current_payload,
    )
    assert create_response.status_code == 201, create_response.text

    paged_response = client_with_atl_auth.get(
        f"/api/v1/aircraft/{aircraft_id}/atl/paged?page=1&page_size=20&sort=asc"
    )
    assert paged_response.status_code == 200, paged_response.text
    items = paged_response.json()["items"]
    row = next(item for item in items if item["sequence_no"] == "010")

    assert row["auto_comp_airframe_run_time"] == 1.5
    assert row["auto_comp_airframe_aftt"] == 91.5
    assert row["auto_comp_engine_tsn"] == 110.5
    assert row["auto_comp_engine_tso"] == 30.5
    assert row["auto_comp_propeller_tsn"] == 60.5
    assert row["auto_comp_propeller_tso"] == 20.5


def test_aircraft_technical_log_paged_sequence_sort_does_not_change_auto_computation(
    client_with_atl_auth: TestClient,
    test_aircraft_data: dict,
):
    """Sorting by sequence_no should only change row order, not the computed auto_* values."""
    aircraft_payload = {
        **test_aircraft_data,
        "msn": "TEST-MSN-ATL-SORT-STABLE",
        "registration": "TEST-ATL-SORT-STABLE",
        "airframe_aftt": 10.0,
        "engine_tsn": 100.0,
        "engine_tso": 20.0,
        "propeller_tsn": 50.0,
        "propeller_tso": 10.0,
    }
    aircraft_response = client_with_atl_auth.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(aircraft_payload)},
        files={},
    )
    assert aircraft_response.status_code == 200, aircraft_response.text
    aircraft_id = aircraft_response.json()["id"]

    async def seed_rows() -> None:
        async with TestSessionLocal() as session:
            session.add_all(
                [
                    AircraftTechnicalLog(
                        aircraft_fk=aircraft_id,
                        sequence_no="001",
                        airframe_aftt=11.0,
                        engine_tsn=101.0,
                        engine_tso=21.0,
                        propeller_tsn=51.0,
                        propeller_tso=11.0,
                        tachometer_start=1.0,
                        tachometer_end=2.0,
                    ),
                    AircraftTechnicalLog(
                        aircraft_fk=aircraft_id,
                        sequence_no="002",
                        airframe_aftt=20.0,
                        engine_tsn=102.0,
                        engine_tso=22.0,
                        propeller_tsn=52.0,
                        propeller_tso=12.0,
                        tachometer_start=2.0,
                        tachometer_end=3.0,
                    ),
                    AircraftTechnicalLog(
                        aircraft_fk=aircraft_id,
                        sequence_no="010",
                        tachometer_start=10.0,
                        tachometer_end=11.5,
                    ),
                ]
            )
            await session.commit()

    asyncio.run(seed_rows())
    asyncio.run(_persist_auto_columns_for_all_atl_rows(aircraft_id))

    asc_response = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/paged?aircraft_fk={aircraft_id}&limit=10&page=1&sort=sequence_no"
    )
    assert asc_response.status_code == 200, asc_response.text
    asc_items = {item["sequence_no"]: item for item in asc_response.json()["items"]}

    desc_response = client_with_atl_auth.get(
        f"/api/v1/aircraft-technical-log/paged?aircraft_fk={aircraft_id}&limit=10&page=1&sort=-sequence_no"
    )
    assert desc_response.status_code == 200, desc_response.text
    desc_items = {item["sequence_no"]: item for item in desc_response.json()["items"]}

    assert list(asc_items.keys()) == ["001", "002", "010"]
    assert list(desc_items.keys()) == ["010", "002", "001"]

    for sequence_no in ("001", "002", "010"):
        assert asc_items[sequence_no]["auto_airframe_run_time"] == desc_items[sequence_no]["auto_airframe_run_time"]
        assert asc_items[sequence_no]["auto_airframe_aftt"] == desc_items[sequence_no]["auto_airframe_aftt"]
        assert asc_items[sequence_no]["auto_engine_tsn"] == desc_items[sequence_no]["auto_engine_tsn"]
        assert asc_items[sequence_no]["auto_engine_tso"] == desc_items[sequence_no]["auto_engine_tso"]
        assert asc_items[sequence_no]["auto_propeller_tsn"] == desc_items[sequence_no]["auto_propeller_tsn"]
        assert asc_items[sequence_no]["auto_propeller_tso"] == desc_items[sequence_no]["auto_propeller_tso"]

    assert asc_items["010"]["auto_airframe_run_time"] == 1.5
    assert asc_items["010"]["auto_airframe_aftt"] == 21.5
    assert asc_items["010"]["auto_engine_tsn"] == 103.5
    assert asc_items["010"]["auto_engine_tso"] == 23.5
    assert asc_items["010"]["auto_propeller_tsn"] == 53.5
    assert asc_items["010"]["auto_propeller_tso"] == 13.5
