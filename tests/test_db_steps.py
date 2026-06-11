from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml
from typer.testing import CliRunner

from argus.cli import app
from argus.db import database_path


def test_sqlite_steps_match_manifest_steps(tmp_path: Path) -> None:
    topic = tmp_path / "topic.md"
    topic.write_text("# Parallel decision\n\nShould reviewers run in parallel?\n")
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "architecture",
            "--backends",
            "fake-delay,fake-delay,fake-delay",
            "--project-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    manifest_step_ids = {step["id"] for step in manifest["steps"]}

    with sqlite3.connect(database_path(tmp_path)) as connection:
        db_step_ids = {
            row[0]
            for row in connection.execute(
                "SELECT id FROM steps WHERE run_id = ?", (run_dir.name,)
            ).fetchall()
        }

    assert db_step_ids == manifest_step_ids
