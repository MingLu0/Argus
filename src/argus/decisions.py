from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

import yaml

from argus.artifacts import write_yaml
from argus.models import RunManifest, RunStatus, utc_now


class DecisionAction(StrEnum):
    APPROVE = "approve"
    CHOOSE_OPTION = "choose-option"
    REVISE = "revise"
    REQUEST_MORE_REVIEW = "request-more-review"
    DEFER = "defer"
    ABORT = "abort"


def run_dir_for(project_root: Path, run_id: str) -> Path:
    run_dir = project_root / ".argus" / "runs" / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise ValueError(f"run not found: {run_id}")
    return run_dir


def load_manifest(run_dir: Path) -> RunManifest:
    data = yaml.safe_load((run_dir / "run.yaml").read_text())
    return RunManifest.model_validate(data)


def apply_decision(
    *,
    project_root: Path,
    run_id: str,
    action: DecisionAction,
    note: str = "",
    choice: str = "",
) -> RunManifest:
    run_dir = run_dir_for(project_root, run_id)
    manifest = load_manifest(run_dir)
    decided_at = utc_now()

    manifest.decision_action = action
    manifest.decision_note = note
    manifest.decision_choice = choice
    manifest.decided_at = decided_at
    manifest.updated_at = decided_at
    manifest.status = _status_for_action(action)

    _write_decision_markdown(
        run_dir / "decision.md",
        action=action,
        note=note,
        choice=choice,
        decided_at=decided_at,
    )
    write_yaml(run_dir / "run.yaml", manifest)
    return manifest


def render_run_show(project_root: Path, run_id: str) -> str:
    run_dir = run_dir_for(project_root, run_id)
    manifest = load_manifest(run_dir)
    lines = [
        f"# {manifest.title}",
        "",
        f"- Run: `{manifest.id}`",
        f"- Mode: `{manifest.mode}`",
        f"- Status: {manifest.status}",
    ]
    if manifest.decision_action:
        lines.append(f"- Decision: {manifest.decision_action}")
    _append_artifact_excerpt(lines, run_dir / "run-summary.md", "Run Summary")
    _append_artifact_excerpt(lines, run_dir / "decision-gate.yaml", "Decision Gate")
    _append_artifact_excerpt(lines, run_dir / "recommendation.md", "Recommendation")
    return "\n".join(lines).strip() + "\n"


def _status_for_action(action: DecisionAction) -> RunStatus:
    if action == DecisionAction.APPROVE:
        return RunStatus.COMPLETED
    if action == DecisionAction.ABORT:
        return RunStatus.CANCELLED
    return RunStatus.AWAITING_DECISION


def _write_decision_markdown(
    path: Path,
    *,
    action: DecisionAction,
    note: str,
    choice: str,
    decided_at: datetime,
) -> None:
    lines = [
        "# Decision",
        "",
        f"- Action: {action}",
        f"- Decided at: {decided_at.isoformat()}",
    ]
    if choice:
        lines.append(f"- Choice: {choice}")
    if note:
        lines.extend(["", "## Note", "", note])
    path.write_text("\n".join(lines).strip() + "\n")


def _append_artifact_excerpt(lines: list[str], path: Path, title: str) -> None:
    lines.extend(["", f"## {title}", ""])
    if not path.exists():
        lines.append("Not generated.")
        return
    content = path.read_text().strip()
    lines.append(content if content else "Empty artifact.")
