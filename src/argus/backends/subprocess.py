from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from argus.models import BackendResult


async def run_backend_command(
    *,
    backend_id: str,
    reviewer_id: str,
    command: list[str],
    cwd: Path,
    timeout_seconds: float,
    input_text: str,
) -> BackendResult:
    started_at = datetime.now(UTC)
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    timed_out = False
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(input_text.encode()), timeout=timeout_seconds
        )
    except TimeoutError:
        timed_out = True
        process.kill()
        stdout_bytes, stderr_bytes = await process.communicate()

    completed_at = datetime.now(UTC)
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    return BackendResult(
        backend_id=backend_id,
        reviewer_id=reviewer_id,
        command=command,
        exit_code=process.returncode,
        stdout=stdout_bytes.decode(errors="replace"),
        stderr=stderr_bytes.decode(errors="replace"),
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        timed_out=timed_out,
    )
