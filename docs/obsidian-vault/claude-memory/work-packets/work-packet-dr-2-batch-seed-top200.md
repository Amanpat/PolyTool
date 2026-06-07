---
title: "Work Packet — DR-2 Batch-Seed Top-200 Corpus"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-06-04
lifecycle: draft
tags: [work-packet, wallet-discovery, day-run, batch-seed, leaderboard, rate-limit]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — DR-2 Batch-Seed Top-200 Corpus

**Status: DRAFT — pending architect review.**

## Goal
Scan the current top-200 leaderboard wallets in one batch to build the first corpus, ingest each to RIS, and produce the realized-PnL-sorted leaderboard the operator hands to an LLM offline. This is the firehose that achieves the actual goal; the scheduler is the trickle that follows.

## Context (audit evidence)
- `wallet-scan` already batch-scans an `--input` list with `--extract-dossier`, ingests to RIS, and writes `leaderboard.json`/`leaderboard.md` sorted desc by `realized_net_pnl` (`tools/cli/wallet_scan.py:573-661`, `:751-790`). PnL read from `coverage_reconciliation_report.json` (`:421-448`).
- Leaderboard fetch exists: `fetch_leaderboard()` against `https://data-api.polymarket.com` (`packages/polymarket/discovery/leaderboard_fetcher.py:46-88`).
- **Rate gap:** the leaderboard fetch loops pages with no inter-page sleep (`:55-88`); the data-api scan path (`fetch_all_trades`/`fetch_all_activity`) also pages with no sleep (`packages/polymarket/data_api.py`). Retry/backoff covers 429 but is reactive. 200 wallets back-to-back is the aggressive-bulk case → add pacing.

## Scope
1. **Top-200 input list.** Provide a thin, documented way to materialize the current top-200 leaderboard addresses as a `wallet-scan --input` file. Prefer reusing `fetch_leaderboard(top=200)`; if no export helper exists, add a minimal `discovery export-leaderboard --top 200 --out <file>` (read-only fetch → write addresses). Do NOT rebuild leaderboard logic.
2. **Bulk-path rate pacing.** Add an optional, config-driven per-page / per-wallet sleep (e.g. small fixed delay or a simple token-bucket) on the scan path so a 200-wallet batch stays polite. Default conservative; operator-tunable. Must not change behavior of the gentle scheduler cadence unless enabled.
3. **Batch run command + dossier ingest.** Run `wallet-scan --input <top200> --extract-dossier` through the same RIS supersede path. Confirm artifacts: per-user dossiers on disk, RIS docs/claims, and `leaderboard.json`/`leaderboard.md`.
4. **Resumability check.** Confirm a re-run (or a run interrupted partway) does not duplicate or corrupt — relies on the existing supersede + all-or-nothing ingest. Document expected behavior.

## Steps
1. Add/confirm the top-200 export helper (read-only).
2. Add config-driven pacing to the bulk scan path; default conservative.
3. Dry-run on a small N (5-10) → verify dossiers, RIS rows, leaderboard artifacts.
4. Document the full batch-seed command + where the ranked export lands (for the manual LLM handoff).
5. Tests (export helper output shape; pacing applied when enabled) + dev log + CURRENT_STATE.

## Definition of Done
- [ ] Top-200 leaderboard addresses can be exported to a `wallet-scan` input file (reusing existing fetch).
- [ ] Bulk scan path supports config-driven pacing; default conservative; gentle scheduler cadence unaffected.
- [ ] `wallet-scan --input <top200> --extract-dossier` produces dossiers + RIS ingest + ranked `leaderboard.json`/`md`.
- [ ] Re-run / interrupted-run behavior documented (no dup/corruption via supersede + all-or-nothing).
- [ ] Tests + dev log written; ranked-export path documented for the manual LLM step.

## Acceptance Gates
1. **Reuse, don't reinvent.** No new leaderboard fetch or PnL-ranking logic — use `wallet-scan`'s existing path.
2. **Polite by default.** A 200-wallet batch must not hammer the data-api unthrottled.
3. **Goal artifact present.** The ranked `leaderboard.json` is the explicit deliverable.
4. **Denylist untouched.**

## Non-Goals
No automated LLM analysis (manual/offline); no scheduler changes; no retention cap; no insider scoring.

## Dependencies
None hard (API + ClickHouse up). Can run first.

## Cross-References
- [[claude-memory/work-packets/work-packet-scan-day-run-sprint]]
- [[claude-memory/session-notes/2026-06-04-scan-day-run-readiness-scoping]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
