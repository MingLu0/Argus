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
        ("j", "next_conflict", "Next conflict"),
        ("k", "previous_conflict", "Previous conflict"),
        ("enter", "toggle_raw_review", "Raw review"),
        ("a", "accept_recommendation", "Accept"),
        ("c", "choose_option", "Choose option"),
        ("m", "request_more_review", "More review"),
        ("d", "defer", "Defer"),
        ("x", "abort", "Abort"),
        ("h", "toggle_help", "Help"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, *, project_root: Path, run_id: str | None = None) -> None:
        super().__init__()
        self.project_root = project_root
        self.run_id = run_id
        self.selected_conflict_index = 0
        self.show_raw_review = False
        self.show_help = False
        self.abort_confirmation_requested = False

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
        self._cancel_abort_confirmation()
        self.refresh_run()

    def action_accept_recommendation(self) -> None:
        self._cancel_abort_confirmation()
        self._apply_gate_decision(
            DecisionAction.APPROVE,
            "Accepted recommendation from TUI; accepted risk recorded.",
        )

    def action_choose_option(self) -> None:
        self._cancel_abort_confirmation()
        state = self._current_state()
        if state is None:
            return
        selected_conflict = selected_conflict_for(state.conflicts, self.selected_conflict_index)
        if selected_conflict is None:
            return
        choice = default_choice_for_conflict(selected_conflict)
        self._apply_gate_decision(
            DecisionAction.CHOOSE_OPTION,
            "Chose option from TUI; accepted risk recorded.",
            choice=choice,
        )

    def action_request_more_review(self) -> None:
        self._cancel_abort_confirmation()
        self._apply_gate_decision(
            DecisionAction.REQUEST_MORE_REVIEW,
            "Follow-up review requested from TUI.",
        )

    def action_defer(self) -> None:
        self._cancel_abort_confirmation()
        self._apply_gate_decision(DecisionAction.DEFER, "Decision deferred from TUI.")

    def action_abort(self) -> None:
        state = self._current_state()
        if state is None or state.manifest.status != RunStatus.AWAITING_DECISION:
            return
        if not self.abort_confirmation_requested:
            self.abort_confirmation_requested = True
            self.refresh_run()
            return
        self._apply_gate_decision(DecisionAction.ABORT, "Aborted from TUI after confirmation.")

    def action_next_conflict(self) -> None:
        self._cancel_abort_confirmation()
        state = self._current_state()
        if state is None or not state.conflicts:
            return
        self.selected_conflict_index = min(
            self.selected_conflict_index + 1,
            len(state.conflicts) - 1,
        )
        self.refresh_run()

    def action_previous_conflict(self) -> None:
        self._cancel_abort_confirmation()
        if self.selected_conflict_index > 0:
            self.selected_conflict_index -= 1
        self.refresh_run()

    def action_toggle_raw_review(self) -> None:
        self._cancel_abort_confirmation()
        self.show_raw_review = not self.show_raw_review
        self.refresh_run()

    def action_toggle_help(self) -> None:
        self._cancel_abort_confirmation()
        self.show_help = not self.show_help
        self.refresh_run()

    def _cancel_abort_confirmation(self) -> None:
        self.abort_confirmation_requested = False

    def _apply_gate_decision(
        self,
        action: DecisionAction,
        note: str,
        choice: str = "",
    ) -> None:
        if not self.run_id:
            return
        state = self._current_state()
        if state is None:
            return
        if state.manifest.status != RunStatus.AWAITING_DECISION:
            return
        apply_decision(
            project_root=self.project_root,
            run_id=self.run_id,
            action=action,
            note=note,
            choice=choice,
        )
        self.abort_confirmation_requested = False
        self.refresh_run()

    def _current_state(self) -> TuiState | None:
        if not self.run_id:
            return None
        try:
            return load_tui_state(self.project_root, self.run_id)
        except ValueError:
            return None

    def refresh_run(self) -> None:
        try:
            self.run_id = self.run_id or latest_run_id(self.project_root)
            state = load_tui_state(self.project_root, self.run_id)
        except ValueError as exc:
            self.query_one("#overview", Static).update(f"Argus TUI\n\n{exc}")
            return
        self.query_one("#overview", Static).update(format_overview(state))
        self.query_one("#pipeline", Static).update(format_pipeline(state.manifest))
        self.selected_conflict_index = clamp_conflict_index(
            self.selected_conflict_index,
            state.conflicts,
        )
        self.query_one("#conflicts", Static).update(
            format_conflicts(
                state.conflicts,
                selected_index=self.selected_conflict_index,
                show_raw_review=self.show_raw_review,
                run_dir=state.run_dir,
            )
        )
        self.query_one("#log", Static).update(format_log_tail(state.run_dir))
        self.query_one("#actions", Static).update(
            format_action_bar(
                state.manifest,
                abort_confirmation_requested=self.abort_confirmation_requested,
                show_help=self.show_help,
            )
        )


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
        try:
            reconstructed = reconstruct_run(project_root, run_id)
        except ValueError:
            reconstructed = None
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


def format_conflicts(
    conflicts: list[dict[str, Any]],
    *,
    selected_index: int = 0,
    show_raw_review: bool = False,
    run_dir: Path | None = None,
) -> str:
    lines = ["Conflicts And Findings"]
    if not conflicts:
        lines.append("No conflicts recorded.")
        return "\n".join(lines)
    selected_index = clamp_conflict_index(selected_index, conflicts)
    for index, conflict in enumerate(conflicts):
        marker = ">" if index == selected_index else " "
        lines.append(
            f"{marker} {conflict['id']}: {conflict['status']} / {conflict['risk_level']} "
            f"({conflict['affected_decision']})"
        )
        for position in conflict.get("positions", []):
            lines.append(f"  - {position['reviewer_id']}: {position['claim']}")
    if show_raw_review and run_dir is not None:
        lines.extend(["", "Raw Review"])
        lines.extend(raw_review_lines(run_dir, selected_conflict_for(conflicts, selected_index)))
    return "\n".join(lines)


def format_action_bar(
    manifest: RunManifest,
    *,
    abort_confirmation_requested: bool = False,
    show_help: bool = False,
) -> str:
    lines = ["Actions"]
    if manifest.status == RunStatus.AWAITING_DECISION:
        lines.append("[a] accept  [c] choose  [m] more review  [d] defer  [x] abort  [h] help")
        if abort_confirmation_requested:
            lines.append("Press [x] again to confirm abort.")
    else:
        lines.append("[j/k] select  [enter] raw review  [r] refresh  [h] help  [q] quit")
    if show_help:
        lines.extend(
            [
                "",
                "Help",
                "j/k: move conflict selection",
                "enter: toggle raw reviewer output",
                "a: accept recommendation and accepted risk",
                "c: choose the selected conflict's first option",
                "m: request follow-up review",
                "d: defer decision",
                "x: abort, requires confirmation",
            ]
        )
    return "\n".join(lines)


def clamp_conflict_index(index: int, conflicts: list[dict[str, Any]]) -> int:
    if not conflicts:
        return 0
    return max(0, min(index, len(conflicts) - 1))


def selected_conflict_for(
    conflicts: list[dict[str, Any]],
    selected_index: int,
) -> dict[str, Any] | None:
    if not conflicts:
        return None
    return conflicts[clamp_conflict_index(selected_index, conflicts)]


def default_choice_for_conflict(conflict: dict[str, Any] | None) -> str:
    if conflict is None:
        return "selected recommendation"
    positions = conflict.get("positions", [])
    if positions:
        claim = (positions[0].get("claim") or "").strip()
        if claim:
            return claim
    affected_decision = (conflict.get("affected_decision") or "").strip()
    return affected_decision or "selected recommendation"


def raw_review_lines(run_dir: Path, conflict: dict[str, Any] | None) -> list[str]:
    if conflict is None:
        return ["No selected conflict."]
    reviewer_ids = [position.get("reviewer_id", "") for position in conflict.get("positions", [])]
    reviews_dir = run_dir / "reviews"
    resolved_reviews_dir = reviews_dir.resolve(strict=False)
    lines: list[str] = []
    for reviewer_id in reviewer_ids:
        raw_path = reviews_dir / f"{reviewer_id}.raw.md"
        if raw_path.resolve(strict=False).parent != resolved_reviews_dir:
            continue
        if not raw_path.exists() or raw_path.is_symlink():
            continue
        lines.append(f"## {reviewer_id}")
        try:
            raw_review = raw_path.read_text(errors="replace")
        except OSError as exc:
            lines.append(f"Unable to read raw review: {exc}")
            continue
        lines.extend(raw_review.strip().splitlines()[:12] or ["Empty raw review."])
    return lines or ["Raw review not found."]


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
