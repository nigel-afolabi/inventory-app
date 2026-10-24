# AGENT_CONTEXT.md — Urban Air Ledger (Local ERP System)

## 1. Executive Summary & Purpose
Urban Air Ledger is a local ERP and inventory management web application for multi-location retail stores. It automates inventory tracking, parses CSV/Excel inventory ledger uploads, calculates weekly sales/weeks of supply, and runs real-time audit reconciliations to flag stock shrinkage and surplus over-ordering.

---

## 2. System Architecture & Tech Stack
* **Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic, JWT (`pyjwt`), Bcrypt.
* **Database:** 
  * **Production:** PostgreSQL on Supabase (`DATABASE_URL`). Connected via `psycopg2-binary`.
  * **Demo Mode:** Local SQLite database (`demo_inventory.db`).
* **Frontend:** Static HTML/CSS/JS (`index.html`, `dashboard.html`, `styles.css`, `app.js`) served by FastAPI via `StaticFiles` and `FileResponse`.
* **Hosting Platform:** Render (Backend API & Frontend host).
* **CORS Settings:** Configured via `CORS_ORIGINS` env var: `https://inventory-app-xbz2.onrender.com,https://urbaninventory.vercel.app,http://localhost:8000`

---

## 3. Environment Variables (Configured on Render)
* `SECRET_KEY`: `8F3mQ7xL1pK9rV2uN6wD4cY0sH5tJ8aP1` (JWT HMAC-SHA256 signature key).
* `SUPABASE_URL`: `https://afofpdnrpwwcjwaqfeai.supabase.co`
* `DATABASE_URL`: `postgresql://postgres:Olatunde12%23@db.afofpdnrpwwcjwaqfeai.supabase.co:5432/postgres`
* `LOCATION_1_NAME`: `Port Saint Lucie`
* `LOCATION_2_NAME`: `Daytona Beach`
* `MANAGER_USERNAME`: `manager`
* `MANAGER2_USERNAME`: `manager2`
* `ADMIN_USERNAME`: `admin_oversight`
* `MANAGER_SEED_PASSWORD`: `7K2sL9mQ4xP8vR1dN6cH3jW0yT5uB8pM2`
* `MANAGER2_SEED_PASSWORD`: `3X9qR2tY6nK7wM1vC4pL8dH5sB2uJ7fQ9`
* `ADMIN_SEED_PASSWORD`: `9A4nL2mQ7xV6pR1sT3cK8wD5uH2yB9jF4`
* `DEMO_DB_PATH`: `demo_inventory.db`
* `CORS_ORIGINS`: `https://inventory-app-xbz2.onrender.com,https://urbaninventory.vercel.app,http://localhost:8000`

---

## 4. Database Schema Specification (PostgreSQL / Supabase)

### `locations`
* `id` (INTEGER, PRIMARY KEY)
* `name` (TEXT)

### `users`
* `id` (SERIAL, PRIMARY KEY)
* `location_id` (INTEGER, FOREIGN KEY -> `locations.id`)
* `username` (TEXT, UNIQUE)
* `password_hash` (TEXT)
* `role` (TEXT) — `manager` or `admin`

### `products`
* `sku` (TEXT)
* `location_id` (INTEGER, FOREIGN KEY -> `locations.id`)
* `name` (TEXT)
* `current_stock` (INTEGER, DEFAULT 0)
* **Primary Key:** `(sku, location_id)`

### `weekly_sales`
* `id` (SERIAL, PRIMARY KEY)
* `sku` (TEXT)
* `location_id` (INTEGER)
* `week_date` (TEXT)
* `units_sold` (INTEGER)

### `ledger_snapshots`
Tracks historical ledger upload states per location for order calculation and reconciliation.
* `id` (SERIAL, PRIMARY KEY)
* `location_id` (INTEGER)
* `item` (TEXT)
* `unit` (TEXT)
* `par` (REAL, DEFAULT 0)
* `current_inv` (REAL, DEFAULT 0)
* `sales_proj` (REAL, DEFAULT 0)
* `order_needed` (REAL, DEFAULT 0)
* `previous_current_inv` (REAL, DEFAULT 0)
* `expected_ending_inv` (REAL, DEFAULT 0)
* `actual_discrepancy` (REAL, DEFAULT 0)
* `received_shipments` (REAL, DEFAULT 0)
* `audit_flag` (TEXT) — `SHRINKAGE_ALERT` or `SURPLUS_WASTE_ALERT`
* `audit_message` (TEXT)
* `uploaded_at` (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)

---

## 5. Active Bug Checklist & Instructions for Codex

### Issue 1: "View Demo" Instantly Redirects Back to Login Page
* **Root Cause in `app.js`:** The top of `initDashboardPage()` checks `if (!token) { window.location.href = '/'; return; }`. Clicking "View Demo" clears the token, so navigating to `/dashboard` immediately triggers this guard before demo rendering code can run.
* **Fix Required:** Remove the top `if (!token) { window.location.href = '/'; return; }` redirect check inside `initDashboardPage()` in `app.js`.

### Issue 2: Manager Login "Invalid Credentials" Sync Issue
* **Root Cause:** If seed user passwords in environment variables were updated after initial database creation, existing rows in Supabase retain old password hashes.
* **Fix Required:** 
  1. Ensure `upsert_seed_users` in `main.py` properly updates existing user password hashes (`ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash`).
  2. If credentials still fail, run `DELETE FROM users WHERE username = 'manager';` in Supabase SQL Editor and redeploy to let `init_db()` re-seed fresh hashes.

### Issue 3: Dependencies Verification
* Verify `requirements.txt` includes:
fastapi uvicorn pydantic pyjwt bcrypt python-dotenv openpyxl psycopg2-binary