from __future__ import annotations

from pathlib import Path

import pytest

from argus.backends.discovery import discover_backends
from argus.executor.run import run_discussion
from argus.models import RunStatus


async def run_real_backend_smoke(project_root: Path, backend_id: str) -> None:
    backend = next((status for status in discover_backends() if status.id == backend_id), None)
    if backend is None or not backend.available:
        pytest.skip(f"{backend_id} binary not available")

    topic_path = project_root / "real-backend-topic.md"
    topic_path.write_text(
        "# Argus real backend smoke test\n\n"
        "Review this harmless test topic. Return exactly one low-risk structured JSON review.\n"
    )

    manifest = await run_discussion(
        topic_path=topic_path,
        mode="tech-stack",
        project_root=project_root,
        backend_selection=backend_id,
        timeout_seconds=120,
    )

    run_dir = project_root / ".argus" / "runs" / manifest.id
    assert manifest.status in {RunStatus.COMPLETED, RunStatus.AWAITING_DECISION}
    assert (run_dir / "run.yaml").exists()
    assert (run_dir / "reviewers.json").exists()
    assert (run_dir / "backend-report.json").exists()
    assert (run_dir / "recommendation.md").exists()
    assert list((run_dir / "logs").glob("*.stderr.log"))
