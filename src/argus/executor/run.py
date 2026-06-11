from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from argus.artifacts import (
    append_event,
    copy_topic,
    ensure_run_dirs,
    slugify,
    write_json,
    write_yaml,
)
from argus.backends.adapters import adapter_for
from argus.backends.discovery import discover_backends
from argus.backends.selection import (
    fake_backend_statuses,
    resolve_backend_selection,
    selection_uses_fake_backends,
    selection_uses_real_backends,
)
from argus.backends.subprocess import run_backend_command
from argus.config import load_config
from argus.models import ReviewerRecord, RunManifest, RunStatus, StepRecord, StepStatus, utc_now
from argus.modes import reviewer_specs_for_backends
from argus.prompts import render_reviewer_prompt, render_synthesis


async def run_discussion(
    *,
    topic_path: Path,
    mode: str,
    project_root: Path,
    backend_selection: str = "auto",
    timeout_seconds: float = 30,
) -> RunManifest:
    topic = topic_path.read_text()
    title = topic.splitlines()[0].lstrip("# ").strip() or topic_path.stem
    run_id = f"{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{slugify(title)}"
    run_dir = project_root / ".argus" / "runs" / run_id
    ensure_run_dirs(run_dir)
    copy_topic(topic_path, run_dir)

    manifest = RunManifest(
        id=run_id,
        title=title,
        mode=mode,
        status=RunStatus.RUNNING,
        topic_path=str(topic_path),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    write_yaml(run_dir / "run.yaml", manifest)
    append_event(run_dir, {"type": "run_started", "run_id": run_id})

    config = load_config(project_root)
    statuses: list = []
    if selection_uses_fake_backends(backend_selection):
        statuses.extend(fake_backend_statuses(project_root))
    if selection_uses_real_backends(backend_selection):
        statuses.extend(discover_backends(config.backends))
    selected_backends = resolve_backend_selection(backend_selection, statuses)
    write_json(run_dir / "backend-report.json", statuses)
    _write_backend_report_markdown(run_dir / "backend-report.md", statuses)

    reviewer_specs = reviewer_specs_for_backends(
        mode,
        [backend.id for backend in selected_backends],
    )
    manifest.steps = [
        StepRecord(id=spec.id, name=f"{spec.backend} {spec.role}") for spec in reviewer_specs
    ]
    write_yaml(run_dir / "run.yaml", manifest)
    reviewer_records: list[ReviewerRecord] = [
        ReviewerRecord(id=spec.id, role=spec.role, backend=spec.backend) for spec in reviewer_specs
    ]

    review_tasks = []
    for spec, step, reviewer_record in zip(
        reviewer_specs, manifest.steps, reviewer_records, strict=True
    ):
        backend = next((status for status in statuses if status.id == spec.backend), None)
        if backend is None or not backend.available or backend.path is None:
            step.status = StepStatus.SKIPPED
            step.error = f"backend {spec.backend} unavailable"
            reviewer_record.status = StepStatus.SKIPPED
            reviewer_record.error = step.error
            continue
        prompt = render_reviewer_prompt(topic=topic, mode=mode, role=spec.role)
        invocation = adapter_for(spec.backend).build_invocation(path=backend.path, prompt=prompt)
        reviewer_record.command = invocation.command
        review_tasks.append(
            (
                spec.id,
                step,
                reviewer_record,
                run_backend_command(
                    backend_id=spec.backend,
                    reviewer_id=spec.id,
                    command=invocation.command,
                    cwd=project_root,
                    timeout_seconds=timeout_seconds,
                    input_text=invocation.input_text,
                ),
            )
        )
        step.status = StepStatus.RUNNING
        reviewer_record.status = StepStatus.RUNNING
        step.started_at = utc_now()
        append_event(run_dir, {"type": "step_started", "step_id": step.id})

    review_coroutines = (task for _, _, _, task in review_tasks)
    results = await asyncio.gather(*review_coroutines, return_exceptions=True)
    review_outputs: dict[str, str] = {}
    for (reviewer_id, step, reviewer_record, _), result in zip(review_tasks, results, strict=True):
        step.completed_at = utc_now()
        if isinstance(result, Exception):
            step.status = StepStatus.FAILED
            step.error = str(result)
            reviewer_record.status = StepStatus.FAILED
            reviewer_record.error = step.error
            append_event(run_dir, {"type": "step_failed", "step_id": step.id, "error": step.error})
            continue
        step.duration_ms = result.duration_ms
        reviewer_record.duration_ms = result.duration_ms
        reviewer_record.exit_code = result.exit_code
        reviewer_record.timed_out = result.timed_out
        raw_path = run_dir / "reviews" / f"{reviewer_id}.raw.md"
        stdout_path = run_dir / "logs" / f"{reviewer_id}.stdout.log"
        stderr_path = run_dir / "logs" / f"{reviewer_id}.stderr.log"
        raw_path.write_text(result.stdout)
        stdout_path.write_text(result.stdout)
        stderr_path.write_text(result.stderr)
        write_json(run_dir / "artifacts" / f"{reviewer_id}.result.json", result)
        step.artifacts = [str(raw_path.relative_to(run_dir)), str(stdout_path.relative_to(run_dir))]
        reviewer_record.artifacts = [
            str(raw_path.relative_to(run_dir)),
            str(stdout_path.relative_to(run_dir)),
            str(stderr_path.relative_to(run_dir)),
        ]
        if result.timed_out or result.exit_code not in (0, None):
            step.status = StepStatus.FAILED
            step.error = "timed out" if result.timed_out else f"exit code {result.exit_code}"
            reviewer_record.status = StepStatus.FAILED
            reviewer_record.error = step.error
        else:
            step.status = StepStatus.COMPLETED
            reviewer_record.status = StepStatus.COMPLETED
            review_outputs[reviewer_id] = result.stdout
        append_event(run_dir, {"type": "step_completed", "step_id": step.id, "status": step.status})

    write_json(run_dir / "reviewers.json", reviewer_records)

    successful_reviews = len(review_outputs)
    synthesis = render_synthesis(topic, review_outputs)
    (run_dir / "synthesis.md").write_text(synthesis)
    _write_run_summary(run_dir / "run-summary.md", manifest, reviewer_records, successful_reviews)
    _write_recommendation(run_dir / "recommendation.md", synthesis, reviewer_records)
    write_json(run_dir / "findings.json", [])
    write_json(run_dir / "conflicts.json", [])

    if successful_reviews >= config.backend_policy.minimum_successful_reviewers:
        manifest.status = RunStatus.COMPLETED
    else:
        manifest.status = RunStatus.AWAITING_DECISION
        write_yaml(
            run_dir / "decision-gate.yaml",
            {
                "reason": "too few successful reviewers",
                "successful_reviewers": successful_reviews,
                "minimum_successful_reviewers": config.backend_policy.minimum_successful_reviewers,
            },
        )
    manifest.updated_at = utc_now()
    write_yaml(run_dir / "run.yaml", manifest)
    append_event(run_dir, {"type": "run_completed", "run_id": run_id, "status": manifest.status})
    return manifest


def _write_backend_report_markdown(path: Path, statuses: list) -> None:
    lines = ["# Backend Report", ""]
    for status in statuses:
        marker = "available" if status.available else "missing"
        detail = status.path or status.reason or ""
        lines.append(f"- {status.id}: {marker} {detail}".rstrip())
    path.write_text("\n".join(lines) + "\n")


def _write_run_summary(
    path: Path,
    manifest: RunManifest,
    reviewers: list[ReviewerRecord],
    successful_reviews: int,
) -> None:
    lines = [
        "# Run Summary",
        "",
        f"- Run: `{manifest.id}`",
        f"- Mode: `{manifest.mode}`",
        f"- Successful reviewers: {successful_reviews}/{len(reviewers)}",
        "",
        "## Reviewers",
        "",
    ]
    if not reviewers:
        lines.append("- No reviewers selected.")
    for reviewer in reviewers:
        detail = f"- `{reviewer.id}` ({reviewer.backend}, {reviewer.role}): {reviewer.status}"
        if reviewer.error:
            detail += f" - {reviewer.error}"
        if reviewer.duration_ms is not None:
            detail += f" ({reviewer.duration_ms}ms)"
        lines.append(detail)
    path.write_text("\n".join(lines) + "\n")


def _write_recommendation(
    path: Path,
    synthesis: str,
    reviewers: list[ReviewerRecord],
) -> None:
    lines = ["# Recommendation", "", "## Reviewer Status", ""]
    if not reviewers:
        lines.append("- No reviewers selected.")
    for reviewer in reviewers:
        detail = f"- `{reviewer.id}`: {reviewer.status}"
        if reviewer.error:
            detail += f" - {reviewer.error}"
        lines.append(detail)
    lines.extend(["", synthesis.strip(), ""])
    path.write_text("\n".join(lines))
