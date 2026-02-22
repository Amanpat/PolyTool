# Roadmap

This is the public roadmap for PolyTool. Each milestone is a self-contained
deliverable. Check the box when a milestone is fully shipped and verified.

---

## Milestone Checklist

### Roadmap 0 - Foundation [COMPLETE]

- [x] ClickHouse schema with ReplacingMergeTree tables
- [x] API ingest endpoints (trades, activity, positions, markets)
- [x] Grafana dashboards (User Trades, Strategy Detectors, PnL, Arb Feasibility)
- [x] `scan` CLI command with env-driven and flag-driven configuration
- [x] Strategy detectors (HOLDING_STYLE, DCA_LADDERING, MARKET_SELECTION_BIAS, COMPLETE_SET_ARBISH)
- [x] PnL computation (FIFO realized + MTM)
- [x] Arb feasibility analysis (dynamic fees + slippage)

**Acceptance**: All API endpoints return 200, Grafana dashboards render, scan
produces data in ClickHouse.

---

### Roadmap 1 - Examination Pipeline [COMPLETE]

- [x] `export-dossier` with resolution outcomes (WIN/LOSS/PROFIT_EXIT/LOSS_EXIT/PENDING/UNKNOWN_RESOLUTION)
- [x] `llm-bundle` generates evidence bundle + prompt template
- [x] `llm-save` stores report + manifest + auto-generates LLM_note
- [x] `examine` orchestrator (scan -> dossier -> bundle -> prompt)
- [x] User identity resolution (`polytool/user_context.py`: handle-first, strict mapping)
- [x] RAG index + query (vector via Chroma, lexical via FTS5, hybrid via RRF, rerank via cross-encoder)
- [x] `rag-eval` retrieval quality harness
- [x] `cache-source` with allowlist + TTL + robots.txt
- [x] MCP server (stdio, official `mcp` SDK)
- [x] Hypothesis schema v1 (`docs/specs/hypothesis_schema_v1.json`)
- [x] Strategy playbook v0 (`docs/STRATEGY_PLAYBOOK.md`)
- [x] Plan of Record documentation (`docs/PLAN_OF_RECORD.md`)

**Acceptance**: Roadmap 1 is complete when ALL of the following are true:

1. `python -m polytool scan --user "@handle"` resolves identity and completes
   end-to-end via the canonical CLI path.
2. A real examination run has produced a dossier, bundle, and prompt under the
   correct canonical paths (confirmed; does NOT need to be re-run).
3. `python -m polytool rag-query --hybrid --rerank` returns relevant results
   from the local index.
4. `python -m polytool llm-save` stores a report + manifest and writes an
   LLM_note.
5. The MCP server starts without protocol errors (`python -m polytool mcp`).
6. `pytest` passes with no regressions (known pre-existing failures excepted).
7. Pre-push guard passes (`python tools/guard/pre_push_guard.py`).
8. Plan of Record and supporting docs are committed and reviewed.

**Stop condition**: Do not proceed to Roadmap 2 until all 8 criteria are met.

---

### Roadmap 2 - Trust Artifacts & Scan Canonicalization [COMPLETE]

- [x] Canonical trust artifact emission from `python -m polytool scan`
- [x] `coverage_reconciliation_report.json` emitted with split UID metrics:
  `deterministic_trade_uid_coverage` and `fallback_uid_coverage`
- [x] `run_manifest.json` emitted with canonical `command_name = "scan"`
- [x] Empty-export diagnostics documented (`--debug-export`) and warnings surfaced
  when `positions_total = 0`
- [x] Docs updated to treat `scan` as canonical and `examine` as legacy

**Acceptance**: Scan runs consistently emit trust artifacts in the run root under
`artifacts/dossiers/users/.../<run_id>/`, and docs clearly describe interpretation
and troubleshooting.

**Handoff**: Reducing `UNKNOWN_RESOLUTION`, improving outcome coverage quality,
and closing missing PnL/fees gaps are owned by Roadmap 3.

---

### Roadmap 3 - Resolution Coverage [COMPLETE]

- [x] OnChainCTFProvider reading CTF payout state from Polygon RPC
- [x] SubgraphResolutionProvider as fallback via The Graph
- [x] 4-stage CachedResolutionProvider chain (ClickHouse -> OnChainCTF -> Subgraph -> Gamma)
- [x] Resolution dataclass with explicit `reason` field for traceability
- [x] Unit tests for all resolution providers with mocked RPC/subgraph
- [x] Reduce `UNKNOWN_RESOLUTION` rate for resolved markets to near-zero
- [x] Enrichment parity: `--enrich-resolutions` without explicit knobs achieves
  comparable coverage, or dataset mismatch is detected via `resolution_parity_debug.json`

**Acceptance**: `UNKNOWN_RESOLUTION` rate for markets that are objectively resolved
on-chain drops to < 5%. All resolution sources carry explicit `resolution_source`
and `reason` fields. Unit tests pass with mocked providers. No-knob enrichment
runs produce identical payloads to knobbed runs (or mismatch is reported).

**Evidence**: See `docs/roadmap3_completion.md` and trust-artifact run
`dd32ff26-b751-41a3-9aae-e9f59645040f` (2026-02-12).

**Kill condition**: If Gamma API coverage is already sufficient (>95% resolved
markets covered), defer on-chain provider to a future milestone.

---

### Roadmap 4 - Segment Analysis, Fees & Audit Hardening [COMPLETE]

- [x] Segment analysis with breakdowns by `entry_price_tier`, `market_type`, `league`, `sport`, `category`
- [x] `segment_analysis.json` artifact emitted alongside coverage report (Spec-0003, ADR-0006)
- [x] YAML-configurable entry price tiers (`polytool.yaml` `segment_config.entry_price_tiers`)
- [x] Fee estimation: 2 % on gross profit, configurable via `fee_config.profit_fee_rate` (ADR-0007)
- [x] Market metadata backfill (self-referential, no network call) with `market_metadata_coverage` in report
- [x] Category segmentation: Polymarket `category` field verbatim; absent â†’ `"Unknown"` (ADR-0009)
- [x] Category ingestion fix: LEFT JOIN `polymarket_tokens` in lifecycle query (was reporting 0 % coverage)
- [x] `audit-coverage` CLI: offline trust sanity, reads latest run artifacts, no ClickHouse/network (Spec-0007)
- [x] Scan auto-audit: every `scan` emits `audit_coverage_report.md` unconditionally (Spec-0008)
- [x] Audit default: all positions, not a fixed sample (ADR-0011)
- [x] History position-count fallback: use body rows when history row reports 0 (ADR-0010)
- [x] Root `README.md` with canonical quickstart runbook

**Acceptance**: All scan runs emit `segment_analysis.json` and `audit_coverage_report.md`.
`audit-coverage` runs fully offline. Category coverage is non-zero after the market
backfill pipeline has run. Schema version `1.4.0`.

**Evidence**: See `docs/pdr/PDR-ROADMAP4-WRAPUP.md` and ADRs 0006â€“0011.

---

### Roadmap 5 - CLV & Time/Price Context Signals [COMPLETE]

#### 5.0 Prerequisites

- [x] Confirm category coverage > 0 % post-backfill (regression from 4.6 confirmed fixed)
- [x] Default `market_type` moneyline rule for team-vs-team markets
- [x] Surface notional/size end-to-end (USDC position size in dossier and audit report)

#### 5.1 CLV Capture

- [x] Add `scan --compute-clv` enrichment stage (cache-first; explicit missingness)
- [x] Capture closing-line price snapshot per market before resolution
- [x] Compute CLV per position: `closing_price âˆ’ entry_price` (binary markets)
- [x] Store price snapshots in ClickHouse; populate at scan time when markets close
- [x] Report CLV coverage rate in `coverage_reconciliation_report`
- [x] Surface CLV in `segment_analysis.by_entry_price_tier` breakdown

#### 5.2 Time/Price Context

- [ ] Track price trajectory over hold period (from ClickHouse snapshot cadence)
- [ ] Minimal snapshot caching (TTL-based; no crawl depth)

#### 5.5 Batch-Run Harness + Hypothesis Leaderboard [COMPLETE]

- [x] `python -m polytool batch-run` command with multi-user input file support
- [x] Deterministic leaderboard artifacts: JSON + Markdown
- [x] Batch trust artifact: `batch_manifest.json` with output path/run-root traceability
- [x] Offline-safe tests via injected scan callable (no network / no ClickHouse)

**Acceptance**: `segment_analysis.json` includes `clv` for positions where snapshot
data is available. Coverage report includes CLV coverage rate. Positions without
closing-line data report `clv: null`, not missing.

**Kill condition**: If snapshot capture rate is < 30 % after 3 scan runs, document
the gap and defer CLV computation.

**Evidence**: See `docs/pdr/PDR-ROADMAP5-WRAPUP.md` and associated PDRs for CLV verification and prerequisite checks.

---

### Roadmap 6 - Source Caching & Crawl [NOT STARTED]

- [ ] Full robots.txt parsing (currently basic)
- [ ] Crawl depth support (follow links within domain)
- [ ] PDF/DOCX support for cached sources
- [ ] Automatic TTL-based refresh
- [ ] Cache eviction for expired content

**Acceptance**: `cache-source` can crawl 2 levels deep with full robots.txt
compliance. Expired content is automatically pruned.

**Kill condition**: If `cache-source` is sufficient for current research needs,
defer this milestone.

---

### Roadmap 7 - MCP Hardening [NOT STARTED]

- [ ] HTTP transport (currently stdio only)
- [ ] Authentication for multi-user scenarios
- [ ] Resource endpoints for direct file access
- [ ] Streaming for large responses

**Acceptance**: MCP works via HTTP transport with Claude Desktop. Auth prevents
unauthorized access when exposed on network.

**Kill condition**: If manual workflow remains sufficient, defer indefinitely.

---

### Roadmap 8 - Multi-User & Comparison [NOT STARTED]

- [ ] Compare users side-by-side
- [ ] Portfolio-level aggregation
- [ ] User clustering by strategy similarity

**Acceptance**: Two users can be compared in a single Grafana dashboard or CLI
report.

**Kill condition**: Single-user analysis is sufficient for research needs.

---

### Roadmap 9 - CLI & Dashboard Polish [NOT STARTED]

- [ ] Progress bars for long operations
- [ ] JSON output mode for all commands
- [ ] Tab completion for bash/zsh
- [ ] User comparison dashboard
- [ ] Category breakdown panel
- [ ] Win rate trend over time
- [ ] Position lifecycle visualization

**Acceptance**: All CLI commands support `--json` output. Grafana has category
breakdown and lifecycle panels.

**Kill condition**: Current UX is sufficient for research workflows.

---

### Roadmap 10 - CI & Testing [NOT STARTED]

- [ ] Integration tests for scan-first workflow (legacy examine smoke kept separate)
- [ ] Mock ClickHouse for CI (no Docker dependency)
- [ ] Property-based tests for fee calculation
- [ ] RAG index load testing

**Acceptance**: CI pipeline runs full test suite without Docker. Fee property
tests cover edge cases.

**Kill condition**: Test suite is comprehensive enough for current codebase size.

---

## Kill / Stop Conditions (Global)

These guard against feature creep. Do NOT start the next milestone until the
current one is fully shipped.

- **No backtesting** until Roadmap 5 CLV and context signal capture is shipped.
- **No real-time monitoring** (out of scope entirely; see TODO.md).
- **No external LLM API calls** (remains local-only forever).
- **No mobile app / web UI** (out of scope entirely).
- **No multi-tenant hosting** (local-first only).
- If a milestone is blocked by an external dependency (API change, SDK bug),
  park it and document the blocker in TODO.md rather than working around it.

---

## Deprecation: polyttool shim

The `polyttool` backward-compatibility shim (double-t typo) will be removed
after version 0.2.0. Until then, `python -m polyttool` still works but prints
a deprecation warning. All new docs and scripts must use `python -m polytool`.
See [ADR-0001](adr/ADR-0001-cli-and-module-rename.md) for details.

