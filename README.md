# Argus

Argus is a local multi-agent technical deliberation tool: many eyes on hard technical decisions.

It coordinates locally installed agent backends such as `claude`, `opencode`, and `codex`, runs independent reviewer roles in parallel, captures structured artifacts, groups disagreement, and produces a recommendation with explicit human decision gates for high-risk cases.

## MVP Commands

```bash
argus doctor
argus agents
argus run topic.md --mode tech-stack --backends fake
argus status
```

The first milestone uses file artifacts under `.argus/runs/`. SQLite and the TUI come later.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```
