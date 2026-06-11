from __future__ import annotations

import json

from pydantic import ValidationError

from argus.findings.schema import ReviewResult


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

    seen_ids: set[str] = set()
    for index, finding in enumerate(review.findings, start=1):
        base_id = finding.id.strip() if finding.id else f"finding-{index}"
        namespaced = f"{reviewer_id}-{base_id}"
        unique_id = namespaced
        suffix = 2
        while unique_id in seen_ids:
            unique_id = f"{namespaced}-{suffix}"
            suffix += 1
        finding.id = unique_id
        seen_ids.add(unique_id)
    return review


def _extract_json_candidate(raw_output: str) -> str | None:
    stripped = raw_output.strip()
    if stripped.startswith("{"):
        balanced = _balanced_json_object(stripped, 0)
        if balanced is not None:
            return balanced

    for start in _candidate_object_starts(raw_output):
        balanced = _balanced_json_object(raw_output, start)
        if balanced is None:
            continue
        try:
            json.loads(balanced)
        except json.JSONDecodeError:
            continue
        return balanced
    return None


def _candidate_object_starts(text: str) -> list[int]:
    return [index for index, char in enumerate(text) if char == "{"]


def _balanced_json_object(text: str, start: int) -> str | None:
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _parse_error_result(reviewer_id: str, message: str) -> ReviewResult:
    return ReviewResult(
        reviewer_id=reviewer_id,
        risk_rationale="Reviewer output could not be parsed as structured findings.",
        parse_error=message,
    )
