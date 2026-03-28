# Project State

## Current Position
- **Milestone:** v1.0 — Core RAG Pipeline
- **Current Phase:** 5 (Reranking)
- **Status:** In Progress

Last activity: 2026-03-28 - Completed quick-038: Phase 1B truth sync and roadmap v5_1 checkbox update -- 6 checkboxes flipped to [x] (Rebuild CLAUDE.md, OPERATOR_SETUP_GUIDE.md, MarketMakerV1, benchmark_v1, Market Selection Engine, Discord alert system); CURRENT_STATE.md and CLAUDE.md drift reconciled; next-step pointer added; dev log written; 31 tests passing.

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
- CandidateDiscovery: pool_size = min(max_candidates * 10, 200); shortage_boost weight=0.40 beats depth (0.30) and probe (0.20); shortage now live-loaded via load_live_shortage() — no manual updates required
- load_live_shortage(): guarded import of capture_status inside function body; returns (dict, source_label); 4 fallback cases; BUCKET_OTHER always 0
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
- Phase 1B gate2 sweep: YES-asset-ID fallback chain is 5-level (prep_meta -> meta context -> watch_meta -> market_meta -> silver_meta); bucket_breakdown only in gate payload when bucket metadata present; monkeypatch must target importing module namespace not source module
- quick-026 Gate 2 NOT_RUN semantics: min_eligible_tapes=50 threshold; NOT_RUN = exit 0 (corpus gap is informational); FAILED = exit 1 (corpus ran but did not meet 70% threshold); market_maker_v1 is canonical Phase 1 strategy (SPEC-0012 updated)
- quick-026 diagnostic fill_opportunity: when quote_count == -1 (no manifest data), assume quoted (treat as 1) so zero-profit no-fill tapes classify as no_touch not unknown

### Blockers/Concerns
- Track 2 market availability: Polymarket has no active BTC/ETH/SOL 5m/15m binary pair markets as of 2026-03-25. Coinbase feed unblock is confirmed; waiting for market schedule to rotate these markets back in. Use `crypto-pair-watch --watch` to poll.
- Track 1 Gate 2 corpus: recovery corpus has 10/50 qualifying tapes. Silver reconstruction exhausted. No gate-core or strategy changes needed. Next action: live Gold shadow capture per campaign packet. Run `python tools/gates/capture_status.py` to see current shortage. Capture per `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`. Gate 2 rerun unblocked when corpus_audit.py exits 0. Shortage by bucket: sports=15, politics=9, crypto=10, new_market=5, near_resolution=1 (as of 2026-03-27).

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
| 026 | Phase 1B recovery: resolved SPEC-0012 v0/v1 authority conflict, fixed Gate 2 NOT_RUN semantics (min_eligible_tapes=50, exit 0), added mm_sweep_diagnostic.py per-tape root cause tool (TDD RED+GREEN). Root cause: 41/50 tapes SKIPPED_TOO_SHORT, 9/50 RAN_ZERO_PROFIT/no_touch | 2026-03-26 | ca3dcb5 | [26-recover-phase-1b-after-failed-gate-2-res](./quick/26-recover-phase-1b-after-failed-gate-2-res/) |
| 027 | Corpus recovery tooling: SPEC-phase1b-corpus-recovery-v1, corpus_audit.py (scan/admit/quota/manifest), 6 TDD tests, corpus audit run (9/50 qualify, shortage_report.md), CORPUS_GOLD_CAPTURE_RUNBOOK.md, CURRENT_STATE.md + STATE.md updated | 2026-03-26 | 160a8d6 | [27-recover-phase-1b-corpus-recovery-spec-ta](./quick/27-recover-phase-1b-corpus-recovery-spec-ta/) |
| 028 | Phase 1B residual shortage packet: salvaged 70-event politics tape via metadata injection (10/50), re-ran corpus_audit, wrote phase1b_residual_shortage_v1.md (definitive operator guide for live Gold capture), dev log, CURRENT_STATE.md + STATE.md updated | 2026-03-27 | 59f8e31 | [28-finish-phase-1b-execution-path-gold-capt](./quick/28-finish-phase-1b-execution-path-gold-capt/) |
| 029 | Phase 1B gold capture campaign packet: campaign spec, runbook tightened, capture_status.py helper (exit 0/1), 4 tests, CURRENT_STATE.md updated | 2026-03-27 | be2a56b | [29-convert-phase-1b-to-clean-operator-captu](./quick/29-convert-phase-1b-to-clean-operator-captu/) |
| 030 | Repo cleanup: fix 26MB corrupted test (→22KB), add .claudeignore, split CURRENT_STATE (1072→644 lines), consolidate devlogs, patch pyproject.toml, add file size guard, migrate users.txt, update README | 2026-03-27 | a53caed | [30-polytool-repo-cleanup-fix-corrupted-test](./quick/30-polytool-repo-cleanup-fix-corrupted-test/) |
| 031 | Harden Phase 1B market targeting: TargetResolver accepts market slug/URL/event slug/URL, ranked child-market shortlist with skip reasons, wired into simtrader shadow CLI, 19 offline tests | 2026-03-27 | 8a579c0 | [31-harden-phase-1b-market-targeting-accept-](./quick/31-harden-phase-1b-market-targeting-accept-/) |
| 032 | Phase 1B candidate discovery upgrade: CandidateDiscovery module (bucket inference, shortage scoring, 200-market pool), wired into quickrun --list-candidates, 27 new offline tests, 2712 passing | 2026-03-27 | e5116b0 | [32-improve-phase-1b-candidate-discovery-bro](./quick/32-improve-phase-1b-candidate-discovery-bro/) |
| 033 | Dynamic shortage ranking: load_live_shortage() replaces hardcoded dicts, live corpus state auto-loaded from tape dirs via capture_status.compute_status(), 4-case fallback, source label in CLI output, 5 new offline tests, 2717 passing | 2026-03-28 | 759dc9f | [33-dynamic-shortage-ranking-for-phase-1b-ca](./quick/33-dynamic-shortage-ranking-for-phase-1b-ca/) |
| 034 | Google Drive sync workflow branch-agnostic fix: branches: ['**'] replaces hardcoded list, branch-echo log step added (GITHUB_REF_NAME), YAML validated, 2717 passing | 2026-03-28 | adcf6b8 | [34-fix-google-drive-docs-sync-to-be-branch-](./quick/34-fix-google-drive-docs-sync-to-be-branch-/) |
| 035 | Remove paths filter from Google Drive sync workflow: every push to any branch now triggers unconditionally, explanatory comment added, dev log, 2717 passing | 2026-03-28 | dc300e6 | [35-remove-paths-filter-from-google-drive-sy](./quick/35-remove-paths-filter-from-google-drive-sy/) |
| 036 | Artifacts directory restructure: unified 53MB into artifacts/tapes/{gold,silver,shadow,crypto}/ hierarchy; updated 18 Python path constants; CLAUDE.md layout reference added; dev log written; 2717 passing | 2026-03-28 | 4a0da5d | [36-artifacts-directory-restructure-unified-](./quick/36-artifacts-directory-restructure-unified-/) |
| 037 | Market Selection Engine: seven-factor scorer (category_edge/spread/volume/competition/reward_apr/adverse_selection/time_gaussian) + NegRisk penalty + longshot bonus; config.py, passes_gates(), SevenFactorScore, MarketScorer; market-scan CLI rewritten with --all/--include-failing/--skip-events/--max-fetch/--json; 11 new tests; 2728 passing | 2026-03-28 | d5b88e2 | [37-market-selection-engine-seven-factor-com](./quick/37-market-selection-engine-seven-factor-com/) |
| 038 | Phase 1B truth sync -- roadmap v5_1 checkbox update: flipped 6 items to [x] (Rebuild CLAUDE.md, OPERATOR_SETUP_GUIDE.md, MarketMakerV1, benchmark_v1, Market Selection Engine, Discord alert system); reconciled CURRENT_STATE.md and CLAUDE.md drift from quick-036/037; added next-executable-step sentence; dev log written; 31 tests passing | 2026-03-28 | 970381c | [38-phase-1b-truth-sync-roadmap-checkbox-upd](./quick/38-phase-1b-truth-sync-roadmap-checkbox-upd/) |
