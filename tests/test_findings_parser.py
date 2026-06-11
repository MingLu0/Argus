from __future__ import annotations

from pathlib import Path

from argus.findings import FindingAction, RiskLevel, Severity, parse_reviewer_output

FIXTURES = Path(__file__).parent / "fixtures" / "agent_outputs"


def test_parse_valid_json_review_assigns_deterministic_finding_ids() -> None:
    raw = (FIXTURES / "valid_review.json").read_text()

    review = parse_reviewer_output(raw, "claude-skeptic")

    assert review.parse_error is None
    assert review.recommendation == "revise"
    assert review.risk_level == RiskLevel.MEDIUM
    assert review.findings[0].id == "claude-skeptic-finding-1"
    assert review.findings[0].severity == Severity.WARNING
    assert review.findings[0].action == FindingAction.ASK_USER


def test_parse_fenced_json_review_preserves_existing_finding_id() -> None:
    raw = (FIXTURES / "fenced_review.md").read_text()

    review = parse_reviewer_output(raw, "opencode-repo-fit")

    assert review.parse_error is None
    assert review.risk_level == RiskLevel.LOW
    assert review.findings[0].id == "opencode-repo-fit-custom-1"


def test_parse_invalid_review_returns_parse_error_without_crashing() -> None:
    raw = (FIXTURES / "invalid_review.txt").read_text()

    review = parse_reviewer_output(raw, "codex-alternatives")

    assert review.parse_error == "no JSON object found in reviewer output"
    assert review.reviewer_id == "codex-alternatives"
    assert review.findings == []


def test_parse_invalid_schema_returns_parse_error() -> None:
    review = parse_reviewer_output('{"findings":[{"severity":"bad"}]}', "bad-reviewer")

    assert review.parse_error is not None
    assert review.findings == []


def test_parse_json_followed_by_trailing_prose_succeeds() -> None:
    raw = (
        'Here is the review:\n'
        '{"recommendation":"approve","risk_level":"low",'
        '"findings":[{"severity":"info","action":"recommend","claim":"ok"}]} '
        '// notes from the reviewer'
    )

    review = parse_reviewer_output(raw, "reviewer-a")

    assert review.parse_error is None
    assert review.findings[0].id == "reviewer-a-finding-1"


def test_parse_deduplicates_colliding_finding_ids() -> None:
    raw = (
        '{"recommendation":"revise","risk_level":"low","findings":['
        '{"id":"dup","severity":"info","action":"recommend","claim":"a"},'
        '{"id":"dup","severity":"info","action":"recommend","claim":"b"}'
        ']}'
    )

    review = parse_reviewer_output(raw, "reviewer-b")

    assert review.parse_error is None
    assert [finding.id for finding in review.findings] == [
        "reviewer-b-dup",
        "reviewer-b-dup-2",
    ]
