from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml
from typer.testing import CliRunner

from argus.cli import app
from argus.db import database_path, reconstruct_run


def test_run_can_be_reconstructed_from_db_plus_artifacts(tmp_path: Path) -> None:
    run_id = _create_conflicting_run(tmp_path)

    reconstructed = reconstruct_run(tmp_path, run_id)

    assert reconstructed["run"]["id"] == run_id
    assert reconstructed["run"]["status"] == "awaiting_decision"
    assert reconstructed["reviewers"]
    assert reconstructed["findings"]
    assert reconstructed["conflicts"]
    artifact_paths = {artifact["path"] for artifact in reconstructed["artifacts"]}
    assert "run.yaml" in artifact_paths
    assert "decision-gate.yaml" in artifact_paths


def test_run_reconstruction_orders_events_by_sequence(tmp_path: Path) -> None:
    run_id = _create_conflicting_run(tmp_path)
    with sqlite3.connect(database_path(tmp_path)) as connection:
        connection.execute("DELETE FROM events WHERE run_id = ?", (run_id,))
        connection.execute(
            "INSERT INTO events(run_id, sequence, type, raw_json) VALUES (?, ?, ?, ?)",
            (run_id, 2, "second", '{"type": "second"}'),
        )
        connection.execute(
            "INSERT INTO events(run_id, sequence, type, raw_json) VALUES (?, ?, ?, ?)",
            (run_id, 1, "first", '{"type": "first"}'),
        )

    reconstructed = reconstruct_run(tmp_path, run_id)

    assert [event["sequence"] for event in reconstructed["events"]] == [1, 2]


def test_decision_response_updates_sqlite_decision_state(tmp_path: Path) -> None:
    run_id = _create_conflicting_run(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "respond",
            run_id,
            "--action",
            "approve",
            "--note",
            "Approved after review.",
            "--project-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output

    manifest = yaml.safe_load((tmp_path / ".argus" / "runs" / run_id / "run.yaml").read_text())
    with sqlite3.connect(database_path(tmp_path)) as connection:
        run_status = connection.execute(
            "SELECT status FROM runs WHERE id = ?", (run_id,)
        ).fetchone()[0]
        decision = connection.execute(
            "SELECT action, note FROM decisions WHERE run_id = ?", (run_id,)
        ).fetchone()

    assert manifest["status"] == "completed"
    assert run_status == "completed"
    assert decision == ("approve", "Approved after review.")


def _create_conflicting_run(project_root: Path) -> str:
    topic = project_root / "topic.md"
    topic.write_text("# Database choice\n\nShould we use Postgres or DynamoDB?\n")
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "tech-stack",
            "--backends",
            "fake-postgres,fake-dynamodb",
            "--project-root",
            str(project_root),
        ],
    )
    assert result.exit_code == 0, result.output
    return next((project_root / ".argus" / "runs").iterdir()).name
