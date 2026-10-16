"""GET /api/v1/reports/aircraft-fleet-dashboard."""

import asyncio

from fastapi.testclient import TestClient

from app.models.aircraft import Aircraft
from app.models.fleet_daily_update import FleetDailyUpdate
from app.models.tcc_maintenance import TCCMaintenance
from tests.conftest import TestSessionLocal

ENDPOINT = "/api/v1/reports/aircraft-fleet-dashboard"


async def _seed() -> None:
    async with TestSessionLocal() as session:
        primary = Aircraft(
            registration="RP-C603",
            model="172",
            msn="MSN-MAG-603",
            base="MNL",
            ownership="Owner",
            status="Active",
            display_order=1,
        )
        secondary = Aircraft(
            registration="RP-C700",
            model="182",
            msn="MSN-MAG-700",
            base="MNL",
            ownership="Owner",
            status="Active",
            display_order=2,
        )
        bare = Aircraft(
            registration="RP-C111",
            model="172",
            msn="MSN-MAG-111",
            base="MNL",
            ownership="Owner",
            status="Active",
            display_order=3,
        )
        removed = Aircraft(
            registration="RP-C999",
            model="172",
            msn="MSN-MAG-999",
            base="MNL",
            ownership="Owner",
            status="Active",
            display_order=4,
            is_deleted=True,
        )
        session.add_all([primary, secondary, bare, removed])
        await session.flush()

        session.add_all(
            [
                FleetDailyUpdate(
                    aircraft_fk=primary.id,
                    status="Operational",
                    tach_time_eod=490.2,
                ),
                FleetDailyUpdate(
                    aircraft_fk=secondary.id,
                    status="AOG",
                    tach_time_eod=1000.0,
                ),
            ]
        )
        session.add_all(
            [
                TCCMaintenance(
                    aircraft_fk=primary.id,
                    part_number="4371",
                    serial_number="6031787",
                    description="RH MAGNETO",
                    last_done_tach=400.0,
                    component_limit_hours=100.0,
                    remaining_tach=9.8,
                    display_order=2,
                ),
                TCCMaintenance(
                    aircraft_fk=primary.id,
                    part_number="4370",
                    serial_number="6031786",
                    description="LH MAGNETO",
                    last_done_tach=390.0,
                    component_limit_hours=100.0,
                    remaining_tach=12.5,
                    display_order=1,
                ),
                TCCMaintenance(
                    aircraft_fk=primary.id,
                    part_number="ENG-1",
                    serial_number="E1",
                    description="Engine",
                    last_done_tach=10.0,
                    component_limit_hours=500.0,
                    display_order=3,
                ),
                TCCMaintenance(
                    aircraft_fk=primary.id,
                    part_number="OLD",
                    serial_number="OLD-1",
                    description="MAGNETO",
                    last_done_tach=1.0,
                    component_limit_hours=1.0,
                    display_order=4,
                    is_deleted=True,
                ),
                TCCMaintenance(
                    aircraft_fk=secondary.id,
                    part_number="5000",
                    serial_number="7001",
                    description="magneto",
                    last_done_tach=None,
                    component_limit_hours=50.0,
                    display_order=1,
                ),
                TCCMaintenance(
                    aircraft_fk=bare.id,
                    part_number="ENG-2",
                    serial_number="E2",
                    description="Engine",
                    last_done_tach=1.0,
                    component_limit_hours=1.0,
                    display_order=1,
                ),
                TCCMaintenance(
                    aircraft_fk=removed.id,
                    part_number="GONE",
                    serial_number="GONE-1",
                    description="RH MAGNETO",
                    last_done_tach=1.0,
                    component_limit_hours=1.0,
                    display_order=1,
                ),
            ]
        )
        await session.commit()


def test_aircraft_fleet_dashboard_lists_registered_aircraft(client: TestClient):
    asyncio.run(_seed())

    response = client.get(ENDPOINT)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["pages"] == 1

    items = body["items"]
    assert [row["aircraft_ident"] for row in items] == ["RP-C603", "RP-C700", "RP-C111"]

    primary = items[0]
    assert primary["status"] == "Operational"
    assert primary["eod_tach"] == "490.2"
    assert primary["components"] == [
        {
            "magneto": "LH MAGNETO",
            "due_for_replacement_tach": "390.0",
            "remaining_hours": "12.5",
            "part_number": "4370",
            "serial_number": "6031786",
        },
        {
            "magneto": "RH MAGNETO",
            "due_for_replacement_tach": "400.0",
            "remaining_hours": "9.8",
            "part_number": "4371",
            "serial_number": "6031787",
        },
    ]

    secondary = items[1]
    assert secondary["status"] == "AOG"
    assert secondary["eod_tach"] == "1000.0"
    assert secondary["components"] == [
        {
            "magneto": "magneto",
            "due_for_replacement_tach": None,
            "remaining_hours": None,
            "part_number": "5000",
            "serial_number": "7001",
        }
    ]

    bare = items[2]
    assert bare["status"] is None
    assert bare["eod_tach"] is None
    assert bare["components"] == []


def test_aircraft_fleet_dashboard_search_and_status_filters(client: TestClient):
    asyncio.run(_seed())

    by_tail = client.get(ENDPOINT, params={"search": "c603"})
    assert by_tail.status_code == 200
    tails = [row["aircraft_ident"] for row in by_tail.json()["items"]]
    assert tails == ["RP-C603"]

    operational = client.get(ENDPOINT, params={"status": "Operational"})
    assert operational.status_code == 200
    assert [row["aircraft_ident"] for row in operational.json()["items"]] == ["RP-C603"]

    aog = client.get(ENDPOINT, params={"status": "aog"})
    assert aog.status_code == 200
    assert [row["aircraft_ident"] for row in aog.json()["items"]] == ["RP-C700"]

    invalid = client.get(ENDPOINT, params={"status": "Active"})
    assert invalid.status_code == 422


def test_aircraft_fleet_dashboard_paginates_by_aircraft(client: TestClient):
    async def _seed_many() -> None:
        async with TestSessionLocal() as session:
            for index in range(21):
                aircraft = Aircraft(
                    registration=f"RP-C{index:03d}",
                    model="172",
                    msn=f"MSN-PAGE-{index}",
                    base="MNL",
                    ownership="Owner",
                    status="Active",
                    display_order=index + 1,
                )
                session.add(aircraft)
                await session.flush()
                if index == 0:
                    session.add(
                        FleetDailyUpdate(
                            aircraft_fk=aircraft.id,
                            status="Ongoing Maintenance",
                            tach_time_eod=10.0,
                        )
                    )
                    session.add(
                        TCCMaintenance(
                            aircraft_fk=aircraft.id,
                            part_number="PN-0",
                            serial_number="SN-0",
                            description="RH MAGNETO",
                            last_done_tach=100.0,
                            component_limit_hours=50.0,
                            remaining_tach=77.7,
                            display_order=1,
                        )
                    )
            await session.commit()

    asyncio.run(_seed_many())

    first = client.get(ENDPOINT)
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["total"] == 21
    assert first_body["page_size"] == 20
    assert first_body["pages"] == 2
    assert len(first_body["items"]) == 20
    assert first_body["items"][0]["aircraft_ident"] == "RP-C000"
    assert first_body["items"][0]["status"] == "Ongoing Maintenance"
    assert first_body["items"][0]["components"][0]["due_for_replacement_tach"] == "100.0"
    assert first_body["items"][0]["components"][0]["remaining_hours"] == "77.7"
    assert first_body["items"][1]["components"] == []
    assert first_body["items"][1]["status"] is None

    second = client.get(ENDPOINT, params={"page": 2})
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["page"] == 2
    assert len(second_body["items"]) == 1
    assert second_body["items"][0]["aircraft_ident"] == "RP-C020"


def test_aircraft_fleet_dashboard_rejects_invalid_page_size(client: TestClient):
    response = client.get(ENDPOINT, params={"page_size": 0})
    assert response.status_code == 422


def test_aircraft_fleet_dashboard_empty(client: TestClient):
    response = client.get(ENDPOINT)
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["pages"] == 0
