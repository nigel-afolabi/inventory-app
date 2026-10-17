import pytest
from fastapi.testclient import TestClient

from main import app, verify_token

client = TestClient(app)


@pytest.fixture
def manager_override():
    app.dependency_overrides[verify_token] = lambda: {"location_id": 1, "role": "manager", "sub": "manager"}
    yield
    app.dependency_overrides.clear()


def test_upload_sales_rejects_missing_required_columns(manager_override):
    csv_body = "ITEM,UNIT,PAR\nGUTTER GUARD,BOX,48\n"

    response = client.post(
        "/upload-sales",
        files={"file": ("ledger.csv", csv_body, "text/csv")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert "Row 2 is incomplete" in payload["detail"]
    assert "7 columns" in payload["detail"]


def test_upload_sales_accepts_valid_csv_with_all_required_columns(manager_override):
    csv_body = (
        "ITEM,SKU,UNIT,PAR,CURRENT INV,SALES PROJ,ORDER NEEDED\n"
        "GUTTER GUARD,UA-100,BOX,48,26,18,40\n"
        "CHICAGO DEEP DISH,UA-101,PIZZA,30,14,21,37\n"
    )

    response = client.post(
        "/upload-sales",
        files={"file": ("ledger.csv", csv_body, "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["rows_processed"] == 2
    assert payload["items"][0]["item"] == "GUTTER GUARD"
