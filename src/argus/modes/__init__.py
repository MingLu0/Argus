from __future__ import annotations

from argus.models import ReviewerSpec

DEFAULT_MODE_REVIEWERS: dict[str, list[tuple[str, str]]] = {
    "architecture": [
        ("skeptic", "claude"),
        ("maintainer", "opencode"),
        ("alternatives", "codex"),
    ],
    "tech-stack": [
        ("skeptic", "claude"),
        ("repo-fit", "opencode"),
        ("alternatives", "codex"),
    ],
    "debugging": [
        ("root-cause", "claude"),
        ("repo-fit", "opencode"),
        ("test-strategy", "codex"),
    ],
}


def reviewer_specs_for_mode(mode: str, *, fake: bool = False) -> list[ReviewerSpec]:
    if mode not in DEFAULT_MODE_REVIEWERS:
        raise ValueError(f"unknown mode: {mode}")
    specs = []
    for role, backend in DEFAULT_MODE_REVIEWERS[mode]:
        backend_id = "fake" if fake else backend
        specs.append(ReviewerSpec(id=f"{backend_id}-{role}", role=role, backend=backend_id))
    return specs


def supported_modes() -> list[str]:
    return sorted(DEFAULT_MODE_REVIEWERS)
