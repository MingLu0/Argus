from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

import yaml
from typer.testing import CliRunner

from argus.cli import app


def test_run_with_fake_backends_creates_artifacts(tmp_path: Path) -> None:
    topic = tmp_path / "topic.md"
    topic.write_text("# Choose auth stack\n\nShould we use Clerk or Auth.js?\n")

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "tech-stack",
            "--backends",
            "fake",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    runs_dir = tmp_path / ".argus" / "runs"
    runs = list(runs_dir.iterdir())
    assert len(runs) == 1
    run_dir = runs[0]
    assert (run_dir / "run.yaml").exists()
    assert (run_dir / "backend-report.md").exists()
    assert (run_dir / "reviewers.json").exists()
    assert (run_dir / "run-summary.md").exists()
    assert (run_dir / "synthesis.md").exists()
    assert (run_dir / "open-questions.md").exists()
    assert (run_dir / "next-actions.md").exists()
    assert "Implementation readiness: ready" in (run_dir / "recommendation.md").read_text()
    assert len(list((run_dir / "reviews").glob("*.raw.md"))) == 3
    parsed_reviews = list((run_dir / "reviews").glob("*.parsed.json"))
    assert len(parsed_reviews) == 3
    findings = json.loads((run_dir / "findings.json").read_text())
    assert len(findings) == 3
    assert findings[0]["id"]
    assert findings[0]["reviewer_id"]


def test_run_with_failed_fake_backend_creates_decision_gate(tmp_path: Path) -> None:
    topic = tmp_path / "topic.md"
    topic.write_text("# Risky decision\n\nShould we migrate databases?\n")

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "tech-stack",
            "--backends",
            "fake-nonzero",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    summary = (run_dir / "run-summary.md").read_text()
    recommendation = (run_dir / "recommendation.md").read_text()
    assert manifest["status"] == "awaiting_decision"
    assert (run_dir / "decision-gate.yaml").exists()
    assert "exit code 17" in summary
    assert "exit code 17" in recommendation


def test_run_with_conflicting_fake_backends_creates_conflict_gate(tmp_path: Path) -> None:
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
    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    conflicts = json.loads((run_dir / "conflicts.json").read_text())
    decision_gate = yaml.safe_load((run_dir / "decision-gate.yaml").read_text())
    assert manifest["status"] == "awaiting_decision"
    assert conflicts[0]["id"] == "conflict-database"
    assert conflicts[0]["status"] == "unresolved"
    assert decision_gate["required"] is True
    assert decision_gate["conflict_ids"] == ["conflict-database"]


def test_run_with_high_risk_fake_backend_creates_decision_gate(tmp_path: Path) -> None:
    topic = tmp_path / "topic.md"
    topic.write_text("# Risky migration\n\nShould we migrate without rollback details?\n")

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "architecture",
            "--backends",
            "fake-high-risk,fake-success",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    decision_gate = yaml.safe_load((run_dir / "decision-gate.yaml").read_text())
    assert manifest["status"] == "awaiting_decision"
    assert decision_gate["required"] is True
    assert decision_gate["risk_level"] == "high"
    assert any("reported high run risk" in reason for reason in decision_gate["reasons"])


def test_run_with_timeout_fake_backend_creates_decision_gate(tmp_path: Path) -> None:
    topic = tmp_path / "topic.md"
    topic.write_text("# Slow decision\n\nShould we wait?\n")

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "debugging",
            "--backends",
            "fake-timeout",
            "--timeout",
            "0.1",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    manifest = yaml.safe_load((run_dir / "run.yaml").read_text())
    assert manifest["status"] == "awaiting_decision"
    assert "timed out" in (run_dir / "run-summary.md").read_text()


def test_run_with_stderr_fake_backend_captures_stderr(tmp_path: Path) -> None:
    topic = tmp_path / "topic.md"
    topic.write_text("# Warning decision\n\nShould stderr be captured?\n")

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "architecture",
            "--backends",
            "fake-stderr,fake-success",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    stderr_logs = list((run_dir / "logs").glob("*.stderr.log"))
    assert stderr_logs
    assert any("fake warning on stderr" in path.read_text() for path in stderr_logs)
    assert len(list((run_dir / "reviews").glob("*.parsed.json"))) == 2


def test_run_with_repeated_delay_fake_backend_runs_in_parallel(tmp_path: Path) -> None:
    topic = tmp_path / "topic.md"
    topic.write_text("# Parallel decision\n\nShould reviewers run in parallel?\n")

    started_at = perf_counter()
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "architecture",
            "--backends",
            "fake-delay,fake-delay,fake-delay",
            "--project-root",
            str(tmp_path),
        ],
    )
    elapsed_seconds = perf_counter() - started_at

    assert result.exit_code == 0, result.output
    assert elapsed_seconds < 1.5
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    assert len(list((run_dir / "reviews").glob("*.raw.md"))) == 3


def test_run_with_unknown_backend_raises_bad_parameter(tmp_path: Path) -> None:
    topic = tmp_path / "topic.md"
    topic.write_text("# Typo\n\nShould a typo fail loudly?\n")

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "tech-stack",
            "--backends",
            "cluade",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "cluade" in result.output


def test_run_with_missing_fake_backend_discloses_skipped_reviewer(tmp_path: Path) -> None:
    topic = tmp_path / "topic.md"
    topic.write_text("# Missing backend\n\nShould missing backends be disclosed?\n")

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "tech-stack",
            "--backends",
            "fake-success,fake-missing",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    summary = (run_dir / "run-summary.md").read_text()
    recommendation = (run_dir / "recommendation.md").read_text()
    assert "fake-missing" in summary
    assert "skipped" in summary
    assert "fake-missing" in recommendation
    assert "skipped" in recommendation


def test_run_with_mixed_fake_and_real_backends(tmp_path: Path, monkeypatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_claude = bin_dir / "claude"
    fake_claude.write_text("#!/usr/bin/env python3\nprint('# mixed claude')\n")
    fake_claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    topic = tmp_path / "topic.md"
    topic.write_text("# Mixed selection\n\nShould fake and real backends coexist?\n")

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "architecture",
            "--backends",
            "fake-success,claude",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    reviewers = (run_dir / "reviewers.json").read_text()
    assert "fake-success" in reviewers
    assert "claude" in reviewers
    assert len(list((run_dir / "reviews").glob("*.raw.md"))) == 2


def test_run_auto_pool_uses_available_cli_named_backends(tmp_path: Path, monkeypatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for binary_name in ["claude", "opencode", "codex"]:
        fake_binary = bin_dir / binary_name
        fake_binary.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('# Fake named backend')\n"
            "print(' '.join(sys.argv[1:]))\n"
        )
        fake_binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    topic = tmp_path / "topic.md"
    topic.write_text("# Named backend pool\n\nShould named backends run?\n")

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "tech-stack",
            "--backends",
            "auto-pool",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    reviewers = (run_dir / "reviewers.json").read_text()
    assert "claude" in reviewers
    assert "opencode" in reviewers
    assert "codex" in reviewers
    assert len(list((run_dir / "reviews").glob("*.raw.md"))) == 3


def test_run_explicit_named_backends_preserves_selection(tmp_path: Path, monkeypatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for binary_name in ["claude", "opencode", "codex"]:
        fake_binary = bin_dir / binary_name
        fake_binary.write_text("#!/usr/bin/env python3\nprint('# explicit backend')\n")
        fake_binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    topic = tmp_path / "topic.md"
    topic.write_text("# Explicit backend list\n\nShould explicit backends run?\n")

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "tech-stack",
            "--backends",
            "opencode,claude",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    reviewers = (run_dir / "reviewers.json").read_text()
    assert "opencode" in reviewers
    assert "claude" in reviewers
    assert "codex" not in reviewers
    assert len(list((run_dir / "reviews").glob("*.raw.md"))) == 2


def test_run_auto_selects_first_available_named_backend(tmp_path: Path, monkeypatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_codex = bin_dir / "codex"
    fake_codex.write_text("#!/usr/bin/env python3\nprint('# auto backend')\n")
    fake_codex.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    topic = tmp_path / "topic.md"
    topic.write_text("# Auto backend\n\nShould auto select codex?\n")

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(topic),
            "--mode",
            "debugging",
            "--backends",
            "auto",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / ".argus" / "runs").iterdir())
    reviewers = (run_dir / "reviewers.json").read_text()
    assert "codex" in reviewers
    assert "claude" not in reviewers
    assert "opencode" not in reviewers
