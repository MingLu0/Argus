from __future__ import annotations

from typer.testing import CliRunner

from argus.cli import app


def test_version_command() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_doctor_command(tmp_path) -> None:
    result = CliRunner().invoke(app, ["doctor", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Argus" in result.output
    assert "architecture" in result.output
