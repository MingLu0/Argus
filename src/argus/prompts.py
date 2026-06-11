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


def render_synthesis(topic: str, review_outputs: dict[str, str]) -> str:
    sections = ["# Synthesis", "", "## Topic", "", topic.strip(), "", "## Reviews"]
    for reviewer_id, output in review_outputs.items():
        sections.extend(["", f"### {reviewer_id}", "", output.strip()])
    sections.extend(
        [
            "",
            "## Recommendation",
            "",
            "This MVP synthesis records reviewer outputs for human inspection. "
            "Structured conflict grouping comes in a later phase.",
        ]
    )
    return "\n".join(sections).strip() + "\n"
