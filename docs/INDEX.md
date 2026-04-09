# Documentation Index

Quick-reference index of all key docs and what they cover.

## Getting Started

| Doc | Purpose |
|-----|---------|
| [README](../README.md) | Top-level overview, quick start, API reference |
| [Operator Quickstart](OPERATOR_QUICKSTART.md) | **Start here** — end-to-end guide: research loop, RAG, SimTrader, Grafana |
| [docs/README](README.md) | Documentation hub with recommended reading order |
| [Current State](CURRENT_STATE.md) | What exists today, pipeline diagram, CLI commands |
| [Roadmap](ROADMAP.md) | Milestone checklist, acceptance criteria, kill conditions |
| [Roadmap 3 Completion](roadmap3_completion.md) | Final evidence summary for Resolution Coverage milestone completion |
| [Trust Artifacts](TRUST_ARTIFACTS.md) | Roadmap 2 scan trust artifacts: practical schema, warning interpretation, reproducibility fields |

## Planning & Design

| Doc | Purpose |
|-----|---------|
| [Plan of Record](PLAN_OF_RECORD.md) | Durable plan: mission, data gaps, fees policy, taxonomy, validation framework |
| [Architecture](ARCHITECTURE.md) | Components, data flow, RAG metadata schema |
| [Architect Context Pack](ARCHITECT_CONTEXT_PACK.md) | Deep context snapshot for maintainers (generated, high-signal overview) |
| [Project Context (Public)](PROJECT_CONTEXT_PUBLIC.md) | Goals, non-goals, data gaps, artifact contract |
| [Strategy Playbook](STRATEGY_PLAYBOOK.md) | Outcome taxonomy, EV framework, falsification methodology |
| [Hypothesis Standard](HYPOTHESIS_STANDARD.md) | Prompt template, output rules, quality rubric |
| [Risk Policy](RISK_POLICY.md) | Privacy guardrails, pre-push guard, secret scanning |

## Workflows

| Doc | Purpose |
|-----|---------|
| [Operator Quickstart](OPERATOR_QUICKSTART.md) | **End-to-end guide** — research loop, RAG one-command (`rag-refresh`), SimTrader gates, Grafana links |
| [SimTrader Operator Guide](README_SIMTRADER.md) | Replay-first + shadow mode simulated trading, sweeps/batch, and local HTML reports |
| [Bounded Dislocation Capture Trial](dev_logs/2026-03-07_bounded_dislocation_capture_trial.md) | Short operator checklist for the current Gate 2 live trial loop |
| [Gate 2 Eligible Tape Acquisition](runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md) | **Current critical path** — discover candidates, watch/record, check corpus, close Gate 2 |
| [Stage 1 Live Deployment](runbooks/LIVE_DEPLOYMENT_STAGE1.md) | Stage 1 live deployment operator runbook |
| [Runbook: Manual Examine](RUNBOOK_MANUAL_EXAMINE.md) | Scan-first manual workflow; examine guidance retained as legacy |
| [Local RAG Workflow](LOCAL_RAG_WORKFLOW.md) | RAG index, query, eval, scoping, retrieval modes (`rag-refresh` = one-command rebuild) |
| [LLM Bundle Workflow](LLM_BUNDLE_WORKFLOW.md) | Evidence bundle assembly, prompt template, report saving |
| [Research Sources](RESEARCH_SOURCES.md) | Curated source domains, allowlist, TTL, cache-source usage |

## Standards & Conventions

| Doc | Purpose |
|-----|---------|
| [Docs Best Practices](DOCS_BEST_PRACTICES.md) | Where docs live, ADR format, naming conventions |
| [Knowledge Base Conventions](KNOWLEDGE_BASE_CONVENTIONS.md) | Public/private boundary, KB layout, agent run logs |

## Reference

| Doc | Purpose |
|-----|---------|
| [TODO](TODO.md) | Deferred items by priority, spec stubs |
| [RAG Implementation Report](RAG_IMPLEMENTATION_REPORT.md) | Technical details of RAG implementation |
| [ADR-0001: CLI Rename](adr/ADR-0001-cli-and-module-rename.md) | polytool -> polytool rename decision |

## Features

| Doc | Purpose |
|-----|---------|
| [Wallet-Scan v0](features/wallet-scan-v0.md) | Batch scan for handles/wallets -> deterministic leaderboard by net PnL |
| [Alpha-Distill v0](features/alpha-distill-v0.md) | Cross-user segment aggregation -> ranked edge hypothesis candidates (no LLM) |
| [Track A: Live CLOB Wiring + Gate Harness](features/FEATURE-trackA-live-clob-wiring.md) | Track A live CLOB integration, gate harness, market-scan CLI |
| [Gate 2 Eligible Tape Acquisition](features/FEATURE-gate2-eligible-tape-acquisition.md) | tape-manifest CLI, regime labeling, eligibility invariant, corpus coverage tracking |
| [Discord Alerting — Track A](features/FEATURE-discord-alerting-tracka.md) | Discord webhook transport, gate hooks, kill-switch and risk-halt alerts |
| [Discord Session Lifecycle Hooks](features/FEATURE-discord-session-lifecycle-hooks.md) | `simtrader live` now fires Discord session start/stop/error alerts at the CLI boundary and reuses the same notifier for runtime alerts |
| [Regime Integrity for Gate 2 Artifacts](features/FEATURE-regime-integrity-gate2-artifacts.md) | Machine-derived regime classification, provenance fields, mismatch detection, shared coverage helper |
| [Gate 2 Candidate Ranking](features/FEATURE-phase1-gate2-candidate-ranking.md) | Explainable multi-factor ranking for Gate 2 candidate markets (reward/volume/competition/new-market/regime) |
| [Gate 2 Preflight](features/FEATURE-gate2-preflight.md) | Operator-safe READY/BLOCKED preflight for sweep readiness, eligible tape visibility, and mixed-regime blockers |
| [Gate 2 Capture Session Pack](features/FEATURE-gate2-capture-session-pack.md) | `make-session-pack` turns an explicit Gate 2 selection into an exact watchlist file plus a watcher-compatible session plan; coverage-aware via `--prefer-missing-regimes` / `--target-regime` |
| [Scan Derived Regime Context](features/FEATURE-scan-derived-regime-context.md) | Gate 2 scan output now derives regime from metadata first, shows provenance, and prints explicit age/regime unknowns |
| [Scan Metadata Enrichment](features/FEATURE-scan-metadata-enrichment.md) | Optional live `--enrich` fetch reduces UNKNOWN reward/volume/age/competition/regime-context fields without changing the default scan path |
| [Scan Exact Slug Export](features/FEATURE-scan-exact-slug-export.md) | `scan-gate2-candidates --watchlist-out` writes exact full slugs for the shown ranked candidates so operators do not copy truncated table values |
| [Capture Metadata Snapshot Hardening](features/FEATURE-capture-metadata-snapshot-hardening.md) | Watch/prep artifacts now persist additive capture-time market snapshots that tape-manifest prefers for regime/new-market derivation |
| [Wallet Discovery v1](features/wallet-discovery-v1.md) | Spec frozen: Loop A leaderboard discovery, watchlist/queue/snapshot ClickHouse tables, unified scan --quick, MVF computation |

## Specs

| Doc | Purpose |
|-----|---------|
| [SPEC-0001: Dossier Resolution Enrichment](specs/SPEC-0001-dossier-resolution-enrichment.md) | Resolution outcome enrichment for dossiers |
| [SPEC-0002: LLM Bundle Coverage Section](specs/SPEC-0002-llm-bundle-coverage.md) | Coverage report inclusion logic in bundle.md |
| [LLM Bundle Input Contract](specs/LLM_BUNDLE_CONTRACT.md) | What files the LLM reads, each file's role, TODO sections, and RAG execution status |
| [SPEC: Wallet-Scan v0](specs/SPEC-wallet-scan-v0.md) | Batch wallet scan spec: input format, output schema, leaderboard ordering, error handling |
| [SPEC: Alpha-Distill v0](specs/SPEC-alpha-distill-v0.md) | Segment edge distillation spec: aggregation, ranking formula, candidate schema, friction flags |
| `packages/polymarket/market_selection/` | Market scoring, filters, Gamma API client |
| [Hypothesis Schema v1](specs/hypothesis_schema_v1.json) | JSON schema for structured hypothesis output |
| [SPEC-0010: SimTrader Vision and Roadmap](specs/SPEC-0010-simtrader-vision-and-roadmap.md) | Full SimTrader architecture, realism constraints, strategy classes, and phased roadmap (MVP0-MVP6) |
| [SPEC-0011: Live Execution Layer](specs/SPEC-0011-live-execution-layer.md) | Optional gated execution layer: gate model, interfaces, capital stages, policy alignment |
| [SPEC-0012: Phase 1 Track A Live Bot Program](specs/SPEC-0012-phase1-tracka-live-bot-program.md) | **Canonical Track A spec** — strategy, promotion ladder, validation corpus, market selection, alerting, kill conditions |
| [SPEC-0013: Phase 1 Track A Gap Matrix](specs/SPEC-0013-phase1-tracka-gap-matrix.md) | Read-only audit: implementation gap matrix for all 11 Phase 1 requirements; risk ranking; recommended packets |
| [SPEC-0014: Gate 2 Eligible Tape Acquisition](specs/SPEC-0014-gate2-eligible-tape-acquisition.md) | Candidate discovery flow, mixed-regime corpus policy, eligibility invariant, manifest schema, operator workflow |
| [SPEC-0015: Discord Alerting and Operator Notifications](specs/SPEC-0015-discord-alerting-and-operator-notifications.md) | Event taxonomy, transport contract, env config, failure behavior, test strategy |
| [SPEC-0016: Regime Integrity for Gate 2 Artifacts](specs/SPEC-0016-regime-integrity-for-gate2-artifacts.md) | Regime provenance contract for Gate 2 tape manifest: derived vs operator labels, mismatch detection, shared coverage helper |
| [SPEC-0017: Phase 1 Gate 2 Candidate Ranking](specs/SPEC-0017-phase1-gate2-candidate-ranking.md) | Ranking factors, weights, missing-data policy, new-market logic, operator guidance |
| [SPEC-0018: Gate 2 Capture Session Pack](specs/SPEC-0018-gate2-capture-session-pack.md) | Session pack format, CLI contract, watcher-compatible plan JSON, and post-session template |
| [SPEC: Wallet Discovery v1](specs/SPEC-wallet-discovery-v1.md) | Wallet discovery v1 contract: Loop A, ClickHouse table contracts, lifecycle state machine, unified scan, MVF |

## Dev Logs (recent)

| Log | Date | Topic |
|-----|------|-------|
| [Phase 1 Track A Docs Truth Sync](dev_logs/2026-03-10_phase1_tracka_docs_truth_sync.md) | 2026-03-10 | Docs-only truth sync: status date, Gate 2 tooling inventory, corpus state, INDEX gaps all corrected |
| [Session Pack Target-Regime Fix](dev_logs/2026-03-10_session_pack_target_regime_fix.md) | 2026-03-10 | Fixed: UNKNOWN-regime markets no longer falsely claim to advance named-regime coverage via session-level `--regime` operator fallback |
| [Phase 1 Track A Contract Exercise](dev_logs/2026-03-10_phase1_tracka_contract_exercise.md) | 2026-03-10 | Offline contract exercise: full ranked-JSON → session pack → watcher loader chain verified; corpus confirmed 0 eligible tapes, sports coverage only |
| [Background Gate 2 Session Helper](dev_logs/2026-03-10_background_gate2_session_helper.md) | 2026-03-10 | `tools/ops/run_gate2_session.ps1` — PowerShell helper that runs scan → session pack → background watch in one command |
| [Coverage-Aware Session Pack](dev_logs/2026-03-10_coverage_aware_session_pack.md) | 2026-03-10 | `make-session-pack` now accepts `--prefer-missing-regimes` / `--target-regime`; adds `coverage_intent` field to session_plan.json |
| [Ranked Scan → Session Pack Pipeline](dev_logs/2026-03-09_ranked_scan_to_session_pack.md) | 2026-03-09 | `scan-gate2-candidates --ranked-json-out` emits advisory JSON; `make-session-pack --ranked-json` consumes it with rank/gate2_status/explanation preserved in the session plan |
| [Gate 2 Capture Session Pack](dev_logs/2026-03-09_gate2_capture_session_pack.md) | 2026-03-09 | `make-session-pack` now accepts ranked watchlist input and writes a watcher-compatible plan JSON with per-slug planning context |
| [Phase 1 Track A Offline Verification](dev_logs/2026-03-09_phase1_tracka_offline_verification.md) | 2026-03-09 | Offline verification pass for the end-to-end Gate 2 toolchain against local artifact fixtures |
| [Gate 2 Regime Coverage Fix](dev_logs/2026-03-09_gate2_regime_coverage_fix.md) | 2026-03-09 | Fixed regime coverage derivation in tape-manifest and corpus summary |
| [Watch Arb Duration Fix](dev_logs/2026-03-09_watch_arb_duration_fix.md) | 2026-03-09 | `watch-arb-candidates` now enforces `--duration` with a monotonic deadline and capped sleep so bounded watch sessions exit automatically |
| [Watch Arb CLI Ergonomics](dev_logs/2026-03-08_watch_arb_cli_ergonomics.md) | 2026-03-08 | `watch-arb-candidates --markets` now accepts repeated or comma-delimited slugs; empty malformed input prints the expected format |
| [Phase 1 Gate 2 Candidate Ranking](dev_logs/2026-03-08_phase1_gate2_candidate_ranking.md) | 2026-03-08 | Gate2RankScore, score_gate2_candidate, rank_gate2_candidates, 14 new tests |
| [Scan Derived Regime Context](dev_logs/2026-03-08_scan_derived_regime_context.md) | 2026-03-08 | scan metadata pass-through, derived regime provenance, Age/RegSrc output, 27 passing tests |
| [Scan Metadata Enrichment](dev_logs/2026-03-08_scan_metadata_enrichment.md) | 2026-03-08 | optional live `--enrich`, reward/market metadata fetch, conservative UNKNOWN fallback, 31 passing tests |
| [Capture Metadata Snapshot Hardening](dev_logs/2026-03-08_capture_metadata_snapshot_hardening.md) | 2026-03-08 | additive market_snapshot persistence, manifest snapshot preference, legacy fallback, 75 passing tests |
| [Scan Exact Slug Export](dev_logs/2026-03-08_scan_exact_slug_export.md) | 2026-03-08 | `scan-gate2-candidates --watchlist-out` exports exact full slugs for the shown ranked candidates; default output unchanged |
| [Regime Integrity for Gate 2 Artifacts](dev_logs/2026-03-08_regime_integrity_gate2_artifacts.md) | 2026-03-08 | derive_tape_regime, coverage_from_classified_regimes, TapeRecord provenance fields, schema v2, 25 new tests |
| [Discord Alerting — Track A](dev_logs/2026-03-08_discord_alerting_tracka.md) | 2026-03-08 | Discord webhook module, gate hooks, LiveRunner notifier, 29 tests |
| [Discord Session Lifecycle Hooks](dev_logs/2026-03-08_discord_session_lifecycle_hooks.md) | 2026-03-08 | `simtrader live` CLI lifecycle hooks, safe notifier dispatch, 4 new offline tests |
| [Gate 2 Eligible Tape Acquisition](dev_logs/2026-03-08_gate2_eligible_tape_acquisition.md) | 2026-03-08 | tape-manifest CLI, regime labeling on capture tools, eligibility invariant, 34 new tests |
| [Gate 2 Preflight](dev_logs/2026-03-08_gate2_preflight.md) | 2026-03-08 | operator READY/BLOCKED preflight, eligible tape list, exact next action, 55 passing tests |
| [Phase 1 Track A Gap Audit](dev_logs/2026-03-08_phase1_tracka_gap_audit.md) | 2026-03-08 | Read-only audit: gap matrix findings, top 3 blockers, recommended packets (→ SPEC-0013) |
| [Phase 1 Track A Truth Sync](dev_logs/2026-03-08_phase1_tracka_truth_sync.md) | 2026-03-08 | Docs-only truth sync: canonical strategy, Discord alerting, gate ladder, SPEC-0012 |
| [Usability Streamlining Pass](dev_logs/2026-03-07_usability_streamlining_pass.md) | 2026-03-07 | CLI grouping, rag-refresh alias, Studio Grafana links, OPERATOR_QUICKSTART rewrite |
| [Wallet Anomaly Backlog Entry](dev_logs/2026-03-07_wallet_anomaly_backlog_entry.md) | 2026-03-07 | Deferred backlog entry for wallet anomaly / flow discrepancy alerts |
| [Docs Sync: SimTrader Status](dev_logs/2026-03-07_docs_sync_simtrader_status.md) | 2026-03-07 | Repo-truth sync for current SimTrader and gate status |
| [Bounded Dislocation Capture Trial](dev_logs/2026-03-07_bounded_dislocation_capture_trial.md) | 2026-03-07 | Operator checklist for the current bounded live trial |
| [Dislocation Watch + Auto-Record](dev_logs/2026-03-07_dislocation_watch_recorder.md) | 2026-03-07 | Bounded live watcher and auto-record flow for Gate 2 capture |
| [Wallet-Scan v0](dev_logs/2026-03-05_wallet_scan_v0.md) | 2026-03-05 | Batch wallet scan implementation |
| [Alpha-Distill v0](dev_logs/2026-03-05_alpha_distill_v0.md) | 2026-03-05 | Cross-user segment distillation implementation |
| [Docs Sync: Track B Foundation](dev_logs/2026-03-05_docs_sync_trackB_foundation.md) | 2026-03-05 | Documentation sync for Track B foundation work |

## Archive

Historical and superseded docs are in `docs/archive/`. See [docs/README](README.md)
for the full archive listing.

| Doc | Purpose |
|-----|---------|
| [Construction Manual Mapping](archive/MASTER_CONSTRUCTION_MANUAL_MAPPING.md) | Future-direction mapping: Construction Manual concepts -> current repo modules; labels live trading as out of scope |
