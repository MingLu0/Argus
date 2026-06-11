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


def reviewer_specs_for_backends(mode: str, backend_ids: list[str]) -> list[ReviewerSpec]:
    if mode not in DEFAULT_MODE_REVIEWERS:
        raise ValueError(f"unknown mode: {mode}")
    roles = [role for role, _ in DEFAULT_MODE_REVIEWERS[mode]]
    specs: list[ReviewerSpec] = []
    used_ids: set[str] = set()
    for index, backend_id in enumerate(backend_ids):
        role = roles[index % len(roles)]
        spec_id = f"{backend_id}-{role}"
        if spec_id in used_ids:
            suffix = 2
            while f"{spec_id}-{suffix}" in used_ids:
                suffix += 1
            spec_id = f"{spec_id}-{suffix}"
        used_ids.add(spec_id)
        specs.append(ReviewerSpec(id=spec_id, role=role, backend=backend_id))
    return specs


def supported_modes() -> list[str]:
    return sorted(DEFAULT_MODE_REVIEWERS)
