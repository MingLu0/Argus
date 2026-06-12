from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("ARGUS_REAL_BACKENDS") == "1":
        return
    skip_real_backend = pytest.mark.skip(
        reason="set ARGUS_REAL_BACKENDS=1 to run real backend integration tests"
    )
    for item in items:
        if "real_backend" in item.keywords:
            item.add_marker(skip_real_backend)
