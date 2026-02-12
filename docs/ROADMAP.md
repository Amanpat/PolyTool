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

### Roadmap 3 - Resolution Coverage [IN PROGRESS]

- [x] OnChainCTFProvider reading CTF payout state from Polygon RPC
- [x] SubgraphResolutionProvider as fallback via The Graph
- [x] 4-stage CachedResolutionProvider chain (ClickHouse -> OnChainCTF -> Subgraph -> Gamma)
- [x] Resolution dataclass with explicit `reason` field for traceability
- [x] Unit tests for all resolution providers with mocked RPC/subgraph
- [ ] Reduce `UNKNOWN_RESOLUTION` rate for resolved markets to near-zero

**Acceptance**: `UNKNOWN_RESOLUTION` rate for markets that are objectively resolved
on-chain drops to < 5%. All resolution sources carry explicit `resolution_source`
and `reason` fields. Unit tests pass with mocked providers.

**Kill condition**: If Gamma API coverage is already sufficient (>95% resolved
markets covered), defer on-chain provider to a future milestone.

---

### Roadmap 4 - Hypothesis Validation Loop [NOT STARTED]

- [ ] Reduce `UNKNOWN_RESOLUTION` by improving resolution coverage and settlement enrichment
- [ ] Improve outcome coverage reliability for held-to-resolution classification
- [ ] Reduce `missing_realized_pnl_count` and `fees_source = unknown` rates where data allows
- [ ] Automatic schema validation on `llm-save` (reject non-conforming JSON)
- [ ] Summary bullet extraction from report for LLM_notes
- [ ] Hypothesis diff comparison across runs (detect claim drift)
- [ ] Falsification test harness (automated threshold checks)

**Acceptance**: `llm-save` rejects invalid hypothesis.json. Hypothesis diff
between two runs produces a readable changelog. Coverage quality trends down for
`UNKNOWN_RESOLUTION` and other known gap metrics.

**Kill condition**: Do not start backtesting until this milestone is shipped.

---

### Roadmap 5 - Source Caching & Crawl [NOT STARTED]

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

### Roadmap 6 - MCP Hardening [NOT STARTED]

- [ ] HTTP transport (currently stdio only)
- [ ] Authentication for multi-user scenarios
- [ ] Resource endpoints for direct file access
- [ ] Streaming for large responses

**Acceptance**: MCP works via HTTP transport with Claude Desktop. Auth prevents
unauthorized access when exposed on network.

**Kill condition**: If manual workflow remains sufficient, defer indefinitely.

---

### Roadmap 7 - Multi-User & Comparison [NOT STARTED]

- [ ] Compare users side-by-side
- [ ] Portfolio-level aggregation
- [ ] User clustering by strategy similarity

**Acceptance**: Two users can be compared in a single Grafana dashboard or CLI
report.

**Kill condition**: Single-user analysis is sufficient for research needs.

---

### Roadmap 8 - CLI & Dashboard Polish [NOT STARTED]

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

### Roadmap 9 - CI & Testing [NOT STARTED]

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

- **No backtesting** until Roadmap 4 hypothesis validation is done.
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
