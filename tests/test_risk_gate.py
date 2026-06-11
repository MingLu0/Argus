from __future__ import annotations

from argus.conflicts import ConflictStatus, build_decision_gate
from argus.conflicts.schema import Conflict
from argus.findings.schema import Finding, FindingAction, ReviewResult, RiskLevel, Severity


def test_decision_gate_required_for_too_few_successful_reviewers() -> None:
    gate = build_decision_gate(
        reviews=[],
        conflicts=[],
        successful_reviewers=1,
        minimum_successful_reviewers=2,
    )

    assert gate.required is True
    assert gate.risk_level == RiskLevel.HIGH
    assert "too few successful reviewers" in gate.reasons


def test_decision_gate_required_for_ask_user_finding() -> None:
    review = ReviewResult(
        reviewer_id="claude",
        findings=[
            Finding(
                id="finding-1",
                severity=Severity.WARNING,
                action=FindingAction.ASK_USER,
                claim="Choose database intentionally.",
            )
        ],
    )

    gate = build_decision_gate(
        reviews=[review],
        conflicts=[],
        successful_reviewers=2,
        minimum_successful_reviewers=2,
    )

    assert gate.required is True
    assert gate.risk_level == RiskLevel.MEDIUM
    assert gate.finding_ids == ["finding-1"]


def test_decision_gate_required_for_unresolved_conflict() -> None:
    conflict = Conflict(
        id="conflict-database",
        affected_decision="database",
        risk_level=RiskLevel.MEDIUM,
        status=ConflictStatus.UNRESOLVED,
        rationale="distinct positions",
        positions=[],
    )

    gate = build_decision_gate(
        reviews=[],
        conflicts=[conflict],
        successful_reviewers=2,
        minimum_successful_reviewers=2,
    )

    assert gate.required is True
    assert gate.conflict_ids == ["conflict-database"]


def test_decision_gate_not_required_for_low_risk_clean_reviews() -> None:
    review = ReviewResult(reviewer_id="claude", risk_level=RiskLevel.LOW)

    gate = build_decision_gate(
        reviews=[review],
        conflicts=[],
        successful_reviewers=2,
        minimum_successful_reviewers=2,
    )

    assert gate.required is False
    assert gate.reasons == []
