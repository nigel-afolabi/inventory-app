from pathlib import Path

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_login_and_location_scope_are_correct():
    manager_resp = client.post(
        "/login",
        json={"username": "manager", "password": "sample-manager-password-123"},
    )
    assert manager_resp.status_code == 200
    manager_payload = manager_resp.json()
    assert manager_payload["location_id"] == 1
    assert manager_payload["role"] == "manager"

    manager2_resp = client.post(
        "/login",
        json={"username": "manager2", "password": "sample-manager-password-123"},
    )
    assert manager2_resp.status_code == 200
    manager2_payload = manager2_resp.json()
    assert manager2_payload["location_id"] == 2
    assert manager2_payload["role"] == "manager"

    admin_resp = client.post(
        "/login",
        json={"username": "admin", "password": "sample-admin-password-123"},
    )
    assert admin_resp.status_code == 200
    admin_payload = admin_resp.json()
    assert admin_payload["role"] == "admin"

    manager_inventory = client.get(
        "/inventory",
        headers={"Authorization": f"Bearer {manager_payload['access_token']}"},
    )
    assert manager_inventory.status_code == 200
    assert {item["location_id"] for item in manager_inventory.json()["inventory"]} == {1}

    manager2_inventory = client.get(
        "/inventory",
        headers={"Authorization": f"Bearer {manager2_payload['access_token']}"},
    )
    assert manager2_inventory.status_code == 200
    assert {item["location_id"] for item in manager2_inventory.json()["inventory"]} == {2}

    admin_inventory = client.get(
        "/inventory",
        headers={"Authorization": f"Bearer {admin_payload['access_token']}"},
    )
    assert admin_inventory.status_code == 200
    admin_locations = {item["location_id"] for item in admin_inventory.json()["inventory"]}
    assert admin_locations == {1, 2}


def test_dashboard_uses_live_inventory_api_for_logged_in_users():
    app_js = Path("static/app.js").read_text(encoding="utf-8")
    assert "fetch('/inventory'" in app_js
    assert "renderLedgerRows([" not in app_js
