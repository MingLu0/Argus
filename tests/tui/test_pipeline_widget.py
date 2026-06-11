from __future__ import annotations

from pathlib import Path

from argus.executor.run import run_discussion
from argus.models import RunManifest, RunStatus, StepRecord, StepStatus, utc_now
from argus.tui import ArgusTuiApp, format_pipeline, load_tui_state


def test_pipeline_shows_completed_and_failed_step_durations() -> None:
    manifest = RunManifest(
        id="run-1",
        title="Run 1",
        mode="debugging",
        status=RunStatus.AWAITING_DECISION,
        topic_path="topic.md",
        created_at=utc_now(),
        updated_at=utc_now(),
        steps=[
            StepRecord(
                id="reviewer-a",
                name="fake reviewer",
                status=StepStatus.COMPLETED,
                duration_ms=42,
            ),
            StepRecord(
                id="reviewer-b",
                name="fake reviewer",
                status=StepStatus.FAILED,
                duration_ms=17,
                error="exit code 1",
            ),
        ],
    )

    rendered = format_pipeline(manifest)

    assert "reviewer-a: completed (42ms)" in rendered
    assert "reviewer-b: failed (17ms) - exit code 1" in rendered


async def test_tui_launches_specific_run(tmp_path: Path) -> None:
    run_id = await _create_conflicting_run(tmp_path)
    state = load_tui_state(tmp_path, run_id)

    assert state.reconstructed is not None
    app_instance = ArgusTuiApp(project_root=tmp_path, run_id=run_id)
    async with app_instance.run_test() as pilot:
        await pilot.pause()
        overview = app_instance.query_one("#overview").render()

    assert run_id in str(overview)


async def _create_conflicting_run(project_root: Path) -> str:
    topic = project_root / "topic.md"
    topic.write_text("# Database choice\n\nShould we use Postgres or DynamoDB?\n")
    manifest = await run_discussion(
        topic_path=topic,
        mode="tech-stack",
        project_root=project_root,
        backend_selection="fake-postgres,fake-dynamodb",
    )
    return manifest.id
