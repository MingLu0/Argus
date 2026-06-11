from __future__ import annotations

from pathlib import Path

import yaml

from argus.executor.run import run_discussion
from argus.tui import ArgusTuiApp, default_choice_for_conflict, format_action_bar


async def test_tui_choose_option_persists_decision(tmp_path: Path) -> None:
    run_id = await _create_conflicting_run(tmp_path)

    app_instance = ArgusTuiApp(project_root=tmp_path, run_id=run_id)
    async with app_instance.run_test() as pilot:
        await pilot.press("c")
        await pilot.pause()

    run_dir = tmp_path / ".argus" / "runs" / run_id
    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    decision = (run_dir / "decision.md").read_text()
    assert manifest["status"] == "completed"
    assert manifest["decision_action"] == "choose-option"
    assert manifest["decision_choice"]
    assert "accepted risk recorded" in decision


async def test_tui_request_more_review_persists_followup_intent(tmp_path: Path) -> None:
    run_id = await _create_conflicting_run(tmp_path)

    app_instance = ArgusTuiApp(project_root=tmp_path, run_id=run_id)
    async with app_instance.run_test() as pilot:
        await pilot.press("m")
        await pilot.pause()

    run_dir = tmp_path / ".argus" / "runs" / run_id
    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    decision = (run_dir / "decision.md").read_text()
    assert manifest["status"] == "awaiting_decision"
    assert manifest["decision_action"] == "request-more-review"
    assert "Follow-up review requested" in decision


async def test_tui_defer_persists_decision(tmp_path: Path) -> None:
    run_id = await _create_conflicting_run(tmp_path)

    app_instance = ArgusTuiApp(project_root=tmp_path, run_id=run_id)
    async with app_instance.run_test() as pilot:
        await pilot.press("d")
        await pilot.pause()

    manifest = yaml.safe_load((tmp_path / ".argus" / "runs" / run_id / "run.yaml").read_text())
    assert manifest["status"] == "awaiting_decision"
    assert manifest["decision_action"] == "defer"


async def test_tui_accept_recommendation_records_accepted_risk(tmp_path: Path) -> None:
    run_id = await _create_conflicting_run(tmp_path)

    app_instance = ArgusTuiApp(project_root=tmp_path, run_id=run_id)
    async with app_instance.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()

    decision = (tmp_path / ".argus" / "runs" / run_id / "decision.md").read_text()
    assert "accepted risk recorded" in decision


def test_default_choice_uses_first_conflict_position() -> None:
    choice = default_choice_for_conflict(
        {
            "affected_decision": "database",
            "positions": [{"claim": "Use Postgres."}, {"claim": "Use DynamoDB."}],
        }
    )

    assert choice == "Use Postgres."


def test_default_choice_falls_back_when_first_claim_blank() -> None:
    choice = default_choice_for_conflict(
        {
            "affected_decision": "database",
            "positions": [{"claim": "   "}, {"claim": "Use DynamoDB."}],
        }
    )

    assert choice == "database"


def test_default_choice_falls_back_to_default_when_everything_blank() -> None:
    choice = default_choice_for_conflict({"affected_decision": "", "positions": []})

    assert choice == "selected recommendation"


async def test_tui_choose_option_no_conflicts_is_noop(tmp_path: Path) -> None:
    run_id = await _create_conflicting_run(tmp_path)
    run_dir = tmp_path / ".argus" / "runs" / run_id
    (run_dir / "conflicts.json").write_text("[]")

    app_instance = ArgusTuiApp(project_root=tmp_path, run_id=run_id)
    async with app_instance.run_test() as pilot:
        await pilot.press("c")
        await pilot.pause()

    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    assert manifest["status"] == "awaiting_decision"
    assert manifest["decision_action"] is None


async def test_tui_abort_confirmation_reset_by_navigation(tmp_path: Path) -> None:
    run_id = await _create_conflicting_run(tmp_path)

    app_instance = ArgusTuiApp(project_root=tmp_path, run_id=run_id)
    async with app_instance.run_test() as pilot:
        await pilot.press("x")
        await pilot.pause()
        assert app_instance.abort_confirmation_requested is True
        await pilot.press("j")
        await pilot.pause()
        assert app_instance.abort_confirmation_requested is False
        await pilot.press("x")
        await pilot.pause()

    manifest = yaml.safe_load((tmp_path / ".argus" / "runs" / run_id / "run.yaml").read_text())
    assert manifest["status"] == "awaiting_decision"


def test_action_bar_help_overlay_lists_keybindings() -> None:
    rendered = format_action_bar(_awaiting_manifest(), show_help=True)

    assert "j/k: move conflict selection" in rendered
    assert "x: abort, requires confirmation" in rendered


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


def _awaiting_manifest():
    from argus.models import RunManifest, RunStatus, utc_now

    return RunManifest(
        id="run-1",
        title="Run 1",
        mode="tech-stack",
        status=RunStatus.AWAITING_DECISION,
        topic_path="topic.md",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
