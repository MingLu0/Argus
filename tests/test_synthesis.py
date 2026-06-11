from __future__ import annotations

from argus.conflicts.schema import Conflict, ConflictStatus, DecisionGate
from argus.findings.schema import Finding, FindingAction, ReviewResult, RiskLevel, Severity
from argus.models import ReviewerRecord, StepStatus
from argus.prompts import render_synthesis_prompt
from argus.synthesis import (
    render_next_actions_markdown,
    render_open_questions_markdown,
    render_recommendation_markdown,
    render_synthesis_markdown,
)


def test_synthesis_includes_summary_agreement_disagreement_and_risk() -> None:
    reviews = [
        ReviewResult(
            reviewer_id="fake-postgres-skeptic",
            risk_level=RiskLevel.MEDIUM,
            risk_rationale="Database choice affects reporting.",
            findings=[
                Finding(
                    id="a",
                    severity=Severity.WARNING,
                    action=FindingAction.ASK_USER,
                    claim="Use Postgres for reporting requirements.",
                    affected_decision="database",
                )
            ],
        ),
        ReviewResult(
            reviewer_id="fake-dynamodb-alternatives",
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
    conflicts = [
        Conflict(
            id="conflict-database",
            affected_decision="database",
            risk_level=RiskLevel.MEDIUM,
            status=ConflictStatus.UNRESOLVED,
            rationale="distinct positions",
            positions=[],
        )
    ]

    synthesis = render_synthesis_markdown(
        topic="# Database choice",
        reviews=reviews,
        raw_outputs={"fake-postgres-skeptic": "raw output"},
        conflicts=conflicts,
    )

    assert "## Reviewer Summary" in synthesis
    assert "## Areas Of Agreement" in synthesis
    assert "## Areas Of Disagreement" in synthesis
    assert "conflict-database" not in synthesis
    assert "Use Postgres" in synthesis
    assert "Database choice affects reporting" in synthesis


def test_recommendation_includes_readiness_matrix_conflicts_and_status() -> None:
    review = ReviewResult(
        reviewer_id="fake-high-risk-skeptic",
        risk_level=RiskLevel.HIGH,
        risk_rationale="No rollback plan.",
    )
    gate = DecisionGate(
        required=True,
        reasons=["fake-high-risk-skeptic reported high run risk"],
        risk_level=RiskLevel.HIGH,
        successful_reviewers=1,
        minimum_successful_reviewers=1,
    )

    recommendation = render_recommendation_markdown(
        reviewers=[
            ReviewerRecord(
                id="fake-nonzero-skeptic",
                role="skeptic",
                backend="fake-nonzero",
                status=StepStatus.FAILED,
                error="exit code 17",
            )
        ],
        reviews=[review],
        conflicts=[],
        decision_gate=gate,
    )

    assert "Implementation readiness: blocked" in recommendation
    assert "## Decision Matrix" in recommendation
    assert "reported high run risk" in recommendation
    assert "exit code 17" in recommendation


def test_open_questions_and_next_actions_are_extracted() -> None:
    review = ReviewResult(
        reviewer_id="fake-postgres-skeptic",
        open_questions=["What reporting queries are required?"],
        findings=[
            Finding(
                id="a",
                severity=Severity.WARNING,
                action=FindingAction.RECOMMEND,
                claim="Document the migration path.",
            )
        ],
    )
    gate = DecisionGate(
        required=False,
        successful_reviewers=1,
        minimum_successful_reviewers=1,
    )

    open_questions = render_open_questions_markdown(reviews=[review])
    next_actions = render_next_actions_markdown(
        reviews=[review],
        conflicts=[],
        decision_gate=gate,
    )

    assert "What reporting queries are required?" in open_questions
    assert "Document the migration path" in next_actions


def test_synthesis_prompt_template_names_required_sections() -> None:
    prompt = render_synthesis_prompt(
        topic="# Database choice",
        structured_reviews_json='[{"reviewer_id":"fake"}]',
    )

    assert "agreement" in prompt
    assert "disagreement" in prompt
    assert "readiness" in prompt
    assert "Structured reviews" in prompt
