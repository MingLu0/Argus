from __future__ import annotations

import sqlite3
from pathlib import Path

from argus.db import SCHEMA_VERSION, database_path, initialize_database


def test_initialize_database_creates_schema_and_migration_record(tmp_path: Path) -> None:
    db_path = initialize_database(tmp_path)

    assert db_path == database_path(tmp_path)
    assert db_path.exists()
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "runs" in tables
        assert "steps" in tables
        assert "reviewers" in tables
        assert "findings" in tables
        assert "conflicts" in tables
        assert "decisions" in tables
        assert "schema_migrations" in tables
        version = connection.execute("SELECT version FROM schema_migrations").fetchone()[0]
    assert version == SCHEMA_VERSION
