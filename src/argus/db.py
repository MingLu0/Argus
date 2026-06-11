"""SQLite state-store helpers for persisted Argus run artifacts."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml

from argus.models import RunManifest

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    topic_path TEXT NOT NULL,
    run_dir TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS steps (
    run_id TEXT NOT NULL,
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,
    error TEXT,
    artifacts_json TEXT NOT NULL,
    PRIMARY KEY (run_id, id),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS backends (
    run_id TEXT NOT NULL,
    id TEXT NOT NULL,
    binary TEXT NOT NULL,
    available INTEGER NOT NULL,
    path TEXT,
    reason TEXT,
    PRIMARY KEY (run_id, id),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reviewers (
    run_id TEXT NOT NULL,
    id TEXT NOT NULL,
    role TEXT NOT NULL,
    backend TEXT NOT NULL,
    status TEXT NOT NULL,
    exit_code INTEGER,
    timed_out INTEGER NOT NULL,
    duration_ms INTEGER,
    error TEXT,
    command_json TEXT NOT NULL,
    artifacts_json TEXT NOT NULL,
    PRIMARY KEY (run_id, id),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS findings (
    run_id TEXT NOT NULL,
    id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    action TEXT NOT NULL,
    confidence TEXT NOT NULL,
    affected_decision TEXT NOT NULL,
    claim TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (run_id, id),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conflicts (
    run_id TEXT NOT NULL,
    id TEXT NOT NULL,
    affected_decision TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL,
    rationale TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (run_id, id),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decisions (
    run_id TEXT PRIMARY KEY,
    action TEXT,
    note TEXT NOT NULL,
    choice TEXT NOT NULL,
    decided_at TEXT,
    raw_json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS artifacts (
    run_id TEXT NOT NULL,
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    PRIMARY KEY (run_id, path),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    run_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    type TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (run_id, sequence),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);
"""


def database_path(project_root: Path) -> Path:
    """Return the project-local Argus SQLite database path."""
    return project_root / ".argus" / "argus.db"


def initialize_database(project_root: Path) -> Path:
    """Create the SQLite schema and record the current migration version."""
    path = database_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
    return path


def persist_run_artifacts(project_root: Path, run_id: str) -> None:
    """Upsert one run's file artifacts into the SQLite state store."""
    run_dir = project_root / ".argus" / "runs" / run_id
    manifest = RunManifest.model_validate(_read_yaml(run_dir / "run.yaml"))
    database = initialize_database(project_root)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        _delete_run_dependents(connection, run_id)
        _upsert_run(connection, manifest, run_dir)
        _insert_steps(connection, manifest)
        _insert_backends(connection, run_id, _read_json(run_dir / "backend-report.json", []))
        _insert_reviewers(connection, run_id, _read_json(run_dir / "reviewers.json", []))
        _insert_findings(connection, run_id, _read_json(run_dir / "findings.json", []))
        _insert_conflicts(connection, run_id, _read_json(run_dir / "conflicts.json", []))
        _insert_decision(connection, manifest)
        _insert_artifacts(connection, run_id, run_dir)
        _insert_events(connection, run_id, run_dir / "events.jsonl")
        connection.commit()


def reconstruct_run(project_root: Path, run_id: str) -> dict[str, Any]:
    """Return a run and its persisted child records ordered for reconstruction."""
    database = database_path(project_root)
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        run = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if run is None:
            raise ValueError(f"run not found: {run_id}")
        table_ordering = {
            "steps": "id",
            "backends": "id",
            "reviewers": "id",
            "findings": "reviewer_id, id",
            "conflicts": "id",
            "artifacts": "path",
            "events": "sequence",
        }
        reconstructed: dict[str, Any] = {"run": dict(run)}
        for table, order_by in table_ordering.items():
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE run_id = ? ORDER BY {order_by}", (run_id,)
            ).fetchall()
            reconstructed[table] = [dict(row) for row in rows]
        decision = connection.execute(
            "SELECT * FROM decisions WHERE run_id = ?", (run_id,)
        ).fetchone()
        reconstructed["decision"] = dict(decision) if decision else None
        return reconstructed


def _delete_run_dependents(connection: sqlite3.Connection, run_id: str) -> None:
    for table in [
        "steps",
        "backends",
        "reviewers",
        "findings",
        "conflicts",
        "decisions",
        "artifacts",
        "events",
    ]:
        connection.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))


def _upsert_run(connection: sqlite3.Connection, manifest: RunManifest, run_dir: Path) -> None:
    data = manifest.model_dump(mode="json")
    connection.execute(
        """
        INSERT OR REPLACE INTO runs(
            id, title, mode, status, topic_path, run_dir, created_at, updated_at, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            manifest.id,
            manifest.title,
            manifest.mode,
            manifest.status,
            manifest.topic_path,
            str(run_dir),
            data["created_at"],
            data["updated_at"],
            _json(data),
        ),
    )


def _insert_steps(connection: sqlite3.Connection, manifest: RunManifest) -> None:
    for step in manifest.steps:
        data = step.model_dump(mode="json")
        connection.execute(
            """
            INSERT INTO steps(
                run_id, id, name, status, started_at, completed_at, duration_ms, error,
                artifacts_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                manifest.id,
                step.id,
                step.name,
                step.status,
                data.get("started_at"),
                data.get("completed_at"),
                step.duration_ms,
                step.error,
                _json(data["artifacts"]),
            ),
        )


def _insert_backends(connection: sqlite3.Connection, run_id: str, backends: list[dict]) -> None:
    for backend in backends:
        connection.execute(
            """
            INSERT INTO backends(run_id, id, binary, available, path, reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                backend["id"],
                backend["binary"],
                int(backend["available"]),
                backend.get("path"),
                backend.get("reason"),
            ),
        )


def _insert_reviewers(connection: sqlite3.Connection, run_id: str, reviewers: list[dict]) -> None:
    for reviewer in reviewers:
        connection.execute(
            """
            INSERT INTO reviewers(
                run_id, id, role, backend, status, exit_code, timed_out, duration_ms, error,
                command_json, artifacts_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                reviewer["id"],
                reviewer["role"],
                reviewer["backend"],
                reviewer["status"],
                reviewer.get("exit_code"),
                int(reviewer.get("timed_out", False)),
                reviewer.get("duration_ms"),
                reviewer.get("error"),
                _json(reviewer.get("command", [])),
                _json(reviewer.get("artifacts", [])),
            ),
        )


def _insert_findings(connection: sqlite3.Connection, run_id: str, findings: list[dict]) -> None:
    for finding in findings:
        connection.execute(
            """
            INSERT INTO findings(
                run_id, id, reviewer_id, severity, action, confidence, affected_decision,
                claim, evidence_json, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                finding["id"],
                finding["reviewer_id"],
                finding["severity"],
                finding["action"],
                finding["confidence"],
                finding["affected_decision"],
                finding["claim"],
                _json(finding.get("evidence", [])),
                _json(finding),
            ),
        )


def _insert_conflicts(connection: sqlite3.Connection, run_id: str, conflicts: list[dict]) -> None:
    for conflict in conflicts:
        connection.execute(
            """
            INSERT INTO conflicts(
                run_id, id, affected_decision, risk_level, status, rationale, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                conflict["id"],
                conflict["affected_decision"],
                conflict["risk_level"],
                conflict["status"],
                conflict["rationale"],
                _json(conflict),
            ),
        )


def _insert_decision(connection: sqlite3.Connection, manifest: RunManifest) -> None:
    if manifest.decision_action is None:
        return
    data = manifest.model_dump(mode="json")
    connection.execute(
        """
        INSERT INTO decisions(run_id, action, note, choice, decided_at, raw_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            manifest.id,
            manifest.decision_action,
            manifest.decision_note,
            manifest.decision_choice,
            data.get("decided_at"),
            _json(
                {
                    "action": manifest.decision_action,
                    "note": manifest.decision_note,
                    "choice": manifest.decision_choice,
                    "decided_at": data.get("decided_at"),
                }
            ),
        ),
    )


def _insert_artifacts(connection: sqlite3.Connection, run_id: str, run_dir: Path) -> None:
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        relative_path = path.relative_to(run_dir).as_posix()
        connection.execute(
            "INSERT INTO artifacts(run_id, path, kind) VALUES (?, ?, ?)",
            (run_id, relative_path, path.suffix.lstrip(".") or "file"),
        )


def _insert_events(connection: sqlite3.Connection, run_id: str, path: Path) -> None:
    if not path.exists():
        return
    for sequence, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        event = json.loads(line)
        connection.execute(
            "INSERT INTO events(run_id, sequence, type, raw_json) VALUES (?, ?, ?, ?)",
            (run_id, sequence, event.get("type", "unknown"), _json(event)),
        )


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text())


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)
