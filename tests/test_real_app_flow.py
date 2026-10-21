import os
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

MANAGER_USERNAME = os.getenv("MANAGER_USERNAME", "manager")
MANAGER2_USERNAME = os.getenv("MANAGER2_USERNAME", "manager2")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin_oversight")
MANAGER_PASSWORD = os.getenv("MANAGER_SEED_PASSWORD", "sample-manager-password-123")
MANAGER2_PASSWORD = os.getenv("MANAGER2_SEED_PASSWORD", "sample-manager-password-123")
ADMIN_PASSWORD = os.getenv("ADMIN_SEED_PASSWORD", "sample-admin-password-123")


def test_login_and_location_scope_are_correct():
    manager_resp = client.post(
        "/login",
        json={"username": MANAGER_USERNAME, "password": MANAGER_PASSWORD},
    )
    assert manager_resp.status_code == 200
    manager_payload = manager_resp.json()
    assert manager_payload["location_id"] == 1
    assert manager_payload["role"] == "manager"

    manager2_resp = client.post(
        "/login",
        json={"username": MANAGER2_USERNAME, "password": MANAGER2_PASSWORD},
    )
    assert manager2_resp.status_code == 200
    manager2_payload = manager2_resp.json()
    assert manager2_payload["location_id"] == 2
    assert manager2_payload["role"] == "manager"

    admin_resp = client.post(
        "/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
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


def test_guest_demo_upload_is_functional_without_touching_live_db():
    csv_body = (
        "ITEM,SKU,UNIT,PAR,CURRENT INV,SALES PROJ,ORDER NEEDED\n"
        "GUEST ITEM,DEMO-100,BOX,10,7,3,6\n"
    )

    response = client.post(
        "/api/upload-ledger",
        files={"file": ("demo.csv", csv_body, "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["rows_processed"] == 1
    assert payload["items"][0]["item"] == "GUEST ITEM"


def test_postgres_compatible_placeholders_and_seed_refresh(monkeypatch):
    import main

    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:pass@db.example.com:5432/app")
    assert main.get_sql_placeholders(2) == "%s, %s"

    monkeypatch.setattr(main, "MANAGER_SEED_PASSWORD", "fresh-manager-pass")
    monkeypatch.setattr(main, "MANAGER2_SEED_PASSWORD", "fresh-manager2-pass")
    monkeypatch.setattr(main, "ADMIN_SEED_PASSWORD", "fresh-admin-pass")

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, location_id INTEGER, username TEXT UNIQUE, password_hash TEXT, role TEXT)"
    )
    conn.execute(
        "INSERT INTO users (location_id, username, password_hash, role) VALUES (1, 'manager', 'old-hash', 'manager')"
    )
    conn.execute(
        "INSERT INTO users (location_id, username, password_hash, role) VALUES (2, 'manager2', 'old-hash-2', 'manager')"
    )
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ('admin_oversight', 'old-admin-hash', 'admin')"
    )

    main.upsert_seed_users(conn, is_pg=False)

    rows = conn.execute(
        "SELECT username, password_hash FROM users ORDER BY username"
    ).fetchall()
    usernames = {row[0] for row in rows}
    assert {"manager", "manager2", "admin_oversight"}.issubset(usernames)
    assert conn.execute("SELECT password_hash FROM users WHERE username = 'manager' ").fetchone()[0] != "old-hash"
    assert conn.execute("SELECT password_hash FROM users WHERE username = 'manager2' ").fetchone()[0] != "old-hash-2"
    assert conn.execute("SELECT password_hash FROM users WHERE username = 'admin_oversight' ").fetchone()[0] != "old-admin-hash"
    conn.close()
