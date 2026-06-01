---
title: "Work Packet — WI-4 Two-Tier Watchlist + Promotion Criteria"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-29
lifecycle: draft
tags: [work-packet, wallet-discovery, ingestion, watchlist, human-gate]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — WI-4 Two-Tier Watchlist + Promotion Criteria + CLI Review

**Status: DRAFT — pending architect review.**

## Goal
Make the watchlist two-tiered: an **auto/candidate** tier the system populates from deep-scan evidence (continuously updating), and a **locked/manual** tier the operator controls that the system never edits. Keep promotion to "watched" behind the existing enforced human gate. Produce the promotion-criteria + evidence-summary logic (a short human-readable reason string) that WP-5 (Discord) will consume. Add a CLI review command as a dev/ops utility.

## Context (audit evidence)
- Human gate IS enforced: `packages/polymarket/discovery/models.py :: validate_transition` (lines 100-125) requires `review_status=approved` for `reviewed → promoted`; no auto-promote path exists.
- No tier/lock columns: `infra/clickhouse/initdb/27_wallet_discovery.sql :: watchlist DDL` (lines 12-40). Loop A inserts `lifecycle_state=discovered`, `review_status=pending`.
- Lifecycle states/transitions: `packages/polymarket/discovery/models.py :: LifecycleState/ReviewStatus/VALID_TRANSITIONS` (lines 21-69).

## Scope
1. **DDL.** Add `tier` (candidate|locked), `source` (auto|manual), `locked` (bool) to the watchlist table. Forward migration; existing rows default to a sensible tier.
2. **Auto candidate-tier population.** The consumer/worker (WP-1) writes/updates candidate-tier entries from deep-scan evidence (MVF flags, PnL, win rate, CLV, churn trigger) using thresholds in config. Candidate tier is system-owned and may update continuously.
3. **Locked-tier immutability.** Operator-set entries (`source=manual`, `locked=true`) are NEVER modified or removed by any automated path.
4. **Promotion criteria + evidence summary.** A new module computes a short reason string from the evidence (e.g., "+$24k PnL, 64% win / 180 trades, CLV +3.2%, churn-triggered"). Deterministic. Shared by the CLI command and WP-5.
5. **CLI review utility.** `discovery review --approve|--deny <wallet>` writes `review_status` through `validate_transition` (reuse the enforced gate). This is a dev/ops tool, not the production UI.
6. **Gate preservation.** Auto-population only fills the candidate tier; promotion to watched/promoted still requires the human gate. No auto-promote.

## Steps
1. DDL + migration for tier/source/locked.
2. Candidate-tier auto-population from scan evidence (config thresholds).
3. Enforce locked-tier immutability in all auto paths.
4. Promotion-criteria/evidence-summary module (deterministic reason string).
5. `discovery review` CLI over the enforced transition.
6. Tests (tier population, locked immutability, gate enforcement) + dev log.

## Definition of Done
- [x] Candidate tier auto-populates from deep-scan evidence; updates on rescan. — `candidate_population.py` + worker advancer; thresholds in `config/watchlist_promotion.json`.
- [x] Locked tier is operator-only and never auto-modified. — single `is_locked_row` choke point; byte-identical after a full discovery+rescan cycle (tested).
- [x] Evidence-summary reason string generated deterministically from criteria. — `evidence_summary.summarize_evidence()` (the WI-5 contract).
- [x] `discovery review --approve/--deny` promotes/denies through the existing gate. — routes through `validate_transition`.
- [x] Auto-population never bypasses the human gate to watched/promoted. — auto only writes `scanned`+`pending`; no auto-promote path (tested).
- [x] Tests + dev log. — 38 new tests; dev log written.

**COMPLETED 2026-06-01.** Fork #1: kept existing `source` (origin), added `tier` (candidate|locked) + `locked` (UInt8) — no clobber. Fork #2: columns/values match WI-3 `resolve_tier` (verified by `TestResolveTierAlignment`) — scheduler now honors real tiers. **Live-CH DDL applied by orchestrator (2026-06-01):** `ALTER TABLE polytool.watchlist ADD COLUMN IF NOT EXISTS tier ... / locked ...`; existing smoke row backfilled to `tier='candidate', locked=0` (verified). 38 new + existing discovery suites green.

## Acceptance Gates
1. **Gate intact.** No code path auto-promotes past `validate_transition`'s approval requirement.
2. **Locked immutability.** A locked entry is unchanged after a full discovery+rescan cycle (test it).
3. **Determinism.** Same evidence → same reason string.
4. **Regression.** Existing lifecycle/transition tests pass with 0 new failures.

## Non-Goals
No Discord here (WP-5 consumes the criteria module); no auto-promotion past the gate; no removal/edit of locked entries by automation; no off-leaderboard discovery sourcing.

## Dependencies
WP-1 (scan evidence to populate from). Feeds WP-5.

## Cross-References
- [[claude-memory/work-packets/work-packet-wallet-ingestion-v1-sprint]]
- [[claude-memory/work-packets/work-packet-wi-5-discord-approval]]
- [[claude-memory/session-notes/2026-05-29-wallet-ingestion-audit-results]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
