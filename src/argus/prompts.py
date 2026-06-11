from __future__ import annotations


def render_reviewer_prompt(*, topic: str, mode: str, role: str) -> str:
    return f"""You are an independent technical reviewer for Argus.

Mode: {mode}
Role: {role}

Review the topic below. Return a single JSON object, optionally inside a
```json fenced block. Do not include prose outside the object.

Schema:
{{
  "recommendation": "approve | revise | reject | uncertain",
  "risk_level": "low | medium | high",
  "risk_rationale": "short rationale",
  "findings": [
    {{
      "severity": "error | warning | info",
      "action": "no-op | recommend | ask-user | block",
      "claim": "specific technical claim",
      "evidence": ["supporting context"],
      "confidence": "low | medium | high",
      "affected_decision": "short decision area"
    }}
  ],
  "open_questions": ["question"]
}}

Topic:
{topic}
"""


def render_synthesis_prompt(*, topic: str, structured_reviews_json: str) -> str:
    return f"""You are synthesizing Argus technical review outputs.

Produce a concise recommendation that includes agreement, disagreement, risk,
readiness, open questions, and next actions. Do not hide failed reviewers,
uncertainty, or conflicts.

Topic:
{topic}

Structured reviews:
{structured_reviews_json}
"""
