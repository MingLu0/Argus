from __future__ import annotations

import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from argus.cli import app
from argus.db import database_path


def test_run_persists_core_tables_to_sqlite(tmp_path: Path) -> None:
    run_id = _run_fake_discussion(tmp_path)

    assert database_path(tmp_path).exists()
    with sqlite3.connect(database_path(tmp_path)) as connection:
        run = connection.execute("SELECT id, status FROM runs WHERE id = ?", (run_id,)).fetchone()
        backend_count = connection.execute("SELECT COUNT(*) FROM backends").fetchone()[0]
        reviewer_count = connection.execute("SELECT COUNT(*) FROM reviewers").fetchone()[0]
        finding_count = connection.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        artifact_count = connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
        event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    assert run == (run_id, "completed")
    assert backend_count >= 1
    assert reviewer_count == 3
    assert finding_count == 3
    assert artifact_count > 0
    assert event_count > 0


def _run_fake_discussion(project_root: Path) -> str:
    topic = project_root / "topic.md"
    topic.write_text("# Choose auth stack\n\nShould we use Clerk or Auth.js?\n")
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "tech-stack",
            "--backends",
            "fake",
            "--project-root",
            str(project_root),
        ],
    )
    assert result.exit_code == 0, result.output
    return next((project_root / ".argus" / "runs").iterdir()).name
