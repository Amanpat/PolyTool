# CURRENT_STATE.md Decomposition Plan

**Date:** 2026-04-21  
**Status:** Plan only — no files moved, no files created, no files deleted  
**Phase:** Classification phase. Phase 2 (execution) requires operator sign-off.

---

## Summary Block

| Metric | Value |
|--------|-------|
| Total entries classified | 45 (1 intro block + 44 `##` sections) |
| NAV (becomes new CURRENT_STATE.md shell) | 1 |
| CHANGELOG (pure — whole section moves) | 35 |
| STATE (pure — whole section goes to state doc) | 1 |
| MIXED (needs splitting before move) | 8 |
| OTHER | 0 |

### Estimated final sizes

| Output file | Estimated lines | Notes |
|-------------|-----------------|-------|
| `docs/CHANGELOG.md` | ~1 350 | Bulk of the file; all dated shipment records |
| `docs/state/GATE2.md` | ~55 | Gate status, path forward, escalation verdict |
| `docs/state/TRACK1A.md` | ~30 | Crypto pair bot blockers only |
| `docs/state/TRACK1B.md` | 0 → **skip** | No dedicated content; Gate 2 covers MM state |
| `docs/state/TRACK1C.md` | 0 → **skip** | No sections found in file |
| `docs/state/RIS.md` | ~25 | v2 deferred lists from two MIXED sections |
| `docs/state/INFRASTRUCTURE.md` | ~15 | n8n current version; canonical workflow path |
| `docs/state/BLOCKERS.md` | ~13 | "Roadmap Items Not Yet Implemented" |
| `docs/CURRENT_STATE.md` (nav shell) | ~30 | Stripped preamble + pointer table |

### Items flagged for operator review before Phase 2

1. **State docs vs. CLAUDE.md duplication** — The Gate 2 status, Track 2 blockers, benchmark policy lock, and artifact paths already appear verbatim in `CLAUDE.md`. The state docs produced here would duplicate that content unless `CLAUDE.md` is updated to point to the state docs instead. Operator must decide which is the authority before Phase 2 runs.
2. **Section 5 split boundary** — "Status as of 2026-03-29" (lines 131–582) is 452 lines of mixed state and dated history. The proposed split at line 205 should be reviewed before execution; the state summary portion ends naturally at the `## Phase 1B` header boundary (line 205 is after the "RESUME_CRYPTO_CAPTURE" sentence), but the exact line may shift after a close read.
3. **Section 7 historical verdict** — "Phase 1B — Corpus Recovery Tooling" (lines 669–729) describes a tape shortage (10/50) that was subsequently resolved (50/50 per section 5 lines 139–143). Proposed treatment: pure CHANGELOG, no state extraction. Confirm this is correct before moving.
4. **TRACK1B omission** — No dedicated Track 1B section appears. Market-maker gate state is embedded in the Gate 2 section. Confirm TRACK1B should not get its own state file.

---

## Classification Table

Line numbers are 0-indexed as returned by the Read tool (match the line column shown in read output). Ranges are inclusive.

| # | Section title | Line range | Classification | Target | Rationale |
|---|---------------|-----------|----------------|--------|-----------|
| 0 | **[INTRO / PREAMBLE]** — "# Current State / What We Built" + "Branch workflow" + "Docs governance" bullets | 0–30 | **MIXED → NAV** | New `CURRENT_STATE.md` shell + strip dated bullets to CHANGELOG | Preamble introduces the file and has two dated sub-bullets (branch consolidation 2026-04-06, docs ADR citation); strip those to CHANGELOG, keep the 4-line purpose statement as the nav shell. Split: keep lines 0–11 (intro + governing-roadmap sentence); move lines 12–30 to CHANGELOG. |
| 1 | `## Roadmap Items Not Yet Implemented (v5 framing)` | 32–44 | **STATE** | `state/BLOCKERS.md` | Lists four live blockers (control plane, research expansion, UI, live-bot path) with no ship date; content changes as phases complete; re-read in 1 month could differ. |
| 2 | `## Wallet Discovery v1 (Shipped, 2026-04-10)` | 45–63 | **CHANGELOG** | `CHANGELOG.md` | Header includes ship date; content is past-tense shipment record; scope, commit hashes, test counts — stable in 3 months. |
| 3 | `## Gate 2 Corpus Visibility Improvements (quick-260410-izh, 2026-04-10)` | 64–79 | **CHANGELOG** | `CHANGELOG.md` | Dated quick-code record; describes CLI changes, helper names, test counts; past shipment. |
| 4 | `## Infrastructure Fixes (quick-260405-gef + quick-260405-j2t, 2026-04-05)` | 80–129 | **CHANGELOG** | `CHANGELOG.md` | Series of dated Docker/Dockerfile fixes with exact quick codes and commit references; past-tense description of what changed; value unchanged in 3 months. |
| 5 | `## Status as of 2026-03-29 (Phase 1B — Gate 2 FAILED, 7/50 positive at 14%) — Re-confirmed 2026-04-14` | 130–581 | **MIXED** | State portion → `state/GATE2.md`; history portion → `CHANGELOG.md` | **Proposed split at line 205** (after "No AI agent should autonomously trigger benchmark_v2..." sentence and "Do NOT modify…" sentence). Lines 130–205: current gate ladder, path-forward options, escalation verdict, crypto-return verdict — these change as gates progress. Lines 206–581: dated sub-bullets for artifacts restructure (quick-036), market selection (quick-037), live execution (quick-040), Silver tapes, benchmark closure history, gap-fill planner, gap-fill execution, new-market capture, closure orchestrator — all past-tense shipment history. |
| 6 | `## Phase 1B — Gate 2 Benchmark Sweep Tooling Complete (2026-03-26)` | 583–666 | **MIXED** | State portion → `state/GATE2.md`; tooling description → `CHANGELOG.md` | **Proposed split at line 620** ("Gate 2 execution result…"). Lines 583–619: tooling code changes shipped on 2026-03-26 — CHANGELOG. Lines 620–666: Gate 2 NOT_RUN result, diagnostic breakdown, Gate 3 status, "Next action" — these are current status records (superseded by the re-sweep in section 5, but the NOT_RUN finding is historically significant and the "Next action" is still the gate path). Recommend keeping only lines 620–630 (NOT_RUN verdict block) as supplementary context in `state/GATE2.md` under a "History" heading; rest to CHANGELOG. |
| 7 | `## Phase 1B — Corpus Recovery Tooling (2026-03-26)` | 668–729 | **CHANGELOG** | `CHANGELOG.md` | Describes tooling shipped and a shortage state (10/50 tapes) that is **fully superseded**: section 5 lines 139–143 confirm 50/50 corpus complete. "Next action: Capture Gold shadow tapes" is no longer valid. Entire section is historical. ⚠️ **FLAG**: confirm section is superseded before moving. |
| 8 | `## Track 2 / Phase 1A — Crypto Pair Bot (2026-03-23)` | 730–843 | **MIXED** | State portion → `state/TRACK1A.md`; implementation history → `CHANGELOG.md` | **Proposed split at line 785** ("Track 2 paper soak: BLOCKED…"). Lines 730–784: implementation details, module list, CLI, Grafana dashboard, runbook pointers — dated shipment record. Lines 785–843 (minus dividers): paper-soak BLOCKED status, live deployment blockers list (5 items), oracle mismatch concern, deployment environment note — these are current conditions that change when markets become available or paper soak completes. Note: Coinbase feed confirmed working / Binance geo-restricted (lines 799–801) is a live environment fact that belongs in state. Lines 843–848 are section dividers and the archive notice — move to nav. |
| 9 | `## RIS v1 Data Foundation (quick-055, 2026-04-01)` | 850–865 | **CHANGELOG** | `CHANGELOG.md` | Dated quick-code shipment; authority conflict noted as "(RESOLVED)" — past event. |
| 10 | `## RIS Phase 2 — Corpus Seeding and Extractor Benchmark (quick-260401-nzz, 2026-04-01)` | 867–902 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment record; module names, test counts, fixture paths — past state. |
| 11 | `## RIS Phase 2 — Operator Feedback Loop and Richer Query Integration (260401-o1q, 2026-04-01)` | 904–938 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; schema v2 bump, CLI subcommands, test counts — past. |
| 12 | `## RIS Phase 2 — Query Spine Wiring (quick-260402-ivb, 2026-04-02)` | 940–975 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; three-way RRF architecture description, new CLI flags, test counts. |
| 13 | `## RIS Phase 3 — Real Extractor Integration and Corpus Backfill (quick-260402-m6p, 2026-04-02)` | 977–1027 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; extractor table, files changed, test counts. |
| 14 | `## RIS Phase 3 — Evaluation Gate Hardening (quick-260402-m6t, 2026-04-02)` | 1029–1070 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; feature extraction families, dedup module, eval artifact persistence. |
| 15 | `## RIS Phase 4 — External Source Acquisition (quick-260402-ogu, 2026-04-02)` | 1072–1108 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; adapter modules, CLI extension, fixture paths. |
| 16 | `## RIS Phase 4 — Claim Extraction and Evidence Linking (quick-260402-ogq, 2026-04-02)` | 1110–1142 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; design decisions, idempotency note, test counts. |
| 17 | `## RIS Social Ingestion v1 -- Reddit + YouTube (quick-260402-wj9, 2026-04-02)` | 1144–1154 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; adapter additions, deferred Twitter/X rationale. |
| 18 | `## RIS_01 Academic Ingestion — Practical v1 Closure (quick-260402-wj3, 2026-04-02)` | 1156–1172 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; LiveAcademicFetcher, BookAdapter, SSRN deferred. |
| 19 | `## RIS Report Persistence and Catalog (quick-260402-xbt, 2026-04-02)` | 1174–1201 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; ReportLedger, CLI subcommands, storage schema. |
| 20 | `## RIS Query Planner, HyDE Expansion, and Combined Retrieval (quick-260402-xbj, 2026-04-03)` | 1203–1233 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; QueryPlan, HyDE, retrieval.py — past implementation. |
| 21 | `## RIS_05 Synthesis Engine v1 -- Deterministic Report and Precheck Synthesis (quick-260402-xbo, 2026-04-03)` | 1235–1267 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; CitedEvidence, ResearchBrief, EnhancedPrecheck — past. |
| 22 | `## RIS Operator Stats and Metrics Export (quick-260403-1sg, 2026-04-03)` | 1269–1289 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; RisMetricsSnapshot, collect_ris_metrics, CLI. |
| 23 | `## RIS Monitoring and Health Checks (quick-260403-1sc, 2026-04-03)` | 1291–1320 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; run_log, health_checks, alert_sink, 6-condition list. |
| 24 | `## RIS Scheduler v1 (quick-260403-1s3, 2026-04-03)` | 1322–1354 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; 8-job registry, APScheduler, CLI. |
| 25 | `## RIS SimTrader Bridge v1 (quick-260403-jyg, 2026-04-03)` | 1356–1382 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; brief_to_candidate, register_research_hypothesis, bridge functions. |
| 26 | `## RIS_07 Dev Agent Integration and Fast-Research Preservation (quick-260403-jyl, 2026-04-03)` | 1384–1408 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; CLAUDE.md update, integration tests — past. Note: v2 deferred items list in this section was updated in the conditional close (section 44) so this copy is stale; do not extract as state. |
| 27 | `## RIS R5 Dossier Pipeline and Discovery Loop (quick-260403-jy8, 2026-04-03)` | 1410–1438 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; DossierExtractor, DossierAdapter, CLI, batch mode. |
| 28 | `## RIS Final Dossier Operationalization (quick-260403-lim, 2026-04-03)` | 1440–1468 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; --extract-dossier flag, PostScanExtractor hook, integration tests. |
| 29 | `## RIS Bridge CLI and MCP KnowledgeStore Routing (quick-260403-lir, 2026-04-03)` | 1470–1487 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; research_bridge.py, mcp_server.py KS routing, ks_active flag. |
| 30 | `## RIS Dossier Queryability Fix (quick-260403-n2o, 2026-04-03)` | 1489–1518 | **CHANGELOG** | `CHANGELOG.md` | Dated bugfix; root cause, two files changed, 6 new tests. |
| 31 | `## RIS v1 — Complete (2026-04-03)` | 1520–1548 | **MIXED** | "v1 Complete" list → `CHANGELOG.md`; "v2 Deferred" list → `state/RIS.md` | **Proposed split at line 1537** ("v2 Deferred…" header). Lines 1520–1536: inventory of what shipped in v1 — historical record. Lines 1537–1548: v2 deferred items list — these change as phases ship; re-read in 1 month the list would differ. |
| 32 | `## RIS n8n Pilot Roadmap Complete (quick-260404-sb4, 2026-04-05)` | 1550–1569 | **MIXED** | Current canonical path sentence → `state/INFRASTRUCTURE.md`; rest → `CHANGELOG.md` | **Proposed split**: extract only "the current canonical active workflow source is `infra/n8n/workflows/ris-unified-dev.json`" and "Scoped to RIS ingestion only per ADR 0013" (lines 1552–1554 approximately) to `state/INFRASTRUCTURE.md`; everything else is historical workflow-content description. |
| 33 | `## RIS n8n Runtime Path Fixed and Smoke Tested (quick-260404-t5l, 2026-04-05)` | 1571–1594 | **CHANGELOG** | `CHANGELOG.md` | Dated fix record; docker-exec pattern, custom n8n image, smoke test results. The docker-exec pattern IS a current architectural fact but it's already documented in `docs/runbooks/RIS_OPERATOR_GUIDE.md`. |
| 34 | `## RIS n8n Docs Reconciliation (quick-260404-uav, 2026-04-05)` | 1596–1609 | **CHANGELOG** | `CHANGELOG.md` | Docs-only fix session; 5 specific drift corrections — past event. |
| 35 | `## n8n Version Bump: 1.88.0 -> 1.123.28 (quick-260405-vbn, 2026-04-05)` | 1611–1620 | **CHANGELOG** | `CHANGELOG.md` | Dated version bump record — fully superseded by the next section which upgrades to 2.14.2. No state to extract. |
| 36 | `## n8n 2.x Migration: 1.123.28 -> 2.14.2 (quick-260406-ido, 2026-04-06)` | 1622–1641 | **MIXED** | Current facts → `state/INFRASTRUCTURE.md`; migration details → `CHANGELOG.md` | **Proposed split**: extract "current n8n version = 2.14.2", "MCP backend endpoint works on community edition", "`N8N_MCP_BEARER_TOKEN` compose env var", and "`N8N_RUNNERS_MODE=internal` (2.x API)" as current-state facts to `state/INFRASTRUCTURE.md`. Rest (build verification, startup check, workflow import count, specific 2.x API behavior) is migration history. |
| 37 | `## n8n Instance MCP Connection Debug (quick-260406-le7, 2026-04-06)` | 1643–1654 | **CHANGELOG** | `CHANGELOG.md` | Dated debug session; root cause (Claude Code doesn't expand ${VAR} in .mcp.json), fix applied. Permanent gotcha already documented in dev log; state doc not the right home. |
| 38 | `## RIS Phase 2 -- Cloud Provider Routing (quick-260408-*, 2026-04-08)` | 1656–1664 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; Gemini + DeepSeek clients, routing chain, config file. |
| 39 | `## RIS Phase 2 -- Ingest/Review Integration (quick-260408-*, 2026-04-08)` | 1666–1673 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; pipeline dispositions, research-review CLI, pending_review tables. |
| 40 | `## RIS Phase 2 -- Monitoring Truth (quick-260408-oyu, 2026-04-08)` | 1675–1682 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; 5 new snapshot fields, model_unavailable real check, review_queue_backlog check. |
| 41 | `## RIS Phase 2 -- Retrieval Benchmark Truth (quick-260408-oz0, 2026-04-08)` | 1684–1691 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; query class segmentation, 8 metrics, baseline artifacts. |
| 42 | `## Discord Alert Embed Conversion (quick-260409-*, 2026-04-09)` | 1693–1699 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; 10 nodes converted, sender node updated, color-coded severity. |
| 43 | `## Discord Embed Final Polish (quick-260409-*, 2026-04-09)` | 1701–1711 | **CHANGELOG** | `CHANGELOG.md` | Dated shipment; conditional fields, shortened footers, URL truncation, live curl test. |
| 44 | `## RIS Phase 2 -- Conditional Close (2026-04-09)` | 1713–1729 | **MIXED** | "Shipped items" → `CHANGELOG.md`; "Deferred items" → `state/RIS.md` | **Proposed split at line 1725** ("Deferred items…" header). Lines 1713–1724: shipped items inventory — historical. Lines 1725–1729: explicit deferred items list (broad n8n orchestration, n8n scheduling, FastAPI, autoresearch import-results) — current state of what Phase 2 left behind. |

---

## Flagged Items

### A. Cross-reference risks

1. **Section 5 ("Status as of 2026-03-29") internal forward references** — This 452-line section contains 20+ inline references to specific dev logs (`docs/dev_logs/2026-03-XX_*.md`), config paths (`config/benchmark_v1.*`), artifact paths (`artifacts/gates/gate2_sweep/gate_failed.json`), and commands. After splitting, the changelog portion retains all of these inline references, and the state portion retains a much smaller set. No refs are broken as long as the split is at line 205 (the sub-bullets starting at line 164 are all changelog and move together).

2. **Section 7 references section 5's manifest** — Line 725–726 references `config/recovery_corpus_v1.tape_manifest` and the gate re-run command. After section 7 moves to CHANGELOG this cross-reference becomes intra-CHANGELOG (same file), so no issue.

3. **RIS phase sections (9–31) reference each other** — Phase 3 references Phase 2 modules; Phase 4 references Phase 3 output. All of these sections are pure CHANGELOG, so they land in the same `CHANGELOG.md` file and remain co-located. No broken references.

4. **Section 8 (Track 2) references section 5's gate state** — Lines 796–801 reference Gate 2 crypto captures. The state portion of section 8 (deployment blockers) doesn't reference section 5 directly; only the historical portion does. Split is clean.

### B. Spec, decision, or governance content (wrong file)

1. **Gate 3 criteria mentioned in section 5** (line ~199): "Shadow PnL should stay within 25% of replay prediction" — this is spec language already defined in `docs/specs/SPEC-phase1b-gate2-shadow-packet.md`. The CURRENT_STATE.md copy is redundant with the spec. Recommend dropping from the state portion; confirm the spec is authoritative.

2. **Section 1 ("Roadmap Items Not Yet Implemented")** — This is a strategic "what's out of scope" list that arguably belongs in `PLAN_OF_RECORD.md` or `ARCHITECTURE.md` rather than a state doc. It's classified STATE/BLOCKERS here to be conservative, but the operator may prefer to move it to the governing plan doc rather than creating `state/BLOCKERS.md`.

3. **Section 5 "Benchmark policy lock" paragraph** (lines 199–205) — These are operating rules ("Do NOT modify…", "No AI agent should autonomously trigger benchmark_v2") that are also in `CLAUDE.md`. They are governance directives, not state observations. Recommend dropping from `state/GATE2.md` and treating `CLAUDE.md` as the authority for these rules.

### C. Content duplicated in other active docs

| Content | Lives in CURRENT_STATE.md | Also in | Recommendation |
|---------|--------------------------|---------|----------------|
| Gate 2 FAILED (7/50=14%, threshold 70%) | Section 5 lines 138–143 | `CLAUDE.md` lines ~180–186 | `CLAUDE.md` is authoritative; `state/GATE2.md` should supersede or cross-reference, not duplicate |
| Track 2 BLOCKED — awaiting markets | Section 8 lines 785–786 | `CLAUDE.md` "Live deployment BLOCKED" block | Same — choose one authority |
| Benchmark policy lock ("Do NOT modify config/benchmark_v1.*") | Section 5 lines 199–204 | `CLAUDE.md` "Benchmark policy lock" block | `CLAUDE.md` is authoritative; drop from state doc |
| Artifact directory layout | Section 5 lines 164–166 | `CLAUDE.md` "Artifacts directory layout" section | `CLAUDE.md`; drop from state doc |
| ClickHouse auth rule (fail-fast, no polytool_admin fallback) | Section 5 lines ~501–519 (changelog portion anyway) | `CLAUDE.md` "ClickHouse authentication rule" block | Changelog portion only; no state duplication issue |
| Crypto markets returned 2026-04-14 | Section 5 line ~200 | `CLAUDE.md` "Gate 2" block | `CLAUDE.md`; fine to include in state doc as current signal |

**Key question for operator:** After decomposition, should `state/GATE2.md` be the new authority (and `CLAUDE.md` updated to point to it), or should `CLAUDE.md` remain authoritative and the state doc be a secondary view? This determines whether the state docs are "new truth" or "derived summaries." The plan proceeds assuming the operator will update `CLAUDE.md` references after Phase 2.

---

## State Topic Bucket Summary

| Topic | Lines surviving to state doc | Source sections | Zero-content flag |
|-------|------------------------------|-----------------|-------------------|
| GATE2 | ~55 | Sections 5 (state portion), 6 (verdict only) | No |
| TRACK1A | ~30 | Section 8 (state portion: blockers list) | No |
| TRACK1B | 0 | None | ⚠️ ZERO — skip file |
| TRACK1C | 0 | None | ⚠️ ZERO — skip file |
| RIS | ~25 | Sections 31, 44 (v2/deferred lists) | No |
| INFRASTRUCTURE | ~15 | Sections 32, 36 (n8n canonical path + version) | No |
| BLOCKERS | ~13 | Section 1 (Roadmap Items Not Yet Implemented) | No |

---

## Self-Verification

- **Every section appears exactly once**: 45 entries in table (0–44), one row per entry. ✓
- **No missing Target**: every row has a Target column. ✓
- **No STATE or MIXED entry targeted at "CHANGELOG" (as sole target)**: All MIXED entries list both targets. ✓
- **Line range coverage**: Preamble (0–30) + all 44 ## sections cover the file from line 0 through line 1729. Lines 843–848 are divider/archive-notice content between sections 8 and 9; they are implicitly covered by the NAV category (archive notice "Historical details moved to…" belongs in the new nav shell or can be dropped since `docs/archive/CURRENT_STATE_HISTORY.md` already exists). ✓

---

## Verdict

**Blocked — operator review needed on 4 items before Phase 2:**

1. **Authority question** (CLAUDE.md vs state docs): Which is the single source of truth for Gate 2 status, Track 2 blockers, and benchmark policy? Phase 2 should not be run until this is decided — otherwise Phase 2 produces docs that immediately conflict with CLAUDE.md.

2. **Section 5 split point**: Confirm line 205 is the right boundary for the "Status as of 2026-03-29" MIXED section. The state portion from line 130 to line 204 contains current gate status, path-forward options, and escalation verdict. The changelog portion from line 205 onwards is all dated sub-bullets. Operator should read lines 196–214 before approving.

3. **Section 7 historical verdict**: Confirm that "Phase 1B — Corpus Recovery Tooling" (lines 668–729) is entirely superseded by the 50/50 corpus completion and may be moved to CHANGELOG wholesale with no state extraction.

4. **TRACK1B omission and Section 1 placement**: Confirm (a) TRACK1B gets no dedicated state file, and (b) the "Roadmap Items Not Yet Implemented" block should go to `state/BLOCKERS.md` rather than `PLAN_OF_RECORD.md`.

Once these four questions are answered, Phase 2 (actual file moves and creation) can proceed.
