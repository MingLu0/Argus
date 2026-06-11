# Argus

Argus is a local multi-agent technical deliberation tool: many eyes on hard technical decisions.

It coordinates locally installed agent backends such as `claude`, `opencode`, and `codex`, runs independent reviewer roles in parallel, captures structured artifacts, groups disagreement, and produces a recommendation with explicit human decision gates for high-risk cases.

## MVP Commands

```bash
argus doctor
argus agents
argus run topic.md --mode tech-stack --backends auto
argus status
```

### `argus run` options

- `--mode` — reviewer role set to use. Supported: `architecture`, `tech-stack`, `debugging`.
- `--backends` — which backends to fan out to. Accepts:
  - `auto` (default) — pick the first available real backend.
  - `auto-pool` — use every available real backend.
  - `fake` — use the bundled `fake-success` fixture three times (hermetic, no real agents required).
  - A comma-separated list of backend ids (e.g. `claude,codex`, or fixtures like `fake-delay,fake-stderr`). Unknown ids are rejected.
- `--timeout` — per-reviewer subprocess timeout in seconds (default `30`).
- `--project-root` — root directory for `.argus/` artifacts (default: current directory).

Reviewer roles are assigned to selected backends in the order they appear; duplicate `<backend>-<role>` ids are de-duplicated with a numeric suffix.

### Run artifacts

Each run writes to `.argus/runs/<run-id>/`:

- `run.yaml` — run manifest with per-step status.
- `backend-report.json` / `backend-report.md` — discovered backends and availability.
- `reviewers.json` — per-reviewer record (command, exit code, duration, timed-out flag, artifacts).
- `reviews/<reviewer-id>.raw.md`, `reviews/<reviewer-id>.parsed.json`, `logs/<reviewer-id>.{stdout,stderr}.log`, `artifacts/<reviewer-id>.result.json` — raw reviewer output, the structured `ReviewResult` parsed from it, and execution detail.
- `synthesis.md`, `run-summary.md`, `recommendation.md` — synthesized output, per-reviewer status summary, and the final recommendation.
- `findings.json` — consolidated structured findings across reviewers; each entry carries a namespaced `id`, `reviewer_id`, `severity`, `action`, `claim`, `evidence`, `confidence`, and `affected_decision`.
- `conflicts.json` — placeholder for cross-reviewer disagreement (populated by later milestones).

Reviewers are prompted to emit a single JSON object (optionally inside a ```json fenced block). When the output cannot be parsed, the per-reviewer `.parsed.json` records a `parse_error` and `findings.json` simply omits that reviewer's findings.

The first milestone uses file artifacts under `.argus/runs/`. SQLite and the TUI come later.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```
