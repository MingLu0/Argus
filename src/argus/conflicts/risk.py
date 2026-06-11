from __future__ import annotations

from argus.conflicts.schema import Conflict, ConflictStatus, DecisionGate
from argus.findings.schema import FindingAction, ReviewResult, RiskLevel


def build_decision_gate(
    *,
    reviews: list[ReviewResult],
    conflicts: list[Conflict],
    successful_reviewers: int,
    minimum_successful_reviewers: int,
) -> DecisionGate:
    reasons: list[str] = []
    conflict_ids: list[str] = []
    finding_ids: list[str] = []
    gate_risk = RiskLevel.LOW

    if successful_reviewers < minimum_successful_reviewers:
        reasons.append("too few successful reviewers")
        gate_risk = RiskLevel.HIGH

    for review in reviews:
        if review.risk_level == RiskLevel.HIGH:
            reasons.append(f"{review.reviewer_id} reported high run risk")
            gate_risk = RiskLevel.HIGH
        if review.parse_error:
            reasons.append(f"{review.reviewer_id} output could not be parsed")
            gate_risk = _max_risk(gate_risk, RiskLevel.MEDIUM)
        for finding in review.findings:
            if finding.action == FindingAction.BLOCK:
                reasons.append(f"{finding.id} blocks the decision")
                finding_ids.append(finding.id)
                gate_risk = RiskLevel.HIGH
            elif finding.action == FindingAction.ASK_USER:
                reasons.append(f"{finding.id} requires human input")
                finding_ids.append(finding.id)
                gate_risk = _max_risk(gate_risk, RiskLevel.MEDIUM)

    for conflict in conflicts:
        if conflict.status == ConflictStatus.UNRESOLVED:
            reasons.append(f"{conflict.id} is unresolved")
            conflict_ids.append(conflict.id)
            gate_risk = _max_risk(gate_risk, conflict.risk_level)
        elif conflict.risk_level == RiskLevel.HIGH:
            reasons.append(f"{conflict.id} is high risk")
            conflict_ids.append(conflict.id)
            gate_risk = RiskLevel.HIGH

    return DecisionGate(
        required=bool(reasons),
        reasons=_dedupe(reasons),
        risk_level=gate_risk,
        conflict_ids=_dedupe(conflict_ids),
        finding_ids=_dedupe(finding_ids),
        successful_reviewers=successful_reviewers,
        minimum_successful_reviewers=minimum_successful_reviewers,
    )


def _max_risk(left: RiskLevel, right: RiskLevel) -> RiskLevel:
    order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
    return left if order[left] >= order[right] else right


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
