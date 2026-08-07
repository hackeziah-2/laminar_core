"""Integration tests for GET /api/v1/dashboard/aircraft-fuel-report."""

import asyncio
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import AircraftTechnicalLog, WorkStatus
from app.services.aircraft_fuel_report_service import invalidate_fuel_report_cache
from tests.conftest import TestSessionLocal

ENDPOINT = "/api/v1/dashboard/aircraft-fuel-report"


async def _seed() -> dict:
    invalidate_fuel_report_cache()
    async with TestSessionLocal() as session:
        ac1 = Aircraft(
            registration="RP-C12",
            model="172",
            msn="MSN-FUEL-A",
            base="MNL",
            ownership="Owner",
            status="Active",
        )
        ac2 = Aircraft(
            registration="RP-C14",
            model="182",
            msn="MSN-FUEL-B",
            base="MNL",
            ownership="Owner",
            status="Active",
        )
        session.add_all([ac1, ac2])
        await session.flush()

        logs = [
            AircraftTechnicalLog(
                aircraft_fk=ac1.id,
                sequence_no="1001",
                work_status=WorkStatus.APPROVED,
                origin_date=date(2026, 1, 10),
                airframe_run_time=Decimal("2.00"),
                fuel_qty_left_prior_departure=Decimal("18"),
                fuel_qty_right_prior_departure=Decimal("17"),
                fuel_qty_left_after_on_blks=Decimal("13"),
                fuel_qty_right_after_on_blks=Decimal("10"),
                oil_qty_prior_departure=Decimal("8"),
                oil_qty_after_on_blks=Decimal("6"),
                number_of_landings=1,
            ),
            # RUN TIME = 0 → burn must be null
            AircraftTechnicalLog(
                aircraft_fk=ac1.id,
                sequence_no="1002",
                work_status=WorkStatus.COMPLETED,
                origin_date=date(2026, 1, 20),
                airframe_run_time=Decimal("0"),
                fuel_qty_left_prior_departure=Decimal("10"),
                fuel_qty_right_prior_departure=Decimal("10"),
                fuel_qty_left_after_on_blks=Decimal("5"),
                fuel_qty_right_after_on_blks=Decimal("5"),
                oil_qty_prior_departure=Decimal("4"),
                oil_qty_after_on_blks=Decimal("3"),
                number_of_landings=0,
            ),
            AircraftTechnicalLog(
                aircraft_fk=ac2.id,
                sequence_no="2001",
                work_status=WorkStatus.APPROVED,
                origin_date=date(2026, 2, 5),
                airframe_run_time=Decimal("1.50"),
                fuel_qty_left_prior_departure=Decimal("20"),
                fuel_qty_right_prior_departure=Decimal("20"),
                fuel_qty_left_after_on_blks=Decimal("15"),
                fuel_qty_right_after_on_blks=Decimal("14"),
                oil_qty_prior_departure=Decimal("5"),
                oil_qty_after_on_blks=Decimal("4"),
                number_of_landings=2,
            ),
            # Missing fuel left prior → treated as 0: (0+10)-(5+5)=0
            AircraftTechnicalLog(
                aircraft_fk=ac2.id,
                sequence_no="2002",
                work_status=WorkStatus.APPROVED,
                origin_date=date(2026, 2, 15),
                airframe_run_time=Decimal("1.00"),
                fuel_qty_left_prior_departure=None,
                fuel_qty_right_prior_departure=Decimal("10"),
                fuel_qty_left_after_on_blks=Decimal("5"),
                fuel_qty_right_after_on_blks=Decimal("5"),
                oil_qty_prior_departure=Decimal("2"),
                oil_qty_after_on_blks=Decimal("1"),
                number_of_landings=1,
            ),
            # FOR_REVIEW excluded
            AircraftTechnicalLog(
                aircraft_fk=ac1.id,
                sequence_no="1003",
                work_status=WorkStatus.FOR_REVIEW,
                origin_date=date(2026, 1, 25),
                airframe_run_time=Decimal("9"),
                fuel_qty_left_prior_departure=Decimal("50"),
                fuel_qty_right_prior_departure=Decimal("50"),
                fuel_qty_left_after_on_blks=Decimal("1"),
                fuel_qty_right_after_on_blks=Decimal("1"),
                number_of_landings=9,
            ),
        ]
        session.add_all(logs)
        await session.commit()
        return {
            "ac1": ac1.registration,
            "ac2": ac2.registration,
            "ac1_id": ac1.id,
            "ac2_id": ac2.id,
        }


@pytest.mark.no_auth
def test_monthly_report_shape_and_aggregates(client: TestClient):
    asyncio.run(_seed())

    response = client.get(
        ENDPOINT,
        params={"start_month": "2026-01", "end_month": "2026-02"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["meta"]["source"] == "ATL Logbook"
    assert body["meta"]["range"] == {"start": "2026-01", "end": "2026-02"}
    assert "generated_at" in body["meta"]
    assert len(body["monthly"]) == 2

    jan = body["monthly"][0]
    assert jan["month"] == "2026-01"
    assert jan["month_label"] == "Jan-26"
    assert jan["hours"] == 2.0  # 2 + 0
    assert jan["fuel_gal"] == 22.0  # 12 + 10
    assert jan["fuel_burn_per_hour"] == 11.0
    assert jan["landings"] == 1

    feb = body["monthly"][1]
    assert feb["month"] == "2026-02"
    assert feb["hours"] == 2.5  # 1.5 + 1.0
    assert feb["fuel_gal"] == 11.0  # 11 + (0+10)-(5+5)=0
    assert feb["landings"] == 3

    assert body["summary"]["total_hours"] == 4.5
    assert body["summary"]["total_fuel_gal"] == 33.0
    assert body["summary"]["total_landings"] == 4
    assert not any(f["code"] == "missing_fuel_fields" for f in body["data_quality_flags"])


@pytest.mark.no_auth
def test_single_zero_run_time_row_burn_is_null(client: TestClient):
    """Integration: RUN TIME = 0 → fuel_burn_per_hour null (never NaN/error)."""
    invalidate_fuel_report_cache()

    async def seed_zero():
        async with TestSessionLocal() as session:
            ac = Aircraft(
                registration="RP-C99",
                model="172",
                msn="MSN-ZERO",
                base="MNL",
                ownership="Owner",
                status="Active",
            )
            session.add(ac)
            await session.flush()
            session.add(
                AircraftTechnicalLog(
                    aircraft_fk=ac.id,
                    sequence_no="Z1",
                    work_status=WorkStatus.APPROVED,
                    origin_date=date(2026, 5, 1),
                    airframe_run_time=Decimal("0"),
                    fuel_qty_left_prior_departure=Decimal("10"),
                    fuel_qty_right_prior_departure=Decimal("10"),
                    fuel_qty_left_after_on_blks=Decimal("5"),
                    fuel_qty_right_after_on_blks=Decimal("5"),
                    oil_qty_prior_departure=Decimal("2"),
                    oil_qty_after_on_blks=Decimal("1"),
                    number_of_landings=0,
                )
            )
            await session.commit()

    asyncio.run(seed_zero())
    response = client.get(
        ENDPOINT,
        params={
            "start_month": "2026-05",
            "end_month": "2026-05",
            "aircraft": "RP-C99",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["monthly"][0]["hours"] == 0.0
    assert body["monthly"][0]["fuel_gal"] == 10.0
    assert body["monthly"][0]["fuel_burn_per_hour"] is None
    assert body["summary"]["avg_fuel_burn_per_hour"] is None


@pytest.mark.no_auth
def test_aircraft_filter_and_unknown_tail(client: TestClient):
    seeded = asyncio.run(_seed())

    ok = client.get(
        ENDPOINT,
        params={"start_month": "2026-02", "end_month": "2026-02", "aircraft": "RP-C14"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["summary"]["total_hours"] == 2.5
    assert all(
        a["tail_number"] == "RP-C14"
        for m in body["monthly"]
        for a in m["aircraft_breakdown"]
    )

    by_id = client.get(
        ENDPOINT,
        params={
            "start_month": "2026-02",
            "end_month": "2026-02",
            "aircraft_id": str(seeded["ac2_id"]),
        },
    )
    assert by_id.status_code == 200
    assert by_id.json()["summary"]["total_hours"] == 2.5

    bad = client.get(
        ENDPOINT,
        params={"start_month": "2026-01", "end_month": "2026-01", "aircraft": "RP-XX"},
    )
    assert bad.status_code == 422

    bad_id = client.get(
        ENDPOINT,
        params={"start_month": "2026-01", "end_month": "2026-01", "aircraft_id": "999999"},
    )
    assert bad_id.status_code == 422


@pytest.mark.no_auth
def test_empty_range_returns_empty_monthly_not_404(client: TestClient):
    invalidate_fuel_report_cache()
    response = client.get(
        ENDPOINT,
        params={"start_month": "2099-01", "end_month": "2099-03"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["monthly"] == []
    assert body["summary"]["total_hours"] == 0.0
    assert body["meta"]["range"] == {"start": "2099-01", "end": "2099-03"}


@pytest.mark.no_auth
def test_query_validation(client: TestClient):
    assert (
        client.get(ENDPOINT, params={"start_month": "2026-13", "end_month": "2026-01"}).status_code
        == 422
    )
    assert (
        client.get(
            ENDPOINT, params={"start_month": "2026-06", "end_month": "2026-01"}
        ).status_code
        == 422
    )
