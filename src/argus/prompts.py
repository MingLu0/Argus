from __future__ import annotations


def render_reviewer_prompt(*, topic: str, mode: str, role: str) -> str:
    return f"""You are an independent technical reviewer for Argus.

Mode: {mode}
Role: {role}

Review the topic below. Return concise Markdown with a clear recommendation,
risk level, major concerns, minor concerns, and open questions.

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
