from __future__ import annotations

from argus.tui import format_conflicts


def test_conflict_widget_shows_conflict_and_positions() -> None:
    rendered = format_conflicts(
        [
            {
                "id": "conflict-database",
                "status": "unresolved",
                "risk_level": "medium",
                "affected_decision": "database",
                "positions": [
                    {"reviewer_id": "postgres-reviewer", "claim": "Use Postgres."},
                    {"reviewer_id": "dynamodb-reviewer", "claim": "Use DynamoDB."},
                ],
            }
        ]
    )

    assert "conflict-database: unresolved / medium (database)" in rendered
    assert "postgres-reviewer: Use Postgres." in rendered
    assert "dynamodb-reviewer: Use DynamoDB." in rendered


def test_conflict_widget_handles_empty_conflicts() -> None:
    rendered = format_conflicts([])

    assert "No conflicts recorded." in rendered
