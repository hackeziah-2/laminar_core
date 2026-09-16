"""Pytest for AD Monitoring REST API."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ad_monitoring_payload(aircraft_id: int) -> dict:
    """Minimal create payload for one AD monitoring record."""
    return {
        "aircraft_fk": aircraft_id,
        "ad_number": "AD-2024-0001",
        "subject": "Test subject",
        "inspection_interval": "100 FH",
    }


def test_ad_monitoring_web_link_crud(
    client: TestClient,
    aircraft_id: int,
    ad_monitoring_payload: dict,
):
    """Create/update/get optional web_link on global and aircraft-scoped endpoints."""
    create_payload = {
        **ad_monitoring_payload,
        "web_link": "https://example.com/ad/initial",
    }
    create_response = client.post(
        "/api/v1/ad-monitoring/",
        json=create_payload,
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    ad_id = created["id"]
    assert created["web_link"] == create_payload["web_link"]

    get_response = client.get(f"/api/v1/ad-monitoring/{ad_id}")
    assert get_response.status_code == 200
    assert get_response.json()["web_link"] == create_payload["web_link"]

    update_payload = {"web_link": "https://example.com/ad/updated"}
    update_response = client.put(
        f"/api/v1/ad-monitoring/{ad_id}",
        json=update_payload,
    )
    assert update_response.status_code == 200
    assert update_response.json()["web_link"] == update_payload["web_link"]

    scoped_get = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/{ad_id}",
    )
    assert scoped_get.status_code == 200
    assert scoped_get.json()["web_link"] == update_payload["web_link"]

    scoped_update = client.put(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/{ad_id}",
        json={"web_link": "https://example.com/ad/scoped"},
    )
    assert scoped_update.status_code == 200
    assert scoped_update.json()["web_link"] == "https://example.com/ad/scoped"


def test_ad_monitoring_web_link_optional(
    client: TestClient,
    ad_monitoring_payload: dict,
):
    """web_link may be omitted on create."""
    response = client.post(
        "/api/v1/ad-monitoring/",
        json=ad_monitoring_payload,
    )
    assert response.status_code == 201, response.text
    assert response.json()["web_link"] is None


def test_work_order_ad_monitoring_create_writes_audit_log(
    client: TestClient,
    aircraft_id: int,
    ad_monitoring_payload: dict,
):
    """Work-order AD monitoring create should persist a CREATE audit log."""
    from app.constants.audit import WORK_ORDER_AD_MONITORING_MODULE_NAME

    ad_response = client.post("/api/v1/ad-monitoring/", json=ad_monitoring_payload)
    assert ad_response.status_code == 201, ad_response.text
    ad_id = ad_response.json()["id"]

    wo_payload = {
        "ad_monitoring_fk": ad_id,
        "work_order_number": "WO-TEST-001",
        "atl_ref": "ATL-001",
    }
    create_response = client.post(
        "/api/v1/work-order-ad-monitoring/",
        json=wo_payload,
    )
    assert create_response.status_code == 201, create_response.text
    work_order_id = create_response.json()["id"]

    audit_response = client.get(
        "/api/v1/audit-logs/"
        f"?module_name={WORK_ORDER_AD_MONITORING_MODULE_NAME}&record_id={work_order_id}"
    )
    assert audit_response.status_code == 200
    payload = audit_response.json()
    create_logs = [item for item in payload["items"] if item["action"] == "CREATE"]
    assert len(create_logs) == 1
    assert create_logs[0]["table_name"] == "workorder_ad_monitoring"
    assert create_logs[0]["new_data"]["work_order_number"] == "WO-TEST-001"


def test_work_order_ad_monitoring_delete_writes_audit_log(
    client: TestClient,
    aircraft_id: int,
    ad_monitoring_payload: dict,
):
    """Work-order AD monitoring delete should persist a DELETE audit log."""
    from app.constants.audit import WORK_ORDER_AD_MONITORING_MODULE_NAME

    ad_response = client.post("/api/v1/ad-monitoring/", json=ad_monitoring_payload)
    assert ad_response.status_code == 201, ad_response.text
    ad_id = ad_response.json()["id"]

    wo_payload = {
        "ad_monitoring_fk": ad_id,
        "work_order_number": "WO-TEST-DEL",
        "atl_ref": "ATL-002",
    }
    create_response = client.post(
        "/api/v1/work-order-ad-monitoring/",
        json=wo_payload,
    )
    assert create_response.status_code == 201, create_response.text
    work_order_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/work-order-ad-monitoring/{work_order_id}"
    )
    assert delete_response.status_code == 204

    audit_response = client.get(
        "/api/v1/audit-logs/"
        f"?module_name={WORK_ORDER_AD_MONITORING_MODULE_NAME}"
        f"&record_id={work_order_id}&action=DELETE"
    )
    assert audit_response.status_code == 200
    payload = audit_response.json()
    assert payload["total"] >= 1
    delete_log = payload["items"][0]
    assert delete_log["action"] == "DELETE"
    assert delete_log["old_data"] is not None
    assert delete_log["new_data"] is None


def _create_ad_records(client: TestClient, aircraft_id: int, count: int, prefix: str = "AD-PAGE"):
    ids = []
    for i in range(count):
        response = client.post(
            "/api/v1/ad-monitoring/",
            json={
                "aircraft_fk": aircraft_id,
                "ad_number": f"{prefix}-{i:04d}",
                "subject": f"Subject {i}",
                "inspection_interval": "100 FH" if i % 2 == 0 else "200 FH",
            },
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    return ids


@pytest.fixture
def fifty_one_ads(client: TestClient, aircraft_id: int):
    """51 AD records so default page size 50 yields two pages."""
    return _create_ad_records(client, aircraft_id, 51)


def _assert_paged_envelope(payload: dict, *, total: int, page: int, pages: int, page_size: int = 50):
    assert set(payload.keys()) >= {"items", "total", "page", "page_size", "pages"}
    assert payload["total"] == total
    assert payload["page"] == page
    assert payload["page_size"] == page_size
    assert payload["pages"] == pages
    assert isinstance(payload["items"], list)


def test_ad_monitoring_pagination_default_page_size(
    client: TestClient,
    aircraft_id: int,
    fifty_one_ads,
):
    """Omitted page_size defaults to 50; pages = ceil(total / page_size)."""
    response = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/paged?page=1"
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    _assert_paged_envelope(payload, total=51, page=1, pages=2)
    assert len(payload["items"]) == 50

    page_two = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/paged?page=2"
    )
    assert page_two.status_code == 200
    page_two_payload = page_two.json()
    _assert_paged_envelope(page_two_payload, total=51, page=2, pages=2)
    assert len(page_two_payload["items"]) == 1


def test_ad_monitoring_pagination_valid_page_sizes(
    client: TestClient,
    aircraft_id: int,
    fifty_one_ads,
):
    """Allowed page sizes 50, 100, and 500 return a full matching page."""
    for page_size, expected_len, expected_pages in (
        (50, 50, 2),
        (100, 51, 1),
        (500, 51, 1),
    ):
        response = client.get(
            f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/paged"
            f"?page=1&page_size={page_size}"
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        _assert_paged_envelope(
            payload,
            total=51,
            page=1,
            pages=expected_pages,
            page_size=page_size,
        )
        assert len(payload["items"]) == expected_len


def test_ad_monitoring_pagination_maximum_page_size(
    client: TestClient,
    aircraft_id: int,
    fifty_one_ads,
):
    """Maximum page size is 500; limit alias is accepted."""
    response = client.get(
        f"/api/v1/ad-monitoring/paged?aircraft_fk={aircraft_id}&page=1&limit=500"
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    _assert_paged_envelope(payload, total=51, page=1, pages=1, page_size=500)
    assert len(payload["items"]) == 51


def test_ad_monitoring_pagination_empty_result(
    client: TestClient,
    aircraft_id: int,
    fifty_one_ads,
):
    """No matches: empty items, total 0, pages 0."""
    response = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/paged"
        "?page=1&page_size=50&search=NO-SUCH-AD-RECORD"
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    _assert_paged_envelope(payload, total=0, page=1, pages=0)
    assert payload["items"] == []


def test_ad_monitoring_pagination_out_of_range(
    client: TestClient,
    aircraft_id: int,
    fifty_one_ads,
):
    """Page past the last page returns empty items; oversized page_size is 422."""
    response = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/paged?page=99&page_size=50"
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    _assert_paged_envelope(payload, total=51, page=99, pages=2)
    assert payload["items"] == []

    too_large = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/paged?page=1&page_size=501"
    )
    assert too_large.status_code == 422
    assert "page_size must be one of 50, 100, or 500" in str(too_large.json()["detail"])

    not_allowed = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/paged?page=1&page_size=10"
    )
    assert not_allowed.status_code == 422
    assert "page_size must be one of 50, 100, or 500" in str(not_allowed.json()["detail"])


def test_ad_monitoring_pagination_preserves_search_and_sort(
    client: TestClient,
    aircraft_id: int,
    fifty_one_ads,
):
    """Search, filter, and sort still apply on top of database pagination."""
    search_response = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/paged"
        "?page=1&page_size=50&search=AD-PAGE-0001"
    )
    assert search_response.status_code == 200, search_response.text
    search_payload = search_response.json()
    assert search_payload["total"] == 1
    assert search_payload["pages"] == 1
    assert len(search_payload["items"]) == 1
    assert search_payload["items"][0]["ad_number"] == "AD-PAGE-0001"

    interval_response = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/paged"
        "?page=1&page_size=100&inspection_interval=200%20FH"
    )
    assert interval_response.status_code == 200
    interval_payload = interval_response.json()
    assert interval_payload["total"] == 25
    assert all(
        item["inspection_interval"] == "200 FH"
        for item in interval_payload["items"]
    )

    sort_response = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/paged"
        "?page=1&page_size=50&sort=ad_number"
    )
    assert sort_response.status_code == 200
    numbers = [item["ad_number"] for item in sort_response.json()["items"]]
    assert numbers == sorted(numbers)


def test_work_order_ad_monitoring_pagination_empty_and_out_of_range(
    client: TestClient,
    aircraft_id: int,
    ad_monitoring_payload: dict,
):
    """Work-order paged list: empty items, default size, and out-of-range page."""
    ad_response = client.post("/api/v1/ad-monitoring/", json=ad_monitoring_payload)
    assert ad_response.status_code == 201, ad_response.text
    ad_id = ad_response.json()["id"]

    empty = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/{ad_id}"
        "/work-order-ad-monitoring/paged?page=1"
    )
    assert empty.status_code == 200, empty.text
    empty_payload = empty.json()
    _assert_paged_envelope(empty_payload, total=0, page=1, pages=0)
    assert empty_payload["items"] == []

    for i in range(51):
        created = client.post(
            "/api/v1/work-order-ad-monitoring/",
            json={
                "ad_monitoring_fk": ad_id,
                "work_order_number": f"WO-PAGE-{i:04d}",
                "atl_ref": f"ATL-{i:04d}",
            },
        )
        assert created.status_code == 201, created.text

    default_page = client.get(
        f"/api/v1/work-order-ad-monitoring/paged?ad_monitoring_fk={ad_id}&page=1"
    )
    assert default_page.status_code == 200, default_page.text
    default_payload = default_page.json()
    _assert_paged_envelope(default_payload, total=51, page=1, pages=2)
    assert len(default_payload["items"]) == 50

    past_end = client.get(
        f"/api/v1/work-order-ad-monitoring/paged"
        f"?ad_monitoring_fk={ad_id}&page=10&page_size=50"
    )
    assert past_end.status_code == 200
    past_payload = past_end.json()
    _assert_paged_envelope(past_payload, total=51, page=10, pages=2)
    assert past_payload["items"] == []

    max_page = client.get(
        f"/api/v1/aircraft/{aircraft_id}/ad_monitoring/{ad_id}"
        "/work-order-ad-monitoring/paged?page=1&page_size=500"
    )
    assert max_page.status_code == 200
    max_payload = max_page.json()
    _assert_paged_envelope(max_payload, total=51, page=1, pages=1, page_size=500)
    assert len(max_payload["items"]) == 51
