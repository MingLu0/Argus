from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from argus.cli import app


def test_recommendation_artifacts_include_readiness_questions_and_actions(
    tmp_path: Path,
) -> None:
    topic = tmp_path / "topic.md"
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
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    recommendation = (run_dir / "recommendation.md").read_text()
    synthesis = (run_dir / "synthesis.md").read_text()
    open_questions = (run_dir / "open-questions.md").read_text()
    next_actions = (run_dir / "next-actions.md").read_text()

    assert "## Executive Recommendation" in recommendation
    assert "Implementation readiness: needs human decision" in recommendation
    assert "## Decision Matrix" in recommendation
    assert "conflict-database" in recommendation
    assert "## Reviewer Summary" in synthesis
    assert "What reporting queries are required?" in open_questions
    assert "Resolve `decision-gate.yaml`" in next_actions


def test_recommendation_snapshot_fixture_exists() -> None:
    fixture = Path("tests/fixtures/recommendations/conflict_recommendation.md")

    assert fixture.exists()
    assert "Implementation readiness: needs human decision" in fixture.read_text()
