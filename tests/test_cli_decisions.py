from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from argus.cli import app


def test_show_prints_run_summary(tmp_path: Path) -> None:
    run_id = _create_awaiting_run(tmp_path)

    result = CliRunner().invoke(
        app,
        ["show", run_id, "--project-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Run Summary" in result.output
    assert "Decision Gate" in result.output
    assert "Recommendation" in result.output


def test_respond_approve_completes_awaiting_run(tmp_path: Path) -> None:
    run_id = _create_awaiting_run(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "respond",
            run_id,
            "--action",
            "approve",
            "--note",
            "Approved with known tradeoffs.",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = tmp_path / ".argus" / "runs" / run_id
    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    decision = (run_dir / "decision.md").read_text()
    assert manifest["status"] == "completed"
    assert manifest["decision_action"] == "approve"
    assert manifest["decision_note"] == "Approved with known tradeoffs."
    assert manifest["decided_at"]
    assert "Approved with known tradeoffs." in decision


def test_respond_abort_cancels_run(tmp_path: Path) -> None:
    run_id = _create_awaiting_run(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "respond",
            run_id,
            "--action",
            "abort",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = yaml.safe_load((tmp_path / ".argus" / "runs" / run_id / "run.yaml").read_text())
    assert manifest["status"] == "cancelled"
    assert manifest["decision_action"] == "abort"


def test_respond_choose_option_records_choice(tmp_path: Path) -> None:
    run_id = _create_awaiting_run(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "respond",
            run_id,
            "--action",
            "choose-option",
            "--choice",
            "Postgres",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = tmp_path / ".argus" / "runs" / run_id
    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    decision = (run_dir / "decision.md").read_text()
    assert manifest["status"] == "awaiting_decision"
    assert manifest["decision_action"] == "choose-option"
    assert manifest["decision_choice"] == "Postgres"
    assert "Choice: Postgres" in decision


def test_invalid_response_action_fails_without_mutating_run(tmp_path: Path) -> None:
    run_id = _create_awaiting_run(tmp_path)
    run_dir = tmp_path / ".argus" / "runs" / run_id

    result = CliRunner().invoke(
        app,
        [
            "respond",
            run_id,
            "--action",
            "ship-it",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert not (run_dir / "decision.md").exists()
    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    assert "decision_action" not in manifest or manifest["decision_action"] is None


def _create_awaiting_run(project_root: Path) -> str:
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
