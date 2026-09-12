"""Pytest for Nature of Flight Description REST API."""
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def description_payload(aircraft_id: int):
    return {
        "aircraft_fk": aircraft_id,
        "nature_of_flight": "TR",
        "remarks": "Training flight remarks",
        "action_taken": "No action required",
    }


def test_list_descriptions_empty(client: TestClient):
    response = client.get("/api/v1/nature-of-flight-descriptions/paged?page_size=50&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0
    assert data["items"] == []


def test_create_description(client: TestClient, description_payload: dict):
    response = client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["aircraft_fk"] == description_payload["aircraft_fk"]
    assert data["nature_of_flight"] == "TR"
    assert data["remarks"] == "Training flight remarks"
    assert data["action_taken"] == "No action required"
    assert data["id"] is not None


def test_create_description_aircraft_not_found(client: TestClient):
    payload = {
        "aircraft_fk": 99999,
        "nature_of_flight": "TR",
        "remarks": "x",
        "action_taken": "y",
    }
    response = client.post("/api/v1/nature-of-flight-descriptions/", json=payload)
    assert response.status_code == 404
    assert "aircraft" in response.json()["detail"].lower()


def test_create_duplicate_aircraft_and_nature_of_flight_returns_409(
    client: TestClient, description_payload: dict
):
    first = client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    assert first.status_code == 201, first.text

    duplicate = client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"].lower()


def test_create_same_nature_of_flight_different_aircraft_ok(
    client: TestClient, description_payload: dict, test_aircraft_data: dict
):
    first = client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    assert first.status_code == 201, first.text

    other_aircraft = dict(test_aircraft_data)
    other_aircraft["registration"] = "TEST-NOF-002"
    other_aircraft["msn"] = "TEST-MSN-NOF-002"
    create_aircraft = client.post(
        "/api/v1/aircraft/",
        data={"json_data": json.dumps(other_aircraft)},
        files={},
    )
    assert create_aircraft.status_code == 200, create_aircraft.text
    other_id = create_aircraft.json()["id"]

    second = client.post(
        "/api/v1/nature-of-flight-descriptions/",
        json={**description_payload, "aircraft_fk": other_id},
    )
    assert second.status_code == 201, second.text
    assert second.json()["aircraft_fk"] == other_id
    assert second.json()["nature_of_flight"] == "TR"


def test_create_same_aircraft_different_nature_of_flight_ok(
    client: TestClient, description_payload: dict
):
    first = client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/nature-of-flight-descriptions/",
        json={**description_payload, "nature_of_flight": "PSF"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["nature_of_flight"] == "PSF"


def test_create_after_soft_delete_allows_same_combo(
    client: TestClient, description_payload: dict
):
    first = client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    assert first.status_code == 201, first.text
    entry_id = first.json()["id"]

    deleted = client.delete(f"/api/v1/nature-of-flight-descriptions/{entry_id}")
    assert deleted.status_code == 204

    recreated = client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["id"] != entry_id


def test_update_to_duplicate_aircraft_and_nature_of_flight_returns_409(
    client: TestClient, description_payload: dict
):
    first = client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/nature-of-flight-descriptions/",
        json={**description_payload, "nature_of_flight": "PSF"},
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]

    conflict = client.put(
        f"/api/v1/nature-of-flight-descriptions/{second_id}",
        json={"nature_of_flight": "TR"},
    )
    assert conflict.status_code == 409
    assert "already exists" in conflict.json()["detail"].lower()


def test_create_invalid_nature_of_flight(client: TestClient, aircraft_id: int):
    payload = {
        "aircraft_fk": aircraft_id,
        "nature_of_flight": "INVALID",
        "remarks": "x",
        "action_taken": "y",
    }
    response = client.post("/api/v1/nature-of-flight-descriptions/", json=payload)
    assert response.status_code == 422


def test_get_description(client: TestClient, description_payload: dict):
    create_resp = client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/nature-of-flight-descriptions/{entry_id}")
    assert response.status_code == 200
    assert response.json()["id"] == entry_id
    assert response.json()["nature_of_flight"] == "TR"


def test_get_description_not_found(client: TestClient):
    response = client.get("/api/v1/nature-of-flight-descriptions/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_paged_with_filter(client: TestClient, description_payload: dict):
    client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)

    response = client.get(
        "/api/v1/nature-of-flight-descriptions/paged?page_size=50&page=1&nature_of_flight=TR"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["nature_of_flight"] == "TR"

    response_other = client.get(
        "/api/v1/nature-of-flight-descriptions/paged?page_size=50&page=1&nature_of_flight=PSF"
    )
    assert response_other.status_code == 200
    assert "items" in response_other.json()


def test_list_paged_search_remarks(client: TestClient, description_payload: dict):
    client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    response = client.get(
        "/api/v1/nature-of-flight-descriptions/paged?page_size=50&page=1&search=Training"
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


def test_update_description(client: TestClient, description_payload: dict):
    create_resp = client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    response = client.put(
        f"/api/v1/nature-of-flight-descriptions/{entry_id}",
        json={
            "remarks": "Updated remarks",
            "action_taken": "Inspected and released",
            "nature_of_flight": "PSF",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["remarks"] == "Updated remarks"
    assert data["action_taken"] == "Inspected and released"
    assert data["nature_of_flight"] == "PSF"


def test_update_description_not_found(client: TestClient):
    response = client.put(
        "/api/v1/nature-of-flight-descriptions/99999",
        json={"remarks": "missing"},
    )
    assert response.status_code == 404


def test_delete_description(client: TestClient, description_payload: dict):
    create_resp = client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    response = client.delete(f"/api/v1/nature-of-flight-descriptions/{entry_id}")
    assert response.status_code == 204

    get_resp = client.get(f"/api/v1/nature-of-flight-descriptions/{entry_id}")
    assert get_resp.status_code == 404


def test_list_by_aircraft_paged(client: TestClient, description_payload: dict, aircraft_id: int):
    client.post("/api/v1/nature-of-flight-descriptions/", json=description_payload)

    response = client.get(
        f"/api/v1/aircraft/{aircraft_id}/nature-of-flight-descriptions/paged?page_size=50&page=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["aircraft_fk"] == aircraft_id


def test_create_get_update_delete_by_aircraft(client: TestClient, aircraft_id: int):
    create_resp = client.post(
        f"/api/v1/aircraft/{aircraft_id}/nature-of-flight-descriptions/",
        json={
            "nature_of_flight": "EGR",
            "remarks": "Engine ground run",
            "action_taken": "Logged",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    data = create_resp.json()
    assert data["aircraft_fk"] == aircraft_id
    assert data["nature_of_flight"] == "EGR"
    entry_id = data["id"]

    get_resp = client.get(
        f"/api/v1/aircraft/{aircraft_id}/nature-of-flight-descriptions/EGR"
    )
    assert get_resp.status_code == 200
    assert get_resp.json() == {
        "remarks": "Engine ground run",
        "action_taken": "Logged",
    }

    update_resp = client.put(
        f"/api/v1/aircraft/{aircraft_id}/nature-of-flight-descriptions/{entry_id}",
        json={"action_taken": "Completed"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["action_taken"] == "Completed"

    delete_resp = client.delete(
        f"/api/v1/aircraft/{aircraft_id}/nature-of-flight-descriptions/{entry_id}"
    )
    assert delete_resp.status_code == 204
    assert (
        client.get(
            f"/api/v1/aircraft/{aircraft_id}/nature-of-flight-descriptions/EGR"
        ).status_code
        == 404
    )


def test_get_by_aircraft_and_nature_of_flight(
    client: TestClient, description_payload: dict, aircraft_id: int
):
    create_resp = client.post(
        "/api/v1/nature-of-flight-descriptions/", json=description_payload
    )
    assert create_resp.status_code == 201, create_resp.text

    response = client.get(
        f"/api/v1/aircraft/{aircraft_id}/nature-of-flight-descriptions/TR"
    )
    assert response.status_code == 200
    assert response.json() == {
        "remarks": "Training flight remarks",
        "action_taken": "No action required",
    }


def test_get_by_aircraft_and_nature_of_flight_not_found(
    client: TestClient, aircraft_id: int
):
    response = client.get(
        f"/api/v1/aircraft/{aircraft_id}/nature-of-flight-descriptions/PSF"
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_by_aircraft_and_nature_of_flight_invalid_enum(
    client: TestClient, aircraft_id: int
):
    response = client.get(
        f"/api/v1/aircraft/{aircraft_id}/nature-of-flight-descriptions/INVALID"
    )
    assert response.status_code == 422
