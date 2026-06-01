---
title: "Work Packet — WI-6 MVF Input Fix"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-29
lifecycle: draft
tags: [work-packet, wallet-discovery, ingestion, mvf, data-quality]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — WI-6 MVF Input Fix

**Status: DRAFT — pending architect review.** Independent — can run any time, parallel to WP-1..WP-5.

## Goal
Fix the silent MVF degradation caused by field-name mismatches so `late_entry_rate`, `avg_hold_duration_hours`, and `trade_frequency_per_day` compute on real values instead of falling back. Formally resolve the dimension count (the code computes 11, docs claim 12). Wire `maker_taker_ratio` only if WP-1's maker/taker rider landed.

## Context (audit evidence)
- `packages/polymarket/discovery/mvf.py :: compute_mvf` (lines 377-492) emits 11 dimensions.
- Field-name mismatches (audit §B table): helpers expect `first_trade_timestamp`/`last_trade_timestamp` and `market_open_ts`/`market_created_at`, but scan output uses `entry_ts`/`exit_ts` and lacks the expected market-open names → `late_entry_rate`, `avg_hold_duration_hours`, `trade_frequency_per_day` silently degrade.
- `maker_taker_ratio` input absent from position rows → currently null (`packages/polymarket/llm_research_packets.py` export, lines 1600-1639).

## Scope
1. **Reconcile field names** between the scan dossier position export and the MVF helpers — prefer adapting the MVF helpers (or a normalization boundary) to consume the actual scan field names, rather than changing the scan schema. Cover `entry_ts`/`exit_ts` ↔ hold-duration + trade-frequency, and the market-open/create timestamp used by `late_entry_rate`.
2. **Verify non-degradation** of the three affected dimensions on real scan output.
3. **Resolve dimension count** — either define and add the missing 12th dimension or formally drop the claim to 11 (update docs/roadmap). Record the decision.
4. **maker_taker_ratio** — leave null unless WP-1 preserved maker/taker; if it did, wire the input.
5. **Strengthen tests** — `tests/test_mvf.py` should assert correct values for the previously-degraded dimensions, not just the dimension count.

## Steps
1. Map each degraded dimension's expected vs actual field names.
2. Adapt helpers/normalization so they read the real fields.
3. Verify on a real scan; assert values in tests.
4. Decide + record the dimension-count resolution.
5. Conditionally wire maker_taker_ratio.
6. Dev log.

## Definition of Done
- [x] `late_entry_rate`, `avg_hold_duration_hours`, `trade_frequency_per_day` compute on real values (no silent fallback). — field-name resolvers consume real scan fields (`entry_ts`/`exit_ts`/`resolved_at`); `late_entry_rate` plumbs `markets_enriched.start_date_iso` (market-open) via the existing close-ts JOIN.
- [x] Tests assert correct values for those dimensions. — `test_mvf.py` asserts real values (e.g. hold=14.0, freq=1.333, late_entry=1.0 on sample), not just count.
- [x] Dimension count resolved and documented — corrected to **11** (code always emitted 11; no clean data-backed 12th; `maker_taker_ratio` has no live input). Authoritative in `mvf.py` docstring.
- [x] `maker_taker_ratio` documented null (absent from Polymarket Data API per WI-1); helper retained for archive backfill if a `maker`/`side_type` field is ever supplied.
- [x] Dev log written.

**COMPLETED 2026-06-01.** Ran in parallel with WI-3 (disjoint files). 57 passed (mvf + wallet_discovery_integrated, `== 11` green). `late_entry_rate` was initially deferred ("market-open absent") but orchestrator verified `start_date_iso` exists in `markets_enriched` — plumbed it through (NOT a new data source); now computes real values. No MVF algorithm redesign, no insider scoring.

## Acceptance Gates
1. **Determinism.** Same scan input → same MVF vector.
2. **No redesign.** No new MVF algorithm or new external data source (maker/taker comes only from WP-1).
3. **Regression.** Existing MVF tests pass; count assertions updated to match the resolved count.

## Non-Goals
No MVF algorithm redesign; no new data sources; no insider scoring.

## Dependencies
Independent. `maker_taker_ratio` wiring is contingent on WP-1's rider.

## Cross-References
- [[claude-memory/work-packets/work-packet-wallet-ingestion-v1-sprint]]
- [[claude-memory/session-notes/2026-05-29-wallet-ingestion-audit-results]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
