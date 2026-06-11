from __future__ import annotations

import pytest

from argus.backends.selection import (
    resolve_backend_selection,
    selection_uses_fake_backends,
    selection_uses_real_backends,
)
from argus.models import BackendStatus


def test_auto_selects_first_available_backend() -> None:
    statuses = [
        BackendStatus(id="claude", binary="claude", available=False),
        BackendStatus(id="opencode", binary="opencode", available=True, path="/bin/opencode"),
        BackendStatus(id="codex", binary="codex", available=True, path="/bin/codex"),
    ]

    selected = resolve_backend_selection("auto", statuses)

    assert [backend.id for backend in selected] == ["opencode"]


def test_auto_pool_selects_all_available_backends() -> None:
    statuses = [
        BackendStatus(id="claude", binary="claude", available=True, path="/bin/claude"),
        BackendStatus(id="opencode", binary="opencode", available=False),
        BackendStatus(id="codex", binary="codex", available=True, path="/bin/codex"),
    ]

    selected = resolve_backend_selection("auto-pool", statuses)

    assert [backend.id for backend in selected] == ["claude", "codex"]


def test_explicit_selection_preserves_requested_order() -> None:
    statuses = [
        BackendStatus(id="claude", binary="claude", available=True, path="/bin/claude"),
        BackendStatus(id="opencode", binary="opencode", available=True, path="/bin/opencode"),
        BackendStatus(id="codex", binary="codex", available=True, path="/bin/codex"),
    ]

    selected = resolve_backend_selection("codex,claude", statuses)

    assert [backend.id for backend in selected] == ["codex", "claude"]


def test_fake_selection_expands_to_three_success_reviewers() -> None:
    statuses = [
        BackendStatus(
            id="fake-success",
            binary="fake-agent",
            available=True,
            path="/bin/fake-agent",
        )
    ]

    selected = resolve_backend_selection("fake", statuses)

    assert [backend.id for backend in selected] == ["fake-success"] * 3


def test_explicit_selection_raises_on_unknown_backend_id() -> None:
    statuses = [
        BackendStatus(id="claude", binary="claude", available=True, path="/bin/claude"),
    ]

    with pytest.raises(ValueError, match="cluade"):
        resolve_backend_selection("cluade", statuses)


def test_selection_uses_real_backends_for_mixed_selection() -> None:
    assert selection_uses_fake_backends("fake-success,claude") is True
    assert selection_uses_real_backends("fake-success,claude") is True


def test_selection_uses_real_backends_false_for_pure_fake() -> None:
    assert selection_uses_real_backends("fake") is False
    assert selection_uses_real_backends("fake-success,fake-delay") is False


def test_selection_uses_real_backends_true_for_auto() -> None:
    assert selection_uses_real_backends("auto") is True
    assert selection_uses_real_backends("auto-pool") is True
