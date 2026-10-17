import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    from main import app
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def pytest_configure():
    db_fd, db_path = tempfile.mkstemp(prefix="inventory_test_", suffix=".db")
    os.close(db_fd)
    os.environ["DB_PATH"] = db_path

    project_root = Path(__file__).resolve().parents[1]
    db_file = Path(db_path)
    if not db_file.exists():
        db_file.touch()

    os.environ["DB_PATH"] = str(project_root / "inventory_test.db")
