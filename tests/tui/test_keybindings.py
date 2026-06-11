from __future__ import annotations

from argus.tui import clamp_conflict_index, format_action_bar, selected_conflict_for


def test_conflict_selection_clamps_to_available_conflicts() -> None:
    conflicts = [{"id": "a"}, {"id": "b"}]

    assert clamp_conflict_index(-1, conflicts) == 0
    assert clamp_conflict_index(99, conflicts) == 1


def test_selected_conflict_returns_current_item() -> None:
    conflicts = [{"id": "a"}, {"id": "b"}]

    assert selected_conflict_for(conflicts, 1) == {"id": "b"}


def test_help_overlay_documents_keyboard_navigation() -> None:
    from argus.models import RunManifest, RunStatus, utc_now

    manifest = RunManifest(
        id="run-1",
        title="Run 1",
        mode="tech-stack",
        status=RunStatus.AWAITING_DECISION,
        topic_path="topic.md",
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    rendered = format_action_bar(manifest, show_help=True)

    assert "enter: toggle raw reviewer output" in rendered
    assert "m: request follow-up review" in rendered
