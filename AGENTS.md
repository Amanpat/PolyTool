# AGENTS.md — PolyTool (Codex)

## Purpose

This file is Codex's front-loaded working context for the PolyTool repository. Codex should read this file at session start, then any context the Architect's prompt provides inline. Codex sessions are task-scoped and self-contained; rely on this file for permanent rules, rely on the Architect's prompt for task state.

If the Architect's prompt contradicts this file on a non-negotiable rule, stop and surface the conflict. Do not silently split the difference.

## Document Priority (when resolving conflicts)

1. `docs/PLAN_OF_RECORD.md`
2. `docs/ARCHITECTURE.md`
3. `docs/STRATEGY_PLAYBOOK.md`
4. `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`
5. `docs/CURRENT_STATE.md`
6. `docs/CURRENT_DEVELOPMENT.md`
7. This file (AGENTS.md)
8. The Architect's prompt (lowest priority when it conflicts with the above)

If two docs disagree, stop and ask. Do not split the difference.

## What PolyTool Is

A Polymarket-first research, simulation, and execution system with three parallel revenue tracks: Avellaneda-Stoikov market making (Track 1B), crypto pair bot (Track 1A), and sports directional model (Track 1C). Not a reverse-engineering repo — the reverse-engineering is one input to a strategy pipeline that validates via SimTrader gates, then deploys live with hard risk limits.

Near-term focus: Polymarket. Longer-term: Kalshi and further prediction venues through a platform abstraction layer once Polymarket is profitable.

## Codex's Role In This Project

Codex is invoked for:

- **Small, scoped tasks** (< 50 lines changed, no side effects): refactors, formatting, test additions, doc updates.
- **Adversarial reviews** on files flagged by the Codex Review Policy (see below).
- **Context fetches**: read-only reporting of repo state when the Architect needs information it doesn't have.
- **Parallel execution** when Claude Code is handling a different work unit.
- **Fallback execution** when Claude Code is approaching token limits.

Codex is **not** invoked for: multi-file refactors spanning unrelated modules, new strategy implementations, live-trading code, kill-switch modifications, or anything requiring project-wide architectural judgment. If the Architect's prompt asks you to do one of these, stop and ask for clarification.

## Non-Negotiable Principles

1. **Simple path first.** Make raw CLI flows work manually before adding orchestration.
2. **First dollar before perfect system.** Revenue paths > elegant machinery.
3. **Triple-track strategy.** Do not make project success depend on one strategy.
4. **Front-load context, not chat.** Put conventions in docs, not session messages.
5. **Checklist, not calendar.** Finish checklist items; don't invent deadlines.
6. **Use existing visibility.** Grafana first. No new frontend before profit.

## Repository Structure (verify before assuming)

- `docs/` — all project documentation, dev logs, specs, features, runbooks
- `docs/specs/` — effectively read-only; do not modify casually
- `docs/dev_logs/` — mandatory output for every meaningful work unit
- `config/` — benchmark manifests, strategy configs, benchmark lock/audit files
- `artifacts/` — gitignored runtime outputs (tapes, gate results, sweeps, dossiers)
- `infra/` — Docker Compose and infrastructure configuration
- `tools/cli/` — CLI entrypoints
- `tests/` — unit and integration tests
- `packages/` — shared libraries (Python core lives here)

If a path differs from this file in the actual repo, inspect the repo and adapt. Do not force the repo to match this file.

## Database One-Sentence Rule

**ClickHouse handles all live streaming writes. DuckDB handles all historical Parquet reads. They do not replace each other.**

## ClickHouse Authentication Rule

All CLI entrypoints that touch ClickHouse MUST read credentials from the `CLICKHOUSE_PASSWORD` environment variable with fail-fast behavior:

```python
if not ch_password:
    sys.exit(1)
```

Never use a hardcoded fallback like `"polytool_admin"`. Never silently default to an empty string. This rule exists because three separate auth-propagation bugs were shipped and debugged between 2026-03-18 and 2026-03-19, each caused by a CLI entrypoint falling back to a wrong default.

- Admin user: `CLICKHOUSE_USER` from `.env` (default name `polytool_admin`)
- Grafana read-only user: `grafana_ro` / `grafana_readonly_local` (SELECT only)

When adding any new CLI command that queries or writes ClickHouse, copy the credential-loading pattern from an existing passing entrypoint (e.g., `close_benchmark_v1.main()`), not from memory.

## Tape Tiers

- **Gold**: live tape recorder output, tick-level / millisecond precision. Highest fidelity. Required for Gate 2 sweeps.
- **Silver**: reconstructed tapes from pmxt + Jon-Becker + polymarket-apis. Useful for autoresearch and price history; **NOT suitable for Gate 2 sweep** — no L2 book data means zero fills.
- **Bronze**: Jon-Becker trade-level only. Lower-fidelity. Useful for category analysis and κ MLE.

Every tape-driven result preserves tier metadata. Do not treat Bronze or price-only data as equivalent to Gold. If a task involves tape selection or tape-based validation, verify tier before running.

## Risk, Fees, and Live-Trading Guardrails

- Fee realism matters. Do not assume zero-friction profitability in replay or live code.
- Legacy research pipeline uses a 2% gross-profit fee model; Polymarket market-specific fee handling can differ. Be explicit about which fee model a component uses.
- Respect current platform rate limits: 60 orders/min CLOB, 100 req/min REST.
- Always preserve the kill-switch model. Five layers: file-based (`touch artifacts/simtrader/KILL`), daily loss cap, WS disconnect trigger, inventory limit breach, Discord `/stop`.
- Inventory limits, daily loss caps, max order/notional caps are not optional.
- Do not weaken risk defaults to make a backtest or paper run look better.
- No live capital before SimTrader shadow gate (Gate 3) passes.

## Human-in-the-Loop Rules

You may perform autonomously:

- Candidate discovery and wallet scanning
- Alpha distillation
- Lower-level validation runs (L1, L2)
- Research ingestion after quality gates
- Bounded parameter tuning within documented allowlists
- Kill-switch triggers on risk breaches

Stop and ask the operator before:

- Promoting a strategy to live capital
- Increasing capital stage
- Structural code changes in autoresearch
- Anything flagged LOW_CONFIDENCE by evaluation
- Modifying kill-switch, risk manager, or rate limiter logic
- Adding a strategy class never previously validated
- Disabling a live strategy
- Modifying any file in `docs/specs/` without explicit direction
- Touching private keys, capital movement, or infrastructure secrets

If a task touches these areas, stop and ask. Do not improvise.

## Dev Log Requirement

Every meaningful work unit produces a dev log at:

docs/dev*logs/YYYY-MM-DD*<slug>.md

Minimum contents:

- Files changed and why
- Commands run + exact output (pass/fail counts, not "tests pass")
- Decisions made during the session
- Open questions or blockers for the next work unit
- Codex review summary (if applicable): tier, issues found, issues addressed

Dev logs are the handoff between agents. Do not skip.

## Smoke Test Requirement

After any code change, run this before declaring the task done:

```bash
python -m polytool --help
python -m pytest tests/ -x -q --tb=short
```

If infrastructure was touched:

```bash
docker compose ps
```

If ClickHouse tables were modified:

```bash
curl "http://localhost:8123/?query=SELECT%201"
```

Report exact pass/fail counts ("142 passed, 0 failed, 3 skipped"), not summaries.

## Multi-Agent Awareness

Multiple agents (Claude Code, Codex, Gemini CLI, Cline) may work on this repo in parallel or sequence. At session start:

1. `git status` — check for uncommitted changes from another agent or manual edits
2. `git log --oneline -5` — see recent commits you did not make
3. `python -m polytool --help` — verify CLI still loads and command names match expectations
4. Do not assume your last session's state is still current

If you see unexpected changes, surface them to the operator before proceeding. Do not silently revert or overwrite another agent's work.

## Git Conventions

- Single branch: `main`. Commit and push directly.
- Do not create routine feature branches unless the operator explicitly requests one.
- Commits should be atomic — one logical change per commit.
- Commit messages: imperative mood, scope prefix (`feat(crypto):`, `fix(benchmark):`, `docs(runbook):`).
- Do not use `git push --force` on `main` without operator confirmation.

## Codex Review Policy (when you are the reviewer)

When invoked via `/codex:review` or `/codex:adversarial-review`, the severity bar depends on file category:

**Mandatory review files** (bar: every issue that could cause incorrect trades, lost capital, or bypassed safety):

- `execution/*`, `kill_switch.py`, `risk_manager.py`, `rate_limiter.py`
- `pair_engine.py`, `reference_feed.py`
- Any code touching `py_clob_client` order placement, EIP-712 signing, or best bid/ask price extraction

**Recommended review files** (bar: correctness issues + obvious performance regressions):

- Strategy files, SimTrader core (`broker_sim`, `replay_runner`, `tape_recorder`)
- WebSocket connection and reconnection logic
- ClickHouse write paths
- `market_discovery.py`
- Autoresearch engine files

**Skip** (no review): docs, config, tests, Grafana JSON, CLI formatting, artifacts.

Review output should distinguish:

- **Blocking**: must fix before merge
- **Non-blocking**: recommendation, explain tradeoff
- **Informational**: context for future work

Do not produce a review that is mostly style nitpicks on a Mandatory file. If you find nothing substantive on a Mandatory file, say so explicitly so the operator knows the review actually happened.

## Testing Conventions

- Prefer small, offline, deterministic tests first
- Every feature adds or updates targeted tests
- Use `tests/test_<feature>.py` naming
- Avoid network-dependent tests unless the task is explicitly integration-focused
- Do not claim a feature is done without naming the commands run and the pass/fail result
- Preserve existing tests; do not silently delete failing tests to green a change
- For strategy or replay changes, validate both logic correctness and friction realism

## Known Windows Gotchas

- PowerShell `cp1252` encoding can mangle Unicode arrows and symbols in logs
- Prefer plain ASCII in CLI output when possible
- Docker Desktop + WSL2 permission behavior differs from the real Windows user account
- Path separator issues (`\\` vs `/`) show up in scripts and artifact paths
- `.env` encoding and line endings can break parsing
- When giving shell commands, prefer PowerShell-safe or clearly label Bash-only commands

## Don't-Do List

- Do not commit secrets (keys, tokens, `.env` contents)
- Do not modify `docs/specs/` casually
- Do not add Kafka or any new message broker
- Do not build a new frontend pre-profit
- Do not move core logic into FastAPI handlers
- Do not replace ClickHouse with DuckDB (or vice versa)
- Do not assume paper results imply live viability
- Do not skip dev logs
- Do not create sweeping refactors when an atomic change will do
- Do not weaken gate language or risk defaults to make results look better
- Do not scatter docs outside `docs/`
- Do not invent repo structure or command syntax without checking
- Do not lower `min_events=50` threshold on benchmark work
- Do not autonomously trigger `benchmark_v2` — human decision only

## When to Escalate

Stop and ask the operator if:

- The prompt conflicts with a non-negotiable rule in this file
- The prompt asks you to touch a Human-Only area (keys, capital, infrastructure secrets)
- You encounter repo state you can't explain (uncommitted changes, unexpected files, failing tests from an unrelated module)
- The task requires architectural judgment that the Architect should be making
- A smoke test fails and the cause isn't obvious from the session's work

Escalation format: state the conflict, quote the relevant rule, propose the cheapest way to resolve (usually a context-fetch or a question to the operator).

## Default Session Output

A good Codex session in PolyTool leaves behind:

- Code changes scoped to one objective
- Targeted tests
- A dev log in `docs/dev_logs/`
- Any needed doc update under `docs/`
- Explicit open questions or blockers
- No secrets, no undocumented behavior changes, no silent scope creep
