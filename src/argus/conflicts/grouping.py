from __future__ import annotations

import re
from collections import defaultdict

from argus.conflicts.schema import Conflict, ConflictPosition, ConflictStatus
from argus.findings.schema import Finding, FindingAction, ReviewResult, RiskLevel, Severity


def group_conflicts(reviews: list[ReviewResult]) -> list[Conflict]:
    findings_by_decision: dict[str, list[tuple[ReviewResult, Finding]]] = defaultdict(list)
    for review in reviews:
        for finding in review.findings:
            findings_by_decision[_normalize_decision(finding.affected_decision)].append(
                (review, finding)
            )

    conflicts: list[Conflict] = []
    for affected_decision, entries in sorted(findings_by_decision.items()):
        if not entries:
            continue
        positions = [
            ConflictPosition(
                reviewer_id=review.reviewer_id,
                finding_id=finding.id,
                claim=finding.claim,
                action=finding.action,
                severity=finding.severity,
                confidence=finding.confidence,
                evidence=finding.evidence,
            )
            for review, finding in entries
        ]
        status = _conflict_status(positions)
        risk_level = _risk_level(entries, status)
        conflicts.append(
            Conflict(
                id=f"conflict-{_slugify(affected_decision)}",
                affected_decision=affected_decision,
                risk_level=risk_level,
                status=status,
                rationale=_rationale(affected_decision, positions, status, risk_level),
                positions=positions,
            )
        )
    return conflicts


def _normalize_decision(value: str) -> str:
    normalized = " ".join(value.strip().lower().split())
    return normalized or "general"


def _conflict_status(positions: list[ConflictPosition]) -> ConflictStatus:
    reviewer_count = len({position.reviewer_id for position in positions})
    distinct_claims = {position.claim.strip().lower() for position in positions}
    blocking_actions = {
        FindingAction.ASK_USER,
        FindingAction.BLOCK,
        FindingAction.RECOMMEND,
    }
    actionable_count = sum(position.action in blocking_actions for position in positions)
    if reviewer_count > 1 and len(distinct_claims) > 1 and actionable_count > 0:
        return ConflictStatus.UNRESOLVED
    return ConflictStatus.NON_CONFLICTING


def _risk_level(entries: list[tuple[ReviewResult, Finding]], status: ConflictStatus) -> RiskLevel:
    if any(review.risk_level == RiskLevel.HIGH for review, _ in entries):
        return RiskLevel.HIGH
    if any(finding.action == FindingAction.BLOCK for _, finding in entries):
        return RiskLevel.HIGH
    if status == ConflictStatus.UNRESOLVED:
        return RiskLevel.MEDIUM
    if any(finding.severity == Severity.ERROR for _, finding in entries):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _rationale(
    affected_decision: str,
    positions: list[ConflictPosition],
    status: ConflictStatus,
    risk_level: RiskLevel,
) -> str:
    reviewer_count = len({position.reviewer_id for position in positions})
    if status == ConflictStatus.UNRESOLVED:
        return (
            f"{reviewer_count} reviewers raised distinct positions for "
            f"{affected_decision}; risk is {risk_level}."
        )
    return f"Findings for {affected_decision} do not currently conflict; risk is {risk_level}."


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "general"
