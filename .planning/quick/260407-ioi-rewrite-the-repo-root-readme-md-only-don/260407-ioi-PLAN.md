---
phase: quick-260407-ioi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - README.md
  - docs/dev_logs/2026-04-07_root_readme_refresh.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "A new operator reading only README.md can understand what PolyTool is, what it is not, and what is actually shipped today"
    - "Every user-facing CLI command from polytool/__main__.py appears in the README, grouped logically with a short description"
    - "README contains copy-pasteable install, config, and workflow commands that work on a fresh clone"
    - "No stale or aspirational language presents unshipped features as available"
    - "Links to deeper docs (OPERATOR_QUICKSTART, CURRENT_STATE, README_SIMTRADER, INDEX) are present"
  artifacts:
    - path: "README.md"
      provides: "Complete operator-facing root README"
      min_lines: 200
    - path: "docs/dev_logs/2026-04-07_root_readme_refresh.md"
      provides: "Dev log documenting the rewrite decisions and test results"
      min_lines: 30
  key_links:
    - from: "README.md"
      to: "docs/OPERATOR_QUICKSTART.md"
      via: "markdown link"
      pattern: "OPERATOR_QUICKSTART"
    - from: "README.md"
      to: "docs/CURRENT_STATE.md"
      via: "markdown link"
      pattern: "CURRENT_STATE"
---

<objective>
Rewrite the repo root README.md to be a clear, accurate, complete operator reference
based on current shipped repo truth. The current README is ~900 lines with duplicate
sections (two quickstarts, two command references, stale gate status from March 2026),
aspirational language about Telegram alerts and alpha factory that are not shipped, and
a SimTrader Studio user guide that duplicates docs/README_SIMTRADER.md.

Purpose: A new operator should be able to read README.md and understand what PolyTool
is, install it, configure it, see every CLI command, and know where to go next --
without being misled about what is shipped vs. planned.

Output: Rewritten README.md + mandatory dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@README.md
@polytool/__main__.py
@pyproject.toml
@docker-compose.yml
@.env.example
@docs/OPERATOR_QUICKSTART.md
@docs/CURRENT_STATE.md
@docs/INDEX.md
@docs/README_SIMTRADER.md
@docs/PLAN_OF_RECORD.md
@docs/ARCHITECTURE.md
@CLAUDE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Inventory CLI commands and verify current truth</name>
  <files>docs/dev_logs/2026-04-07_root_readme_refresh.md</files>
  <action>
Run `python -m polytool --help` and capture the full output. This is the authoritative
CLI command inventory. Cross-reference against `polytool/__main__.py`
`_COMMAND_HANDLER_NAMES` dict and the special-cased commands (rag-refresh, examine,
cache-source, mcp) to produce a complete, grouped command list.

Also run `python -m pytest -q --tb=short` to capture current test count as baseline
evidence.

Then create the dev log at `docs/dev_logs/2026-04-07_root_readme_refresh.md` with:
- Files changed and why
- Command inventory source of truth used (--help output + __main__.py code inspection)
- Commands run + output summaries
- Test results (pass/fail counts)
- Decisions made (what was removed from old README and why)
- Any conflicts found between README and governing docs
- Note: Telegram alerts section removed (not shipped -- Discord alerting is shipped but
  optional and documented in OPERATOR_QUICKSTART). Note: "Alpha Factory" section removed
  (marketing language, not a shipped feature name). Note: SimTrader Studio inline guide
  removed (duplicates docs/README_SIMTRADER.md). Note: duplicate quickstart sections
  consolidated. Note: stale gate status dates removed in favor of directing operators
  to run `gate_status.py` for current truth.
  </action>
  <verify>
    <automated>python -m polytool --help</automated>
  </verify>
  <done>
Dev log exists at docs/dev_logs/2026-04-07_root_readme_refresh.md with CLI inventory,
test results, and decisions documented.
  </done>
</task>

<task type="auto">
  <name>Task 2: Rewrite README.md from scratch</name>
  <files>README.md</files>
  <action>
Delete the entire current README.md content and write a new one from scratch. The new
README must include ALL of the following sections, in this order:

**1. Header and one-paragraph overview**
- What PolyTool is in plain English (local-first Polymarket research, simulation, and
  execution toolchain)
- What it is NOT (not a hosted service, not a signal provider, not live-ready without
  passing validation gates)

**2. What is shipped today (honest current state)**
- Research pipeline (Track B): wallet scanning, alpha distillation, hypothesis registry,
  RAG, dossier/bundle evidence exports
- SimTrader (Track A): tape recording, replay, shadow mode, sweeps, batch, strategies
  (market_maker_v0, market_maker_v1, binary_complement_arb, copy_wallet_replay), Studio
  browser UI
- Market selection engine
- Crypto pair bot (Track 2 / Phase 1A): scanning, paper runs, backtesting, reporting,
  market watching -- standalone, not yet live-deployed
- Research Intelligence System (RIS): evaluation, ingestion, prechecking, claims
  extraction, scheduling, reporting, health monitoring
- Data import: DuckDB historical reads, Silver tape reconstruction, benchmark manifest
- Execution layer: kill switch, rate limiter, risk manager, live executor -- all gated,
  dry-run by default
- Infrastructure: ClickHouse, Grafana dashboards, Docker Compose stack
- Validation gates: Gate 1 PASSED, Gate 2 FAILED (14%, need 70%), Gate 3 BLOCKED, Gate 4
  PASSED. Direct operators to `python tools/gates/gate_status.py` for current truth
  rather than embedding a stale date.

**3. Prerequisites**
- Python 3.10+ (pyproject.toml says >=3.10)
- Docker Desktop (for ClickHouse + Grafana)
- Git

**4. Installation**
- Clone, venv, `pip install -e ".[all]"` for everything or `pip install -e ".[dev]"` for
  core + tests. List optional dependency groups from pyproject.toml: rag, mcp, simtrader,
  studio, dev, historical, historical-import, live, ris, all.
- `python -m polytool --help` to verify

**5. Configuration**
- Copy `.env.example` to `.env`, set CLICKHOUSE_PASSWORD at minimum
- `docker compose up -d` to start ClickHouse + Grafana + API + migrations
- Mention optional profiles: `--profile cli`, `--profile pair-bot`, `--profile ris-n8n`
- Bootstrap private dirs: `tools/bootstrap_kb.ps1` or `tools/bootstrap_kb.sh`
- Run tests: `python -m pytest -q --tb=short`

**6. Quick workflows (copy-pasteable)**
- Research loop: wallet-scan -> alpha-distill -> hypothesis-register
- Single user examination: scan -> llm-bundle -> llm-save
- RAG: rag-refresh -> rag-query
- Market scanning: market-scan
- SimTrader dev loop: quickrun/shadow -> browse
- RIS precheck before new work

**7. Complete CLI command reference**
Group ALL commands from __main__.py print_usage() into a table format with command name
and short description. Use the EXACT groupings from print_usage():
- Research Loop (Track B): wallet-scan, alpha-distill, hypothesis-register,
  hypothesis-status, hypothesis-diff, hypothesis-summary, experiment-init, experiment-run,
  hypothesis-validate
- Analysis and Evidence: scan, batch-run, audit-coverage, export-dossier,
  export-clickhouse
- RAG and Knowledge: rag-refresh, rag-index, rag-query, rag-run, rag-eval, cache-source,
  llm-bundle, llm-save
- Research Intelligence (RIS): research-eval, research-precheck, research-ingest,
  research-seed, research-benchmark, research-calibration, research-extract-claims,
  research-acquire, research-report, research-scheduler, research-stats, research-health,
  research-dossier-extract, research-register-hypothesis, research-record-outcome
- Crypto Pair Bot (Track 2): crypto-pair-scan, crypto-pair-run, crypto-pair-backtest,
  crypto-pair-report, crypto-pair-watch, crypto-pair-await-soak,
  crypto-pair-seed-demo-events
- SimTrader / Execution (Track A): simtrader (with subcommands: quickrun, shadow, run,
  sweep, batch, record, tape-info, replay, report, browse, clean, diff, live, kill,
  studio), market-scan, scan-gate2-candidates, prepare-gate2, watch-arb-candidates,
  tape-manifest, gate2-preflight, make-session-pack
- Data Import: import-historical, smoke-historical, fetch-price-2min,
  reconstruct-silver, batch-reconstruct-silver, benchmark-manifest, new-market-capture,
  capture-new-market-tapes, close-benchmark-v1, summarize-gap-fill
- Integrations and Utilities: mcp, examine (legacy), agent-run (internal)

**8. Operator surfaces**
- CLI: `python -m polytool <command>` (primary interface)
- Grafana: http://localhost:3000 (analytics dashboards after data ingestion)
- SimTrader Studio: `python -m polytool simtrader studio --open` (browser UI for
  sessions, tapes, reports, OnDemand replay)
- MCP: `python -m polytool mcp` (Claude Desktop integration, optional)
- n8n (optional, scoped RIS pilot): `docker compose --profile ris-n8n up -d n8n`

**9. Project structure (brief)**
- `polytool/` -- package root and CLI entry
- `packages/polymarket/` -- core analytics, SimTrader, execution, strategies, RAG
- `tools/cli/` -- CLI command implementations
- `services/api/` -- FastAPI service
- `infra/` -- ClickHouse schemas, Grafana provisioning
- `docs/` -- all documentation
- `tests/` -- test suite
- `artifacts/` and `kb/` -- private local data (gitignored)
- `config/` -- benchmark manifests and strategy config

**10. Deeper documentation links**
- docs/OPERATOR_QUICKSTART.md -- end-to-end operator guide
- docs/CURRENT_STATE.md -- detailed current state
- docs/README_SIMTRADER.md -- SimTrader operator guide
- docs/INDEX.md -- full documentation index
- docs/PLAN_OF_RECORD.md -- mission, constraints, data gaps
- docs/ARCHITECTURE.md -- components and data flow

**11. Security reminders**
- Never commit .env, kb/, artifacts/
- Use dedicated trading wallet
- Kill switch: `python -m polytool simtrader kill`
- No live capital before all gates pass

**12. License**
MIT (from pyproject.toml)

IMPORTANT CONSTRAINTS FOR THE README:
- Do NOT present Gate 2 as passed or imminent. It FAILED at 14%.
- Do NOT mention Telegram alerts (not shipped; Discord is the shipped alerting path).
- Do NOT use "Alpha Factory" as a product name (it is not a shipped feature).
- Do NOT present Stage 1/Stage 2 live trading as a near-term reality.
- Do NOT duplicate the full SimTrader Studio user guide (link to docs instead).
- Do NOT include the old "Historical Quick Status" archive block.
- Do NOT duplicate the full gate walkthrough (link to OPERATOR_QUICKSTART instead).
- Do NOT use marketing language like "complete system for discovering profitable trading
  strategies."
- DO include an explicit "What is NOT shipped" or "Experimental / Gated" section so
  operators know what requires caution.
- DO make every code block copy-pasteable.
- DO use `python -m polytool` as the canonical invocation (not bare `polytool`).
  </action>
  <verify>
    <automated>python -m polytool --help && python -m pytest -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
README.md is rewritten with all sections above. Every CLI command from __main__.py
print_usage() appears in the command reference. No stale or aspirational language remains.
Copy-pasteable commands work. Tests still pass. Dev log is complete.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries apply -- this is a documentation-only change.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | Information Disclosure | README.md | accept | README is public. No secrets, no private data, no wallet addresses. .env.example uses placeholders only. |
</threat_model>

<verification>
1. `python -m polytool --help` exits 0 and the command list in README matches its output
2. `python -m pytest -q --tb=short` passes with no new failures
3. README.md has no references to Telegram alerts, "Alpha Factory", or stale gate dates
4. Every command from `_COMMAND_HANDLER_NAMES` in __main__.py appears in the README
5. Links to docs/OPERATOR_QUICKSTART.md, docs/CURRENT_STATE.md, docs/README_SIMTRADER.md,
   docs/INDEX.md are present
</verification>

<success_criteria>
- README.md is a single, non-duplicated, accurate document
- All 60+ CLI commands are listed with short descriptions
- New operator can install, configure, and use PolyTool from README alone
- No code, tests, configs, or other docs were modified
- Dev log exists with full audit trail
</success_criteria>

<output>
After completion, create `.planning/quick/260407-ioi-rewrite-the-repo-root-readme-md-only-don/260407-ioi-SUMMARY.md`
</output>
