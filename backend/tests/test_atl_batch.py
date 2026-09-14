"""ATL batch aircraft_id create, uniqueness, and list filter."""
from fastapi.testclient import TestClient


def test_atl_batch_aircraft_id_create_list_and_uniqueness(
    client: TestClient,
    aircraft_id: int,
):
    created = client.post(
        "/api/v1/atl-batch/",
        json={
            "name": "Batch One",
            "description": "scoped",
            "aircraft_id": aircraft_id,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["aircraft_id"] == aircraft_id
    assert body["name"] == "Batch One"

    duplicate = client.post(
        "/api/v1/atl-batch/",
        json={"name": "Batch One", "aircraft_id": aircraft_id},
    )
    assert duplicate.status_code == 400

    other = client.post(
        "/api/v1/atl-batch/",
        json={"name": "Batch One"},
    )
    assert other.status_code == 201, other.text
    assert other.json()["aircraft_id"] is None

    missing_aircraft = client.post(
        "/api/v1/atl-batch/",
        json={"name": "No Aircraft", "aircraft_id": 999999},
    )
    assert missing_aircraft.status_code == 400

    filtered = client.get(f"/api/v1/atl-batch/paged?page=1&page_size=50&aircraft_id={aircraft_id}")
    assert filtered.status_code == 200, filtered.text
    data = filtered.json()
    assert data["total"] == 1
    assert data["items"][0]["aircraft_id"] == aircraft_id

    listed = client.get(f"/api/v1/atl-batch/list?aircraft_id={aircraft_id}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["aircraft_id"] == aircraft_id
