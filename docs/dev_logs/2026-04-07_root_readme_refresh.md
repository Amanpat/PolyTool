# Dev Log: Root README Refresh (2026-04-07)

**Task:** Rewrite root `README.md` from scratch to accurately reflect shipped repo truth.
**Quick task ID:** quick-260407-ioi

---

## Files Changed

| File | Action | Reason |
|------|--------|--------|
| `README.md` | Full rewrite | Old README was ~900 lines with duplicated sections, stale gate status, aspirational language, and unshipped feature descriptions |
| `docs/dev_logs/2026-04-07_root_readme_refresh.md` | Created (this file) | Audit trail of decisions, CLI inventory, and test results |

No code, tests, configs, or other docs were modified.

---

## Command Inventory

The authoritative CLI command list was obtained from two sources in priority order:

1. `python -m polytool --help` — live running output from the installed package
2. `polytool/__main__.py` — `_COMMAND_HANDLER_NAMES` dict + special-cased commands

### Special-cased commands (not in `_COMMAND_HANDLER_NAMES`):

- `rag-refresh` — alias for `rag-index --rebuild` (hardcoded in `__main__.py`)
- `examine` — legacy, loaded via `tools.cli.examine` try/except
- `cache-source` — loaded via `tools.cli.cache_source` try/except
- `mcp` — loaded via `tools.cli.mcp_server` try/except

### Complete CLI command inventory (confirmed from --help output):

**Research Loop (Track B):** wallet-scan, alpha-distill, hypothesis-register, hypothesis-status, hypothesis-diff, hypothesis-summary, experiment-init, experiment-run, hypothesis-validate

**Analysis and Evidence:** scan, batch-run, audit-coverage, export-dossier, export-clickhouse

**RAG and Knowledge:** rag-refresh, rag-index, rag-query, rag-run, rag-eval, cache-source, llm-bundle, llm-save

**Research Intelligence (RIS):** research-eval, research-precheck, research-ingest, research-seed, research-benchmark, research-calibration, research-extract-claims, research-acquire, research-report, research-scheduler, research-stats, research-health, research-dossier-extract, research-register-hypothesis, research-record-outcome

**Crypto Pair Bot (Track 2 / Phase 1A):** crypto-pair-scan, crypto-pair-run, crypto-pair-backtest, crypto-pair-report, crypto-pair-watch, crypto-pair-await-soak, crypto-pair-seed-demo-events

**SimTrader / Execution (Track A, gated):** simtrader (with subcommands: quickrun, shadow, run, sweep, batch, record, tape-info, replay, report, browse, clean, diff, live, kill, studio), market-scan, scan-gate2-candidates, prepare-gate2, watch-arb-candidates, tape-manifest, gate2-preflight, make-session-pack

**Data Import:** import-historical, smoke-historical, fetch-price-2min, reconstruct-silver, batch-reconstruct-silver, benchmark-manifest, new-market-capture, capture-new-market-tapes, close-benchmark-v1, summarize-gap-fill

**Integrations and Utilities:** mcp, examine, agent-run

Total: 63 CLI commands (including the simtrader alias).

---

## Test Results

Command: `python -m pytest -q --tb=short`

Result: **3695 passed, 3 deselected, 25 warnings** in 111.58s

No new failures introduced. Baseline confirmed before and after README rewrite (documentation-only change; no code modified).

---

## Decisions Made

### What was removed from the old README and why

| Removed section | Reason |
|----------------|--------|
| Duplicate "Current Status" blocks (March 2026 date) | Stale; README now directs operators to `python tools/gates/gate_status.py` and `docs/CURRENT_STATE.md` |
| "Historical Quick Status" archive block (as of 2026-03-05) | Milestone history belongs in dev logs, not README |
| Opening claim "complete system for discovering profitable trading strategies" | Marketing language; not accurate (Gate 2 FAILED at 14%) |
| "Gate 3 (Shadow) — 90% complete" status | Stale and inaccurate; Gate 3 is BLOCKED behind Gate 2 |
| Inline full SimTrader Studio user guide | Duplicates `docs/README_SIMTRADER.md`; now linked instead |
| Telegram alerts references | Not shipped; Discord alerting is the shipped path (documented in OPERATOR_QUICKSTART) |
| "Alpha Factory" as a product section name | Not a shipped feature name; aspirational marketing language |
| "Stage 1/Stage 2 live trading" as near-term | Gate 2 FAILED; premature to present live stages as accessible |
| Duplicate quickstart sections (two separate Step 1.x blocks with different install steps) | Consolidated into a single install flow |
| Stale "Gate 2 is not passed yet" language (March 2026 context) | Updated to accurate: Gate 2 FAILED at 14% (7/50 tapes positive), as recorded in `docs/CURRENT_STATE.md` |
| `polytool.example.yaml` config step | File does not appear in repo; `.env.example` is the actual config file |
| `pip install py-clob-client` as a separate step | Now part of `pip install -e ".[live]"` optional dep group |
| Python 3.11+ requirement | `pyproject.toml` requires >=3.10; corrected to 3.10+ |

### What was added or clarified

- Explicit "What PolyTool is NOT" section upfront
- Honest validation gate status (Gate 1 PASSED, Gate 2 FAILED at 14%, Gate 3 BLOCKED, Gate 4 PASSED)
- "Experimental / Gated" section noting what requires caution before use
- Optional dependency groups from `pyproject.toml`: rag, mcp, simtrader, studio, dev, historical, historical-import, live, ris, all
- Discord alerting as the shipped notification path (DISCORD_WEBHOOK_URL in .env)
- All 63 CLI commands in a grouped table matching --help output groupings
- Docker Compose profiles: cli, pair-bot, ris-n8n documented
- `python tools/gates/gate_status.py` as the live gate status check
- `python -m polytool` as canonical invocation throughout (not bare `polytool`)

---

## Conflicts Found Between Old README and Governing Docs

| Conflict | Old README claim | Governing doc truth | Resolution |
|----------|-----------------|---------------------|------------|
| Gate 2 status | "Gate 2 not passed yet, tooling complete" | `docs/CURRENT_STATE.md`: Gate 2 FAILED (7/50 = 14%) | README updated to reflect FAILED status |
| Gate 3 status | "90% complete" | `docs/CURRENT_STATE.md`: BLOCKED behind Gate 2 | README updated to BLOCKED |
| Python version | "Python 3.11+" in install steps | `pyproject.toml`: requires-python = ">=3.10" | README corrected to 3.10+ |
| Gate 1 status | Listed as "Open" in old archive block | `docs/CURRENT_STATE.md`: Gate 1 PASSED | README reflects PASSED |
| Config file | `polytool.example.yaml` | Actual repo has `.env.example` | README uses `.env.example` |
| Install command | `pip install -e ".[dev]"` described as "everything" | `pyproject.toml`: `[all]` group includes rag,mcp,simtrader,studio,dev,historical,historical-import,live | README clarifies both options |

All conflicts documented here. No silent choices made.

---

## Codex Review Note

Scope: Documentation-only change. No mandatory files (execution/, kill_switch.py, risk_manager.py, etc.) touched. Codex adversarial review: SKIP (docs category per CLAUDE.md policy).
