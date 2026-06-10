from __future__ import annotations

import shutil
from collections.abc import Mapping

from argus.config import BackendConfig
from argus.models import BackendStatus

DEFAULT_BACKENDS: dict[str, str] = {
    "claude": "claude",
    "opencode": "opencode",
    "codex": "codex",
}


def discover_backends(
    configured_backends: Mapping[str, BackendConfig] | None = None,
    backend_binaries: Mapping[str, str] | None = None,
) -> list[BackendStatus]:
    binaries = dict(backend_binaries or DEFAULT_BACKENDS)
    configured_backends = configured_backends or {}
    statuses: list[BackendStatus] = []

    for backend_id, binary_name in binaries.items():
        configured_path = configured_backends.get(backend_id, BackendConfig()).path
        candidate = configured_path or binary_name
        resolved_path = shutil.which(candidate)
        if resolved_path:
            statuses.append(
                BackendStatus(
                    id=backend_id,
                    binary=binary_name,
                    available=True,
                    path=resolved_path,
                )
            )
            continue
        statuses.append(
            BackendStatus(
                id=backend_id,
                binary=binary_name,
                available=False,
                reason=f"{candidate} not found on PATH",
            )
        )
    return statuses


def available_backend_ids(statuses: list[BackendStatus]) -> list[str]:
    return [status.id for status in statuses if status.available]
