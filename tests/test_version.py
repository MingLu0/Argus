from __future__ import annotations

import tomllib
from pathlib import Path

from typer.testing import CliRunner

import argus
from argus.cli import app


def test_version_matches_package_metadata() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    assert argus.__version__ == pyproject["project"]["version"]


def test_version_command_reports_package_version() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == argus.__version__
