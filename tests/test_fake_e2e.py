from __future__ import annotations

from pathlib import Path

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
    assert (run_dir / "synthesis.md").exists()
    assert len(list((run_dir / "reviews").glob("*.raw.md"))) == 3
