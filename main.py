import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import bcrypt
import jwt
import csv
import io

# Configure logging
logging.basicConfig(
    filename="app_errors.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# --- CORS Security Setup ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

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
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
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


# --- SQLite helper ---
def get_connection():
    return sqlite3.connect(db_path)


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

    cursor.execute("INSERT OR IGNORE INTO locations (id, name) VALUES (1, 'North Branch')")

    default_hash = get_password_hash(MANAGER_SEED_PASSWORD)
    cursor.execute(
        """
        INSERT OR IGNORE INTO users (location_id, username, password_hash, role)
        VALUES (1, 'manager', ?, 'manager')
        """,
        (default_hash,),
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
        ('SKU-101', 1, 'Tactical Cargo Pants', 12)
        """
    )

    conn.commit()
    conn.close()

init_db()


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


# --- Secure File Upload Endpoint ---
@app.post("/upload-sales")
async def upload_power_bi(
    file: UploadFile = File(...), 
    token_payload: dict = Depends(verify_token)
):
    location_id = token_payload.get("location_id")
    
    contents = await file.read()
    decoded = contents.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))
    
    conn = get_connection()
    cursor = conn.cursor()
    
    for row in reader:
        sku = row.get('SKU')
        date = row.get('WeekDate')
        sold = int(row.get('UnitsSold', 0))
        
        cursor.execute(
            """
            INSERT INTO weekly_sales (sku, location_id, week_date, units_sold) 
            VALUES (?, ?, ?, ?)
            """, 
            (sku, location_id, date, sold)
        )
        
        cursor.execute(
            """
            UPDATE products 
            SET current_stock = current_stock - ? 
            WHERE sku = ? AND location_id = ?
            """, 
            (sold, sku, location_id)
        )
        
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Sales data synced and inventory updated."}