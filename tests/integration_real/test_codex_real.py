from __future__ import annotations

from pathlib import Path

import pytest

from .utils import run_real_backend_smoke


@pytest.mark.real_backend
async def test_codex_real_backend_smoke(tmp_path: Path) -> None:
    await run_real_backend_smoke(tmp_path, "codex")
