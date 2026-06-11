from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from argus.db import database_path, reconstruct_run
from argus.decisions import DecisionAction, apply_decision
from argus.models import RunManifest, RunStatus


class ArgusTuiApp(App[None]):
    CSS = """
    Screen { layout: vertical; }
    #main { height: 1fr; }
    #left { width: 2fr; }
    #right { width: 1fr; }
    Static { border: solid $surface; padding: 1; }
    #log { height: 1fr; }
    """

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("a", "approve", "Approve"),
        ("x", "abort", "Abort"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, *, project_root: Path, run_id: str | None = None) -> None:
        super().__init__()
        self.project_root = project_root
        self.run_id = run_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Static(id="overview")
                yield Static(id="pipeline")
                yield Static(id="log")
            with Vertical(id="right"):
                yield Static(id="conflicts")
                yield Static(id="actions")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_run()

    def action_refresh(self) -> None:
        self.refresh_run()

    def action_approve(self) -> None:
        if self.run_id:
            apply_decision(
                project_root=self.project_root,
                run_id=self.run_id,
                action=DecisionAction.APPROVE,
                note="Approved from TUI.",
            )
            self.refresh_run()

    def action_abort(self) -> None:
        if self.run_id:
            apply_decision(
                project_root=self.project_root,
                run_id=self.run_id,
                action=DecisionAction.ABORT,
                note="Aborted from TUI.",
            )
            self.refresh_run()

    def refresh_run(self) -> None:
        try:
            self.run_id = self.run_id or latest_run_id(self.project_root)
            state = load_tui_state(self.project_root, self.run_id)
        except ValueError as exc:
            self.query_one("#overview", Static).update(f"Argus TUI\n\n{exc}")
            return
        self.query_one("#overview", Static).update(format_overview(state))
        self.query_one("#pipeline", Static).update(format_pipeline(state.manifest))
        self.query_one("#conflicts", Static).update(format_conflicts(state.conflicts))
        self.query_one("#log", Static).update(format_log_tail(state.run_dir))
        self.query_one("#actions", Static).update(format_action_bar(state.manifest))


class TuiState:
    def __init__(
        self,
        *,
        project_root: Path,
        run_id: str,
        run_dir: Path,
        manifest: RunManifest,
        conflicts: list[dict[str, Any]],
        reconstructed: dict[str, Any] | None,
    ) -> None:
        self.project_root = project_root
        self.run_id = run_id
        self.run_dir = run_dir
        self.manifest = manifest
        self.conflicts = conflicts
        self.reconstructed = reconstructed


def latest_run_id(project_root: Path) -> str:
    runs_dir = project_root / ".argus" / "runs"
    if not runs_dir.exists():
        raise ValueError("no runs")
    runs = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    if not runs:
        raise ValueError("no runs")
    return runs[-1].name


def load_tui_state(project_root: Path, run_id: str) -> TuiState:
    run_dir = project_root / ".argus" / "runs" / run_id
    if not run_dir.exists():
        raise ValueError(f"run not found: {run_id}")
    manifest = RunManifest.model_validate(yaml.safe_load((run_dir / "run.yaml").read_text()))
    conflicts = _read_json(run_dir / "conflicts.json", [])
    reconstructed = None
    if database_path(project_root).exists():
        reconstructed = reconstruct_run(project_root, run_id)
    return TuiState(
        project_root=project_root,
        run_id=run_id,
        run_dir=run_dir,
        manifest=manifest,
        conflicts=conflicts,
        reconstructed=reconstructed,
    )


def format_overview(state: TuiState) -> str:
    source = "SQLite + artifacts" if state.reconstructed else "artifacts"
    return "\n".join(
        [
            "Argus Run",
            f"Run: {state.manifest.id}",
            f"Title: {state.manifest.title}",
            f"Mode: {state.manifest.mode}",
            f"Status: {state.manifest.status}",
            f"Source: {source}",
        ]
    )


def format_pipeline(manifest: RunManifest) -> str:
    lines = ["Pipeline"]
    if not manifest.steps:
        lines.append("No reviewer steps recorded.")
        return "\n".join(lines)
    for step in manifest.steps:
        duration = _step_duration_text(step.model_dump(mode="json"))
        detail = f"- {step.id}: {step.status} ({duration})"
        if step.error:
            detail += f" - {step.error}"
        lines.append(detail)
    return "\n".join(lines)


def format_conflicts(conflicts: list[dict[str, Any]]) -> str:
    lines = ["Conflicts And Findings"]
    if not conflicts:
        lines.append("No conflicts recorded.")
        return "\n".join(lines)
    for conflict in conflicts:
        lines.append(
            f"- {conflict['id']}: {conflict['status']} / {conflict['risk_level']} "
            f"({conflict['affected_decision']})"
        )
        for position in conflict.get("positions", []):
            lines.append(f"  - {position['reviewer_id']}: {position['claim']}")
    return "\n".join(lines)


def format_action_bar(manifest: RunManifest) -> str:
    if manifest.status == RunStatus.AWAITING_DECISION:
        return "Actions\n[a] approve  [x] abort  [r] refresh  [q] quit"
    return "Actions\n[r] refresh  [q] quit"


def format_log_tail(run_dir: Path, limit: int = 12) -> str:
    lines = ["Log Tail"]
    log_lines: list[str] = []
    for path in sorted((run_dir / "logs").glob("*.stderr.log")):
        content = path.read_text().strip()
        if content:
            log_lines.extend(f"{path.name}: {line}" for line in content.splitlines())
    events_path = run_dir / "events.jsonl"
    if events_path.exists():
        log_lines.extend(events_path.read_text().splitlines())
    lines.extend(log_lines[-limit:] or ["No logs recorded."])
    return "\n".join(lines)


def _step_duration_text(step: dict[str, Any]) -> str:
    if step.get("duration_ms") is not None:
        return f"{step['duration_ms']}ms"
    started_at = step.get("started_at")
    completed_at = step.get("completed_at")
    if started_at and not completed_at:
        started = datetime.fromisoformat(started_at)
        elapsed = datetime.now(UTC) - started
        return f"{int(elapsed.total_seconds())}s elapsed"
    return "pending"


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text())
