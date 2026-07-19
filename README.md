# Inventory Management System

A web-based tool to track stock and sales across multiple locations.

## Features
- Secure login with role-based access (Admin/Manager).
- Automated inventory updates via CSV upload.
- "Weeks of Supply" calculation to monitor stock velocity.
- Multi-location support with isolated data views.

## Quick Start
1. Clone the repo: `git clone [your-repo-link]`
2. Install requirements: `pip install -r requirements.txt`
3. Create a `.env` file with your `SECRET_KEY`.
4. Run the backend: `uvicorn main:app --reload`
