from __future__ import annotations

from pathlib import Path

from argus.models import BackendStatus

FAKE_BACKEND_BINARIES: dict[str, str] = {
    "fake-success": "fake-agent",
    "fake-delay": "fake-delay-agent",
    "fake-timeout": "fake-timeout-agent",
    "fake-nonzero": "fake-nonzero-agent",
    "fake-stderr": "fake-stderr-agent",
    "fake-missing": "fake-missing-agent",
}


def resolve_backend_selection(selection: str, statuses: list[BackendStatus]) -> list[BackendStatus]:
    normalized_selection = selection.strip()
    if normalized_selection == "fake":
        fake_success = next(
            (status for status in statuses if status.id == "fake-success" and status.available),
            None,
        )
        return [fake_success, fake_success, fake_success] if fake_success is not None else []

    available = [status for status in statuses if status.available]
    by_id = {status.id: status for status in statuses}

    if normalized_selection == "auto":
        return available[:1]
    if normalized_selection == "auto-pool":
        return available

    requested_ids = [item.strip() for item in normalized_selection.split(",") if item.strip()]
    if not requested_ids:
        return []
    return [by_id[backend_id] for backend_id in requested_ids if backend_id in by_id]


def fake_backend_statuses(_: Path) -> list[BackendStatus]:
    fake_bin_dir = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "fake_bins"
    statuses: list[BackendStatus] = []
    for backend_id, binary in FAKE_BACKEND_BINARIES.items():
        path = fake_bin_dir / binary
        statuses.append(
            BackendStatus(
                id=backend_id,
                binary=binary,
                available=path.exists(),
                path=str(path) if path.exists() else None,
                reason=None if path.exists() else f"{path} not found",
            )
        )
    return statuses


def selection_uses_fake_backends(selection: str) -> bool:
    return any(item.strip().startswith("fake") for item in selection.split(","))
