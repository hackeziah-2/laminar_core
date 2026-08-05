"""Integration tests for GET /api/v1/dashboard/aircraft-fuel-report."""

import asyncio
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import AircraftTechnicalLog, WorkStatus
from tests.conftest import TestSessionLocal

ENDPOINT = "/api/v1/dashboard/aircraft-fuel-report"


async def _seed_fleet() -> dict:
    """Seed two aircraft with approved/completed ATLs across periods."""
    async with TestSessionLocal() as session:
        ac1 = Aircraft(
            registration="rp-c12",
            model="172",
            msn="MSN-FUEL-1",
            base="MNL",
            ownership="Owner",
            status="Active",
        )
        ac2 = Aircraft(
            registration="RP-C99",
            model="182",
            msn="MSN-FUEL-2",
            base="MNL",
            ownership="Owner",
            status="Active",
        )
        session.add_all([ac1, ac2])
        await session.flush()

        logs = [
            # 2026-W32 Monday — complete (ac1)
            AircraftTechnicalLog(
                aircraft_fk=ac1.id,
                sequence_no="1001",
                work_status=WorkStatus.APPROVED,
                atl_date_time_reported=datetime(2026, 8, 3, 8, 0, 0),
                airframe_flight_time=Decimal("2.00"),
                fuel_qty_left_prior_departure=Decimal("18"),
                fuel_qty_right_prior_departure=Decimal("17"),
                fuel_qty_left_after_on_blks=Decimal("13"),
                fuel_qty_right_after_on_blks=Decimal("10"),
                oil_qty_prior_departure=Decimal("8"),
                oil_qty_after_on_blks=Decimal("6"),
            ),
            # 2026-W32 Wednesday — incomplete (ac1)
            AircraftTechnicalLog(
                aircraft_fk=ac1.id,
                sequence_no="1002",
                work_status=WorkStatus.COMPLETED,
                atl_date_time_reported=datetime(2026, 8, 5, 8, 0, 0),
                airframe_flight_time=None,
                fuel_qty_left_prior_departure=Decimal("18"),
                fuel_qty_right_prior_departure=Decimal("17"),
                fuel_qty_left_after_on_blks=Decimal("13"),
                fuel_qty_right_after_on_blks=Decimal("10"),
                oil_qty_prior_departure=Decimal("8"),
                oil_qty_after_on_blks=Decimal("6"),
            ),
            # August Week 3 — complete (ac2)
            AircraftTechnicalLog(
                aircraft_fk=ac2.id,
                sequence_no="2001",
                work_status=WorkStatus.APPROVED,
                atl_date_time_reported=datetime(2026, 8, 18, 10, 0, 0),
                airframe_flight_time=Decimal("1.50"),
                fuel_qty_left_prior_departure=Decimal("20"),
                fuel_qty_right_prior_departure=Decimal("20"),
                fuel_qty_left_after_on_blks=Decimal("15"),
                fuel_qty_right_after_on_blks=Decimal("14"),
                oil_qty_prior_departure=Decimal("5"),
                oil_qty_after_on_blks=Decimal("4"),
            ),
            # January 2026 — complete (ac1)
            AircraftTechnicalLog(
                aircraft_fk=ac1.id,
                sequence_no="1003",
                work_status=WorkStatus.COMPLETED,
                atl_date_time_reported=datetime(2026, 1, 15, 9, 0, 0),
                airframe_flight_time=Decimal("3.00"),
                fuel_qty_left_prior_departure=Decimal("30"),
                fuel_qty_right_prior_departure=Decimal("30"),
                fuel_qty_left_after_on_blks=Decimal("20"),
                fuel_qty_right_after_on_blks=Decimal("18"),
                oil_qty_prior_departure=Decimal("10"),
                oil_qty_after_on_blks=Decimal("7"),
            ),
            # FOR_REVIEW — must be excluded
            AircraftTechnicalLog(
                aircraft_fk=ac1.id,
                sequence_no="1004",
                work_status=WorkStatus.FOR_REVIEW,
                atl_date_time_reported=datetime(2026, 8, 4, 8, 0, 0),
                airframe_flight_time=Decimal("9.00"),
                fuel_qty_left_prior_departure=Decimal("50"),
                fuel_qty_right_prior_departure=Decimal("50"),
                fuel_qty_left_after_on_blks=Decimal("1"),
                fuel_qty_right_after_on_blks=Decimal("1"),
                oil_qty_prior_departure=Decimal("10"),
                oil_qty_after_on_blks=Decimal("1"),
            ),
            # Invalid negative fuel (August)
            AircraftTechnicalLog(
                aircraft_fk=ac2.id,
                sequence_no="2002",
                work_status=WorkStatus.APPROVED,
                atl_date_time_reported=datetime(2026, 8, 19, 10, 0, 0),
                airframe_flight_time=Decimal("1.00"),
                fuel_qty_left_prior_departure=Decimal("5"),
                fuel_qty_right_prior_departure=Decimal("10"),
                fuel_qty_left_after_on_blks=Decimal("8"),
                fuel_qty_right_after_on_blks=Decimal("5"),
                oil_qty_prior_departure=Decimal("4"),
                oil_qty_after_on_blks=Decimal("3"),
            ),
        ]
        session.add_all(logs)
        await session.commit()
        return {"ac1_id": ac1.id, "ac2_id": ac2.id}


@pytest.mark.no_auth
def test_yearly_fuel_report_filters_and_shape(client: TestClient):
    ids = asyncio.run(_seed_fleet())

    response = client.get(ENDPOINT, params={"period": "yearly", "year": 2026})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["period"] == "yearly"
    assert body["filters"]["year"] == 2026
    assert body["filters"]["month"] is None
    assert body["filters"]["week"] is None
    assert body["filters"]["start_date"] == "2026-01-01"
    assert body["filters"]["end_date"] == "2026-12-31"
    assert len(body["categories"]) == 12
    assert len(body["series"]) == 3
    for series in body["series"]:
        assert len(series["data"]) == 12

    # Jan has 22 gal fuel / 3 hours from ac1
    assert body["series"][0]["data"][0] == 3.0
    assert body["series"][1]["data"][0] == 22.0
    assert body["series"][2]["data"][0] == pytest.approx(7.33, abs=0.01)

    # August: complete rows only — ac1 Mon (12 gal/2h) + ac2 Week3 (11 gal/1.5h)
    # incomplete + invalid counted but not in fuel/hours
    assert body["series"][0]["data"][7] == 3.5
    assert body["series"][1]["data"][7] == 23.0

    assert body["grand_total"]["atl_record_count"] == 5  # excludes FOR_REVIEW
    assert body["grand_total"]["incomplete_record_count"] == 1
    assert body["grand_total"]["invalid_record_count"] == 1
    assert body["grand_total"]["total_fuel_gallons"] == 45.0  # 22+12+11
    assert body["grand_total"]["total_flight_hours"] == 6.5

    # aircraft filter
    filtered = client.get(
        ENDPOINT,
        params={"period": "yearly", "year": 2026, "aircraft_id": ids["ac2_id"]},
    )
    assert filtered.status_code == 200
    fbody = filtered.json()
    assert fbody["filters"]["aircraft_id"] == ids["ac2_id"]
    # ac2 only: Aug complete 11 gal / 1.5h + invalid counted
    assert fbody["grand_total"]["total_fuel_gallons"] == 11.0
    assert fbody["grand_total"]["invalid_record_count"] == 1


@pytest.mark.no_auth
def test_monthly_fuel_report(client: TestClient):
    asyncio.run(_seed_fleet())

    response = client.get(
        ENDPOINT,
        params={"period": "monthly", "year": 2026, "month": 8},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period"] == "monthly"
    assert body["categories"] == ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5"]
    assert body["filters"]["month"] == 8
    assert body["filters"]["start_date"] == "2026-08-01"
    assert body["filters"]["end_date"] == "2026-08-31"

    # Week 1: Mon complete 12 gal / 2h; Wed incomplete
    assert body["series"][0]["data"][0] == 2.0
    assert body["series"][1]["data"][0] == 12.0
    assert body["aircraft_breakdown"][0]["totals"]["incomplete_record_count"] == 1

    # Week 3: ac2 complete + invalid
    assert body["series"][0]["data"][2] == 1.5
    assert body["series"][1]["data"][2] == 11.0
    assert body["aircraft_breakdown"][2]["totals"]["invalid_record_count"] == 1


@pytest.mark.no_auth
def test_weekly_fuel_report(client: TestClient):
    asyncio.run(_seed_fleet())

    response = client.get(
        ENDPOINT,
        params={"period": "weekly", "year": 2026, "week": 32},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period"] == "weekly"
    assert body["categories"] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert body["filters"]["week"] == 32
    assert body["filters"]["start_date"] == "2026-08-03"
    assert body["filters"]["end_date"] == "2026-08-09"

    assert body["series"][0]["data"][0] == 2.0  # Mon
    assert body["series"][1]["data"][0] == 12.0
    assert body["series"][2]["data"][0] == 6.0
    assert body["series"][0]["data"][2] == 0.0  # Wed incomplete → no hours
    assert body["aircraft_breakdown"][2]["totals"]["incomplete_record_count"] == 1


@pytest.mark.no_auth
def test_query_validation_errors(client: TestClient):
    missing_month = client.get(ENDPOINT, params={"period": "monthly", "year": 2026})
    assert missing_month.status_code == 422

    missing_week = client.get(ENDPOINT, params={"period": "weekly", "year": 2026})
    assert missing_week.status_code == 422

    bad_period = client.get(ENDPOINT, params={"period": "daily", "year": 2026})
    assert bad_period.status_code == 422
