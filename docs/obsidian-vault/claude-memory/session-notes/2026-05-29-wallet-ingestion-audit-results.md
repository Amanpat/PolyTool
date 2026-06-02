---
title: "Wallet-Ingestion Codex Audit — Verified Build State"
type: session_note
status: active
source_zone: claude_memory
last_updated: 2026-05-29
lifecycle: reviewed
session_date: 2026-05-29
participants: [operator, claude, codex]
tags: [session-note, audit, wallet-discovery, ingestion, build-state]
---
# Wallet-Ingestion Codex Audit — Verified Build State

## Purpose
Read-only Codex forensic audit of the wallet-ingestion subsystem, run to verify ACTUAL built state in code before writing v1 work packets. Adversarial stance (docs/filenames treated as unverified claims; only traceable code, DDL, and tests trusted). Full verbatim report (with every file:line citation) is the operator-held artifact and was written by Codex to repo `docs/dev_logs/2026-05-29_wallet-ingestion-audit.md`. This note is the authoritative digest + interpretation.

> **Supersedes** the "built / shipped" framing in [[claude-memory/session-notes/2026-05-29-user-ingestion-v1-scoping]] (the "Key Finding" there was over-optimistic — see below).

## Headline
**The pieces are built and individually tested. They are NOT wired into anything that runs end to end.** The expensive algorithmic parts are real (leaderboard fetch, churn, MVF, dossier export, RIS ingestion, heuristic claims, alpha-distill). The connective tissue (queue consumer, discovery→scan arg seam, scheduler) is missing, and several "tweak" items are actually schema changes. Our prior "acquisition path = shipped" model was wrong in the same way the architect's RIS "Phase 2 complete" claim was — the audit caught it before it corrupted packet scoping.

## Verified Status Table

| Component | Status | Key gap |
|---|---|---|
| `python -m polytool` dispatch + command tree | BUILT | — |
| Leaderboard fetch + snapshots | PARTIAL | no explicit data-api rate throttle |
| Churn detection | BUILT | churn enqueues new wallets; no rank-move auto-rescan |
| `scan_queue` storage + in-memory mgr | PARTIAL | **no consumer leases the queue / runs scans**; loader doesn't collapse ReplacingMergeTree versions |
| Staleness / rescan trigger | CANNOT VERIFY (≈NOT BUILT) | no staleness constant or rescan trigger exists; the "14-day default" is fiction |
| Discovery CLI runner (`discovery run-loop-a`) | PARTIAL | stops at fetch→churn→snapshot→enqueue→watchlist insert; does NOT consume queue or scan |
| Watchlist storage + human gate | BUILT | `reviewed→promoted` requires `review_status=approved`, enforced in code |
| Watchlist auto-promote / tiers / locks | NOT BUILT | no tier/locked/manual-vs-auto columns in DDL |
| `scan --quick` | PARTIAL | API-backed; not an offline ingestion worker |
| `wallet-scan --extract-dossier` | PARTIAL | wires post-scan RIS ingest, BUT raw-wallet path passes `--wallet` while `scan` accepts `--user` only → broken handoff |
| MVF fingerprint | PARTIAL | **11 dims, not 12**; several silently degraded by field-name mismatch (`entry_ts/exit_ts` vs expected); `maker_taker_ratio` input absent → null |
| Dossier artifacts | BUILT | fresh `<user>/<wallet>/<date>/<uuid>/`; no overwrite |
| Dossier → RIS ingestion | BUILT | CLI-wired (`research-dossier-extract`) |
| Changed-content re-ingest lifecycle | NOT BUILT | identical content skipped by hash; **changed content = NEW source doc + new active claims, no supersede branch** |
| Derived claims | BUILT | rule-based/heuristic, no LLM |
| Knowledge-store lifecycle/freshness | PARTIAL | `derived_claims` has lifecycle/superseded fields; **`source_documents` does NOT**; `dossier_report` absent from freshness config → treated timeless (never decays) |
| Alpha-distill | BUILT | deterministic, offline |
| Insider scoring | NOT BUILT | no `insider_score.py`; maker/taker attribution dropped from scan output + ClickHouse imports |
| Exemplar selector | NOT BUILT | — |
| LLM hypothesis generation | PARTIAL | synthesis/bridge is deterministic; no autonomous wallet-hypothesis generator |
| Cloud LLM provider plumbing | PARTIAL | Gemini/DeepSeek present but gated behind `RIS_ENABLE_CLOUD_PROVIDERS=1` / `--enable-cloud` (off by default) |
| Loop B Alchemy monitoring | PARTIAL | feasibility probe only; no production WS client |
| Loop D CLOB managed subscription | PARTIAL | probe only; crypto-pair `ClobStreamClient` exists but lacks PING keepalive, dynamic subscribe, lifecycle parsing, backfill |
| Discovery scheduler | NOT BUILT | manual-invoke only |
| RIS scheduler | BUILT (runtime unverified) | APScheduler `JOB_REGISTRY` + docker services exist; `docker compose ps` not run |
| ClickHouse wallet/RIS DDL | PARTIAL | watchlist/leaderboard_snapshots/scan_queue exist; **no `insider_scores` table** |
| DuckDB historical reads | BUILT | raw Jon parquet retains maker/taker; ClickHouse imports drop it |
| Knowledge SQLite / Chroma names | PARTIAL | Chroma is **`polytool_rag`** (+ `academic_papers`), NOT claimed `polytool_brain`; SQLite at `kb/rag/knowledge/knowledge.sqlite3` |
| RIS Obsidian mirror | PARTIAL | already mirrors **all four** partitions incl. dossier rows via generic source/claims path; no dedicated dossier/user_data path |
| Grafana RIS monitoring | BUILT | reads `polytool.n8n_execution_metrics` |
| Grafana wallet-discovery dashboard | NOT BUILT | — |
| Discord notifications | PARTIAL | outbound webhook only; no two-way bot/buttons/interactions |

## Load-Bearing Evidence (for packet authors)
- No queue consumer: `packages/polymarket/discovery/scan_queue.py` (enqueue/lease exist, no drain); `tools/cli/discovery.py :: _run_loop_a` stops at enqueue.
- Arg seam break: `tools/cli/wallet_scan.py :: _default_scan_callable` passes `--wallet`; `tools/cli/scan.py` parser accepts `--user` only.
- Supersede gap: `packages/research/integration/dossier_extractor.py :: ingest_dossier_findings` lines 481-516 (skip-if-identical only); `packages/polymarket/rag/knowledge_store.py :: _init_schema` lines 139-149 (`source_documents` has no lifecycle fields); `config/freshness_decay.json` lacks `dossier_report`.
- Watchlist DDL: `infra/clickhouse/initdb/27_wallet_discovery.sql` lines 12-40 (no tier/lock columns). Human gate: `packages/polymarket/discovery/models.py :: validate_transition` lines 100-125.
- MVF: `packages/polymarket/discovery/mvf.py :: compute_mvf` lines 377-492 (11 dims). Input mismatches documented in audit §B table.
- Insider data path: raw Jon parquet columns include `maker,taker,maker_asset_id,taker_asset_id,maker_amount,taker_amount,fee` (DuckDB-readable); `user_trades`/`jb_trades` ClickHouse DDL drop them.
- Cloud flag: `packages/research/evaluation/providers.py :: get_provider` lines 736-787.
- Scheduler reuse target: `packages/research/scheduling/scheduler.py :: JOB_REGISTRY` lines 54-103.


## Doc-vs-Reality Discrepancies (from audit)
1. `packages/polymarket/metrics/` does not exist — MVF lives in `discovery/mvf.py`.
2. Loop A is not end-to-end — stops at enqueue; no queue consumer.
3. Staleness "14-day default" — not in code at all.
4. Watchlist auto-promotion — not supported; promotion requires approved human review.
5. Watchlist tier/locked/manual — no DDL columns.
6. MVF "12 dimensions" — code computes 11.
7. Raw-wallet scan — `--wallet`/`--user` arg mismatch breaks default path.
8. "Robust dossier dedup/lifecycle" — only skip-if-identical; changed content accumulates; no source-doc lifecycle.
9. Chroma `polytool_brain` — actual default is `polytool_rag` (+ `academic_papers`).
10. Insider scoring — not implemented; maker/taker inputs absent from scan + ClickHouse.
11. Exemplar selector — not implemented.
12. LLM hypothesis loop — deterministic only.
13. Loop B live monitoring — probe only.
14. Loop D managed subscription — probe only; named blockers.
15. Discovery scheduler — none; manual CLI only.
16. Mirror scope — mirrors four partitions (not just external_knowledge + signals).
17. Wallet-discovery Grafana dashboard — none.
18. Discord two-way — outbound webhook only.

## Critical Unknowns → now resolved
1. Re-ingest/supersede: RESOLVED — accumulation, no supersede branch, `source_documents` schema change required.
2. Insider data: RESOLVED — feasible only from raw Jon parquet via DuckDB; live scan output + ClickHouse drop maker/taker.
3. Mirror scope: RESOLVED — already mirrors dossier via generic path; dedicated path is optional polish, not a build.
4. Scheduler state: RESOLVED — RIS scheduler built (runtime unverified); discovery scheduling not built.

## What Changed vs Our Prior Assumptions
- "Scan→dossier→RIS = shipped" → TRUE as manual pieces, FALSE as an automated pipeline (no consumer, broken arg, no scheduler). This is the single biggest correction.
- "Rescan on 14-day staleness" → no such logic exists; rescan policy is greenfield.
- "Supersede = a tweak" → it's a `source_documents` schema change + ingest branch + freshness-config entry.
- "Watchlist tiers = small add" → DDL change; but the human gate is genuinely enforced, so the two-tier (candidate auto / locked manual) design slots in cleanly.
- "Cloud-LLM authority conflict = unresolved blocker" → resolves to flipping one env flag; plumbing already exists.
- "Extend the mirror" → already done via generic path; downgraded to optional.

## Corrected v1 Work-Packet Plan (dependency order)
1. **Queue consumer + arg-seam fix** — lease `scan_queue` → run `wallet-scan` on address → dossier → RIS ingest → complete/fail; fix `--wallet`/`--user`; collapse RMT to latest on load. *Turns parts into a pipeline.*
2. **Dossier supersede + schema** — add lifecycle fields to `source_documents`; supersede-on-changed-content branch (retire prior doc + supersede prior claims for same wallet); register `dossier_report` in freshness config. *Must precede frequent rescanning.*
3. **Discovery + rescan scheduler** — reuse RIS APScheduler `JOB_REGISTRY` pattern; jobs: discovery cadence, watchlist rescan (configurable), continuous queue drain; tier-aware skip-if-recent (greenfield).
4. **Two-tier watchlist** — DDL for tier/source/locked; auto-candidate population from scan evidence; promotion-to-watched stays behind existing human gate; locked tier never auto-edited.
5. **MVF input fix** — reconcile field-name mismatches so degraded dims (late_entry_rate, avg_hold_duration, trade_frequency) work; decide 12th dim + maker/taker sourcing.
6. **Doc corrections** — fold into packets that touch the files (`polytool_rag`, no `metrics/`, 11 dims, no 14-day staleness, Loop A scope).

## Fast-Follow (out of v1)
- Two-way Discord approval bot (v1 uses CLI/DB approval interim — heaviest net-new component, not on critical path).

## Deferred (unchanged, now with known prerequisites)
- Insider scoring — needs maker/taker capture decision (one-way door for live data); archive-calibration via DuckDB raw Jon only.
- LLM hypotheses + exemplar selector — flag-gated; manual Claude-Code trial is interim; needs API-key + exemplar build.
- Loops B/D — probes only; deferred.
- Off-leaderboard discovery (category leaderboards + CLV/skill archive screen) — fast-follow; counterparty crawl rejected.
- Wallet-discovery Grafana dashboard — after pipeline runs.

## Open Decisions for Operator (before packets finalized)
- Confirm v1 boundary (packets 1-6; Discord deferred).
- maker/taker capture now vs later (one-way door for live data).
- Supersede retention: hard-supersede + keep prior report as "previous results" on disk vs archive-retain.
- Work-packet detail level for architect handoff.

## Cross-References
- [[claude-memory/session-notes/2026-05-29-user-ingestion-v1-scoping]] — scoping decisions (build-state superseded by this note)
- [[claude-memory/research/research-wallet-discovery-pipeline]] — four-loop design
- [[claude-memory/research/research-wallet-discovery-roadmap]] — 7-phase roadmap + WP boundaries
- [[claude-memory/session-notes/2026-04-10-ris-phase2-audit-results]] — prior audit (same overstatement pattern)

## Connections
- [[claude-memory/session-notes/_index]]
- [[index|Vault Home]]
