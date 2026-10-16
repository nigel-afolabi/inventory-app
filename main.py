import os
import json
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3
import bcrypt
import jwt
import csv
import io
import openpyxl

# Configure logging
logging.basicConfig(
    filename="app_errors.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables from .env file
load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- CORS Security Setup ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# --- Security Setup ---
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-key-for-dev")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480
MANAGER_SEED_PASSWORD = os.getenv("MANAGER_SEED_PASSWORD", "sample-manager-password-123")
ADMIN_SEED_PASSWORD = os.getenv("ADMIN_SEED_PASSWORD", "sample-admin-password-123")


# --- Direct bcrypt helper functions ---
def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False


# --- Token Verification (The Bouncer) ---
def verify_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if credentials is None:
        return {
            "sub": "Guest Viewer",
            "location_id": 1,
            "role": "Guest Viewer",
            "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        }

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")


# This looks for an environment variable called 'DB_PATH'.
# If it's not there (like when you run it locally), it defaults to 'inventory.db'.
db_path = os.getenv("DB_PATH", "inventory.db")
DEMO_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "demo_catalog.json")


# --- SQLite helper ---
def get_connection():
    return sqlite3.connect(db_path)


def load_demo_catalog():
    try:
        with open(DEMO_CATALOG_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload.get("albums", [])
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


# --- Database Initialization (Local Workbench) ---
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            FOREIGN KEY(location_id) REFERENCES locations(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT,
            location_id INTEGER,
            name TEXT,
            current_stock INTEGER DEFAULT 0,
            PRIMARY KEY (sku, location_id),
            FOREIGN KEY(location_id) REFERENCES locations(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS weekly_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT,
            location_id INTEGER,
            week_date TEXT,
            units_sold INTEGER,
            FOREIGN KEY(sku, location_id) REFERENCES products(sku, location_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER,
            item TEXT,
            unit TEXT,
            par REAL DEFAULT 0,
            current_inv REAL DEFAULT 0,
            sales_proj REAL DEFAULT 0,
            order_needed REAL DEFAULT 0,
            previous_current_inv REAL DEFAULT 0,
            expected_ending_inv REAL DEFAULT 0,
            actual_discrepancy REAL DEFAULT 0,
            received_shipments REAL DEFAULT 0,
            audit_flag TEXT,
            audit_message TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO locations (id, name) VALUES
        (1, 'North Branch'),
        (2, 'South Branch')
        """
    )

    default_hash = get_password_hash(MANAGER_SEED_PASSWORD)
    cursor.execute(
        """
        INSERT OR IGNORE INTO users (location_id, username, password_hash, role)
        VALUES (1, 'manager', ?, 'manager')
        """,
        (default_hash,),
    )

    secondary_hash = get_password_hash(MANAGER_SEED_PASSWORD)
    cursor.execute(
        """
        INSERT OR IGNORE INTO users (location_id, username, password_hash, role)
        VALUES (2, 'manager2', ?, 'manager')
        """,
        (secondary_hash,),
    )

    admin_hash = get_password_hash(ADMIN_SEED_PASSWORD)
    cursor.execute(
        """
        INSERT OR IGNORE INTO users (username, password_hash, role)
        VALUES ('admin', ?, 'admin')
        """,
        (admin_hash,),
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO products (sku, location_id, name, current_stock)
        VALUES 
        ('SKU-100', 1, 'Heavy Duty Zip Hoodie', 45),
        ('SKU-101', 1, 'Tactical Cargo Pants', 12),
        ('SKU-200', 2, 'Urban Air Socks', 66),
        ('SKU-201', 2, 'Premium Lettuce Pack', 22)
        """
    )

    conn.commit()
    conn.close()

init_db()


def _get_previous_ledger_map(location_id: int | None):
    if location_id is None:
        return {}

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT item, current_inv, sales_proj, unit, par, order_needed, previous_current_inv, expected_ending_inv, actual_discrepancy, audit_flag
        FROM ledger_snapshots
        WHERE location_id = ?
        ORDER BY uploaded_at DESC, id DESC
        """,
        (location_id,),
    )

    latest_by_item = {}
    for row in cursor.fetchall():
        item_name = (row[0] or '').strip()
        if item_name and item_name not in latest_by_item:
            latest_by_item[item_name] = {
                "item": item_name,
                "current_inv": _to_float(row[1]),
                "sales_proj": _to_float(row[2]),
                "unit": str(row[3] or ""),
                "par": _to_float(row[4]),
                "order_needed": _to_float(row[5]),
                "previous_current_inv": _to_float(row[6]),
                "expected_ending_inv": _to_float(row[7]),
                "actual_discrepancy": _to_float(row[8]),
                "audit_flag": row[9],
            }

    conn.close()
    return latest_by_item


def _compute_audit_reconciliation(item_row: dict, previous_row: dict | None):
    previous_current_inv = _to_float(previous_row.get("current_inv") if previous_row else 0.0)
    current_inv = _to_float(item_row.get("current_inv"))
    sales_proj = _to_float(item_row.get("sales_proj"))
    par = _to_float(item_row.get("par"))

    received_shipments = _to_float(item_row.get("received_shipments", 0.0))
    if received_shipments == 0:
        received_shipments = max(0.0, current_inv - previous_current_inv + sales_proj)

    expected_ending_inv = previous_current_inv - sales_proj + received_shipments
    actual_discrepancy = expected_ending_inv - current_inv

    audit_flag = None
    audit_message = None
    if actual_discrepancy < -2.0:
        audit_flag = "SHRINKAGE_ALERT"
        audit_message = "Unlogged stock loss detected; review giveaways, theft, or waste before reorder."
    elif actual_discrepancy > 2.0 and sales_proj <= 2.0:
        audit_flag = "SURPLUS_WASTE_ALERT"
        audit_message = "Inventory remains elevated while sales are stagnant; reduce over-ordering risk."

    base_order = max(0.0, par + sales_proj - current_inv)
    unaccounted_buffer = 0.0
    if audit_flag:
        unaccounted_buffer = min(base_order, max(0.0, abs(actual_discrepancy) * 0.5))
    adjusted_order = max(0.0, base_order - unaccounted_buffer)

    return {
        "previous_current_inv": previous_current_inv,
        "expected_ending_inv": expected_ending_inv,
        "actual_discrepancy": actual_discrepancy,
        "received_shipments": received_shipments,
        "audit_flag": audit_flag,
        "audit_message": audit_message,
        "base_order": base_order,
        "adjusted_order": adjusted_order,
    }


def _persist_ledger_rows(location_id: int | None, ledger_rows: list[dict]):
    if location_id is None:
        return ledger_rows

    previous_state = _get_previous_ledger_map(location_id)
    conn = get_connection()
    cursor = conn.cursor()

    for item_row in ledger_rows:
        previous_row = previous_state.get((item_row.get("item") or "").strip())
        reconciliation = _compute_audit_reconciliation(item_row, previous_row)
        item_row.update({
            "previous_current_inv": reconciliation["previous_current_inv"],
            "expected_ending_inv": reconciliation["expected_ending_inv"],
            "actual_discrepancy": reconciliation["actual_discrepancy"],
            "received_shipments": reconciliation["received_shipments"],
            "audit_flag": reconciliation["audit_flag"],
            "audit_message": reconciliation["audit_message"],
            "base_order": reconciliation["base_order"],
            "adjusted_order": reconciliation["adjusted_order"],
        })

        cursor.execute(
            """
            INSERT INTO ledger_snapshots (
                location_id,
                item,
                unit,
                par,
                current_inv,
                sales_proj,
                order_needed,
                previous_current_inv,
                expected_ending_inv,
                actual_discrepancy,
                received_shipments,
                audit_flag,
                audit_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                location_id,
                (item_row.get("item") or "").strip(),
                item_row.get("unit") or "",
                _to_float(item_row.get("par")),
                _to_float(item_row.get("current_inv")),
                _to_float(item_row.get("sales_proj")),
                _to_float(item_row.get("adjusted_order", item_row.get("order_needed", 0.0))),
                reconciliation["previous_current_inv"],
                reconciliation["expected_ending_inv"],
                reconciliation["actual_discrepancy"],
                reconciliation["received_shipments"],
                reconciliation["audit_flag"],
                reconciliation["audit_message"],
            ),
        )

    conn.commit()
    conn.close()
    return ledger_rows




# --- Data Schemas ---
class LoginRequest(BaseModel):
    username: str
    password: str


# --- Secure Login Endpoint ---
@app.post("/login")
async def login_user(request: LoginRequest):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT password_hash, location_id, role FROM users WHERE username = ?",
        (request.username,),
    )
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    db_password_hash, db_location_id, db_role = user

    if not verify_password(request.password, db_password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_payload = {
        "sub": request.username,
        "location_id": db_location_id,
        "role": db_role,
        "exp": expire,
    }

    access_token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "location_id": db_location_id,
        "role": db_role,
    }


# --- Updated Secure Inventory Endpoint (with Admin override) ---
@app.get("/inventory")
async def get_inventory(token_payload: dict = Depends(verify_token)):
    location_id = token_payload.get("location_id")
    role = token_payload.get("role")

    conn = get_connection()
    cursor = conn.cursor()

    # If Admin, show everything. If Manager, filter by location.
    if role == "admin":
        cursor.execute(
            """
            SELECT p.sku, p.name, p.current_stock, COALESCE(SUM(ws.units_sold), 0) / 4.0, p.location_id
            FROM products p
            LEFT JOIN weekly_sales ws ON p.sku = ws.sku AND p.location_id = ws.location_id
            GROUP BY p.sku, p.location_id
            ORDER BY p.location_id, p.sku
            """
        )
    else:
        cursor.execute(
            """
            SELECT p.sku, p.name, p.location_id, p.current_stock, COALESCE(SUM(ws.units_sold), 0) / 4.0
            FROM products p
            LEFT JOIN weekly_sales ws ON p.sku = ws.sku AND p.location_id = ws.location_id
            WHERE p.location_id = ?
            GROUP BY p.sku, p.location_id
            """,
            (location_id,),
        )

    items = []
    for row in cursor.fetchall():
        sku, name, current_stock, avg_weekly_sales, item_location_id = row
        wos = round(current_stock / avg_weekly_sales, 1) if avg_weekly_sales > 0 else (0.0 if current_stock == 0 else "N/A")

        items.append({
            "sku": sku,
            "name": name,
            "current_stock": current_stock,
            "weeks_of_supply": wos,
            "location_id": item_location_id,
        })

    conn.close()
    return {
        "location": location_id,
        "manager": token_payload.get("sub"),
        "inventory": items,
    }


def _to_float(value):
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).strip().replace(",", "").replace("$", "")
    if cleaned in {"", "-", "--", "N/A", "NA"}:
        return 0.0
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value: {value}") from exc


async def _process_ledger_upload(file: UploadFile, location_id: int | None):
    filename = (file.filename or "").lower()

    if not filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Invalid format. Upload CSV or Excel (.xlsx/.xls).")

    try:
        contents = await file.read()

        def parse_file():
            # Urban Air templates always anchor item-level data at row index 2 (Excel Row 3):
            # row 0 = header row, row 1 = optional title/category text, and row 2 is the first item record.
            # We intentionally skip header/title rows so the item ledger starts at a stable universal position.
            if filename.endswith(".csv"):
                decoded = contents.decode("utf-8-sig")
                rows = list(csv.reader(io.StringIO(decoded)))
                if not rows:
                    raise ValueError("CSV file is empty.")

                parsed_rows = []
                for row_index, row in enumerate(rows[1:], start=2):
                    if not row or all(str(cell).strip() == "" for cell in row):
                        break
                    if len(row) < 7:
                        raise ValueError(f"Row {row_index} is incomplete. Expected at least 7 columns.")

                    # Universal Urban Air schema:
                    # row[0] = Item Name, row[2] = Unit, row[3] = PAR, row[4] = Current Inv,
                    # row[5] = Sales Projection, row[6] = Order Needed (derived formula below).
                    item_name = str(row[0]).strip() if row[0] is not None else ""
                    if not item_name:
                        break

                    par = _to_float(row[3])
                    current_inv = _to_float(row[4])
                    sales_proj = _to_float(row[5])
                    order_needed = max(0.0, par + sales_proj - current_inv)

                    parsed_rows.append({
                        "item": item_name,
                        "unit": str(row[2]).strip() if len(row) > 2 and row[2] is not None else "",
                        "par": par,
                        "current_inv": current_inv,
                        "sales_proj": sales_proj,
                        "order_needed": order_needed,
                    })
                return parsed_rows

            workbook = openpyxl.load_workbook(io.BytesIO(contents), data_only=True, read_only=True)
            sheet = workbook.active
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                raise ValueError("Workbook is empty.")

            parsed_rows = []
            for row_index, row in enumerate(rows[1:], start=2):
                if not row or row[0] is None or str(row[0]).strip() == "":
                    break
                if len(row) < 7:
                    raise ValueError(f"Row {row_index} is incomplete. Expected at least 7 columns.")

                # Standardized template anchor: row index 2 is the first active inventory record.
                item_name = str(row[0]).strip()
                par = _to_float(row[3])
                current_inv = _to_float(row[4])
                sales_proj = _to_float(row[5])
                order_needed = max(0.0, par + sales_proj - current_inv)

                parsed_rows.append({
                    "item": item_name,
                    "unit": str(row[2]).strip() if row[2] is not None else "",
                    "par": par,
                    "current_inv": current_inv,
                    "sales_proj": sales_proj,
                    "order_needed": order_needed,
                })
            return parsed_rows

        ledger_rows = await run_in_threadpool(parse_file)

        if not ledger_rows:
            raise HTTPException(status_code=400, detail="No active inventory rows were found in the uploaded ledger.")

        reconciled_rows = _persist_ledger_rows(location_id, ledger_rows)

        total_previous_inv = sum(_to_float(row.get("previous_current_inv")) for row in reconciled_rows)
        total_current_inv = sum(_to_float(row.get("current_inv")) for row in reconciled_rows)
        total_implied_sales = sum(_to_float(row.get("sales_proj")) for row in reconciled_rows)
        total_variance = sum(_to_float(row.get("actual_discrepancy")) for row in reconciled_rows)

        return {
            "status": "success",
            "rows_processed": len(reconciled_rows),
            "items": reconciled_rows,
            "message": "Ledger processed successfully.",
            "summary": {
                "previous_inv_total": total_previous_inv,
                "current_inv_total": total_current_inv,
                "implied_sales_total": total_implied_sales,
                "variance_total": total_variance,
            }
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ledger parse error: {str(exc)}") from exc


# --- Secure File Upload Endpoint ---
@app.post("/api/upload-ledger")
async def upload_ledger(
    file: UploadFile = File(...),
    token_payload: dict = Depends(verify_token),
):
    if token_payload.get("role") == "Guest Viewer":
        raise HTTPException(status_code=403, detail="Demo Mode: Writing disabled for guest preview.")
    return await _process_ledger_upload(file, token_payload.get("location_id"))


@app.post("/upload-sales")
async def upload_spreadsheet(
    file: UploadFile = File(...),
    token_payload: dict = Depends(verify_token),
):
    if token_payload.get("role") == "Guest Viewer":
        raise HTTPException(status_code=403, detail="Demo Mode: Writing disabled for guest preview.")
    return await _process_ledger_upload(file, token_payload.get("location_id"))


@app.get("/api/demo-catalog")
async def get_demo_catalog():
    return {
        "status": "success",
        "items": load_demo_catalog(),
        "message": "Demo Mode — Previewing Live Catalog & Reviews",
    }


# --- Serve Frontend HTML ---
@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))


@app.get("/demo")
async def serve_demo():
    return FileResponse(os.path.join(os.path.dirname(__file__), "dashboard.html"))


@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse(os.path.join(os.path.dirname(__file__), "dashboard.html"))


@app.get("/dashboard.html")
async def serve_dashboard_html():
    return FileResponse(os.path.join(os.path.dirname(__file__), "dashboard.html"))