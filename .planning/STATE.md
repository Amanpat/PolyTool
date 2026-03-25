# Project State

## Current Position
- **Milestone:** v1.0 — Core RAG Pipeline
- **Current Phase:** 5 (Reranking)
- **Status:** In Progress

Last activity: 2026-03-25 - Completed quick-025: Grafana no-data diagnostics — confirmed zero-row root cause (infrastructure intact), added noDataText to all 12 dashboard panels, added operator remediation guide to feature doc. Market availability remains the sole blocker for Track 2 data.

## Recent Progress
- Quick-002: Resolution provider chain (OnChainCTF + Subgraph + cascade), 13 new tests, ROADMAP renumbered (217 tests passing)
- Quick-001: Cross-encoder reranking with hybrid+rerank eval mode (101 tests passing)
- Phase 4.3: Offline RAG eval harness implemented with 20 passing tests
- Phase 4.2: Index reconcile mode for stale chunk cleanup
- Phase 4.1: Hybrid retrieval with FTS5 + RRF

## Key Decisions
- Chroma for vector store, SQLite FTS5 for lexical
- RRF k=60 (standard paper value) for fusion
- SHA256-based deterministic IDs
- Privacy-scoped filtering at both vector and lexical layers
- Cross-encoder reranking: opt-in, top_n=50 default, model cache via SENTENCE_TRANSFORMERS_HOME
- Default rerank model: cross-encoder/ms-marco-MiniLM-L-6-v2 (lightweight, proven)
- Resolution provider chain: ClickHouse -> OnChainCTF -> Subgraph -> Gamma (authoritative-first)
- No web3.py: raw JSON-RPC for on-chain reads (lighter dependency footprint)
- Resolution reason field for debugging/traceability
- Roadmap renumbering: Resolution Coverage as Roadmap 3 (data quality before analysis quality)
- Dual CLV variants: settlement sub-ladder (onchain_resolved_at only), pre-event sub-ladder (gamma closedTime/endDate/umaEndDate)
- Hypothesis ranking cascade: pre_event notional-weighted > settlement notional-weighted > combined > count-weighted fallback
- Roadmap 5 closed [COMPLETE]: CLV infra shipped but 0% coverage triggered kill condition; batch-run harness shipped fully; ROADMAP.md updated
- Mark 5.0 category [x] when code ships even if runtime coverage is 0% (upstream data gap, not code defect)
- Robust stats: sort-based median/trimmed-mean/p25/p75 with MAX_ROBUST_VALUES=500 cap; beat_close is required positional arg in _accumulate_segment_bucket
- quickrun --list-candidates: exits before normal flow; warning (not error) when combined with --market
- quickrun --exclude-market: repeatable; exclude_slugs persisted as list in quickrun_context for JSON serializability
- SimTrader Studio: FastAPI + vanilla HTML+JS, optional dep group [studio], port 8765, subprocess-based command dispatch with allowlist
- OnDemand engine: PortfolioLedger re-instantiated per get_state() call (snapshot pattern); ZERO_LATENCY broker for interactive sessions; session manager stored as closure in create_app()
- OnDemand UI: vanilla JS tab in index.html; odRenderState() shows first-asset depth only; escHtml() reused for XSS-safe order table rendering
- SimTrader Studio --host: default 127.0.0.1, 0.0.0.0 for Docker; --open has no effect inside Docker containers (help text caveat)
- Studio workspace monitor: /api/sessions/{id}/monitor reads only run_manifest+summary (no JSONL rows); wsMonitorFetching Set guards in-flight; 1s interval re-renders from cache; dual interval (1s monitor, 3s full state); openSimulationArtifact() navigates simulation tab from workspace card

- BacktestObservation includes yes/no_accumulated_size (default 0.0) to allow partial-pair state simulation; soft_rule_blocked_all_legs is unreachable in stateless replay due to fair_yes+fair_no=1 complement constraint
- BacktestHarness is pure function: no network, no ClickHouse; CLI layer handles all artifact I/O
- sink_flush_mode lives on CryptoPairRunnerSettings (not the sink) — runner owns when/how often sink is called
- write_event() is a distinct method on sink (not just repeated calls to write_events()) so consecutive-fail guard applies per-event in streaming mode
- RunSummaryEvent always in finalization write_events() batch because it requires the final run_summary dict not available until after run loop
- _streamed_transition_ids dedup uses composite key (not event_id) to match finalization list which reconstructs from raw transition dicts
- crypto-pair-watch: injectable _sleep_fn/_check_fn for offline testing; one-shot exits 0 always; watch exits 0/1 (found/timeout); --symbol/--duration reserved in v0

### Blockers/Concerns
- Track 2 market availability: Polymarket has no active BTC/ETH/SOL 5m/15m binary pair markets as of 2026-03-25. Coinbase feed unblock is confirmed; waiting for market schedule to rotate these markets back in. Use `crypto-pair-watch --watch` to poll.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 001 | Offline reranking for hybrid retrieval (opt-in) | 2026-02-03 | 2bffaed | [001-offline-rerank-hybrid-retrieval](./quick/001-offline-rerank-hybrid-retrieval/) |
| 002 | Resolution provider chain (OnChainCTF + Subgraph) | 2026-02-10 | 81f17d7 | [002-resolution-provider-chain](./quick/002-resolution-provider-chain/) |
| 004 | hypothesis_candidates.json artifact + Hypothesis Candidates markdown section | 2026-02-20 | eaa39f2 | [4-build-hypothesis-candidates-json-artifac](./quick/4-build-hypothesis-candidates-json-artifac/) |
| 005 | Fix notional-weighted metrics null by normalizing position_notional_usd in scan.py | 2026-02-20 | b592d94 | [5-fix-notional-weighted-metrics-null-by-no](./quick/5-fix-notional-weighted-metrics-null-by-no/) |
| 006 | Dual CLV variants (clv_settlement + clv_pre_event) with hypothesis ranking preference | 2026-02-20 | 0407007 | [6-add-dual-clv-variants-clv-settlement-anc](./quick/6-add-dual-clv-variants-clv-settlement-anc/) |
| 007 | Robust segment stats (median, trimmed mean, IQR) for clv_pct and entry_drift_pct | 2026-02-20 | 10f78c2 | [7-add-robust-segment-stats-median-trimmed-](./quick/7-add-robust-segment-stats-median-trimmed-/) |
| 008 | batch-run --aggregate-only, --run-roots, --workers N features | 2026-02-20 | d672fc3 | [8-batch-run-aggregate-only-and-workers-n-f](./quick/8-batch-run-aggregate-only-and-workers-n-f/) |
| 009 | Roadmap 5 wrap-up PDR + mark ROADMAP.md [COMPLETE] | 2026-02-20 | 4e84a36 | [9-roadmap-5-wrap-up-pdr-and-mark-complete-](./quick/9-roadmap-5-wrap-up-pdr-and-mark-complete-/) |
| 010 | quickrun --list-candidates N + --exclude-market SLUG (9 new tests, 56->65) | 2026-02-25 | b95f20b | [10-quickrun-list-candidates-and-exclude-mar](./quick/10-quickrun-list-candidates-and-exclude-mar/) |
| 011 | Sync public docs with shipped simtrader features (probe, clean, diff) | 2026-02-25 | 7de79c4 | [11-sync-public-docs-with-current-simtrader-](./quick/11-sync-public-docs-with-current-simtrader-/) |
| 012 | SimTrader Studio MVP: local FastAPI web UI via `simtrader studio --open` | 2026-02-26 | c614630 | [12-implement-simtrader-studio-mvp-local-fas](./quick/12-implement-simtrader-studio-mvp-local-fas/) |
| 013 | SimTrader Studio OnDemand tab: manual trading sim, L2Book depth, OnDemandSession, 8 API routes, UI, 9 tests | 2026-02-26 | 9913b18 | [13-add-simtrader-studio-ondemand-tab-manual](./quick/13-add-simtrader-studio-ondemand-tab-manual/) |
| 014 | --host flag for simtrader studio Docker binding: help text update, 2 parser tests, README Docker note | 2026-02-26 | 92e4f8e | [14-add-host-flag-to-simtrader-studio-for-do](./quick/14-add-host-flag-to-simtrader-studio-for-do/) |
| 015 | Fix batch time_budget StopIteration: check budget before fetch, wrap next() in try/except StopIteration | 2026-02-26 | d3f2b33 | [15-fix-batch-time-budget-stopiteration-in-d](./quick/15-fix-batch-time-budget-stopiteration-in-d/) |
| 016 | Studio workspace grid real-time monitor: /api/sessions/{id}/monitor, 1s refresh, enhanced session/artifact/ondemand cards | 2026-03-03 | c3f5e73 | [16-studio-workspace-grid-real-time-monitor-](./quick/16-studio-workspace-grid-real-time-monitor-/) |
| 017 | Update README.md with SimTrader Studio user guide: launch, 8-tab reference, workflows A/B/C, troubleshooting, doc links | 2026-03-04 | 76b398e | [17-update-readme-md-with-simtrader-studio-u](./quick/17-update-readme-md-with-simtrader-studio-u/) |
| 018 | Rebuild repo authority docs around Roadmap v5: 6 docs updated, benchmark closure recorded, Track 2 standalone noted | 2026-03-21 | d6a33d1 | [18-rebuild-repo-authority-docs-around-roadm](./quick/18-rebuild-repo-authority-docs-around-roadm/) |
| 019 | Deterministic backtest harness for Phase 1A crypto-pair bot: BacktestHarness, CLI crypto-pair-backtest, 22 tests, feature doc, dev log | 2026-03-23 | c1a57de | [19-add-phase-1a-backtest-history-harness-fo](./quick/19-add-phase-1a-backtest-history-harness-fo/) |
| 020 | Wire paper runner into dormant ClickHouse Track 2 event sink: batch-at-finalization, soft-fail, sink_write_result in manifest, 5 tests, feature doc, dev log | 2026-03-23 | ba8da25 | [20-wire-paper-runner-into-dormant-event-sin](./quick/20-wire-paper-runner-into-dormant-event-sin/) |
| 021 | Add incremental mid-run event emission to paper runner sink: streaming flush mode, write_event() + consecutive-fail guard, sink_flush_mode field, --sink-streaming CLI flag, 8 new offline tests, dedup guard for safety transitions | 2026-03-24 | ddca74b | [21-add-incremental-mid-run-event-emission-f](./quick/21-add-incremental-mid-run-event-emission-f/) |
| 022 | Phase 1A first real paper soak: smoke soak ran cleanly but Binance HTTP 451 geo-restriction blocked all reference feed data; 24h soak intentionally skipped; rubric verdict RERUN; dev log + CURRENT_STATE.md blocker note | 2026-03-25 | e32cc0c | [22-execute-the-first-real-phase-1a-crypto-p](./quick/22-execute-the-first-real-phase-1a-crypto-p/) |
| 023 | Coinbase smoke soak rerun: Coinbase feed confirmed working (--reference-feed-provider coinbase accepted), BLOCKED due to Polymarket having zero active BTC/ETH/SOL 5m/15m markets; blocker shifted from reference feed to market availability | 2026-03-25 | 1c73cec | [23-execute-the-coinbase-based-rerun-smoke-s](./quick/23-execute-the-coinbase-based-rerun-smoke-s/) |
| 024 | Market availability watcher for Track 2: crypto-pair-watch command with one-shot and watch modes, AvailabilitySummary, deterministic artifact bundle (watch_manifest.json, availability_summary.json, .md), 20 offline tests, feature doc, dev log | 2026-03-25 | 6c2c0e9 | [24-implement-track-2-market-availability-wa](./quick/24-implement-track-2-market-availability-wa/) |
| 025 | Grafana no-data diagnostics: confirmed zero-row root cause (infra intact), added noDataText to all 12 dashboard panels, added operator remediation guide to FEATURE-crypto-pair-grafana-panels-v1.md | 2026-03-25 | ff31016 | [25-diagnose-track-2-grafana-dashboard-empti](./quick/25-diagnose-track-2-grafana-dashboard-empti/) |
