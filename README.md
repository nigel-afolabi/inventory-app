# Inventory Management System

This project is a local-first retail inventory application for a real store deployment. It stores data in SQLite, keeps location data isolated, encrypts stored passwords with bcrypt, and supports CSV/XLSX ledger uploads for daily operational reconciliation.

## What is included
- Secure login with manager/admin roles
- Location isolation for Location 1 and Location 2
- Database persistence across logins
- CSV and Excel upload parsing for ledger data
- Daily order reconciliation logic
- Admin visibility across both locations
- Local deployment ready for a real storefront environment

## Default accounts
The app seeds these users at startup:
- `manager` -> Location 1
- `manager2` -> Location 2
- `admin` -> All locations

For production use, set real credentials in a `.env` file before deployment. Do not use the sample values in a live environment.

## Required environment setup
Create a `.env` file using the sample values in `.env.example` and update it with official credentials.

Example:

```bash
SECRET_KEY=replace-with-a-long-random-secret
MANAGER_SEED_PASSWORD=official-location-1-password
MANAGER2_SEED_PASSWORD=official-location-2-password
ADMIN_SEED_PASSWORD=official-admin-password
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

Important:
- `SECRET_KEY` should be a long random value.
- Passwords are stored as bcrypt hashes in SQLite, not plain text.
- The app reads the official values from `.env` when it starts.
- The public demo uses `DEMO_DB_PATH` so upload tests do not affect the live store database.

## Local startup
1. Install dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
2. Create `.env` from `.env.example` and set your live credentials.
3. Start the app:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
4. Open:
   ```text
   http://localhost:8000/
   ```

## Login and access model
- `manager` can only see and manage Location 1 records.
- `manager2` can only see and manage Location 2 records.
- `admin` can view both locations in the main inventory view.
- Guest user can view the demo catalog and upload sample files to a separate demo database without affecting the live store inventory.

## Data isolation rules
The app stores each ledger snapshot and related record with a `location_id`. This prevents overlap between branches and keeps a manager from viewing another branch’s ledger during a later login.

## Upload and reconciliation logic
The upload process:
1. Reads the uploaded CSV or Excel sheet.
2. Anchors on the standard Urban Air row layout.
3. Parses the row values in a fixed order.
4. Saves the ledger to SQLite with the active `location_id`.
5. Reconciles the current upload against the last saved snapshot.
6. Flags shrinkage or surplus risk when the variance crosses threshold values.

The order recommendation uses:

```text
Order Needed = MAX(0, (PAR + Sales Projection) - Current Inv)
```

## Production publishing checklist
Before going live:
1. Create a real `.env` file and set strong secrets/passwords.
2. Confirm the DB file is writable on the deployment host.
3. Run the app with a production-safe host and port.
4. Log in as `manager` and `manager2` separately to validate isolation.
5. Log in as `admin` and validate that both locations appear.
6. Upload a test ledger and confirm the data is saved and visible after logout/login.
7. Confirm that passwords remain hashed in the SQLite database.
8. Back up `inventory.db` regularly.

## Security notes
- Stored passwords are hashed with bcrypt.
- Access is authenticated via a signed JWT token.
- The default sample credentials are only for local demo/dev testing.
- In production, always replace the sample environment values with real passwords.

