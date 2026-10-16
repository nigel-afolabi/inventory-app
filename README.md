# Inventory Management System

A local-first retail inventory platform for Urban Air-style order databases and ledger reconciliation. The application is designed to operate on-site, preserve location-specific state in SQLite, and give staff a clear operational view of inventory variance without requiring public hosting or cloud sync.

## Features
- Secure login with role-based access (Admin/Manager).
- Multi-location persistence via `location_id`-scoped record storage.
- Local FastAPI backend with SQLite persistence.
- CSV and Excel ledger upload processing.
- Urban Air universal template parsing with fixed column semantics.
- Historical ledger reconciliation for shrinkage, waste, and over-order risk detection.
- Industrial dashboard for spreadsheet-style inventory oversight.

## Quick Start
1. Clone the repo.
2. Install requirements: `pip install -r requirements.txt`
3. Create a `.env` file with a local `SECRET_KEY` and optional admin credentials if needed.
4. Run the backend locally: `uvicorn main:app --host 127.0.0.1 --port 8000`
5. Open the browser at `http://127.0.0.1:8000/`

## Client Operations & Ledger Guide

### Multi-Location Persistence
The backend keeps each location isolated by tying all ledger history, item snapshots, and user sessions to a specific `location_id`. In practical terms, data for Location 1 remains separate from Location 2, and the app always queries the latest saved ledger state for the currently logged-in location. This prevents cross-location contamination and ensures that after logout and re-login on a later day, the same inventory ledger state is still available for review and further reconciliation.

The schema is built so that each upload is not global; it is associated with the active location. That means a manager on Location 1 will never see a merged or overwritten ledger from Location 2, and vice versa.

### Spreadsheet Template Convention
The application relies on the standard Urban Air order-database template. Item data extraction begins at row index 2, which corresponds to Excel Row 3. This is the anchor point because row 1 is the template header, and titles or category text can appear above the first actual inventory entry. Parsing starts strictly at that fixed row to keep ledger imports stable across multiple workbooks and multiple locations.

The system remains dynamic for row count: it keeps reading active item rows until it reaches the first empty row. That means any number of inventory items can be uploaded without having to rewrite the parser, while preserving the same strict Urban Air layout.

The fixed schema used for item rows is:
- Column A: Item Name
- Column C: Unit / Packaging
- Column D: PAR
- Column E: Current Inv
- Column F: Sales Projection
- Column G: Order Needed

### Inventory & Sales Reconciliation
The core order formula remains:

`Order Needed = MAX(0, (PAR + Sales Projection) - Current Inv)`

This ensures the system only recommends a reorder when the current inventory fails to meet the target threshold. If current stock is already above the required level, the order quantity is set to zero.

The reconciliation layer compares the previous saved inventory state for the same location against the current upload. If no new shipment was received, the change in inventory over time reflects actual merchandise movement. In other words, a drop in stock without corresponding sales entries can indicate unlogged consumption, free giveaway activity, or product loss. Similarly, if stock remains high while projected movement is weak, that suggests surplus risk or waste risk, especially for perishable products like lettuce.

This is exactly how the system helps management avoid both major operational problems:
- shrinkage caused by unlogged free stock, gifts, or theft
- waste caused by over-ordering perishable inventory that is not actually moving

### Operational Workflow
1. A user logs in to their location-specific profile.
2. The app loads the saved ledger state for that `location_id`.
3. A new Urban Air spreadsheet is uploaded.
4. The parser anchors at row index 2 and reads the active item rows until blank space.
5. The reconciliation engine compares previous vs. current inventory and flags shrinkage or surplus risk.
6. The dashboard displays the recommendation and the alert summary for local operations.

This keeps the process simple, auditable, and persistent across daily logins while still matching the client’s established Urban Air spreadsheet workflow.

