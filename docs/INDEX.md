# Documentation Index

Navigation only. This index routes readers to governing docs and support docs;
it does not establish repo truth. Public-docs surface and cleanup boundaries are
defined in
[ADR 0014](adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md). The
complementary root-level hidden tooling/local-state policy is
[Local State and Tooling Boundary](reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md).

## First-Class Root Docs

| Doc | Role |
|-----|------|
| [Plan of Record](PLAN_OF_RECORD.md) | Primary docs-governance and implementation-policy companion |
| [Architecture](ARCHITECTURE.md) | Architecture truth |
| [Strategy Playbook](STRATEGY_PLAYBOOK.md) | Strategy and falsification methodology |
| [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md) | Strategic roadmap and LLM policy |
| [Current State](CURRENT_STATE.md) | Implemented repo truth |

`README.md` and `INDEX.md` are navigation only. `docs/dev_logs/` is preserved
history, and `docs/obsidian-vault/` is a separate subsystem excluded from
public docs count goals. [ROADMAP.md](ROADMAP.md) is a secondary roadmap
router/operator-facing surface only.

## Getting Started

| Doc | Purpose |
|-----|---------|
| [README](../README.md) | Top-level overview, quick start, API reference |
| [Operator Quickstart](runbooks/OPERATOR_QUICKSTART.md) | **Start here** - end-to-end guide: research loop, RAG, SimTrader, Grafana |
| [Operator Setup Guide](runbooks/OPERATOR_SETUP_GUIDE.md) | Operator-owned setup before live capital: accounts, wallets, funding, host checklist |
| [docs/README](README.md) | Documentation navigation hub |
| [Current State](CURRENT_STATE.md) | Implemented repo truth |
| [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md) | Strategic roadmap and LLM policy |
| [Roadmap 3 Completion](archive/roadmap3_completion.md) | Final evidence summary for Resolution Coverage milestone completion |

## Planning & Design

| Doc | Purpose |
|-----|---------|
| [Plan of Record](PLAN_OF_RECORD.md) | Durable plan: mission, data gaps, fees policy, taxonomy, validation framework |
| [Architecture](ARCHITECTURE.md) | Components, data flow, RAG metadata schema |
| [Master Roadmap v5.1](reference/POLYTOOL_MASTER_ROADMAP_v5_1.md) | Strategic roadmap and LLM policy |
| [Roadmap Router](ROADMAP.md) | Secondary operator-facing roadmap surface; routes to the governing roadmap, current state, and historical roadmap materials |
| [Architect Context Pack](ARCHITECT_CONTEXT_PACK.md) | Deep context snapshot for maintainers (generated, high-signal overview) |
| [Project Context (Public)](PROJECT_CONTEXT_PUBLIC.md) | Goals, non-goals, data gaps, artifact contract |
| [Strategy Playbook](STRATEGY_PLAYBOOK.md) | Outcome taxonomy, EV framework, falsification methodology |
| [Risk Policy](RISK_POLICY.md) | Privacy guardrails, pre-push guard, secret scanning |

## Runbooks

| Doc | Purpose |
|-----|---------|
| [Operator Quickstart](runbooks/OPERATOR_QUICKSTART.md) | **End-to-end guide** - research loop, RAG one-command (`rag-refresh`), SimTrader gates, Grafana links |
| [Operator Setup Guide](runbooks/OPERATOR_SETUP_GUIDE.md) | Account setup, wallet architecture, funding flow, and host checklist |
| [Windows Development Gotchas](runbooks/WINDOWS_DEVELOPMENT_GOTCHAS.md) | Windows host issues, PowerShell-safe commands, and troubleshooting fixes |
| [Partner Deployment Guide (Docker)](runbooks/PARTNER_DEPLOYMENT_GUIDE_docker.md) | Partner-machine deployment path and container handoff notes |
| [SimTrader Operator Guide](runbooks/README_SIMTRADER.md) | Replay-first + shadow mode simulated trading, sweeps/batch, and local HTML reports |
| [Gate 2 Eligible Tape Acquisition](runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md) | **Current critical path** - discover candidates, watch/record, check corpus, close Gate 2 |
| [Stage 1 Live Deployment](runbooks/LIVE_DEPLOYMENT_STAGE1.md) | Stage 1 live deployment operator runbook |
| [Runbook: Manual Examine](runbooks/RUNBOOK_MANUAL_EXAMINE.md) | Scan-first manual workflow; examine guidance retained as legacy |
| [Local RAG Workflow](runbooks/LOCAL_RAG_WORKFLOW.md) | RAG index, query, eval, scoping, retrieval modes (`rag-refresh` = one-command rebuild) |
| [LLM Bundle Workflow](runbooks/LLM_BUNDLE_WORKFLOW.md) | Evidence bundle assembly, prompt template, report saving |
| [RIS Operator Guide](runbooks/RIS_OPERATOR_GUIDE.md) | Full RIS operator guide: research loop, pipeline health, n8n pilot, MCP setup |
| [RIS Phase 2A Operator Guide](runbooks/RIS_PHASE2A_OPERATOR_GUIDE.md) | **Phase 2A** — first-time activation, validation run, daily usage, n8n + Grafana monitoring |
| [RIS Marker Parse Queue Runbook](runbooks/RIS_MARKER_QUEUE_RUNBOOK.md) | **L1 operator path** — enqueue arXiv papers, run IPC warm-process, inspect results, recover failed items, platform behavior, performance expectations |
| [RIS + n8n Operator SOP](runbooks/RIS_N8N_OPERATOR_SOP.md) | Quick-reference cheat sheet: startup, import, health, ingest, monitoring |
| [RIS Discord Alerts](runbooks/RIS_DISCORD_ALERTS.md) | Discord alert format reference, severity meaning, verification procedure |
| [RIS n8n Smoke Test](runbooks/RIS_N8N_SMOKE_TEST.md) | Pre-import repo validation runbook for n8n workflow changes |
| [Wallet Discovery v1 Runbook](runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md) | Go/no-go readiness checklist and research workflow guide for Wallet Discovery v1 |

## Standards & Conventions

| Doc | Purpose |
|-----|---------|
| [Docs Best Practices](DOCS_BEST_PRACTICES.md) | Where docs live, ADR format, naming conventions |
| [Knowledge Base Conventions](KNOWLEDGE_BASE_CONVENTIONS.md) | Public/private boundary, KB layout, agent run logs |

## Reference

| Doc | Purpose |
|-----|---------|
| [TODO](TODO.md) | Deferred items by priority, spec stubs |
| [Hypothesis Standard](reference/HYPOTHESIS_STANDARD.md) | Prompt template, output rules, quality rubric |
| [Trust Artifacts](reference/TRUST_ARTIFACTS.md) | Roadmap 2 scan trust artifacts: practical schema, warning interpretation, reproducibility fields |
| [Research Sources](reference/RESEARCH_SOURCES.md) | Curated source domains, allowlist, TTL, cache-source usage |
| [Local State and Tooling Boundary](reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md) | Root-level classification for hidden tooling, local state, runtime state, scratch, and repo-cleanliness exclusions |
| [ADR-0001: CLI Rename](adr/ADR-0001-cli-and-module-rename.md) | polytool -> polytool rename decision |
| [ADR-0014: Public Docs Surface and Repo Hygiene Boundaries](adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md) | Cleanup boundary, first-class docs allowlist, and non-destructive first-pass rules |

## Audits

| Doc | Purpose |
|-----|---------|
| [Codebase Audit](audits/CODEBASE_AUDIT.md) | Ground-truth inventory of code, CLI surfaces, integrations, and identified drift |
| [RAG Implementation Report](audits/RAG_IMPLEMENTATION_REPORT.md) | Technical details of RAG implementation |
| [RIS Audit Report](audits/RIS_AUDIT_REPORT.md) | Layer-by-layer RIS implementation audit and gap summary |

## Features

| Doc | Purpose |
|-----|---------|
| [Wallet-Scan v0](features/wallet-scan-v0.md) | Batch scan for handles/wallets -> deterministic leaderboard by net PnL |
| [Alpha-Distill v0](features/alpha-distill-v0.md) | Cross-user segment aggregation -> ranked edge hypothesis candidates (no LLM) |
| [Track A: Live CLOB Wiring + Gate Harness](features/FEATURE-trackA-live-clob-wiring.md) | Track A live CLOB integration, gate harness, market-scan CLI |
| [Gate 2 Eligible Tape Acquisition](features/FEATURE-gate2-eligible-tape-acquisition.md) | tape-manifest CLI, regime labeling, eligibility invariant, corpus coverage tracking |
| [Discord Alerting - Track A](features/FEATURE-discord-alerting-tracka.md) | Discord webhook transport, gate hooks, kill-switch and risk-halt alerts |
| [Discord Session Lifecycle Hooks](features/FEATURE-discord-session-lifecycle-hooks.md) | `simtrader live` now fires Discord session start/stop/error alerts at the CLI boundary and reuses the same notifier for runtime alerts |
| [Regime Integrity for Gate 2 Artifacts](features/FEATURE-regime-integrity-gate2-artifacts.md) | Machine-derived regime classification, provenance fields, mismatch detection, shared coverage helper |
| [Gate 2 Candidate Ranking](features/FEATURE-phase1-gate2-candidate-ranking.md) | Explainable multi-factor ranking for Gate 2 candidate markets (reward/volume/competition/new-market/regime) |
| [Gate 2 Preflight](features/FEATURE-gate2-preflight.md) | Operator-safe READY/BLOCKED preflight for sweep readiness, eligible tape visibility, and mixed-regime blockers |
| [Gate 2 Capture Session Pack](features/FEATURE-gate2-capture-session-pack.md) | `make-session-pack` turns an explicit Gate 2 selection into an exact watchlist file plus a watcher-compatible session plan; coverage-aware via `--prefer-missing-regimes` / `--target-regime` |
| [Scan Derived Regime Context](features/FEATURE-scan-derived-regime-context.md) | Gate 2 scan output now derives regime from metadata first, shows provenance, and prints explicit age/regime unknowns |
| [Scan Metadata Enrichment](features/FEATURE-scan-metadata-enrichment.md) | Optional live `--enrich` fetch reduces UNKNOWN reward/volume/age/competition/regime-context fields without changing the default scan path |
| [Scan Exact Slug Export](features/FEATURE-scan-exact-slug-export.md) | `scan-gate2-candidates --watchlist-out` writes exact full slugs for the shown ranked candidates so operators do not copy truncated table values |
| [Capture Metadata Snapshot Hardening](features/FEATURE-capture-metadata-snapshot-hardening.md) | Watch/prep artifacts now persist additive capture-time market snapshots that tape-manifest prefers for regime/new-market derivation |
| [Wallet Discovery v1](features/wallet-discovery-v1.md) | Shipped: Loop A leaderboard discovery, watchlist/queue/snapshot ClickHouse tables, unified scan --quick, MVF computation |
| [RIS Operational Readiness Phase 2A](features/ris_operational_readiness_phase2a.md) | WP1-WP5: scoring fixes, Gemini+DeepSeek routing, budget enforcement, n8n visual improvements, ClickHouse+Grafana monitoring, 31-query retrieval benchmark with P@5 and baseline save |
| [RIS L4 Multi-source Academic Harvesters](features/FEATURE-ris-l4-multisource-academic-harvesters.md) | **COMPLETE 2026-05-09.** 4 harvesters: ArxivHarvester, SemanticScholarHarvester, CrossrefHarvester, OpenReviewHarvester. `AcademicCandidate` dataclass + `dedup_candidates()`. `research-harvest` CLI. `SOURCE_CAPABILITY_MATRIX` with SSRN/NBER deferred. 59 tests pass. |
| [RIS L2 Academic Query — PaperQA2 RAG Control Flow](features/FEATURE-ris-l2-academic-query.md) | **COMPLETE 2026-05-09.** `research-query` CLI; multi-angle KS query; query-time Marker-ready guard (`body_source=marker`, `body_length>=5000`); paper-level grouping; citation output with arxiv_id/body_source; graceful fallback; 36 tests pass. |
| [RIS L1 Marker Production Readiness Rollout](features/FEATURE-ris-l1-marker-production-readiness-rollout.md) | **COMPLETE 2026-05-09.** Repeatable operator path (enqueue→warm-process→inspect); runbook at `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`; Marker-only gate enforced; no pdfplumber fallback; queue states + recovery documented; 158 tests pass. L2/L4 now unblocked. |
| [RIS Marker Structural Parser — Production Default (Layer 1)](features/ris-marker-structural-parser-scaffold.md) | **CODE COMPLETE — Docker IPC warm-worker v1 closed 2026-05-08; L1 production readiness rollout complete 2026-05-09.** Queue v0 shipped 2026-05-05 (queue, CLI, indexing gate, failure semantics, 43 tests; Codex re-review PASS). pdfplumber is legacy/debug only. `body_source=marker` is the RAG-readiness gate. |
| [RIS L3 Pre-fetch Relevance Filter v0 + L3.1 + L3.2](features/FEATURE-ris-prefetch-relevance-filter-v0.md) | Lexical scorer v1.1 (allow=0.80); all four modes: `{off,dry-run,enforce,hold-review}`; `hold-review` queues REVIEW candidates, never ingests; `ReviewQueueStore` + `LabelStore`; `research-prefetch-review` CLI; Scenario B 5.88% (<10% met); QA REJECT=0. **L3.2 complete 2026-05-05**: `research-prefetch-discover` (arXiv metadata → score → enqueue; no PDF/Marker/index; 36 tests). **SVM trigger MET: 30 allow / 31 reject / 1 pending unlabeled.** |
| [RIS L3 v1 SVM Topic Filter](features/FEATURE-ris-svm-filter-v1.md) | **Default-off integrated. Dry-run + hold-review ready. Enforce deferred.** `BAAI/bge-large-en-v1.5` approved as production model (Director 2026-05-07). 156 labels (74/82), train=117, test=39, macro-F1=1.000. `research-prefetch-svm-train` CLI; `--prefetch-filter-scorer svm` on `research-acquire`; `--filter-scorer svm` on `research-prefetch-discover`. SVM enforce returns rc=1 — blocked pending future Director approval. Lexical remains default. |
| [Marker Docker IPC Warm-Worker v1](features/FEATURE-marker-docker-ipc-warm-worker-v1.md) | **COMPLETE 2026-05-08.** Persistent IPC warm-worker subprocess for Marker parse queue on Linux/Docker. Models load once at startup; papers 2+ pay only inference cost (0.13s, 0.22s delta). daemon=False fix applied. `ipc_warm_worker_used` persisted in `results.jsonl`. Revised gate: ≥3 full PDFs/session, papers 2+ delta ≤5s. Validated: 45.55s/69.73s/48.31s on RTX 2070 Super. L1 and L2 later completed 2026-05-09; L4 deferred. |
| [RIS Scientific RAG Evaluation Benchmark v0](features/FEATURE-ris-scientific-eval-benchmark-v0.md) | Baseline locked 2026-05-02: corpus_size=23, P@5=1.0, off_topic_rate=30.43%, Recommendation A (pre-fetch relevance filtering); Rule D secondary/heuristic |
| [SimTrader Fee Model v2](features/simtrader_fee_model_v2.md) | Category-aware Polymarket taker fees, maker=0, Kalshi baseline model, full propagation across all 12 runtime entry points (PMXT Deliverable A) |
| [SimTrader Sports Strategies v1](features/simtrader_sports_strategies_v1.md) | SportsMomentum, SportsFavorite, SportsVWAP — STRATEGY_REGISTRY wiring, `_ns` config priority, clean-room reimplementation, 20 tests (PMXT Deliverable B) |
| [vera-hermes-agent Operator Baseline](features/vera_hermes_operator_baseline.md) | Isolated Hermes operator profile on WSL2; read-only scope, SOUL.md guardrails, healthcheck script, path for future operator query skills |
| [polytool-dev-logs Hermes Skill](features/polytool_dev_logs_skill.md) | Read-only Hermes skill for querying and summarizing dev logs; keyword filter, date filter, summary mode; strict docs/dev_logs/ scope |
| [polytool-status Hermes Skill](features/polytool_status_skill.md) | Read-only Hermes skill for project status queries; active features, Gate 2 blockers, paused items; reads CURRENT_DEVELOPMENT + CURRENT_STATE |
| [polytool-files Hermes Skill](features/polytool_files_skill.md) | Read-only Hermes skill for approved project doc access; whitelist of features/, specs/, runbooks/, adr/, reference/, and root docs |

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
| [SPEC-0012: Phase 1 Track A Live Bot Program](specs/SPEC-0012-phase1-tracka-live-bot-program.md) | **Canonical Track A spec** - strategy, promotion ladder, validation corpus, market selection, alerting, kill conditions |
| [SPEC-0013: Phase 1 Track A Gap Matrix](specs/SPEC-0013-phase1-tracka-gap-matrix.md) | Read-only audit: implementation gap matrix for all 11 Phase 1 requirements; risk ranking; recommended packets |
| [SPEC-0014: Gate 2 Eligible Tape Acquisition](specs/SPEC-0014-gate2-eligible-tape-acquisition.md) | Candidate discovery flow, mixed-regime corpus policy, eligibility invariant, manifest schema, operator workflow |
| [SPEC-0015: Discord Alerting and Operator Notifications](specs/SPEC-0015-discord-alerting-and-operator-notifications.md) | Event taxonomy, transport contract, env config, failure behavior, test strategy |
| [SPEC-0016: Regime Integrity for Gate 2 Artifacts](specs/SPEC-0016-regime-integrity-for-gate2-artifacts.md) | Regime provenance contract for Gate 2 tape manifest: derived vs operator labels, mismatch detection, shared coverage helper |
| [SPEC-0017: Phase 1 Gate 2 Candidate Ranking](specs/SPEC-0017-phase1-gate2-candidate-ranking.md) | Ranking factors, weights, missing-data policy, new-market logic, operator guidance |
| [SPEC-0018: Gate 2 Capture Session Pack](specs/SPEC-0018-gate2-capture-session-pack.md) | Session pack format, CLI contract, watcher-compatible plan JSON, and post-session template |
| [SPEC: Wallet Discovery v1](specs/SPEC-wallet-discovery-v1.md) | Wallet discovery v1 contract: Loop A, ClickHouse table contracts, lifecycle state machine, unified scan, MVF |

## Recent Dev Logs (historical record)

| Log | Date | Topic |
|-----|------|-------|
| [Fix: RIS L1 Closeout — Codex FAIL Blockers](dev_logs/2026-05-09_fix-ris-l1-closeout-codex-blockers.md) | 2026-05-09 | Feature 3 removed from Active Features; stale "L1 NOT unblocked" and ≤10s source comments corrected. 197 tests pass. Active count: 2 (Features 1, 2). |
| [RIS L1 Marker Production Readiness Rollout](dev_logs/2026-05-09_ris-l1-marker-production-readiness-rollout.md) | 2026-05-09 | L1 DoD met: runbook created, stale CLI text fixed, 158 tests pass. Feature doc + completion protocol executed. L2/L4 now unblocked. Active count: 2 (Features 1, 2). |
| [Fix: Marker Final Obsidian Active-Feature-3 References](dev_logs/2026-05-08_fix-marker-final-obsidian-active-feature3-references.md) | 2026-05-08 | Docs-only. Four Obsidian files fixed: "Active Feature 3" and "L1 blocked until Feature 3 closeout verification passes" replaced with closed/resolved language. 10 locations across 4 files. No code/tests/artifacts touched. Codex closeout verification may rerun. |
| [Fix: Marker Final L1-Blocked Status References](dev_logs/2026-05-08_fix-marker-final-l1-blocked-status.md) | 2026-05-08 | Docs-only. Final three stale "L1 blocked on IPC warm-worker" references removed from scaffold feature doc, INDEX, and CURRENT_DEVELOPMENT. Dangling "Active Feature 3" pointer in scaffold doc also updated. No code/tests/artifacts touched. Codex closeout verification may rerun. |
| [Fix: Marker Closeout Stale Status References](dev_logs/2026-05-08_fix-marker-closeout-stale-status-references.md) | 2026-05-08 | Docs-only. Two Codex FAIL blockers fixed: Work Packet line 113 "NOT yet closed" → CLOSED; Current-Focus line 20 stale "L1 remains blocked…Active Feature 3" removed. L2 gate wording tightened. No code/tests/artifacts touched. Codex closeout verification may rerun. |
| [Marker Docker IPC Warm-Worker v1 — Closeout](dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md) | 2026-05-08 | Docs-only completion protocol. Feature doc created. INDEX + CURRENT_DEVELOPMENT + CURRENT_STATE + Current-Focus + Work Packet updated. Feature 3 moved to Recently Completed. Active count: 3→2. L1 production rollout unblocked at the time; L1/L2 later completed 2026-05-09 and L4 remains deferred. |
| [Fix: Marker Structural Parser Integration — Frontmatter Timing Gate](dev_logs/2026-05-08_fix-marker-structural-parser-frontmatter-timing-gate.md) | 2026-05-08 | Docs-only. Final Codex FAIL blocker: Structural Parser Integration WP frontmatter + DANGER callout header + line 31 + lines 34–35 + line 46 fixed. Old ≤10s/paper gate now historical/superseded in all 5 locations. Current blocker updated to Feature 3 closeout. Implementation scope unchanged. Codex closeout verification may rerun. |
| [Codex Verify: Marker Last Timing Gate References (FAIL)](dev_logs/2026-05-08_codex-verify-marker-last-timing-gate-references.md) | 2026-05-08 | FAIL — prior 2 Codex blockers fixed, but Structural Parser Integration WP lines 5, 31, 34 still present old ≤10s/paper gate as active. Fix session above required. |
| [Fix: Marker Last Timing Gate References — Codex Final Blockers](dev_logs/2026-05-08_fix-marker-last-timing-gate-references.md) | 2026-05-08 | Docs-only. 2 Codex mandatory blockers: Control Surface WP (frontmatter + callout gate-update + verdict) and Parse Queue WP line 181 (strikethrough + measured times). 3 additional 2026-05-03 dev log stale-note locations updated. All remaining ≤10s refs verified safe. Codex closeout verification may rerun. |
| [Codex Verify: Marker Final Throughput Claims (FAIL)](dev_logs/2026-05-08_codex-verify-marker-final-throughput-claims.md) | 2026-05-08 | FAIL — 2 mandatory blockers: Control Surface WP (≤10s as active gate in 4 locations) and Parse Queue WP line 181 (no supersession note). Fix session above required. |
| [Fix: Marker Final Throughput Claims — Feature 3 Closeout Blocker](dev_logs/2026-05-08_fix-marker-final-throughput-claims.md) | 2026-05-08 | Docs-only. 6 active-looking ≤10s / 5-10s/paper claims fixed across 3 files (hosting decision lines 19+102, scaffold install section, work-packet lines 43+56+126). All now explicitly superseded/rejected/historical. Codex closeout verification may rerun. |
| [Codex Verify: Marker IPC Revised Gate — All-Docs Consistency (FAIL)](dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-all-docs-consistency.md) | 2026-05-08 | FAIL — hosting decision checklist item + Context claim still active; scaffold install still said ~5-10s/paper; work packet lines 43+56+126 still active-looking. Fix session above required. |
| [Marker IPC — Revised Gate All-Docs Consistency Fix](dev_logs/2026-05-08_fix-marker-ipc-revised-gate-all-docs-consistency.md) | 2026-05-08 | Docs-only. ≤10s/paper gate language superseded in 5 locations across 4 docs (scaffold feature doc, 3 work packets). CURRENT_STATE.md updated: warm-worker v1 is Active Feature 3 not deferred. Feature 3 NOT closed. |
| [Codex Verify: Marker IPC Revised Gate (FAIL — remaining docs)](dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-doc-consistency.md) | 2026-05-08 | FAIL — active ≤10s language remaining in scaffold feature doc + 3 work packets; CURRENT_STATE.md still showed warm-worker as deferred. Fix required before closeout. |
| [Marker IPC — Revised Gate Doc Consistency Fix](dev_logs/2026-05-08_fix-marker-ipc-revised-gate-doc-consistency.md) | 2026-05-08 | Docs-only. CURRENT_DEVELOPMENT updated to Active Feature 3. ≤10s gate language removed from 4 docs. Revised gate (≥3 papers, papers 2+ delta ≤5s) documented consistently. Feature 3 NOT marked complete. |
| [Codex Verify: Marker IPC Revised Gate (FAIL — docs)](dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-and-result-evidence.md) | 2026-05-08 | FAIL — code/tests accepted. CURRENT_DEVELOPMENT still shows warm-worker as Paused not Active Feature 3. Active ≤10s language remaining in 4 docs. Docs fix required before closeout. |
| [Marker IPC — Revised Gate and Result Evidence](dev_logs/2026-05-08_marker-ipc-revised-gate-and-result-evidence.md) | 2026-05-08 | Director gate revision: ≤10s/paper rejected as unrealistic; revised to ≥3 papers warm, papers 2+ delta ≤5s. `ipc_warm_worker_used` persistence fix applied (`_extra_result_fields` param); 4 new tests. 158 tests pass. |
| [L3 v1 SVM Topic Filter — Feature Closeout](dev_logs/2026-05-07_l3-v1-svm-feature-closeout.md) | 2026-05-07 | Docs-only closeout. Director decision: BGE-large approved, enforce deferred. Feature doc created, INDEX + CURRENT_STATE.md + CURRENT_DEVELOPMENT.md updated, Feature 3 moved to Recently Completed. |
| [Codex Verify: Marker IPC Warm-Worker v1 Live Validation](dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-live-validation.md) | 2026-05-07 | PASS — live validation confirmed: 3 papers, body_source=marker, ipc_warm_worker_used=true, papers 2+ delta ≤5s, no daemon error, clean shutdown. Actual timings: 45.55s, 69.73s, 48.31s. |
| [Fix: Marker Historical L1-Unblocked Claims](dev_logs/2026-05-07_fix-marker-historical-l1-unblocked-claims.md) | 2026-05-07 | Docs-only. Stale references claiming L1 production is unblocked corrected to honest state: L1 blocked on IPC warm-worker Feature 3 closeout. |
| [Codex Verify — L3 v1 SVM Director Approval Packet (fixed)](dev_logs/2026-05-06_codex-verify-l3-v1-svm-director-approval-packet-fixed.md) | 2026-05-06 | PASS — corrected approval packet verified: acquire/discover flags correct; dry-run/hold-review already work today with model path; enforce still blocked. |
| [Codex Verify — L3 v1 SVM Expanded 156-Label Train/Eval](dev_logs/2026-05-06_codex-verify-l3-v1-svm-expanded-156.md) | 2026-05-06 | PASS — expanded retrain/eval artifact verified: 156 labels, train=117, test=39, macro-F1=1.000, confusion_matrix=[[19,0],[0,20]]. Enforce still blocked. |
| [L3 v1 SVM — Expanded 156-Label Retrain/Eval](dev_logs/2026-05-06_l3-v1-svm-expanded-156-train-eval.md) | 2026-05-06 | Retrain on 156 labels (74/82); test set nearly 2.5× prior (16→39); metrics unchanged; artifacts under `expanded_156/`; prior 61-label artifacts untouched. |
| [L3 v1 SVM — Default-Off Integration](dev_logs/2026-05-06_l3-v1-svm-default-off-integration.md) | 2026-05-06 | SVM wired behind `--prefetch-filter-scorer svm` on both CLIs; enforce hard-blocked at rc=1; smoke PASS; 136 targeted tests pass. |
| [L3 v1 SVM — Real Artifact Smoke Test](dev_logs/2026-05-06_l3-v1-svm-real-artifact-smoke.md) | 2026-05-06 | Dry-run against real arXiv artifact: `decision=allow score=0.7712`; audit fields present; enforce blocked; label integrity confirmed. |
| [Obsidian Vault + Repo Docs — RIS State Sync](dev_logs/2026-05-05_obsidian-vault-ris-state-sync.md) | 2026-05-05 | Docs-only sync: Current-Focus "as of" date fixed; 3 missing L3.2 dev log INDEX entries added; L3 feature description updated to reflect L3.2 + SVM trigger MET. No code/tests/artifacts touched. |
| [L3.2 Prefetch Label Discovery Mode — Closeout](dev_logs/2026-05-05_l3-2-prefetch-label-discovery-closeout.md) | 2026-05-05 | L3.2 complete. SVM trigger MET: 30 allow / 31 reject / 1 pending unlabeled. `research-prefetch-discover` shipped; 36 tests. Feature 3 slot freed. Next: L3 v1 SVM Topic Filter Readiness + Training. |
| [L3.2 Prefetch Label Discovery Mode — Codex Verify SVM Trigger](dev_logs/2026-05-05_codex-verify-l3-2-svm-trigger.md) | 2026-05-05 | PASS — SVM trigger verified: 30 allow / 31 reject / 1 pending unlabeled. Independent JSONL cross-check + `research-prefetch-review counts` confirm threshold met. Artifacts not tracked in git. 99 tests pass. |
| [L3.2 Prefetch Label Discovery Mode — Codex Review](dev_logs/2026-05-05_codex-review-l3-2-prefetch-label-discovery.md) | 2026-05-05 | PASS — 10/10 checks pass: metadata-only guarantee enforced, no PDF/Marker/ingest/embed scope creep, ALLOW queueing correct, idempotency + `--force` correct, offline tests pass. Non-blocking: pre-impl wording in docs to be cleaned up at closeout. |
| [L3.2 Prefetch Label Discovery Mode — Implementation](dev_logs/2026-05-05_l3-2-prefetch-label-discovery-impl.md) | 2026-05-05 | `research-prefetch-discover` CLI: arXiv Atom API (metadata only) → `RelevanceScorer` → `ReviewQueueStore.enqueue()`; `--force` idempotency override; `--include-allow` and `--decision-filter` flags; 36 offline tests; no PDF/Marker/index path touched. |
| [L3.2 Prefetch Label Discovery Mode — Activation](dev_logs/2026-05-05_l3-2-prefetch-label-discovery-activation.md) | 2026-05-05 | Feature 3 activated: metadata-only arXiv candidate discovery for SVM label accumulation. No PDF/Marker/index. Current labels: 7 allow / 20 reject. Docker IPC warm-worker Option A deferred, not canceled — must revisit after L3/SVM stream. |
| [Marker Canonical Parse Queue v0 — Close-out](dev_logs/2026-05-05_marker-canonical-parse-queue-v0-closeout.md) | 2026-05-05 | v0 shipped: queue, CLI, indexing gate, failure semantics, 43 tests. Docker IPC warm-worker deferred to v1. L1 Marker production still blocked. Feature 3 complete. Next options: IPC warm-worker v1, Windows warm validation, or L2 planning. |
| [Codex Re-review: Marker Canonical Parse Queue v0](dev_logs/2026-05-05_codex-rereview-marker-canonical-parse-queue-v0.md) | 2026-05-05 | PASS — all 7 review points resolved: warm-worker honest docs, Marker-only indexing gate, short-body rejection, no scope creep, tests offline. Live Docker multi-paper validation blocked (IPC warm-worker is v1). |
| [Marker Canonical Parse Queue v0 — Codex Fixes](dev_logs/2026-05-05_marker-canonical-parse-queue-v0-fixes.md) | 2026-05-05 | 3 Codex FAIL blockers resolved: `create_warm_thread_worker()` + honest subprocess docs, Marker-only `IngestPipeline` gate, short Marker body rejection. 146 tests pass. |
| [Codex Review: Marker Canonical Parse Queue v0](dev_logs/2026-05-05_codex-review-marker-canonical-parse-queue-v0.md) | 2026-05-05 | FAIL — 3 blockers: warm-worker overclaim on Linux/Docker, missing Marker-only indexing gate, short Marker body incorrectly marked done. |
| [Marker Canonical Parse Queue v0](dev_logs/2026-05-05_marker-canonical-parse-queue-v0.md) | 2026-05-05 | File-backed parse queue, CLI surface (`enqueue`/`list`/`process`/`counts`), `is_marker_ready()` rule, 43 offline tests. Warm-model design documented. |
| [Marker Canonical Parse Queue — Packet Creation](dev_logs/2026-05-05_marker-canonical-parse-queue-packet.md) | 2026-05-05 | Operator decision: Option A (async parse queue). State model, 9 acceptance gates, architecture sketch. Feature 3 assigned. pdfplumber declared legacy/debug only. |
| [Marker Control Surface — Validation Close-out](dev_logs/2026-05-05_marker-single-paper-control-surface-validation.md) | 2026-05-05 | body_source=marker, body_length=56923, parse_seconds=85.95s; control surface PASS; L1 production BLOCKED — ≤10s/paper gate fails 8.6×; next-step options A/B/C documented |
| [Marker Single-Paper Validation Control Surface](dev_logs/2026-05-05_ris-marker-single-paper-validation-control-surface.md) | 2026-05-05 | `run-academic-url` subcommand; process-boundary cancel (subprocess); `parse_seconds` in result; 5 new tests; 2403 pass |
| [L1 Marker Production Rollout — Reconciliation](dev_logs/2026-05-05_marker-production-rollout-reconciliation.md) | 2026-05-05 | L1 blocked: one-shot timeouts on math-heavy papers; scheduler unsafe for single-paper validation; docs updated; new control surface packet created |
| [RIS GPU Scheduler Safety Audit](dev_logs/2026-05-05_context-ris-gpu-scheduler-marker-validation.md) | 2026-05-05 | Read-only mapping: no single-paper submit path, thread-based cancel, coarse success metadata, all-8-jobs registration; min safe command shape documented |
| [RIS Marker Short-Paper Smoke Validation](dev_logs/2026-05-05_ris-marker-short-paper-smoke.md) | 2026-05-05 | Two papers timed out (1200-1800s); box 114 alone 273s; page count not predictive; cold model load 136-270s; scheduler warm path recommended |
| [RIS L1 Marker Production Rollout — Validation](dev_logs/2026-05-03_ris-marker-production-rollout-validation.md) | 2026-05-03 | Codex FAIL blockers resolved: adapter rejection, scheduler split, cache mount path; 7 new tests; GPU validation PENDING (Docker not running) |
| [Codex Review: RIS L1 Marker Production Rollout](dev_logs/2026-05-03_codex-review-ris-marker-production-rollout.md) | 2026-05-03 | FAIL; 3 blockers: marker_failed not end-to-end rejected, scheduler split unimplemented, cache mount /root vs /home/polytool |
| [RIS L1 Marker Production Rollout — Core](dev_logs/2026-05-03_ris-marker-production-rollout-core.md) | 2026-05-03 | Default parser=marker, GPU Dockerfile.ris, explicit failure semantics, 69 tests, Codex PASS |
| [Academic Pipeline Hosting Decision](dev_logs/2026-05-03_academic-pipeline-hosting-decision.md) | 2026-05-03 | Hosting decision accepted: Docker+GPU dev machine, passthrough verified (RTX 2070 Super, CUDA 13.2), volume-mount weights, hard-cutover rollout; hosting blocker resolved; L1 remains blocked pending Marker Docker IPC warm-worker (v1) Feature 3 closeout |
| [RIS L3.1 Prefetch Review Queue — Closeout](dev_logs/2026-05-02_ris-prefetch-review-queue-closeout.md) | 2026-05-02 | Docs-only close-out: feature doc status updated; CURRENT_DEVELOPMENT + INDEX + Current-Focus synced; next path = label accumulation for SVM |
| [RIS L3.1 Prefetch Review Queue — Codex Fixes](dev_logs/2026-05-02_ris-prefetch-review-queue-fixes.md) | 2026-05-02 | PASS WITH FIXES resolved: M1 queue write status, L2 malformed JSONL warning, L1 feature doc, L3 search-mode test; 160 tests pass |
| [Codex Review: RIS L3.1 Prefetch Review Queue](dev_logs/2026-05-02_codex-review-ris-prefetch-review-queue.md) | 2026-05-02 | PASS WITH FIXES; hold-review safe; M1 queue write failure misleading; L1 feature doc stale; L2 silent JSONL drop; L3 search-mode untested |
| [RIS L3.1 Prefetch Review Queue + Label Store](dev_logs/2026-05-02_ris-prefetch-review-queue-label-store.md) | 2026-05-02 | hold-review mode; ReviewQueueStore + LabelStore; research-prefetch-review CLI; research-health stats; 157 tests pass |
| [RIS L3 Pre-fetch Filter — v0 Close-out](dev_logs/2026-05-02_ris-prefetch-filter-v0-closeout.md) | 2026-05-02 | Codex re-review PASS; completion protocol; enforce readiness record; title-only overclaim corrected; feature doc + INDEX + CURRENT_DEVELOPMENT updated |
| [Codex Re-review: RIS L3 Pre-fetch Filter v0](dev_logs/2026-05-02_codex-rereview-ris-prefetch-filter-v0.md) | 2026-05-02 | PASS WITH FIXES; Scenario B 5.88% YES; QA REJECT=0; dry-run safe; enforce experimental; Scenario A=20.0% ≠ <10% |
| [RIS L3 Pre-fetch Filter — v0 Fix (Codex)](dev_logs/2026-05-02_ris-prefetch-filter-v0-fix.md) | 2026-05-02 | v1.1 threshold calibration; research-acquire filter flags; audit fields; simulation tests |
| [Codex Review: RIS L3 Pre-fetch Filter v0](dev_logs/2026-05-02_codex-review-ris-prefetch-filter-v0.md) | 2026-05-02 | FAIL; 3 blockers: Scenario B 20% (not <10%), acquire not wired, auditability incomplete; docs overclaim title-only 6.25% |
| [RIS L3 Pre-fetch Filter — Cold-Start Lexical Scorer v0](dev_logs/2026-05-02_ris-prefetch-filter-coldstart.md) | 2026-05-02 | Cold-start v0; title-only estimate; DB-backed 20% at allow=0.55; v1.1 (allow=0.80) fix in v0-fix log |
| [RIS L3 Pre-fetch Filter — Packet Activation](dev_logs/2026-05-01_ris-prefetch-filter-packet-activation.md) | 2026-05-01 | Stub → active; L5 Rule A evidence; v0/v1 scope boundary; acceptance gates; training data plan |
| [RIS Eval Benchmark v0 Close-out](dev_logs/2026-05-02_ris-eval-benchmark-v0-closeout.md) | 2026-05-02 | Baseline locked; feature doc created; bulk-accept shortcut documented as one-time; next packet = Pre-fetch Relevance Filtering |
| [RIS Eval Benchmark — Golden QA Finalized](dev_logs/2026-05-02_ris-eval-benchmark-golden-qa-finalized.md) | 2026-05-02 | 35-pair QA set reviewed; 4 weak substrings fixed; dry-run passed; baseline not yet created at that step |
| [Scientific RAG Vault Reconciliation](dev_logs/2026-04-29_scientific-rag-vault-reconciliation.md) | 2026-04-29 | Layer 0/1 status truth-sync; `marker_llm_boost` removed; evaluation benchmark stub created; decision doc cross-ref fixed |
| [Marker Layer 1 — Docs Close-out](dev_logs/2026-04-27_ris-marker-closeout-docs.md) | 2026-04-27 | Canonical feature doc, INDEX/CURRENT_DEVELOPMENT updated, stale Prompt B doc superseded |
| [Marker Layer 1 — Concurrency Fix (Prompt D)](dev_logs/2026-04-27_ris-marker-timeout-concurrency-fix.md) | 2026-04-27 | Confirmed semaphore released while worker still ran; `_MARKER_DISABLED` Event prevents zombie stacking; double-call test proves at-most-one thread |
| [Marker Layer 1 — Timeout and LLM Truthfulness (Prompt C)](dev_logs/2026-04-27_ris-marker-timeout-llm-truthfulness.md) | 2026-04-27 | `_MARKER_DISABLED`; no false `marker_llm_boost`; default parser changed to pdfplumber |
| [Marker Layer 1 — Hardening and Validation (Prompt B)](dev_logs/2026-04-27_ris-marker-hardening-validation.md) | 2026-04-27 | 4 Codex fixes; Docker validation; live smoke; parser benchmark on 3 papers; operator feature doc |
| [Marker Layer 1 — Codex Review](dev_logs/2026-04-27_codex-review-ris-marker-core.md) | 2026-04-27 | PASS WITH FIXES; 4 non-blocking findings; live smoke result documented |
| [Marker Layer 1 — Core Integration (Prompt A)](dev_logs/2026-04-27_ris-marker-core-integration.md) | 2026-04-27 | `MarkerPDFExtractor`, fetcher dispatch, adapter propagation, `ris-marker` extra, 16 tests |
| [Final Roadmap Audit — PMXT Sprint Close-out](dev_logs/2026-04-22_packet-final-roadmap-audit.md) | 2026-04-22 | Docs-only truth-sync after PMXT Deliverables A/B/C; stale notes fixed, work-packets closed |
| [Deliverable C — Retriever Over-fetch Fix (Gap 1)](dev_logs/2026-04-22_deliverable-c_gap1-fix.md) | 2026-04-22 | Fixed retriever truncation; 2/5 threshold met; Deliverable C marked COMPLETE |
| [Deliverable C — Re-review](dev_logs/2026-04-22_deliverable-c_rereview.md) | 2026-04-22 | Codex re-review flagged Gap 1 (retriever truncation); NOT COMPLETE pre-fix |
| [Deliverable C — Completion Pass](dev_logs/2026-04-22_deliverable-c_completion-pass.md) | 2026-04-22 | freshness_decay.json fixed; 65 heuristic claims extracted |
| [Deliverable C — Implementation](dev_logs/2026-04-22_deliverable-c_impl.md) | 2026-04-22 | 7 external_knowledge docs seeded to SQLite |
| [Deliverable B — Close-out](dev_logs/2026-04-22_deliverable-b_closeout.md) | 2026-04-22 | Docs-only close-out: feature doc, INDEX, CURRENT_DEVELOPMENT updated; Deliverable B marked complete |
| [Deliverable B — Re-review](dev_logs/2026-04-22_deliverable-b_rereview.md) | 2026-04-22 | MERGE-READY re-verification: all 4 blockers confirmed resolved, 20/186 tests passing |
| [Deliverable B — Fix Pass](dev_logs/2026-04-22_deliverable-b_fix-pass.md) | 2026-04-22 | 4 blockers fixed (`_ns` keys, min_tick_size, exit reasons, attribution); 11 new tests, 4 tightened |
| [Deliverable B — Validation Pack](dev_logs/2026-04-22_deliverable-b_validation-pack.md) | 2026-04-22 | M1-M4, F1-F4, V1-V4 scenario definitions for momentum/favorite/vwap |
| [Deliverable B — Implementation](dev_logs/2026-04-21_deliverable-b_impl.md) | 2026-04-21 | Initial implementation: SportsMomentum, SportsFavorite, SportsVWAP, facade wiring, 9 baseline tests |
| [Deliverable B — Reference Extract](dev_logs/2026-04-21_deliverable-b_reference-extract.md) | 2026-04-21 | Clean-room license analysis, LGPL determination, parameter extraction from upstream repo |
| [Deliverable B — Context Fetch](dev_logs/2026-04-21_deliverable-b_context-fetch.md) | 2026-04-21 | Upstream repo context fetch, work packet scope definition |
| [Fee Model Overhaul — Docs Close-out](dev_logs/2026-04-21_fee-model-overhaul_closeout.md) | 2026-04-21 | Deliverable A docs-only close-out: feature doc finalized, INDEX updated, CURRENT_DEVELOPMENT moved to Recently Completed |
| [Fee Model Overhaul — Final Codex Merge Gate](dev_logs/2026-04-21_fee-model-overhaul_codex-final-merge-gate.md) | 2026-04-21 | MERGE-READY verdict after CLI truthfulness fix; unrelated RIS red acknowledged |
| [Fee Model Overhaul — CLI Truthfulness Fix](dev_logs/2026-04-21_fee-model-overhaul_cli-truthfulness-fix.md) | 2026-04-21 | `simtrader run`/`sweep` now emit truthful category-aware fee label; 2 new CLI tests |
| [Fee Model Overhaul — Finish Pass](dev_logs/2026-04-21_fee-model-overhaul_finish-pass.md) | 2026-04-21 | Shadow CLI gap closed, manifest truthfulness fixed, full 12-entry-point propagation complete |
| [Fee Model Overhaul — Core Changes](dev_logs/2026-04-21_fee-model-overhaul.md) | 2026-04-21 | Core fees.py: category-aware path, KalshiFeeModel, ledger fee_category/fee_role params |
| [Wallet Discovery v1 Truth Sync and Release Checklist](dev_logs/2026-04-10_wallet_discovery_v1_truth_sync_and_release_checklist.md) | 2026-04-10 | Docs truth-sync: removed "pending" language, ROADMAP all 4 items checked [SHIPPED], enhanced operator runbook with go/no-go checklist |
| [Discord Embed Final Polish](dev_logs/2026-04-09_discord_embed_final_polish.md) | 2026-04-09 | Eliminated n/a and none placeholders, conditional fields, shortened footers, severity markers |
| [Discord Alert Layout Refinement](dev_logs/2026-04-09_discord_alert_layout_refinement.md) | 2026-04-09 | Converted all 10 Discord notification nodes from plain-text to structured embed format |
| [Discord Alert Integration Debug](dev_logs/2026-04-09_discord_alert_integration_debug.md) | 2026-04-09 | Debug session for Discord alert delivery via n8n: EAI_AGAIN, webhook URL injection, Send Webhook node fix |
| [Docs and Ops Final Reconcile](dev_logs/2026-04-09_docs_and_ops_final_reconcile.md) | 2026-04-09 | Index and state doc reconcile for shipped RIS Phase 2 + Discord embeds + operator runbooks |
| [RIS Phase 2 Cloud Provider Routing](dev_logs/2026-04-08_ris_phase2_cloud_provider_routing.md) | 2026-04-08 | Gemini + DeepSeek HTTP clients, routed evaluation chain, fail-closed on malformed JSON |
| [RIS Phase 2 Ingest/Review Integration](dev_logs/2026-04-08_ris_phase2_ingest_review_integration.md) | 2026-04-08 | Pipeline dispositions, research-review CLI, pending_review tables |
| [Unified n8n Alerts and Summary](dev_logs/2026-04-08_unified_n8n_alerts_and_summary.md) | 2026-04-08 | Unified n8n workflow consolidation: 9 sections on one canvas, operator notify path |
| [Phase 1 Track A Docs Truth Sync](dev_logs/2026-03-10_phase1_tracka_docs_truth_sync.md) | 2026-03-10 | Docs-only truth sync: status date, Gate 2 tooling inventory, corpus state, INDEX gaps all corrected |
| [Session Pack Target-Regime Fix](dev_logs/2026-03-10_session_pack_target_regime_fix.md) | 2026-03-10 | Fixed: UNKNOWN-regime markets no longer falsely claim to advance named-regime coverage via session-level `--regime` operator fallback |
| [Phase 1 Track A Contract Exercise](dev_logs/2026-03-10_phase1_tracka_contract_exercise.md) | 2026-03-10 | Offline contract exercise: full ranked-JSON -> session pack -> watcher loader chain verified; corpus confirmed 0 eligible tapes, sports coverage only |
| [Background Gate 2 Session Helper](dev_logs/2026-03-10_background_gate2_session_helper.md) | 2026-03-10 | `tools/ops/run_gate2_session.ps1` - PowerShell helper that runs scan -> session pack -> background watch in one command |
| [Coverage-Aware Session Pack](dev_logs/2026-03-10_coverage_aware_session_pack.md) | 2026-03-10 | `make-session-pack` now accepts `--prefer-missing-regimes` / `--target-regime`; adds `coverage_intent` field to session_plan.json |
| [Ranked Scan -> Session Pack Pipeline](dev_logs/2026-03-09_ranked_scan_to_session_pack.md) | 2026-03-09 | `scan-gate2-candidates --ranked-json-out` emits advisory JSON; `make-session-pack --ranked-json` consumes it with rank/gate2_status/explanation preserved in the session plan |
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
| [Discord Alerting - Track A](dev_logs/2026-03-08_discord_alerting_tracka.md) | 2026-03-08 | Discord webhook module, gate hooks, LiveRunner notifier, 29 tests |
| [Discord Session Lifecycle Hooks](dev_logs/2026-03-08_discord_session_lifecycle_hooks.md) | 2026-03-08 | `simtrader live` CLI lifecycle hooks, safe notifier dispatch, 4 new offline tests |
| [Gate 2 Eligible Tape Acquisition](dev_logs/2026-03-08_gate2_eligible_tape_acquisition.md) | 2026-03-08 | tape-manifest CLI, regime labeling on capture tools, eligibility invariant, 34 new tests |
| [Gate 2 Preflight](dev_logs/2026-03-08_gate2_preflight.md) | 2026-03-08 | operator READY/BLOCKED preflight, eligible tape list, exact next action, 55 passing tests |
| [Phase 1 Track A Gap Audit](dev_logs/2026-03-08_phase1_tracka_gap_audit.md) | 2026-03-08 | Read-only audit: gap matrix findings, top 3 blockers, recommended packets (-> SPEC-0013) |
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
