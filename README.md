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
  - A comma-separated list of backend ids (e.g. `claude,codex`, or fixtures like `fake-delay,fake-stderr`, `fake-postgres`, `fake-dynamodb`, `fake-high-risk`). Unknown ids are rejected.
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
- `conflicts.json` — cross-reviewer disagreement grouped by `affected_decision`. Each conflict carries an `id` (e.g. `conflict-database`), `affected_decision`, `risk_level` (`low`/`medium`/`high`), `status` (`unresolved` or `non_conflicting`), `rationale`, and one `position` per contributing finding (with `reviewer_id`, `finding_id`, `claim`, `action`, `severity`, `confidence`, and `evidence`). Findings with the default `affected_decision` are not bucketed across reviewers, and reviewer disagreement is only marked `unresolved` when at least one position carries an `ask-user` or `block` action.
- `decision-gate.yaml` — written only when human decision is required. Records `required`, the aggregated `risk_level`, the deduplicated `reasons` that triggered the gate, the `conflict_ids` and `finding_ids` referenced by those reasons, and the `successful_reviewers` / `minimum_successful_reviewers` counts. A gate is required when there are too few successful reviewers, any reviewer reported `risk_level: high` or a parse error, any finding has an `ask-user` or `block` action, or any conflict is unresolved or high-risk. When the gate is required, `run.yaml` status is set to `awaiting_decision`; otherwise the run completes.

Reviewers are prompted to emit a single JSON object (optionally inside a ```json fenced block). When the output cannot be parsed, the per-reviewer `.parsed.json` records a `parse_error` and `findings.json` simply omits that reviewer's findings.

The first milestone uses file artifacts under `.argus/runs/`. SQLite and the TUI come later.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```
