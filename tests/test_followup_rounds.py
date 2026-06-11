from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from argus.cli import app
from argus.executor.run import run_discussion
from argus.followup import run_follow_up_review


async def test_follow_up_review_creates_bounded_round_artifacts(tmp_path: Path) -> None:
    run_id = await _create_conflicting_run(tmp_path)

    manifest = await run_follow_up_review(project_root=tmp_path, run_id=run_id)

    run_dir = tmp_path / ".argus" / "runs" / run_id
    round_one_dir = run_dir / "rounds" / "round-1"
    round_two_dir = run_dir / "rounds" / "round-2-conflict-review"
    assert manifest.status == "awaiting_decision"
    assert (round_one_dir / "conflicts.json").exists()
    assert (round_one_dir / "reviews").exists()
    assert (round_two_dir / "prompt.md").exists()
    assert (round_two_dir / "reviewers.json").exists()
    assert (round_two_dir / "findings.json").exists()
    assert (round_two_dir / "conflicts.json").exists()
    assert (round_two_dir / "summary.md").exists()
    assert len(list((round_two_dir / "reviews").glob("*.raw.md"))) == 2


async def test_follow_up_prompt_includes_conflict_context(tmp_path: Path) -> None:
    run_id = await _create_conflicting_run(tmp_path)

    await run_follow_up_review(project_root=tmp_path, run_id=run_id)

    prompt = (
        tmp_path / ".argus" / "runs" / run_id / "rounds" / "round-2-conflict-review" / "prompt.md"
    ).read_text()
    assert "bounded Argus follow-up review" in prompt
    assert "conflict-database" in prompt
    assert "Use Postgres" in prompt
    assert "Use DynamoDB" in prompt


async def test_follow_up_synthesis_discloses_history_and_revised_positions(
    tmp_path: Path,
) -> None:
    run_id = await _create_conflicting_run(tmp_path)

    await run_follow_up_review(project_root=tmp_path, run_id=run_id)

    run_dir = tmp_path / ".argus" / "runs" / run_id
    synthesis = (run_dir / "synthesis.md").read_text()
    summary = (run_dir / "rounds" / "round-2-conflict-review" / "summary.md").read_text()
    assert "Original disagreement remains" in synthesis
    assert "Revised positions are recorded" in synthesis
    assert "Original Disagreement" in summary
    assert "Revised Positions" in summary


async def test_follow_up_review_is_limited_to_one_round(tmp_path: Path) -> None:
    run_id = await _create_conflicting_run(tmp_path)
    await run_follow_up_review(project_root=tmp_path, run_id=run_id)

    with pytest.raises(ValueError, match="already exists"):
        await run_follow_up_review(project_root=tmp_path, run_id=run_id)


def test_cli_request_more_review_runs_follow_up_round(tmp_path: Path) -> None:
    run_id = _create_conflicting_run_with_cli(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "respond",
            run_id,
            "--action",
            "request-more-review",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = tmp_path / ".argus" / "runs" / run_id
    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    follow_up_reviewers = json.loads(
        (run_dir / "rounds" / "round-2-conflict-review" / "reviewers.json").read_text()
    )
    assert manifest["decision_action"] == "request-more-review"
    assert follow_up_reviewers


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


def _create_conflicting_run_with_cli(project_root: Path) -> str:
    topic = project_root / "topic.md"
    topic.write_text("# Database choice\n\nShould we use Postgres or DynamoDB?\n")
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "tech-stack",
            "--backends",
            "fake-postgres,fake-dynamodb",
            "--project-root",
            str(project_root),
        ],
    )
    assert result.exit_code == 0, result.output
    return next((project_root / ".argus" / "runs").iterdir()).name
