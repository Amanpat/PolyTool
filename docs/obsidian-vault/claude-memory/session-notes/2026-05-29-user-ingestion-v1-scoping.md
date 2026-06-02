---
title: "Target-User Ingestion v1 — Scoping Session"
type: session_note
status: active
source_zone: claude_memory
last_updated: 2026-05-29
lifecycle: reviewed
session_date: 2026-05-29
participants: [operator, claude]
tags: [session-note, wallet-discovery, ingestion, ris]
---
# Target-User Ingestion v1 — Scoping Session

## Session Context
Started on the GitHub pipeline (see [[claude-memory/research/research-github-pipeline-survey]]), then Aman pivoted twice: first to "get the RIS loop to a working state," then narrowed to **target-user (wallet) ingestion to a functional production v1**. The GitHub pipeline is parked as a later additive module. This session scoped the wallet-ingestion v1 against the already-existing four-loop design ([[claude-memory/research/research-wallet-discovery-pipeline]], [[claude-memory/research/research-wallet-discovery-roadmap]]).

## Key Finding
The system Aman brain-dumped is the **four-loop wallet discovery architecture**, already researched to work-packet granularity. This is an execution problem, not a research problem — no new external research commissioned. The honest current state: acquisition path (Loop A leaderboard → scan → dossier → RIS → alpha-distill) is **built**; insider scoring, Loop C LLM hypotheses, and Loops B/D are **designed, not built**.

## Decisions Made This Session

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Scope = wallet-ingestion v1; GitHub pipeline parked | One thing at a time; ingestion is the chosen focus |
| 2 | v1 = Loop A + Loop C (deep-scan worker); defer Loop D and real-time Loop B | Don't add heaviest/infra-blocked piece while downstream incomplete |
| 3 | Loop D (live CLOB anomaly + insider) deferred | Largest/riskiest component, paused on ClobStreamClient blockers; adds complexity before downstream is even complete |
| 4 | LLM hypotheses deferred until a good LLM API key | No key yet; cloud-LLM authority conflict (v5.1 vs PLAN_OF_RECORD) unresolved and is the gate for the automated version |
| 5 | Interim: manual Claude-Code (or chat-Claude) hypothesis generation as a **trial** | Validates whether LLM hypotheses are actually useful before building/paying for the automated layer; manual, doesn't scale, not pipeline-integrated |
| 6 | Off-leaderboard discovery = fast-follow, not v1 gate | Leaderboard already captures top performers by definition; high-value off-board methods = per-category/period leaderboards + CLV/skill screen over Jon-Becker archive. Counterparty-crawl rejected (noise) |
| 7 | Watchlist = two tiers: auto/candidate + locked/manual | Reconciles auto-promotion with the existing human-review-gate invariant; operator's manual picks never touched by the system |
| 8 | "Watchlist scanned multiple times/day" = prioritized **scheduled re-scan**, NOT real-time Alchemy Loop B | Much simpler, no streaming infra; scan order watchlist → leaderboard → rest; frequency configurable |
| 9 | Human review gate via Discord **two-way** approval (Approve/Deny buttons) + short evidence-based reason in the message | Operator decides effectively; reason generated from promotion criteria (PnL, win rate, CLV, insider score, churn trigger). Two-way bot > one-way webhook in effort |
| 10 | Re-scan/retention: tier-aware skip-if-recent; supersede on material re-scan; keep prior interpretive report as "previous results"; **must supersede old claims in RAG, not just the disk folder** | Frequent re-scans otherwise accumulate near-duplicate dossier snapshots (changed content = new hash = not deduped). Consider archive-not-hard-delete for raw. Hypothesis regen only on material fingerprint change |

## Storage Architecture (clarified this session)

Three stores, separation rule intact:
- **RAG (knowledge store: SQLite + Chroma)** — interpretive *findings/claims*. Dossier extraction writes up to 3 docs/wallet (Detectors, Hypothesis Candidates, Memo) as `source_documents` + heuristic `derived_claims`. NOT the complete raw scan. LLM hypotheses (later) also land here (`user_data` partition).
- **ClickHouse** — live/operational data: watchlist, leaderboard_snapshots, scan_queue, trade events, scan results, insider_scores.
- **DuckDB** — historical Parquet reads (Jon-Becker / pmxt archive) for the CLV/skill screen + insider-detector calibration.

Raw full dossier JSON lives on disk under `artifacts/dossiers/...` (fresh `<date>/<run_id>/` per run; reruns never overwrite).

## Other Answers Given
- **Grafana ingestion dashboard:** buildable — reads ClickHouse; RIS monitoring-health dashboard already exists; wallet-discovery dashboard (watchlist, churn, queue depth, insider scores, RAG ingestion rate) is a Phase-7 item in the discovery roadmap.
- **RIS Obsidian mirror:** currently mirrors `external_knowledge` + `signals`; extending it to include wallet/dossier findings (`user_data`) is a sync-config extension. Verify current mirror scope.
- **Insider detection reframed:** archive can only *calibrate* the detector against known historical cases (Forbes $1M-in-24h, CBS Iran/Venezuela) — it cannot find *new* insiders (static + old). Live ephemeral-catching = Loop D (deferred). Per the project's own framework, flagged insiders are monitor/don't-copy (risk filter), not a copyable edge. The edge engine is the skilled-wallet side (MVF + alpha-distill).

## Open Items Before Work Packets
1. **Internal Codex audit** of actual built state in `packages/polymarket/discovery/` + `metrics/` vs the four-loop design — the gating next step. Don't scope packets against inferred state.
2. Verify in code: dossier re-ingest supersede behavior, Jon-Becker schema fields for insider math, current RIS-mirror sync scope.
3. **Cloud-LLM authority decision** — parked alongside LLM deferral; required before the automated hypothesis layer.
4. Retention-policy decision: hard-delete vs archive/compress old raw scans.

## Cross-References
- [[claude-memory/research/research-wallet-discovery-pipeline]] — four-loop architecture
- [[claude-memory/research/research-wallet-discovery-roadmap]] — 7-phase implementation roadmap + WP boundaries
- [[claude-memory/research/research-insider-detection]] — detection methods + calibration cases
- [[claude-memory/research/research-metrics-engine-mvf]] — MVF fingerprint spec
- [[claude-memory/session-notes/2026-04-09-wallet-discovery-pipeline-design]] — original design session
- [[claude-memory/research/research-github-pipeline-survey]] — parked GitHub pipeline survey

## Connections
- [[claude-memory/session-notes/_index]]
- [[index|Vault Home]]
