from __future__ import annotations

from collections import defaultdict

from argus.conflicts.schema import Conflict, ConflictStatus, DecisionGate
from argus.findings.schema import Confidence, Finding, FindingAction, ReviewResult, RiskLevel
from argus.models import ReviewerRecord


def render_synthesis_markdown(
    *,
    topic: str,
    reviews: list[ReviewResult],
    raw_outputs: dict[str, str],
    conflicts: list[Conflict],
) -> str:
    lines = ["# Synthesis", "", "## Topic", "", topic.strip(), ""]
    lines.extend(["## Reviewer Summary", ""])
    if not reviews:
        lines.append("- No successful structured reviews were produced.")
    for review in reviews:
        lines.append(
            f"- `{review.reviewer_id}`: {review.recommendation}; "
            f"risk {review.risk_level}; {len(review.findings)} findings; "
            f"{len(review.open_questions)} open questions."
        )

    lines.extend(["", "## Areas Of Agreement", ""])
    agreement_items = _agreement_findings(reviews)
    lines.extend(_bullets(agreement_items, "No clear agreement was found."))

    lines.extend(["", "## Areas Of Disagreement", ""])
    disagreement_items = _disagreement_items(conflicts)
    lines.extend(_bullets(disagreement_items, "No unresolved disagreement was found."))

    lines.extend(["", "## Risk Summary", ""])
    risk_items = _risk_items(reviews)
    lines.extend(_bullets(risk_items, "No risks were raised by successful reviewers."))

    lines.extend(["", "## Raw Review Excerpts", ""])
    if not raw_outputs:
        lines.append("- No raw reviewer output was captured from successful reviewers.")
    for reviewer_id, output in raw_outputs.items():
        excerpt = output.strip().splitlines()[0] if output.strip() else "empty output"
        lines.append(f"- `{reviewer_id}`: {excerpt[:200]}")
    return "\n".join(lines).strip() + "\n"


def render_recommendation_markdown(
    *,
    reviewers: list[ReviewerRecord],
    reviews: list[ReviewResult],
    conflicts: list[Conflict],
    decision_gate: DecisionGate,
) -> str:
    readiness = _implementation_readiness(decision_gate)
    lines = [
        "# Recommendation",
        "",
        "## Executive Recommendation",
        "",
        f"- Implementation readiness: {readiness}",
        f"- Decision gate required: {str(decision_gate.required).lower()}",
        f"- Aggregate risk: {decision_gate.risk_level}",
    ]

    if decision_gate.required:
        lines.extend(["", "## Gate Reasons", ""])
        lines.extend(_bullets(decision_gate.reasons, "No gate reasons recorded."))

    lines.extend(["", "## Decision Matrix", ""])
    lines.extend(_decision_matrix(reviews))

    lines.extend(["", "## Conflicts", ""])
    conflict_lines = [
        f"`{conflict.id}` ({conflict.risk_level}, {conflict.status}): {conflict.rationale}"
        for conflict in conflicts
        if conflict.status == ConflictStatus.UNRESOLVED or conflict.risk_level != RiskLevel.LOW
    ]
    lines.extend(_bullets(conflict_lines, "No unresolved or elevated-risk conflicts."))

    lines.extend(["", "## High-Confidence Risks", ""])
    high_confidence_risks = _risk_items(reviews, confidence=Confidence.HIGH)
    lines.extend(_bullets(high_confidence_risks, "No high-confidence risks were raised."))

    lines.extend(["", "## Speculative Risks", ""])
    speculative_risks = _speculative_risks(reviews)
    lines.extend(_bullets(speculative_risks, "No speculative risks were raised."))

    lines.extend(["", "## Reviewer Status", ""])
    if not reviewers:
        lines.append("- No reviewers selected.")
    for reviewer in reviewers:
        detail = f"`{reviewer.id}` ({reviewer.backend}, {reviewer.role}): {reviewer.status}"
        if reviewer.error:
            detail += f" - {reviewer.error}"
        lines.append(f"- {detail}")
    return "\n".join(lines).strip() + "\n"


def render_open_questions_markdown(*, reviews: list[ReviewResult]) -> str:
    lines = ["# Open Questions", ""]
    questions = [
        f"`{review.reviewer_id}`: {question}"
        for review in reviews
        for question in review.open_questions
    ]
    lines.extend(_bullets(questions, "No open questions were raised."))
    return "\n".join(lines).strip() + "\n"


def render_next_actions_markdown(
    *,
    reviews: list[ReviewResult],
    conflicts: list[Conflict],
    decision_gate: DecisionGate,
) -> str:
    lines = ["# Next Actions", ""]
    actions: list[str] = []
    if decision_gate.required:
        actions.append("Resolve `decision-gate.yaml` before implementation proceeds.")
    actions.extend(
        f"Resolve `{conflict.id}` for `{conflict.affected_decision}`."
        for conflict in conflicts
        if conflict.status == ConflictStatus.UNRESOLVED
    )
    for review in reviews:
        for finding in review.findings:
            if finding.action in {
                FindingAction.RECOMMEND,
                FindingAction.ASK_USER,
                FindingAction.BLOCK,
            }:
                actions.append(f"{finding.action}: {finding.claim}")
    lines.extend(_bullets(actions, "No follow-up actions were identified."))
    return "\n".join(lines).strip() + "\n"


def _agreement_findings(reviews: list[ReviewResult]) -> list[str]:
    agreeable_actions = {FindingAction.NO_OP, FindingAction.RECOMMEND}
    decision_reviewers: dict[str, set[str]] = defaultdict(set)
    for review in reviews:
        for finding in review.findings:
            if finding.action in agreeable_actions:
                decision_reviewers[finding.affected_decision.strip().lower()].add(
                    review.reviewer_id
                )
    shared_decisions = {
        decision for decision, reviewers in decision_reviewers.items() if len(reviewers) > 1
    }
    return [
        f"`{finding.affected_decision}`: {finding.claim}"
        for review in reviews
        for finding in review.findings
        if finding.affected_decision.strip().lower() in shared_decisions
        and finding.action in agreeable_actions
    ]


def _disagreement_items(conflicts: list[Conflict]) -> list[str]:
    items: list[str] = []
    for conflict in conflicts:
        if conflict.status != ConflictStatus.UNRESOLVED:
            continue
        claims = "; ".join(
            f"{position.reviewer_id}: {position.claim}" for position in conflict.positions
        )
        items.append(f"`{conflict.affected_decision}`: {claims}")
    return items


def _risk_items(reviews: list[ReviewResult], confidence: Confidence | None = None) -> list[str]:
    risky_actions = {FindingAction.ASK_USER, FindingAction.BLOCK}
    items: list[str] = []
    for review in reviews:
        if confidence is None and review.risk_level != RiskLevel.LOW:
            items.append(
                f"`{review.reviewer_id}` run risk {review.risk_level}: {review.risk_rationale}"
            )
        for finding in review.findings:
            if confidence is not None and finding.confidence != confidence:
                continue
            if finding.action in risky_actions:
                items.append(_finding_summary(review.reviewer_id, finding))
    return items


def _speculative_risks(reviews: list[ReviewResult]) -> list[str]:
    return [
        _finding_summary(review.reviewer_id, finding)
        for review in reviews
        for finding in review.findings
        if finding.confidence in {Confidence.LOW, Confidence.MEDIUM}
        and finding.action in {FindingAction.ASK_USER, FindingAction.BLOCK}
    ]


def _decision_matrix(reviews: list[ReviewResult]) -> list[str]:
    if not reviews:
        return ["- No successful structured reviews were produced."]
    lines = [
        "| Reviewer | Recommendation | Risk | Findings | Open Questions |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for review in reviews:
        lines.append(
            f"| `{review.reviewer_id}` | {review.recommendation} | {review.risk_level} | "
            f"{len(review.findings)} | {len(review.open_questions)} |"
        )
    return lines


def _implementation_readiness(decision_gate: DecisionGate) -> str:
    if decision_gate.risk_level == RiskLevel.HIGH:
        return "blocked"
    if decision_gate.required:
        return "needs human decision"
    return "ready"


def _finding_summary(reviewer_id: str, finding: Finding) -> str:
    return (
        f"`{reviewer_id}` `{finding.affected_decision}` "
        f"{finding.action}/{finding.confidence}: {finding.claim}"
    )


def _bullets(items: list[str], empty_message: str) -> list[str]:
    if not items:
        return [f"- {empty_message}"]
    return [f"- {item}" for item in items]
