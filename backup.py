import shutil
import datetime
import os

# Ensure backup directory exists
if not os.path.exists("backups"):
    os.makedirs("backups")

# Timestamp for the filename
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
backup_path = f"backups/inventory_backup_{timestamp}.db"

# Copy the database
try:
    shutil.copy2("inventory.db", backup_path)
    print(f"Backup successful: {backup_path}")
except FileNotFoundError:
    print("Error: inventory.db not found. Did you run the app yet?")