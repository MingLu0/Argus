from __future__ import annotations

import json
import re

from pydantic import ValidationError

from argus.findings.schema import ReviewResult

FENCED_JSON_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_reviewer_output(raw_output: str, reviewer_id: str) -> ReviewResult:
    candidate = _extract_json_candidate(raw_output)
    if candidate is None:
        return _parse_error_result(reviewer_id, "no JSON object found in reviewer output")

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as error:
        return _parse_error_result(reviewer_id, f"invalid JSON: {error.msg}")

    payload["reviewer_id"] = reviewer_id
    try:
        review = ReviewResult.model_validate(payload)
    except ValidationError as error:
        return _parse_error_result(reviewer_id, error.errors()[0]["msg"])

    for index, finding in enumerate(review.findings, start=1):
        if not finding.id:
            finding.id = f"{reviewer_id}-{index}"
    return review


def _extract_json_candidate(raw_output: str) -> str | None:
    stripped = raw_output.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    match = FENCED_JSON_PATTERN.search(raw_output)
    if match:
        return match.group(1).strip()
    return None


def _parse_error_result(reviewer_id: str, message: str) -> ReviewResult:
    return ReviewResult(
        reviewer_id=reviewer_id,
        risk_rationale="Reviewer output could not be parsed as structured findings.",
        parse_error=message,
    )
