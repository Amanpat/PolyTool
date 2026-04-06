# CLAUDE.md — PolyTool

## Purpose

This file is the front-loaded working context for Claude Code. It exists to reduce rediscovery, protect scope, and keep every coding session aligned with the current PolyTool repo, roadmap, and operating rules.

Claude Code should read this file first, then `docs/CURRENT_STATE.md`, then the task-specific files. If a task conflicts with the document priority below, stop and surface the conflict before changing code.

## Document Priority (highest wins)

1. `docs/PLAN_OF_RECORD.md`
2. `docs/ARCHITECTURE.md`
3. `docs/STRATEGY_PLAYBOOK.md`
4. `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`
5. `docs/CURRENT_STATE.md`
6. Task-specific spec or feature doc

If two docs disagree, do not “split the difference.” Stop, call out the conflict, and propose the doc update needed before implementation.

## What PolyTool Is

PolyTool is not just a reverse-engineering repo anymore. It is a Polymarket-first research, simulation, and execution system built to:

1. reverse-engineer profitable wallet behavior,
2. convert discovered behavior into hypotheses and runnable strategies,
3. validate those strategies in replay and shadow environments,
4. deploy surviving strategies with hard risk limits,
5. continuously improve through research ingestion, news signals, and autoresearch.

Near-term focus is still Polymarket. Longer-term expansion targets Kalshi and future prediction venues through a platform abstraction layer once the Polymarket path is profitable and stable.

## Current Direction

The repo is in the Phase 0 / Phase 1 era described by Roadmap V5:

- Phase 0: rebuild project context files, finish operator setup, tighten workflow.
- Phase 1A: crypto pair bot as the fastest path to first dollar.
- Phase 1B: market-maker gate closure, benchmark completion, shadow, then staged live deployment.
- Phase 1 uses Grafana for visibility, CLI-first workflows, and simple scheduling.
- No custom frontend is needed pre-profit.
- Broad n8n orchestration is deferred to Phase 3, but a scoped RIS n8n pilot (ADR 0013) is shipped and opt-in via `--profile ris-n8n`.
- No heavy architecture expansion before raw CLI paths work end-to-end manually.

## Non-Negotiable Development Principles

1. **Simple path first.** Make raw CLI flows work manually before adding orchestration.
2. **First dollar before perfect system.** Revenue paths matter more than elegant but unproven machinery.
3. **Triple-track strategy.** Do not make project success depend on one strategy.
4. **Front-load context, not chat.** Put conventions in docs, not repeated session messages.
5. **Checklist, not calendar.** Finish checklist items; do not invent deadlines.
6. **Use existing visibility.** Grafana first. No new frontend before justified.

## Triple-Track Strategy Model

### Track 1 — Market Maker

- Long-term revenue engine.
- Avellaneda-Stoikov style quoting and inventory control.
- Depends on tape quality, calibration, Gate 2, Gate 3, then staged live rollout.

### Track 2 — Crypto Pair Bot (Phase 1A — Standalone)

- Fastest path to first dollar.
- 5m / 15m BTC, ETH, SOL up/down markets.
- Current strategy: directional momentum entries based on gabagool22 pattern
  analysis (quick-049). Favorite leg (direction side) fills at ask <=
  max_favorite_entry (0.75); hedge leg fills only at ask <= max_hedge_price (0.20).
  Pair-cost accumulation (original thesis) was superseded in quick-046/049.
  See dev logs 2026-03-29_gabagool22_crypto_analysis.md and
  2026-03-29_gabagool_strategy_rebuild.md.
- **Live deployment BLOCKED**: no active BTC/ETH/SOL 5m/15m markets on
  Polymarket as of 2026-03-29; full paper soak with real signals not yet run;
  oracle mismatch concern (Coinbase reference feed vs Chainlink on-chain
  settlement oracle); EU VPS likely required for deployment latency assumptions.
- **STANDALONE — does NOT wait for Gate 2 or Gate 3.** This track can be built and deployed
  independently of SimTrader benchmark validation. Phase 1A in v5 framing.
- Phase 1B is market-maker gate closure: Gate 2 scenario sweep against benchmark_v1 manifest,
  then Gate 3 shadow, then staged live deployment.

### Track 3 — Sports Directional Model

- Medium-term model-driven track.
- Uses freely available sports data and probability modeling.
- Needs paper prediction track record before capital deployment.

Do not collapse all roadmap effort into one track. Maintain optionality.

## North-Star Architecture

### Core rule

All business logic belongs in the Python core library. CLI commands wrap the core for developer speed. FastAPI, scheduling, dashboards, and future orchestration are thin layers around working core logic.

### Database one-sentence rule

**ClickHouse handles all live streaming writes. DuckDB handles all historical Parquet reads. They do not replace each other.**

### ClickHouse authentication rule

All CLI entrypoints that touch ClickHouse MUST read credentials from the
`CLICKHOUSE_PASSWORD` environment variable with fail-fast behavior:
`if not ch_password: sys.exit(1)`. Never use a hardcoded fallback like
`"polytool_admin"`. Never silently default to empty string. This rule
exists because three separate auth-propagation bugs were shipped and
debugged between 2026-03-18 and 2026-03-19 — each caused by a different
CLI entrypoint falling back to a wrong default.

- Admin user: `CLICKHOUSE_USER` from `.env` (default name `polytool_admin`).
- Grafana read-only user: `grafana_ro` / `grafana_readonly_local` (SELECT only).
- When adding any new CLI command that queries or writes ClickHouse, copy the
  credential-loading pattern from an existing passing entrypoint (e.g.,
  `close_benchmark_v1.main()`), not from memory.

### Layer roles

- **Python core**: scanners, RAG, SimTrader, strategy logic, execution logic, research evaluation.
- **CLI**: fastest test/debug interface and should never go away.
- **FastAPI wrapper**: thin HTTP layer for automation later; no business logic should live here.
- **Scheduling**: APScheduler is the default scheduler. A scoped n8n pilot handles RIS ingestion workflows (opt-in via `--profile ris-n8n`, see ADR 0013). Broad n8n orchestration remains a Phase 3 target.
- **Visualization**: Grafana only in current pre-profit phases.

## What Is Already Built (high-confidence current state)

### Research pipeline

- ClickHouse schema and ingest pipeline for Polymarket data.
- Grafana dashboards for trades, detectors, PnL, and arbitrage feasibility.
- `scan` CLI and trust artifact emission.
- Strategy detectors including holding style, DCA laddering, market-selection bias, and complete-set-arbish.
- PnL computation with the repo’s current fee model.
- Resolution enrichment and CLV capture.
- `wallet-scan`, `alpha-distill`, hypothesis registry, local RAG, and LLM bundle tooling.

### SimTrader stack

- Tape recorder.
- L2 book reconstruction.
- Replay runner and BrokerSim.
- Sweeps and local reports.
- Shadow mode.
- MarketMakerV0 and MarketMakerV1 (logit Avellaneda-Stoikov, canonical Phase 1 strategy) and execution primitives including kill switch, rate limiter, risk manager, live executor, and live runner.

### Benchmark pipeline

- **benchmark_v1 is CLOSED as of 2026-03-21.**
- `config/benchmark_v1.tape_manifest`, `config/benchmark_v1.lock.json`, and
  `config/benchmark_v1.audit.json` all exist and are validated.
- 50 tapes across 5 buckets: `politics=10, sports=15, crypto=10, near_resolution=10, new_market=5`.
- The silver reconstructor, manifest curator, gap-fill planner/executor, new-market capture
  planner, and closure orchestrator all exist and the full pipeline ran successfully.
- Finalization required explicit `--root artifacts/tapes/new_market` on `benchmark-manifest`
  (default roots do not include that path). See dev log
  `docs/dev_logs/2026-03-21_phase1_docs_closeout.md` for full closure record.
- **Gate 2 scenario sweep is the next step (Phase 2 / Phase 1B).** Run
  `python tools/gates/close_sweep_gate.py` against `config/benchmark_v1.tape_manifest`.
  Gate 2 passes when ≥ 70% of tapes show positive net PnL after fees and realistic-retail
  assumptions. Gate 2 is NOT passed yet. Gate 2 is currently NOT_RUN (not FAILED): the
  corpus has only 10/50 qualifying tapes. The immediate unblock is live Gold capture per
  `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`.
  **Crypto bucket blocked:** no active BTC/ETH/SOL 5m/15m pair markets on Polymarket
  as of 2026-03-29. Use `python -m polytool crypto-pair-watch --one-shot` to check.

When tasking Claude Code, assume the benchmark pipeline has produced the
`config/benchmark_v1.tape_manifest`. The manifest, lock, and audit are finalized
as of 2026-03-21. Do not reopen Phase 1 tasks.

**Benchmark policy lock:** WAIT_FOR_CRYPTO is the current policy (ADR:
`docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md`).
Do NOT: modify `config/benchmark_v1.tape_manifest`, `config/benchmark_v1.lock.json`, or
`config/benchmark_v1.audit.json`. Do NOT improvise around the crypto blocker by:

- Lowering the `min_events=50` threshold
- Relaxing the Gate 2 >= 70% pass condition
- Substituting non-crypto tapes into the crypto bucket
- Treating Gate 2 NOT_RUN as a gate failure
- Autonomously triggering benchmark_v2
  Escalation deadline for benchmark_v2 consideration: **2026-04-12**. Human decision required.

### Market Selection Engine

- Seven-factor composite scorer: category_edge (Jon-Becker 72.1M trades), spread_opportunity,
  volume (log-scaled), competition, reward_apr, adverse_selection, time_gaussian.
- NegRisk penalty (x0.85) and longshot bonus (+0.15 max) applied per market.
- CLI: `python -m polytool market-scan --top 20`
- Artifacts written to `artifacts/market_selection/YYYY-MM-DD.json`.

### Artifacts directory layout

All artifacts are gitignored. The canonical layout (as of 2026-03-28) is:

- `artifacts/tapes/gold/` — live tape recorder output (Gold tier)
- `artifacts/tapes/silver/` — reconstructed Silver tapes
- `artifacts/tapes/bronze/` — Bronze (trade-level only) tapes
- `artifacts/tapes/shadow/` — shadow run tapes
- `artifacts/tapes/crypto/` — crypto pair new-market and paper-run tapes
- `artifacts/gates/gate2_sweep/` — Gate 2 sweep results
- `artifacts/gates/manifests/` — gate manifests (gate2_tape_manifest.json)
- `artifacts/benchmark/` — benchmark closure run artifacts
- `artifacts/simtrader/runs/` — SimTrader replay runs
- `artifacts/simtrader/sweeps/` — SimTrader sweep outputs
- `artifacts/simtrader/ondemand_sessions/` — Studio OnDemand sessions
- `artifacts/dossiers/users/` — wallet/user dossier bundles
- `artifacts/research/batch_runs/` — research batch run outputs
- `artifacts/market_selection/` — market selection artifacts
- `artifacts/watchlists/` — market watchlist artifacts
- `artifacts/debug/` — probe outputs, loose debug files, corpus audits

## Validation Gates and Capital Stages

### Validation ladder

- **L1**: multi-tape replay. Strategy must show positive net PnL across a broad tape set.
- **L2**: scenario sweep under realistic latency / fill assumptions.
- **L3 / Gate 3**: live shadow against real markets using simulated fills only.

### Market-maker gate language

- **Gate 2**: parameter sweep on benchmark set. Current roadmap target is at least 70% positive net PnL after fees and realistic-retail assumptions.
- **Gate 3**: shadow run. Shadow PnL should stay within 25% of replay prediction.
- **Stage 0**: paper live dry-run.
- **Stage 1+**: live capital progression.

### Operating policy for Claude Code

Do not weaken validation language in code or docs. If a feature changes gate definitions, validation metrics, or promotion criteria, update the governing docs first.

## Tape Tiers

- **Gold**: live tape recorder output, tick-level / ms, highest-fidelity source.
- **Silver**: reconstructed tapes from pmxt + Jon-Becker + polymarket-apis, good for Gate 2 and autoresearch.
- **Bronze**: Jon-Becker trade-level only, useful but lower-fidelity.

Every tape-driven result should preserve tier metadata. Do not treat Bronze or coarse price-only data as equivalent to Gold.

## Human-in-the-Loop Rules

### Fully autonomous

- candidate discovery,
- wallet scans,
- alpha distillation,
- lower-level validation runs,
- research ingestion after quality gates,
- signal linking,
- bounded parameter tuning,
- kill-switch triggers on risk breaches.

### Human approval required

- promoting a strategy to live capital,
- capital stage increases,
- review-state strategy decisions,
- structural code changes in autoresearch,
- anything marked low-confidence by evaluation.

### Human only

- private keys,
- funding / moving capital,
- infrastructure secrets,
- adding brand-new strategy classes without prior validation,
- disabling live strategies.

If a task touches these areas, Claude Code should stop and ask for operator direction instead of improvising.

## Repo Working Conventions

### Branch policy

- Single branch: `main`. Commit and push directly to `main`.
- Do not create routine feature branches unless the operator explicitly requests one.
- Historical note: prior to 2026-04-06 the repo used long-lived feature branches
  (phase-1, simtrader, roadmap*, feat/*). All were consolidated into main.

### Documentation policy

- New documentation goes under `docs/`, not scattered across the repo.
- `docs/specs/` contains specification docs and is effectively read-only unless the task explicitly says to revise a spec.
- `docs/features/` describes implemented features.
- `docs/dev_logs/YYYY-MM-DD_<slug>.md` is mandatory for every meaningful work unit.
- `docs/CURRENT_STATE.md` should be updated after meaningful work, not allowed to drift.

### File / artifact naming

- Dev logs: `docs/dev_logs/YYYY-MM-DD_<slug>.md`
- Specs: `docs/specs/SPEC-xxxx-<slug>.md`
- Feature docs: `docs/features/<feature>.md`
- Artifacts: keep generated reports, bundles, manifests, and replay outputs under `artifacts/`
- Benchmark manifests and strategy research config belong under `config/`

### Code placement

- Core logic: library modules / packages, not thin wrappers.
- CLI entrypoints: under the CLI area (`tools/cli/` or equivalent current command module structure).
- Tests: under `tests/`.
- Infra config: under `infra/`.

### Expected high-value paths

Use these as your starting mental model and verify before major changes:

- `docs/`
- `docs/specs/`
- `docs/features/`
- `docs/dev_logs/`
- `docs/CURRENT_STATE.md`
- `docs/PLAN_OF_RECORD.md`
- `docs/ARCHITECTURE.md`
- `docs/STRATEGY_PLAYBOOK.md`
- `config/`
- `artifacts/tapes/gold/` — live Gold tapes
- `artifacts/tapes/silver/` — reconstructed Silver tapes
- `artifacts/tapes/shadow/` — shadow run tapes
- `artifacts/tapes/crypto/` — crypto pair tapes
- `artifacts/gates/gate2_sweep/` — Gate 2 sweep results
- `artifacts/gates/manifests/` — gate manifests
- `artifacts/benchmark/` — benchmark closure artifacts
- `artifacts/debug/` — probe outputs and debug files
- `infra/`
- `tests/`
- `tools/cli/`
- shared libraries under `packages/` and/or the Python package root

If a path differs in the actual repo, inspect and adapt — do not force the repo to match this file blindly.

## Testing Conventions

- Prefer small, offline, deterministic tests first.
- Every feature should add or update targeted tests.
- Use `tests/test_<feature>.py` naming.
- Avoid network-dependent tests unless the task is explicitly integration-focused.
- Do not claim a feature is done without naming the commands run and the pass/fail result.
- Preserve existing tests; do not silently delete failing tests to “green” a change.
- For strategy or replay changes, validate both logic correctness and friction realism.

### What to test by feature type

- **CLI feature**: argument parsing, expected outputs, smoke path.
- **Replay / SimTrader**: deterministic state transitions, fills, fee handling, latency assumptions, invariants.
- **Execution layer**: dry-run safety, rate limiting, kill-switch behavior, inventory/risk checks.
- **Docs / config change**: ensure referenced paths and commands still line up with the repo.

## CLI Reference (known commands / known families)

Use CLI-first flows. Before building orchestration, make these work manually.

**Always verify first:** At the start of any session involving CLI work, run
`python -m polytool --help` and scan the output. Do not assume command names,
flags, or subcommand structure from this file alone — they may have changed
since this doc was last updated. A 2-second check prevents 20-minute debugging.

### Research / dossier workflows

- `scan`
- `wallet-scan`
- `alpha-distill`
- `llm-bundle`
- `candidate-scan`
- `research-precheck`
- `research-ingest`
- `research-acquire`
- `research-report`
- `research-health`
- `research-stats`
- `research-scheduler`

## Research Intelligence System (RIS)

### Purpose

RIS is the project's persistent knowledge base for research findings, academic papers,
and operator-discovered insights. Before implementing a new strategy or feature, check
what existing research says to avoid duplicate effort and catch contradictions early.

### Dev Agent Pre-Build Workflow

Before starting any feature or strategy implementation, run these checks in order:

1. Run a precheck on the planned work:
   ```
   python -m polytool research-precheck run --idea "description of planned work" --no-ledger
   ```
2. Interpret the result:
   - **STOP** -- Do not proceed without operator discussion. A known contradiction or blocker exists.
   - **CAUTION** -- Note the concerns flagged. Proceed with awareness.
   - **GO** -- No blockers found. Proceed.
3. For deeper context, query the knowledge store directly:
   ```
   python -m polytool rag-query --question "relevant topic" --hybrid --knowledge-store default
   ```
4. If precheck cites contradictions, run inspect for full provenance:
   ```
   python -m polytool research-precheck inspect --db kb/rag/knowledge/knowledge.sqlite3
   ```

### Preserving Findings into RIS

After a productive research session (LLM chat, web search, paper read), preserve findings:

- **Save a URL** (paper, blog post, GitHub repo):
  ```
  python -m polytool research-acquire --url URL --source-family FAMILY --no-eval
  ```
  FAMILY values: `academic`, `github`, `blog`, `news`, `book`, `reddit`, `youtube`

- **Save a manual summary** (from a ChatGPT/Gemini/Claude session):
  ```
  python -m polytool research-ingest --text "finding text" --title "Finding Title" --source-type manual --no-eval
  ```

- **Save from a file** (notes, exported doc):
  ```
  python -m polytool research-ingest --file path/to/notes.md --source-type manual --no-eval
  ```

### Pipeline Health

- Status snapshot: `python -m polytool research-health`
- Metrics: `python -m polytool research-stats summary`
- Scheduler status: `python -m polytool research-scheduler status`

All RIS commands are offline-first and do not call external LLM APIs unless `--provider ollama` is used.

### Tape / benchmark workflows

- `fetch-price-2min`
- `batch-reconstruct-silver`
- `benchmark-manifest`
- `close-benchmark-v1`
- `new-market-capture`
- `capture-new-market-tapes`
- tape recorder / replay / sweep commands in the SimTrader toolchain

### Registry / validation workflows

- hypothesis registry commands: register, status, experiment-init, experiment-run, validate, diff, summary

### Planned but not yet implemented

These commands appear in the roadmap but **do not exist in the repo yet**.
Do not try to call them or build features that depend on them without
implementing them first:

- `polytool autoresearch import-results` (Phase 4 deliverable)
- `polytool strategy-codify` (Phase 4 deliverable)
- Any `/api/` FastAPI endpoint (Phase 3 deliverable)

## Risk, Fees, and Live-Trading Guardrails

- Fee realism matters. Do not assume zero-friction profitability in replay or live code.
- The repo’s legacy research pipeline uses a 2% gross-profit fee model for some PnL workflows; Polymarket market-specific fee handling can differ. Be explicit about which fee model a component is using.
- Respect current platform rate limits and existing rate-limiter abstractions.
- Always preserve the kill-switch model.
- Inventory limits, daily loss caps, and max order/notional caps are not optional.
- Do not weaken risk defaults just to make a backtest or paper run look better.

## Known Windows Gotchas

- PowerShell encoding can break Unicode output. Prefer plain ASCII in logs and CLI output when possible.
- `cp1252` shells can mangle arrows and symbols.
- Docker Desktop + WSL2 permission behavior can differ from the real Windows user account.
- Path separator issues (`\\` vs `/`) show up in scripts and artifact paths.
- `.env` encoding and line endings can break parsing.
- When giving shell commands, prefer PowerShell-safe or clearly label Bash-only commands.

## Multi-Agent Awareness

Multiple AI coding agents may work on this repo in parallel or in sequence:
Claude Code, Codex, Gemini CLI, and Cline. Before starting any work session:

1. `git status` — check for uncommitted changes from other agents or manual edits.
2. `git log --oneline -5` — see recent commits you did not make.
3. `python -m polytool --help` — verify CLI still loads and command names match expectations.
4. Do not assume your last session's state is still current.

If you see unexpected changes, surface them to the operator before proceeding.
Do not silently revert or overwrite another agent's work.

## Quick Smoke Test (run after every change)

After any code change, run this minimum verification before declaring the task done:

```bash
python -m polytool --help              # CLI still loads, no import errors
python -m pytest tests/ -x -q --tb=short   # No regressions; stop at first failure
```

If infrastructure was touched:

```bash
docker compose ps                      # All services healthy
```

If ClickHouse tables were modified:

```bash
curl "http://localhost:8123/?query=SELECT%%201"   # ClickHouse responds
```

Do not skip the regression suite. Do not claim "all tests pass" without running them.
Report exact counts: "142 passed, 0 failed, 3 skipped."

## How Claude Code Should Work in This Repo

1. Read this file.
2. Read `docs/CURRENT_STATE.md`.
3. Read the governing doc(s) for the area being changed.
4. Inspect the relevant code paths before proposing refactors.
5. Keep scope tight: one work packet, one clear objective.
6. Update docs/dev log alongside code.
7. Run targeted tests and report exact results.

### When repo state is unclear

Do not guess. Inspect the actual repo, existing dev logs, or the current-state doc before editing.

### When roadmap and code differ

Prefer the document priority order. If the roadmap wants something but the higher-priority docs or implemented safety policy differ, stop and surface the mismatch.

## Don’t-Do List

- Do not commit secrets.
- Do not put private keys in code, docs, or git.
- Do not modify `docs/specs/` casually.
- Do not add Kafka.
- Do not build a new frontend pre-profit.
- Do not move core logic into FastAPI handlers.
- Do not replace ClickHouse with DuckDB or vice versa.
- Do not assume paper results imply live viability.
- Do not skip dev logs.
- Do not create sprawling refactors when an atomic change will do.
- Do not introduce live-capital shortcuts by weakening gate language.
- Do not scatter docs outside `docs/`.
- Do not invent repo structure or command syntax without checking.

## Default Session Output Expectations

A good Claude Code session in PolyTool should usually leave behind:

- code changes scoped to one objective,
- targeted tests,
- a dev log in `docs/dev_logs/`,
- any needed doc update under `docs/`,
- explicit open questions or blockers,
- no secrets, no undocumented behavior changes, and no silent scope creep.

## Codex Review Policy

This project uses the codex-plugin-cc plugin for automated code review via OpenAI Codex. Reviews are file-path driven, not discretionary.

- Mandatory — run /codex:adversarial-review before committing:
  Any file in execution/, kill_switch.py, risk_manager.py, rate_limiter.py,
  pair_engine.py, reference_feed.py, any code touching py_clob_client order placement, EIP-712 signing, or best bid/ask price extraction logic.
- Recommended — run /codex:review --background, log result:
  Strategy files, SimTrader core (broker_sim, replay_runner, tape_recorder),
  WebSocket connection/reconnection, ClickHouse write paths, market_discovery.py, autoresearch engine files.
- Skip — no review: Docs, config, tests, Grafana JSON, CLI formatting, artifacts.

Rules:

- Prefer --background to avoid blocking the session.
- If 5+ mandatory files changed, batch: /codex:adversarial-review --base main --background
- Do NOT use /codex:rescue unless the work packet explicitly delegates a task to Codex.
- Include a one-line Codex review summary in the dev log (tier, issues found, issues addressed).
