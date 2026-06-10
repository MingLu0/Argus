from __future__ import annotations

import os
from pathlib import Path

from argus.backends.discovery import discover_backends


def test_discover_backend_on_path(tmp_path: Path, monkeypatch) -> None:
    fake_bin = tmp_path / "claude"
    fake_bin.write_text("#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    statuses = discover_backends(backend_binaries={"claude": "claude"})

    assert statuses[0].available is True
    assert statuses[0].path == os.fspath(fake_bin)


def test_discover_missing_backend(monkeypatch) -> None:
    monkeypatch.setenv("PATH", "")

    statuses = discover_backends(backend_binaries={"codex": "codex"})

    assert statuses[0].available is False
    assert "not found" in (statuses[0].reason or "")
