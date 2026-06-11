from __future__ import annotations

import re
from collections import defaultdict

from argus.conflicts.schema import Conflict, ConflictPosition, ConflictStatus
from argus.findings.schema import Finding, FindingAction, ReviewResult, RiskLevel, Severity

DEFAULT_AFFECTED_DECISION = "general"


def group_conflicts(reviews: list[ReviewResult]) -> list[Conflict]:
    findings_by_bucket: dict[str, list[tuple[ReviewResult, Finding]]] = defaultdict(list)
    bucket_decision: dict[str, str] = {}
    for review in reviews:
        for finding in review.findings:
            bucket, affected_decision = _decision_bucket(review, finding)
            findings_by_bucket[bucket].append((review, finding))
            bucket_decision.setdefault(bucket, affected_decision)

    conflicts: list[Conflict] = []
    used_conflict_ids: set[str] = set()
    for bucket, entries in sorted(findings_by_bucket.items()):
        if not entries:
            continue
        affected_decision = bucket_decision[bucket]
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
        conflict_id = _unique_conflict_id(f"conflict-{_slugify(bucket)}", used_conflict_ids)
        conflicts.append(
            Conflict(
                id=conflict_id,
                affected_decision=affected_decision,
                risk_level=risk_level,
                status=status,
                rationale=_rationale(affected_decision, positions, status, risk_level),
                positions=positions,
            )
        )
    return conflicts


def _decision_bucket(review: ReviewResult, finding: Finding) -> tuple[str, str]:
    normalized = _normalize_decision(finding.affected_decision)
    if normalized == DEFAULT_AFFECTED_DECISION:
        unique_key = f"{DEFAULT_AFFECTED_DECISION}::{review.reviewer_id}::{finding.id}"
        return unique_key, DEFAULT_AFFECTED_DECISION
    return normalized, normalized


def _normalize_decision(value: str) -> str:
    normalized = " ".join(value.strip().lower().split())
    return normalized or DEFAULT_AFFECTED_DECISION


def _conflict_status(positions: list[ConflictPosition]) -> ConflictStatus:
    reviewer_count = len({position.reviewer_id for position in positions})
    distinct_claims = {position.claim.strip().lower() for position in positions}
    blocking_actions = {
        FindingAction.ASK_USER,
        FindingAction.BLOCK,
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


def _unique_conflict_id(conflict_id: str, used_conflict_ids: set[str]) -> str:
    if conflict_id not in used_conflict_ids:
        used_conflict_ids.add(conflict_id)
        return conflict_id
    suffix = 2
    while f"{conflict_id}-{suffix}" in used_conflict_ids:
        suffix += 1
    unique_conflict_id = f"{conflict_id}-{suffix}"
    used_conflict_ids.add(unique_conflict_id)
    return unique_conflict_id
