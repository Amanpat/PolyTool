---
title: Current Development
type: living-state-doc
status: active
last_verified: 2026-05-07
source_zone: repo
mirror_of: docs/CURRENT_DEVELOPMENT.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Current Development

This file tracks what is actively being built in PolyTool. It is the Director-level gate on feature scope. The Architect reads this file at the top of every chat and refuses to design prompts for features not listed as Active without Director acknowledgment.

## Rules

1. **Max 3 Active features.** A 4th triggers Architect refusal with a "which Active item pauses or completes first?" prompt.
2. **Staleness limit: 7 days.** Active features without a `last_updated` bump for 7+ days get refreshed or moved to Paused.
3. **Completion protocol** (all three required):
   - Create `docs/features/<slug>.md`
   - Update `docs/INDEX.md`
   - Move entry to Recently Completed
4. **No silent scope changes.** DoD edits require a one-line reason. Enlarging scope triggers a Director conversation.
5. **Blockers are first-class.** Active with external blockers is OK if the feature is otherwise ready. Move to Paused only when work cannot meaningfully continue.
6. **"Awaiting Decision" is its own state.** Work that is complete-but-pending-a-decision does not occupy an Active slot.

## Awaiting Director Decision

### Gate 2 Path Forward

- **Context:** Gate 2 swept 2026-03-29 and re-swept 2026-04-14. Both: 7/50 positive (14%), threshold 70%. Crypto bucket alone: 7/10 (70%).
- **Known Decision Options (from `docs/dev_logs/2026-04-15_gate2_decision_packet.md`):**
  1. Adopt crypto-only subset (spec change; technically passes)
  2. Improve strategy for low-frequency markets (research-heavy, open-ended)
  3. Pivot focus to Track 2 (de facto chosen per 2026-04-15 operator runbook; not formally logged)
- **Added Option 4 (from PMXT work packet 2026-04-10):** Land the SimTrader Fee Model Overhaul first, then re-run Gate 2 with correct maker/taker + category-specific fees. Current Gate 2 FAIL used taker-only + single fee rate — systematically pessimistic for maker strategies.
- **Option 4 blocker resolved 2026-04-21:** Fee Model Overhaul (Deliverable A) is complete. Category-aware fees, maker=0, Kalshi baseline, and full runtime propagation are shipped. Re-running Gate 2 under the corrected fee model is now unblocked.
- **Next action:** Director decides whether to re-run Gate 2 now (Option 4) or commit to one of Options 1–3.

## Active Features (max 3)

### Feature 1: Track 2 Paper Soak — 24h Run

- **Track:** 1A (crypto pair bot)
- **Status:** Infrastructure hardened 2026-04-15 across 6 work packets. Ready to launch.
- **Started:** 2026-04-15 (hardening phase complete); soak itself not yet started
- **Last updated:** 2026-04-21
- **Owner:** Aman + partner
- **Current step:** Launch 24h paper soak per `docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md`
- **Blockers:** None. 12 active 5m markets confirmed (BTC×4, ETH×4, SOL×4).
- **Next action:** Kick off soak on partner machine.
- **Note on fee accuracy:** Corrected fee model (Deliverable A, 2026-04-21) is available. Soak should use `category="crypto", role="maker"` for accurate results.
- **Definition of done:**
  - [ ] 24h paper soak completes without unhandled errors
  - [ ] `paper_soak_verdict.json` produced with promote/rerun/reject outcome
  - [ ] `crypto-pair-review` output captured in dev log
  - [ ] `docs/features/track2_paper_soak_24h_v1.md` created
  - [ ] CURRENT_STATE.md Track 2 section updated

### Feature 2: RIS Operational Readiness — Phase 2A

- **Track:** Research Intelligence System
- **Status:** Implementation complete — awaiting operator end-to-end validation run
- **Started:** 2026-04-22
- **Last updated:** 2026-04-23
- **Owner:** Aman
- **Current step:** All WP1–WP5 implementation complete. Next operator action: run end-to-end validation (11 steps defined in `docs/dev_logs/2026-04-23_ris_phase2a_acceptance_pass.md`). Commit WP5 dirty-worktree changes first.
- **Blockers:** None. Pending operator time to run validation.
- **Definition of done:**
  - [x] WP1: Foundation fixes pass acceptance (scoring weights, per-dim floor, provider_event, R0 seed 11+ docs, 5 open-source docs seeded) — COMPLETE 2026-04-22
  - [~] WP2: Cloud LLM providers implemented and routing chain working — Core COMPLETE (Gemini, DeepSeek, routing, budget, CLI); WP2-D/E/F/G (OpenRouter, Groq, Ollama variants) deferred to Phase 2B
  - [x] WP3: n8n workflow visual improvements (structured output, Discord embeds, daily digest) — COMPLETE 2026-04-23
  - [x] WP4: Monitoring infrastructure (ClickHouse DDL + Grafana RIS dashboard + stale alert) — COMPLETE 2026-04-23
  - [x] WP5: Retrieval benchmark — 31 queries across 5 classes, P@5, per-class reporting, --save-baseline — COMPLETE 2026-04-23
  - [x] `docs/features/ris_operational_readiness_phase2a.md` created — COMPLETE 2026-04-23
  - [ ] End-to-end validation run complete (operator manual step — see acceptance dev log)
  - [ ] CURRENT_STATE.md RIS section updated (after validation run)



## Completion-Doc Debt (tracked, not Active)

Four items shipped 2026-04-14/15 without feature docs. Backfill as consolidated docs where sensible:

- [ ] `docs/features/track2_soak_infrastructure.md` — covers all 6 `2026-04-15_track2_*` dev logs
- [ ] `docs/features/gate2_gold_capture_hardening.md` — covers 2026-04-14 path fix + `tape_validator.py`
- [ ] `docs/features/gate2_post_capture_qualification.md` — covers the qualification workflow
- [ ] Verify `docs/features/crypto-pair-reference-feed-v1.md` accurately covers Coinbase fallback

Estimated 2 hours of Claude Code time. Can be done in one session. Not an Active feature — completion protocol enforcement going forward.

## Recently Completed (rolling 30 days)

| Feature                                                       | Completed  | Track    | Completion doc                                                     |
| ------------------------------------------------------------- | ---------- | -------- | ------------------------------------------------------------------ |
| Vera Discord Bot — Phase B (/pending + approve/deny)        | 2026-06-02 | operator | `docs/features/vera_discord_bot_phase_b.md` — first Discord WRITE surface: `/pending` (operator-only, ephemeral) + one-tap approve/deny buttons. THIN TRIGGER over the verified `discovery review` CLI (`validate_transition` is the only writer; bot never writes rows). Author-guard on list+click (fail-closed), full-address re-validation, list-form subprocess (no shell, password via env), in-process idempotency reserve (no double-write). **Codex adversarial review: 3 passes, 10/10 invariants PASS** (invariant 4 double-write race found + fixed). vera-bot container gains ClickHouse creds + read-only artifacts mount; still no PK/CLOB. 52 Vera tests. Live approve/deny verify is operator-gated. Dev log: `docs/dev_logs/2026-06-02_vera-bot-phase-b-approvals.md`. |
| Vera Discord Bot — Phase A (skeleton + /ping)               | 2026-06-02 | operator | `docs/features/vera_discord_bot_phase_a.md` — discord.py bot replacing retired Hermes. `packages/polymarket/discord_bot/`; one slash command `/ping` (ephemeral); `Intents.none()`; `DISCORD_BOT_TOKEN` fail-fast, never logged; `Dockerfile.vera` + opt-in `vera-bot` compose service (least-privilege env, no PK/CLOB/CH secrets in container); 12 offline tests. **Offline verified; live "online + /ping→pong" requires operator token (handoff).** No writes / no gate access. Phase B (approve/deny buttons via `discovery review` gate, Codex-mandatory) is a separate packet. Dev log: `docs/dev_logs/2026-06-02_vera-bot-phase-a-skeleton.md`. |
| RIS Academic Pipeline — Developer/Operator Demo-Ready v1    | 2026-05-28 | RIS      | `docs/features/FEATURE-ris-academic-demo-ready-v1.md` — Batch B (10 medium papers): done=20, failed=0, sidecar_count=20; Chroma 917 chunks / 21 papers / 0 orphans; 7 semantic probes pass. Codex PASS WITH CONCERNS. Caveats: weather lexical false positive (non-blocking), Docker Chroma gap (Windows host fallback), JIT cache unresolved, Batch C/D deferred. Not production-ready. |
| RIS Academic Pipeline — 3-Paper Operator Validation         | 2026-05-09 | RIS      | Dev log: `docs/dev_logs/2026-05-09_ris-academic-pipeline-3paper-operator-validation.md`. Functional end-to-end pass: 3 arXiv papers; queue 3 done / 0 failed; 79 chunks / 373 claims; `research-query` `had_fallback=false` for both queries. Windows/local warm-thread path (`ipc_warm_worker_used=false`). Docker/GPU IPC batch was optional performance/infra follow-up only. Historical note: at this 2026-05-09 checkpoint, SSRN/NBER and L2.1 ChromaDB semantic retrieval were not yet complete; L2.1 completed on 2026-05-25, and Academic RIS reached developer/operator demo-ready v1 on 2026-05-28. |
| RIS L4 Multi-source Academic Harvesters                      | 2026-05-09 | RIS      | `docs/features/FEATURE-ris-l4-multisource-academic-harvesters.md` — 4 harvesters (arXiv, Semantic Scholar, Crossref, OpenReview); `AcademicCandidate` dataclass; `dedup_candidates()` by canonical_id; `research-harvest` CLI; `SOURCE_CAPABILITY_MATRIX` with SSRN/NBER deferred; 61 tests pass after Codex dedupe-audit fix; L3 scoring integrated. Dev log: `docs/dev_logs/2026-05-09_ris-l4-multisource-academic-harvesters.md`. |
| RIS L2 Academic Query — PaperQA2 RAG Control Flow            | 2026-05-09 | RIS      | `docs/features/FEATURE-ris-l2-academic-query.md` — `research-query` CLI; multi-angle KS query; Marker-ready query-time guard (`body_source=marker`, `body_length>=5000`); paper-level grouping; citation output with arxiv_id/body_source; graceful fallback; 36 tests pass. Dev log: `docs/dev_logs/2026-05-09_ris-academic-pipeline-completion-sprint.md`; Codex audit/fix log: `docs/dev_logs/2026-05-09_codex-audit-fix-ris-academic-pipeline-completion-sprint.md`. |
| RIS L1 Marker Production Readiness Rollout                   | 2026-05-09 | RIS      | `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md` — repeatable operator path (enqueue→warm-process→inspect); runbook at `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`; stale "L1 gated" CLI text removed; 158 tests pass; L1 DoD all criteria met. L2 and L4 later completed 2026-05-09. Dev log: `docs/dev_logs/2026-05-09_ris-l1-marker-production-readiness-rollout.md`. |
| Marker Docker IPC Warm-Worker v1                             | 2026-05-08 | RIS      | `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md` — IPC warm-worker subprocess; daemon=False fix; `ipc_warm_worker_used` persisted. **Revised gate (Director 2026-05-08): ≥3 full PDFs/session; papers 2+ delta ≤5s; `body_source=marker`; `ipc_warm_worker_used=true`; no pdfplumber fallback; no daemon error; clean shutdown.** Measured: 45.55s/69.73s/48.31s; papers 2–3 delta=0.13s/0.22s. Original ≤10s/paper gate rejected as unrealistic. L1 production rollout, L2, and L4 later completed 2026-05-09. Dev log: `docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md`. |
| RIS L3 v1 SVM Topic Filter                                   | 2026-05-07 | RIS      | `docs/features/FEATURE-ris-svm-filter-v1.md` — default-off integrated; dry-run + hold-review ready; enforce deferred. **Director decision 2026-05-07: `BAAI/bge-large-en-v1.5` approved as production model; enforce deferred pending future approval.** 156 labels (74/82), train=117, test=39, macro-F1=1.000, confusion=[[19,0],[0,20]]. `research-prefetch-svm-train` CLI; SVM flags on both acquisition CLIs; enforce blocked at rc=1. 123 targeted SVM tests pass. Dev log: `docs/dev_logs/2026-05-07_l3-v1-svm-feature-closeout.md`. |
| RIS L3.2 Prefetch Label Discovery Mode                       | 2026-05-05 | RIS      | `research-prefetch-discover` CLI: arXiv metadata search → `RelevanceScorer` → `ReviewQueueStore` enqueue; no PDF/Marker/index; `--force` idempotency override; 36 tests. SVM trigger reached: **30 allow / 31 reject / 1 pending unlabeled**. Dev log: `docs/dev_logs/2026-05-05_l3-2-prefetch-label-discovery-closeout.md`. Next: L3 v1 SVM Topic Filter Readiness + Training. |
| Marker Canonical Academic Parse Queue v0                     | 2026-05-05 | RIS      | `docs/features/ris-marker-structural-parser-scaffold.md` — file-backed queue, CLI surface, `is_marker_ready()` gate, Marker-only `IngestPipeline` gate, short-body rejection (retryable/terminal), honest platform docs. 43 tests; Codex re-review PASS. Queue v0 shipped; IPC warm-worker v1 closed 2026-05-08 (revised functional gate). Next L1 production/readiness step requires a separate workpacket/Director decision. |
| Marker Single-Paper Validation Control Surface               | 2026-05-05 | RIS      | `run-academic-url` subcommand; process-boundary subprocess cancel; `parse_seconds` in result; 5 new tests. Validated: `body_source=marker`, `body_length=56923`, `parse_seconds=85.95s`. L1 production blocked on ≤10s/paper gate at time of closeout (**gate later revised/superseded 2026-05-08 — see Marker Docker IPC Warm-Worker v1 closeout above**). |
| RIS L3.1 Prefetch Review Queue + Label Store                 | 2026-05-02 | RIS      | `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` — `hold-review` mode: REVIEW candidates queued, not ingested; `ReviewQueueStore` + `LabelStore`; `research-prefetch-review` CLI; Codex PASS WITH FIXES resolved; 160 tests pass |
| RIS L3 Pre-fetch Relevance Filter v0                         | 2026-05-02 | RIS      | `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` — lexical scorer v1.1; `--prefetch-filter-mode {off,dry-run,enforce,hold-review}`; Scenario B 5.88%; QA REJECT=0; dry-run-ready; reject-only enforce experimental |
| RIS Scientific RAG Evaluation Benchmark v0                   | 2026-05-02 | RIS      | `docs/features/FEATURE-ris-scientific-eval-benchmark-v0.md` — baseline locked; P@5=1.0; Recommendation A (pre-fetch relevance filtering); next: corpus quality / relevance filter |
| RIS Operational Readiness — Phase 2A                         | 2026-04-23 | RIS      | `docs/features/ris_operational_readiness_phase2a.md` — WP1-WP5 complete; implementation done; e2e validation run pending operator |
| PMXT Deliverable B (Sports Strategy Foundations)              | 2026-04-22 | Track 1C      | `docs/features/simtrader_sports_strategies_v1.md` — SportsMomentum/SportsFavorite/SportsVWAP, STRATEGY_REGISTRY wiring, 20 tests, MERGE-READY per Codex re-review |
| SimTrader Fee Model Overhaul (PMXT Deliverable A)             | 2026-04-21 | Cross-cutting | `docs/features/simtrader_fee_model_v2.md` — category-aware taker fees, maker=0, Kalshi baseline, full 12-entry-point propagation, 32 new tests, MERGE-READY per Codex gate |
| Wallet Discovery v1 (Loop A + watchlist + unified scan + MVF) | 2026-04-10 | Research | `docs/features/wallet-discovery-v1.md`                             |
| Track 2 paper-soak hardening (6 items)                        | 2026-04-15 | 1A       | ⚠️ debt — see above                                                |
| Gate 2 post-capture qualification workflow                    | 2026-04-14 | 1B       | ⚠️ debt — see above                                                |
| Gold capture hardening (path fix + validator)                 | 2026-04-14 | 1B       | ⚠️ debt — see above                                                |
| benchmark_v1 closure                                          | 2026-03-21 | 1B       | verify doc exists                                                  |
| Coinbase reference feed fallback                              | 2026-03-26 | 1A       | `docs/features/crypto-pair-reference-feed-v1.md` (verify accurate) |
| RIS Marker Layer 1 scaffold (experimental)                    | 2026-04-27 | RIS      | `docs/features/ris-marker-structural-parser-scaffold.md` — optional Marker parsing wired and hardened; default pdfplumber; CPU timeouts; **not production rollout** |

## Paused / Deferred

| Feature                                                | Paused         | Reason                                                                            | Resume trigger                                                |
| ------------------------------------------------------ | -------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| RIS Marker Queue — Docker IPC Warm-Worker (v1)         | COMPLETE 2026-05-08 | Closed under revised functional gate (Director 2026-05-08). Feature doc: `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`. L1 Marker Production Rollout unblocked. | N/A — closed |
| RIS L1 Marker Production Rollout — Validation          | COMPLETE 2026-05-09 | L1 DoD met: runbook, operator path, Marker-only gate, no pdfplumber fallback, bad-parse rejection, inspection commands. Feature doc: `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md`. Runbook: `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`. L2 PaperQA2 and L4 harvesters now unblocked. | N/A — complete |
| Crypto Gold Tape Resumption                            | 2026-04-21     | Director paused pending Gate 2 decision                                           | Gate 2 Option 1 or 4 chosen                                   |
| Wallet Discovery Loop B (Alchemy watched-wallet)       | 2026-04-15     | Feasibility probe complete; implementation not started                            | Alchemy key + Track 2 soak result known                       |
| Wallet Discovery Loop D (managed CLOB + anomaly)       | 2026-04-15     | Feasibility probe complete; ClobStreamClient blockers open                        | ClobStreamClient PING keepalive + dynamic subscription landed |
| Wallet Discovery Loop C / insider detection            | pre-2026-04-09 | Out-of-scope per "Decision - Roadmap Narrowed to V1"                              | Phase 1 revenue path clear                                    |
| RIS Phase 2 audit follow-up (cloud providers, R0 seed) | ACTIVATED      | Promoted to Active (Feature 2) per Director decision 2026-04-22. See dev log `docs/dev_logs/2026-04-22_ris_phase2a_activation_override.md`. | N/A — now Active |
| PMXT Deliverable C (RIS Knowledge Seeding)             | COMPLETE       | 7 docs seeded, freshness_decay.json fixed, 65 claims extracted, retriever over-fetch fixed. Retrieval: 2/5 original queries surface external_knowledge body claims (>=2/5 threshold met). See dev log 2026-04-22_deliverable-c_gap1-fix.md | N/A — complete |
| pmxt Sidecar Architecture                              | 2026-04-10     | Parked per `12-Ideas/Idea - pmxt Sidecar Architecture Evaluation.md`              | Phase 3 activation                                            |
| Phase 1A WebSocket CLOB migration                      | pre-2026-04-15 | Deferred to post-paper-soak                                                       | Paper soak promote verdict                                    |
| Phase 1C sports directional model                      | N/A            | Not yet started                                                                   | After Track 2 ships OR Gate 2 passes                          |

## Notes for the Architect

- Document priority in CLAUDE.md still applies. This file is below those docs in authority but above Architect prompts for _scoping_ ("should we work on this?"), not _technical content_ ("how should we build this?").
- If the Director describes work that doesn't map to any Active feature, your first response must be: "This doesn't match current Active features [list]. (a) Pause one and add new, (b) extend an existing Active feature, or (c) confirm this is a quick one-off?"
- **"Awaiting Decision" items are not Active.** Do not design prompts that advance Gate 2 work until the Director records a decision in this file.
- **Feasibility probes are not Active.** If the Director asks to implement Loop B or Loop D, cite this file's Paused section and resume trigger.
- **PMXT Deliverable A is COMPLETE (2026-04-21).** Category-aware fees, maker=0, Kalshi baseline, and full runtime propagation are shipped.
- **PMXT Deliverable B is COMPLETE (2026-04-22).** SportsMomentum, SportsFavorite, SportsVWAP shipped with STRATEGY_REGISTRY wiring and 20 tests.
- **PMXT Deliverable C is COMPLETE (2026-04-22).** 7 external_knowledge docs seeded to SQLite, freshness_decay.json corrected (external_knowledge: 12), 65 derived_claims extracted (heuristic path), retriever over-fetch truncation fixed (Gap 1). Retrieval: 2/5 original queries surface external_knowledge body claims (>=2/5 threshold met). Q3 ("SimTrader queue position") and Q4 ("Jaccard Levenshtein market matching") both surface body-claims at rank 2. cross_platform_price_divergence_empirics.md and cross_platform_market_matching.md remain explicitly provisional. See dev log 2026-04-22_deliverable-c_gap1-fix.md.
- **Completion-doc debt is tracked.** When a future feature crosses DoD, your NEXT STEP must include the three-step completion protocol explicitly.
- When Active count hits 3, stop offering architectural next-moves that would create a 4th. Redirect to "which Active feature needs a next step?"
- **RIS Phase 2A implementation is COMPLETE (2026-04-23).** WP1 ✓, WP2-core ✓ (WP2-D/E/F/G deferred to Phase 2B), WP3 ✓, WP4 ✓, WP5 ✓. Next operator action: end-to-end validation run (11 steps in `docs/dev_logs/2026-04-23_ris_phase2a_acceptance_pass.md`). Feature doc at `docs/features/ris_operational_readiness_phase2a.md`. **Hermes is OUT OF SCOPE for Phase 2A and Phase 2B base.** ~~Hermes enters only at WP7, which is conditional on a collaborator contributing via WP6 for 2+ weeks AND explicitly requesting continuous mode.~~ **VOID — Hermes was RETIRED 2026-06-02 (see Architect note below). The WP7 Hermes path no longer exists; do not reintroduce Hermes anywhere.** Do not design prompts that introduce Hermes into Phase 2A or WP6 work. **Phase 2B (WP6)** starts only when: Phase 2A e2e validation passes AND at least one friend explicitly agrees to contribute.
- **RIS Scientific RAG Evaluation Benchmark v0 is COMPLETE (2026-05-02).** Baseline locked: corpus_size=23, P@5=1.0, off_topic_rate=30.43%, Recommendation A. Feature doc at `docs/features/FEATURE-ris-scientific-eval-benchmark-v0.md`. Rule D (parser quality) is secondary/heuristic; do not treat it as a blocker ahead of Recommendation A.
- **RIS Marker Canonical Academic Parse Queue v0 is COMPLETE (2026-05-05).** Queue, CLI surface, `is_marker_ready()` gate, Marker-only academic indexing gate (`IngestPipeline`), short-body rejection, honest platform docs, 43 tests. Codex re-review PASS. Feature doc: `docs/features/ris-marker-structural-parser-scaffold.md`. pdfplumber is legacy/debug only. RAG-ready requires `body_source=marker`. **Docker IPC warm-worker (v1) is COMPLETE (2026-05-08)** — Feature 3 closed under revised functional gate; feature doc: `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`. **L1 Marker Production Rollout and L2 Academic Query are COMPLETE (2026-05-09). L2 query normalization fix also applied 2026-05-09:** `_normalize_question()` + `_build_sub_queries()` in `academic_query.py` strip question preambles for retrieval ("what are prediction markets" → also searches "prediction markets"). JSON output preserves original question. `test_research_query.py` now has 54 tests (was 36). Primary retrieval is ChromaDB semantic vector search (L2.1 — COMPLETE 2026-05-25). KnowledgeStore lexical matching is the fallback when semantic yields no results. Retrieval normalization strips common question preambles before both paths.
- **Marker Single-Paper Validation Control Surface is COMPLETE (2026-05-05).** `run-academic-url` subcommand + process-boundary subprocess cancel shipped. One-paper controlled parse validated: `body_source=marker`, `body_length=56923`, `parse_seconds=85.95s`. 5 new tests (43 targeted / 2403 full pass). Dev log: `docs/dev_logs/2026-05-05_ris-marker-single-paper-validation-control-surface.md`.
- **RIS L3 Pre-fetch Relevance Filter v0 + L3.1 are COMPLETE (2026-05-02).** Feature doc at `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md`. DB-backed results: Scenario B = 5.88% (<10% target met), QA REJECT = 0. All four filter modes shipped: `--prefetch-filter-mode {off,dry-run,enforce,hold-review}`, default `off`. **`hold-review` holds REVIEW candidates in `artifacts/research/prefetch_review_queue/review_queue.jsonl` without ingesting — hold-out invariant preserved even on queue write failure.** `research-prefetch-review list/label/counts` CLI manages the queue. Labels accumulate at `artifacts/research/svm_filter_labels/labels.jsonl`. **Dry-run is safe now. Reject-only enforce is mechanically safe but experimental — corresponds to Scenario A (20.0%), not the <10% Scenario B simulation.** Do not claim reject-only enforcement achieves <10%. Full enforce-ready deferred. Do not claim SVM is implemented — v1 (SPECTER2+SVM) triggered by ≥30 allow + ≥30 reject labels. 160 tests pass. Codex PASS WITH FIXES (M1 queue write status, L2 malformed JSONL warning, L3 search-mode coverage) resolved.
- **RIS L3.2 Prefetch Label Discovery Mode is COMPLETE (2026-05-05).** `research-prefetch-discover` CLI shipped: arXiv metadata search → `RelevanceScorer` → `ReviewQueueStore` enqueue; no PDF/Marker/index; 36 tests. **SVM trigger reached: 30 allow / 31 reject / 1 pending unlabeled** (pending does not block readiness). Dev log: `docs/dev_logs/2026-05-05_l3-2-prefetch-label-discovery-closeout.md`.
- **RIS L3 v1 SVM Topic Filter — expanded 156-label retrain/eval COMPLETE (2026-05-06). PROCEED to Director approval review.** Default-off integration shipped (2026-05-06). Expanded corpus retrain/eval complete: 156 labels (74 allow / 82 reject, 3 pending), train=117, test=39, accuracy=1.000, macro-F1=1.000, confusion_matrix=[[19,0],[0,20]]. Test set nearly 2.5× larger than prior run (16→39); no degradation. Artifacts in `artifacts/research/svm_filter_models/expanded_156/`. 123 targeted SVM tests pass. Label gate (>=150) now met. **Enforce is hard-blocked at rc=1** pending Director approval. Remaining blockers before any enforcement: (1) Director approval, (2) model selection decision (SPECTER2 options or declare `BAAI/bge-large-en-v1.5` as production — `peft` is NOT in `pyproject.toml` ris-svm and NOT needed for the bge-large path). Remaining DoD items: feature doc, CURRENT_STATE.md update, closeout dev log. **Active count is 3 (Features 1, 2, 3) — max-3 reached.**
- **RIS L3 v1 SVM Topic Filter is COMPLETE (2026-05-07).** Default-off integrated; dry-run + hold-review ready; enforce deferred. Director decision: `BAAI/bge-large-en-v1.5` approved as production model. Feature doc at `docs/features/FEATURE-ris-svm-filter-v1.md`. SVM enforce remains hard-blocked at rc=1 pending future Director approval. SPECTER2 path remains unresolved; BGE-large is the declared production model. **Marker Docker IPC warm-worker v1 is COMPLETE (2026-05-08) — active count is now 2 (Features 1, 2).** Feature doc: `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`. L1 Marker Production Rollout and L2 Academic Query later completed 2026-05-09.
- **Marker Docker/Linux IPC Warm-Worker (v1) is COMPLETE (2026-05-08).** All revised functional gates PASS: 3 papers, papers 2+ delta ≤5s (0.13s, 0.22s), `body_source=marker`, `ipc_warm_worker_used=true`, no pdfplumber fallback, no daemon error, clean shutdown. Feature doc: `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`. L1 Marker Production Rollout, L2 Academic Query, and L4 Multi-source Academic Harvesters are now complete. Active count: 2 (Features 1, 2).
- **RIS L1 Marker Production Readiness Rollout is COMPLETE (2026-05-09).** L1 DoD fully met: repeatable operator path (enqueue→warm-process→inspect), Marker-only gate enforced, no pdfplumber fallback, queue state machine and recovery documented, bad/short parse rejection, output inspection commands. Feature doc: `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md`. Runbook: `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`. Stale "L1 gated" CLI text removed. 158 tests pass. **L2 PaperQA2 RAG Control Flow and L4 Multi-source Harvesters are now complete.** Active count: 2 (Features 1, 2). Dev log: `docs/dev_logs/2026-05-09_ris-l1-marker-production-readiness-rollout.md`.
- **RIS L2 Academic Query is COMPLETE (2026-05-09).** `research-query` CLI ships multi-angle KS query with a defensive Marker-ready query-time guard (`body_source=marker` and `body_length>=5000`), paper-level grouping by doc_id, citation enrichment (title/arxiv_id/source_url/body_source), graceful fallback. 54 tests pass. **ChromaDB academic path COMPLETE (L2.1, 2026-05-25):** `_embed_body_into_chroma()`, `--reindex-chroma` CLI flag, `check-chroma-links` subcommand shipped; semantic vector search is now the primary retrieval path. Feature doc: `docs/features/FEATURE-ris-l2-academic-query.md`. Dev log: `docs/dev_logs/2026-05-09_ris-academic-pipeline-completion-sprint.md`; audit/fix log: `docs/dev_logs/2026-05-09_codex-audit-fix-ris-academic-pipeline-completion-sprint.md`. Active count: 2 (Features 1, 2).
- **RIS L4 Multi-source Academic Harvesters is COMPLETE (2026-05-09).** 4 harvesters shipped: `ArxivHarvester`, `SemanticScholarHarvester`, `CrossrefHarvester`, `OpenReviewHarvester`. `AcademicCandidate` dataclass + `dedup_candidates()` by canonical_id. `research-harvest` CLI with `--source all|arxiv|semantic_scholar|crossref|openreview`, `--since` monitoring mode, `--dry-run`, `--list-sources`. `SOURCE_CAPABILITY_MATRIX` documents SSRN/NBER as deferred (session/cookie brittleness / outdated scrapers). L3 scoring integrated inline. 61 tests pass (all offline) after Codex added mixed DOI+arXiv alias coverage. Feature doc: `docs/features/FEATURE-ris-l4-multisource-academic-harvesters.md`. Runbook updated with top-down discover→filter→Marker→query flow. Active count: 2 (Features 1, 2).
- **RIS academic pipeline is operator-tested v1 (2026-05-09).** Full functional path (enqueue→warm-process→index-done→research-query) passed with 3 arXiv papers on Windows/local warm-thread path. Queue: 3 done, 0 failed. 79 chunks, 373 claims. `research-query` returned `had_fallback=false` for both queries (`"prediction markets"`, `"sports betting markets" --step-back`). `ipc_warm_worker_used=false` for this run — Docker/GPU IPC batch was a separate optional performance/infra follow-up, not a functional blocker. Historical note: at this 2026-05-09 checkpoint, SSRN/NBER and L2.1 ChromaDB semantic retrieval were not yet complete; L2.1 completed on 2026-05-25. Academic RIS reached developer/operator demo-ready v1 on 2026-05-28; Batch C/D are deferred to post-v1 hardening, and the pipeline is not production-ready. Dev log: `docs/dev_logs/2026-05-09_ris-academic-pipeline-3paper-operator-validation.md`.
- **RIS Academic Pipeline — Developer/Operator Demo-Ready v1 is FORMALLY CLOSED (2026-05-28).** Final Codex review: PASS (`docs/dev_logs/2026-05-28_codex-final-review-academic-ris-demo-ready-v1.md`). Feature doc: `docs/features/FEATURE-ris-academic-demo-ready-v1.md`. Caveats (MUST remain visible in all future references): weather lexical false positive (non-blocking), Docker Chroma gap (Windows host fallback), JIT cache persistence unresolved, Batch C/D deferred to post-v1 hardening (explicit Tier-3 operator approval required for `arxiv:2409.02025` and `arxiv:1011.6402`). **Not production-ready.** Next Academic RIS work: post-v1 hardening only. First hardening item: Docker `jit-cache-check` to verify cross-restart JIT cache persistence before any Batch C/D planning. Do NOT plan Batch C/D without jit-cache-check result and Tier-3 approval for the two named hard papers.
- **Operator Discord surface (2026-06-02):** two decoupled halves — (1)
  **notifications** via the webhook embed card (WP-1 richer evidence fields +
  WP-2 embed card/digest/copy-block; always-on, bot-independent), and (2)
  **interactive approve/deny** via the **Vera discord.py bot** `/pending` (thin
  trigger over `discovery review`, operator-only, Codex 10/10 PASS, live-verified).
  "Vera" = the new bot, NOT the retired `vera-hermes-agent`. See
  `docs/features/FEATURE-vera-discord-bot.md` + `FEATURE-discord-alerting-tracka.md`.
- **Hermes operator agent is RETIRED (2026-06-02).** The `vera-hermes-agent` profile, `hermes-gateway.service`, the operator skills (`polytool-status` / `dev-logs` / `files`), and helper scripts were all removed — Hermes was read-only and isolated, so removal was low-risk. It is replaced by a planned purpose-built **discord.py "Vera" bot** with real approve/deny buttons routed through the existing `discovery review` gate. The **webhook notification path is unaffected and stays.** Do NOT reintroduce Hermes (no profile, no skills, no WP7 Hermes path). Decision: `docs/obsidian-vault/claude-memory/decisions/decision-retire-hermes-build-vera-bot.md`. Dev log: `docs/dev_logs/2026-06-02_retire-hermes-vera-agent.md`.
