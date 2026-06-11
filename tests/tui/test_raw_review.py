from __future__ import annotations

from pathlib import Path

from argus.executor.run import run_discussion
from argus.tui import ArgusTuiApp, format_conflicts, raw_review_lines


def test_raw_review_lines_show_selected_reviewer_output(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reviews_dir = run_dir / "reviews"
    reviews_dir.mkdir(parents=True)
    (reviews_dir / "reviewer-a.raw.md").write_text("raw reviewer output\nsecond line\n")

    lines = raw_review_lines(
        run_dir,
        {"positions": [{"reviewer_id": "reviewer-a"}]},
    )

    assert "## reviewer-a" in lines
    assert "raw reviewer output" in lines


def test_raw_review_lines_ignore_paths_outside_reviews_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reviews_dir = run_dir / "reviews"
    reviews_dir.mkdir(parents=True)
    (run_dir / "outside.raw.md").write_text("outside output\n")

    lines = raw_review_lines(
        run_dir,
        {"positions": [{"reviewer_id": "../outside"}]},
    )

    assert lines == ["Raw review not found."]


def test_raw_review_lines_ignore_symlink_outside_reviews_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reviews_dir = run_dir / "reviews"
    reviews_dir.mkdir(parents=True)
    outside_path = run_dir / "outside.raw.md"
    outside_path.write_text("outside output\n")
    (reviews_dir / "reviewer-a.raw.md").symlink_to(outside_path)

    lines = raw_review_lines(
        run_dir,
        {"positions": [{"reviewer_id": "reviewer-a"}]},
    )

    assert lines == ["Raw review not found."]


def test_raw_review_lines_replaces_invalid_text(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reviews_dir = run_dir / "reviews"
    reviews_dir.mkdir(parents=True)
    (reviews_dir / "reviewer-a.raw.md").write_bytes(b"valid\xfftext\n")

    lines = raw_review_lines(
        run_dir,
        {"positions": [{"reviewer_id": "reviewer-a"}]},
    )

    assert "valid\ufffdtext" in lines


def test_format_conflicts_marks_selected_conflict_and_raw_review(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reviews_dir = run_dir / "reviews"
    reviews_dir.mkdir(parents=True)
    (reviews_dir / "reviewer-b.raw.md").write_text("selected raw output\n")

    rendered = format_conflicts(
        [
            {
                "id": "conflict-a",
                "status": "unresolved",
                "risk_level": "medium",
                "affected_decision": "database",
                "positions": [{"reviewer_id": "reviewer-a", "claim": "Use A."}],
            },
            {
                "id": "conflict-b",
                "status": "unresolved",
                "risk_level": "high",
                "affected_decision": "cache",
                "positions": [{"reviewer_id": "reviewer-b", "claim": "Use B."}],
            },
        ],
        selected_index=1,
        show_raw_review=True,
        run_dir=run_dir,
    )

    assert "> conflict-b" in rendered
    assert "Raw Review" in rendered
    assert "selected raw output" in rendered


async def test_tui_raw_review_toggle_and_conflict_selection(tmp_path: Path) -> None:
    run_id = await _create_conflicting_run(tmp_path)
    app_instance = ArgusTuiApp(project_root=tmp_path, run_id=run_id)

    async with app_instance.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        conflicts_text = str(app_instance.query_one("#conflicts").render())

    assert "Raw Review" in conflicts_text


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
