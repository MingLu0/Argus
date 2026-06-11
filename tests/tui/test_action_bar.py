from __future__ import annotations

from pathlib import Path

import yaml

from argus.executor.run import run_discussion
from argus.models import RunManifest, RunStatus, utc_now
from argus.tui import ArgusTuiApp, format_action_bar, format_log_tail


def test_action_bar_shows_gate_actions_for_awaiting_decision() -> None:
    manifest = RunManifest(
        id="run-1",
        title="Run 1",
        mode="tech-stack",
        status=RunStatus.AWAITING_DECISION,
        topic_path="topic.md",
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    rendered = format_action_bar(manifest)

    assert "[a] approve" in rendered
    assert "[x] abort" in rendered


def test_action_bar_hides_gate_actions_for_completed_run() -> None:
    manifest = RunManifest(
        id="run-1",
        title="Run 1",
        mode="tech-stack",
        status=RunStatus.COMPLETED,
        topic_path="topic.md",
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    rendered = format_action_bar(manifest)

    assert "approve" not in rendered
    assert "abort" not in rendered


def test_log_tail_shows_events(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "events.jsonl").write_text('{"type":"run_started"}\n')

    rendered = format_log_tail(run_dir)

    assert "run_started" in rendered


async def test_tui_can_approve_and_abort_decision_gate(tmp_path: Path) -> None:
    approve_run_id = await _create_conflicting_run(tmp_path)
    approve_app = ArgusTuiApp(project_root=tmp_path, run_id=approve_run_id)
    async with approve_app.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()
    approve_manifest = yaml.safe_load(
        (tmp_path / ".argus" / "runs" / approve_run_id / "run.yaml").read_text()
    )
    assert approve_manifest["status"] == "completed"
    assert approve_manifest["decision_action"] == "approve"

    abort_run_id = await _create_conflicting_run(tmp_path)
    abort_app = ArgusTuiApp(project_root=tmp_path, run_id=abort_run_id)
    async with abort_app.run_test() as pilot:
        await pilot.press("x")
        await pilot.pause()
    abort_manifest = yaml.safe_load(
        (tmp_path / ".argus" / "runs" / abort_run_id / "run.yaml").read_text()
    )
    assert abort_manifest["status"] == "cancelled"
    assert abort_manifest["decision_action"] == "abort"


async def _create_conflicting_run(project_root: Path) -> str:
    topic = project_root / f"topic-{len(list(project_root.glob('topic-*.md')))}.md"
    topic.write_text("# Database choice\n\nShould we use Postgres or DynamoDB?\n")
    manifest = await run_discussion(
        topic_path=topic,
        mode="tech-stack",
        project_root=project_root,
        backend_selection="fake-postgres,fake-dynamodb",
    )
    return manifest.id
