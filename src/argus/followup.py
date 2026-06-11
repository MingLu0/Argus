from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from argus.artifacts import append_event, write_json, write_yaml
from argus.backends.adapters import adapter_for
from argus.backends.subprocess import run_backend_command
from argus.conflicts import build_decision_gate, group_conflicts
from argus.db import persist_run_artifacts
from argus.findings import ReviewResult, parse_reviewer_output
from argus.models import BackendStatus, ReviewerRecord, RunManifest, RunStatus, StepStatus, utc_now
from argus.synthesis import (
    render_next_actions_markdown,
    render_open_questions_markdown,
    render_recommendation_markdown,
    render_synthesis_markdown,
)

ROUND_ONE_DIR = "round-1"
ROUND_TWO_DIR = "round-2-conflict-review"


async def run_follow_up_review(
    *,
    project_root: Path,
    run_id: str,
    timeout_seconds: float = 30,
) -> RunManifest:
    run_dir = _run_dir_for(project_root, run_id)
    manifest = _load_manifest(run_dir)
    if manifest.status != RunStatus.AWAITING_DECISION:
        raise ValueError("follow-up review requires an awaiting_decision run")

    rounds_dir = run_dir / "rounds"
    round_two_dir = rounds_dir / ROUND_TWO_DIR
    if round_two_dir.exists():
        raise ValueError("follow-up review already exists for this run")

    _snapshot_round_one(run_dir)
    round_two_dir.mkdir(parents=True)
    for child in ["reviews", "logs", "artifacts"]:
        (round_two_dir / child).mkdir()

    topic = (run_dir / "topic.md").read_text()
    original_reviews = _load_reviews(run_dir / "reviews")
    conflicts = _read_json(run_dir / "conflicts.json", [])
    selected_reviewers = _selected_reviewers(conflicts)
    reviewer_records = [
        ReviewerRecord.model_validate(item) for item in _read_json(run_dir / "reviewers.json", [])
    ]
    follow_up_reviewers = [record for record in reviewer_records if record.id in selected_reviewers]

    prompt = render_follow_up_prompt(topic=topic, conflicts=conflicts)
    (round_two_dir / "prompt.md").write_text(prompt)
    append_event(run_dir, {"type": "follow_up_started", "run_id": run_id})

    backend_statuses = [
        BackendStatus.model_validate(item)
        for item in _read_json(run_dir / "backend-report.json", [])
    ]
    backend_by_id = {status.id: status for status in backend_statuses}
    follow_up_records, parsed_reviews, raw_outputs = await _run_follow_up_reviewers(
        project_root=project_root,
        round_dir=round_two_dir,
        prompt=prompt,
        reviewers=follow_up_reviewers,
        backend_by_id=backend_by_id,
        timeout_seconds=timeout_seconds,
    )

    write_json(round_two_dir / "reviewers.json", follow_up_records)
    write_json(round_two_dir / "findings.json", _consolidated_findings(parsed_reviews))
    revised_conflicts = group_conflicts(parsed_reviews) if parsed_reviews else []
    write_json(round_two_dir / "conflicts.json", revised_conflicts)

    active_reviews = parsed_reviews or original_reviews
    active_conflicts = group_conflicts(active_reviews)
    combined_reviews = original_reviews + parsed_reviews
    decision_gate = build_decision_gate(
        reviews=active_reviews,
        conflicts=active_conflicts,
        successful_reviewers=len(
            [record for record in follow_up_records if record.status == StepStatus.COMPLETED]
        ),
        minimum_successful_reviewers=1,
    )
    write_json(run_dir / "findings.json", _consolidated_findings(combined_reviews))
    write_json(run_dir / "conflicts.json", active_conflicts)
    write_yaml(run_dir / "decision-gate.yaml", decision_gate)
    _write_follow_up_summary(
        round_two_dir / "summary.md",
        original_conflicts=conflicts,
        revised_conflicts=revised_conflicts,
        reviewers=follow_up_records,
    )
    _write_combined_synthesis(
        run_dir,
        topic=topic,
        reviews=combined_reviews,
        raw_outputs=raw_outputs,
        conflicts=active_conflicts,
        original_conflicts=conflicts,
        revised_conflicts=revised_conflicts,
    )
    (run_dir / "recommendation.md").write_text(
        render_recommendation_markdown(
            reviewers=reviewer_records + follow_up_records,
            reviews=combined_reviews,
            conflicts=active_conflicts,
            decision_gate=decision_gate,
        )
    )
    (run_dir / "open-questions.md").write_text(
        render_open_questions_markdown(reviews=combined_reviews)
    )
    (run_dir / "next-actions.md").write_text(
        render_next_actions_markdown(
            reviews=combined_reviews,
            conflicts=active_conflicts,
            decision_gate=decision_gate,
        )
    )

    manifest.status = RunStatus.AWAITING_DECISION if decision_gate.required else RunStatus.COMPLETED
    manifest.updated_at = utc_now()
    write_yaml(run_dir / "run.yaml", manifest)
    append_event(
        run_dir,
        {"type": "follow_up_completed", "run_id": run_id, "status": manifest.status},
    )
    persist_run_artifacts(project_root, run_id)
    return manifest


def render_follow_up_prompt(*, topic: str, conflicts: list[dict[str, Any]]) -> str:
    lines = [
        "You are performing a bounded Argus follow-up review.",
        "",
        "Respond to the opposing arguments below. Return the same structured JSON "
        "schema as before.",
        "Do not start another review round; this is the final follow-up pass.",
        "",
        "## Topic",
        "",
        topic.strip(),
        "",
        "## Conflict Context",
        "",
    ]
    if not conflicts:
        lines.append("- No conflicts were recorded.")
    for conflict in conflicts:
        lines.append(
            f"- {conflict.get('id', 'conflict')}: {conflict.get('affected_decision', 'decision')} "
            f"({conflict.get('risk_level', 'unknown')})"
        )
        for position in conflict.get("positions", []):
            lines.append(
                f"  - {position.get('reviewer_id', 'reviewer')}: {position.get('claim', '')}"
            )
    return "\n".join(lines).strip() + "\n"


async def _run_follow_up_reviewers(
    *,
    project_root: Path,
    round_dir: Path,
    prompt: str,
    reviewers: list[ReviewerRecord],
    backend_by_id: dict[str, BackendStatus],
    timeout_seconds: float,
) -> tuple[list[ReviewerRecord], list[ReviewResult], dict[str, str]]:
    follow_up_records: list[ReviewerRecord] = []
    tasks = []
    for reviewer in reviewers:
        follow_up_id = f"follow-up-{reviewer.id}"
        record = ReviewerRecord(id=follow_up_id, role=reviewer.role, backend=reviewer.backend)
        follow_up_records.append(record)
        backend = backend_by_id.get(reviewer.backend)
        if backend is None or not backend.available or backend.path is None:
            record.status = StepStatus.SKIPPED
            record.error = f"backend {reviewer.backend} unavailable"
            continue
        invocation = adapter_for(reviewer.backend).build_invocation(
            path=backend.path, prompt=prompt
        )
        record.command = invocation.command
        record.status = StepStatus.RUNNING
        tasks.append(
            (
                follow_up_id,
                record,
                run_backend_command(
                    backend_id=reviewer.backend,
                    reviewer_id=follow_up_id,
                    command=invocation.command,
                    cwd=project_root,
                    timeout_seconds=timeout_seconds,
                    input_text=invocation.input_text,
                ),
            )
        )

    results = await asyncio.gather(*(task for _, _, task in tasks), return_exceptions=True)
    parsed_reviews: list[ReviewResult] = []
    raw_outputs: dict[str, str] = {}
    for (reviewer_id, record, _), result in zip(tasks, results, strict=True):
        if isinstance(result, Exception):
            record.status = StepStatus.FAILED
            record.error = str(result)
            continue
        record.duration_ms = result.duration_ms
        record.exit_code = result.exit_code
        record.timed_out = result.timed_out
        raw_path = round_dir / "reviews" / f"{reviewer_id}.raw.md"
        parsed_path = round_dir / "reviews" / f"{reviewer_id}.parsed.json"
        stdout_path = round_dir / "logs" / f"{reviewer_id}.stdout.log"
        stderr_path = round_dir / "logs" / f"{reviewer_id}.stderr.log"
        raw_path.write_text(result.stdout)
        stdout_path.write_text(result.stdout)
        stderr_path.write_text(result.stderr)
        write_json(round_dir / "artifacts" / f"{reviewer_id}.result.json", result)
        record.artifacts = [
            str(raw_path.relative_to(round_dir)),
            str(stdout_path.relative_to(round_dir)),
            str(stderr_path.relative_to(round_dir)),
        ]
        if result.timed_out or result.exit_code not in (0, None):
            record.status = StepStatus.FAILED
            record.error = "timed out" if result.timed_out else f"exit code {result.exit_code}"
            continue
        record.status = StepStatus.COMPLETED
        raw_outputs[reviewer_id] = result.stdout
        parsed_review = parse_reviewer_output(result.stdout, reviewer_id)
        parsed_reviews.append(parsed_review)
        write_json(parsed_path, parsed_review)
        record.artifacts.append(str(parsed_path.relative_to(round_dir)))
    return follow_up_records, parsed_reviews, raw_outputs


def _snapshot_round_one(run_dir: Path) -> None:
    round_one_dir = run_dir / "rounds" / ROUND_ONE_DIR
    if round_one_dir.exists():
        return
    round_one_dir.mkdir(parents=True)
    for name in [
        "reviews",
        "logs",
        "artifacts",
        "findings.json",
        "conflicts.json",
        "decision-gate.yaml",
        "synthesis.md",
        "recommendation.md",
    ]:
        source = run_dir / name
        if source.is_dir():
            shutil.copytree(source, round_one_dir / name)
        elif source.exists():
            shutil.copyfile(source, round_one_dir / name)


def _write_combined_synthesis(
    run_dir: Path,
    *,
    topic: str,
    reviews: list[ReviewResult],
    raw_outputs: dict[str, str],
    conflicts: list,
    original_conflicts: list[dict[str, Any]],
    revised_conflicts: list,
) -> None:
    synthesis = render_synthesis_markdown(
        topic=topic,
        reviews=reviews,
        raw_outputs=raw_outputs,
        conflicts=conflicts,
    )
    lines = [synthesis.strip(), "", "## Follow-Up Review", ""]
    lines.append("Original disagreement remains in `rounds/round-1/`.")
    lines.append("Revised positions are recorded in `rounds/round-2-conflict-review/`.")
    lines.extend(["", "### Original Conflicts", ""])
    lines.extend(_conflict_lines(original_conflicts))
    lines.extend(["", "### Revised Conflicts", ""])
    lines.extend(
        _conflict_lines([conflict.model_dump(mode="json") for conflict in revised_conflicts])
    )
    (run_dir / "synthesis.md").write_text("\n".join(lines).strip() + "\n")


def _write_follow_up_summary(
    path: Path,
    *,
    original_conflicts: list[dict[str, Any]],
    revised_conflicts: list,
    reviewers: list[ReviewerRecord],
) -> None:
    lines = ["# Follow-Up Review", "", "## Reviewers", ""]
    lines.extend(
        f"- `{reviewer.id}` ({reviewer.backend}, {reviewer.role}): {reviewer.status}"
        for reviewer in reviewers
    )
    lines.extend(["", "## Original Disagreement", ""])
    lines.extend(_conflict_lines(original_conflicts))
    lines.extend(["", "## Revised Positions", ""])
    lines.extend(
        _conflict_lines([conflict.model_dump(mode="json") for conflict in revised_conflicts])
    )
    path.write_text("\n".join(lines).strip() + "\n")


def _conflict_lines(conflicts: list[dict[str, Any]]) -> list[str]:
    if not conflicts:
        return ["- No conflicts recorded."]
    lines: list[str] = []
    for conflict in conflicts:
        lines.append(
            f"- `{conflict.get('id', 'conflict')}` {conflict.get('status', 'unknown')}: "
            f"{conflict.get('affected_decision', 'decision')}"
        )
        for position in conflict.get("positions", []):
            lines.append(
                f"  - `{position.get('reviewer_id', 'reviewer')}`: {position.get('claim', '')}"
            )
    return lines


def _selected_reviewers(conflicts: list[dict[str, Any]]) -> set[str]:
    reviewer_ids: set[str] = set()
    for conflict in conflicts:
        if conflict.get("status") != "unresolved":
            continue
        for position in conflict.get("positions", []):
            reviewer_id = position.get("reviewer_id")
            if reviewer_id:
                reviewer_ids.add(reviewer_id)
    return reviewer_ids


def _load_reviews(reviews_dir: Path) -> list[ReviewResult]:
    reviews: list[ReviewResult] = []
    for path in sorted(reviews_dir.glob("*.parsed.json")):
        reviews.append(ReviewResult.model_validate(json.loads(path.read_text())))
    return reviews


def _load_manifest(run_dir: Path) -> RunManifest:
    return RunManifest.model_validate(yaml.safe_load((run_dir / "run.yaml").read_text()))


def _run_dir_for(project_root: Path, run_id: str) -> Path:
    runs_dir = project_root / ".argus" / "runs"
    run_dir = runs_dir / run_id
    if run_dir.resolve(strict=False).parent != runs_dir.resolve(strict=False):
        raise ValueError(f"invalid run id: {run_id}")
    if not run_dir.exists() or not run_dir.is_dir():
        raise ValueError(f"run not found: {run_id}")
    return run_dir


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def _consolidated_findings(parsed_reviews: list[ReviewResult]) -> list[dict]:
    findings: list[dict] = []
    for review in parsed_reviews:
        for finding in review.findings:
            encoded = finding.model_dump(mode="json")
            encoded["reviewer_id"] = review.reviewer_id
            findings.append(encoded)
    return findings
