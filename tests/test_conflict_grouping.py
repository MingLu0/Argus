from __future__ import annotations

from argus.conflicts import ConflictStatus, group_conflicts
from argus.findings.schema import Finding, FindingAction, ReviewResult, RiskLevel, Severity


def test_group_conflicts_detects_distinct_positions_for_same_decision() -> None:
    reviews = [
        ReviewResult(
            reviewer_id="claude-skeptic",
            risk_level=RiskLevel.MEDIUM,
            findings=[
                Finding(
                    id="a",
                    severity=Severity.WARNING,
                    action=FindingAction.ASK_USER,
                    claim="Use Postgres for reporting.",
                    affected_decision="Database",
                )
            ],
        ),
        ReviewResult(
            reviewer_id="codex-alternatives",
            risk_level=RiskLevel.MEDIUM,
            findings=[
                Finding(
                    id="b",
                    severity=Severity.WARNING,
                    action=FindingAction.ASK_USER,
                    claim="Use DynamoDB for scale.",
                    affected_decision="database",
                )
            ],
        ),
    ]

    conflicts = group_conflicts(reviews)

    assert len(conflicts) == 1
    assert conflicts[0].id == "conflict-database"
    assert conflicts[0].status == ConflictStatus.UNRESOLVED
    assert conflicts[0].risk_level == RiskLevel.MEDIUM
    assert len(conflicts[0].positions) == 2


def test_group_conflicts_marks_single_reviewer_findings_non_conflicting() -> None:
    reviews = [
        ReviewResult(
            reviewer_id="claude-skeptic",
            findings=[
                Finding(
                    id="a",
                    severity=Severity.INFO,
                    action=FindingAction.RECOMMEND,
                    claim="Document rollback.",
                    affected_decision="operations",
                )
            ],
        )
    ]

    conflicts = group_conflicts(reviews)

    assert conflicts[0].status == ConflictStatus.NON_CONFLICTING
    assert conflicts[0].risk_level == RiskLevel.LOW


def test_group_conflicts_marks_blocking_finding_high_risk() -> None:
    reviews = [
        ReviewResult(
            reviewer_id="security",
            findings=[
                Finding(
                    id="security-1",
                    severity=Severity.ERROR,
                    action=FindingAction.BLOCK,
                    claim="Do not ship without an authz model.",
                    affected_decision="authorization",
                )
            ],
        )
    ]

    conflicts = group_conflicts(reviews)

    assert conflicts[0].risk_level == RiskLevel.HIGH
