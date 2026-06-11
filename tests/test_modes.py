from __future__ import annotations

from argus.modes import reviewer_specs_for_backends


def test_reviewer_specs_disambiguate_duplicate_backend_role_pairs() -> None:
    specs = reviewer_specs_for_backends("tech-stack", ["claude", "claude", "claude", "claude"])

    ids = [spec.id for spec in specs]
    assert len(set(ids)) == len(ids)
    assert ids[0] == "claude-skeptic"
    assert ids[3] == "claude-skeptic-2"
