---
title: "Work Packet — Loop A Snapshot Wallet-Field camelCase Fix"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-06-04
lifecycle: draft
tags: [work-packet, wallet-discovery, loop-a, clickhouse, leaderboard-snapshots, camelcase, bugfix, grafana-suspect]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — Loop A Snapshot Wallet-Field camelCase Fix

**Status: DRAFT — ready. Sibling of [[claude-memory/work-packets/work-packet-dr-2a-leaderboard-fetch-fix]] (same root cause, second site). Prime suspect for [[claude-memory/work-packets/work-packet-grafana-user-info-diagnosis]].**

## Goal
Fix the camelCase field mismatch in `to_snapshot_rows` so Loop A's `leaderboard_snapshots` ClickHouse writes contain **real wallet addresses, usernames, and volume/PnL** instead of empty/zero values. DR-2a fixed the same class of bug on the **export** path; Claude Code flagged by inspection that `to_snapshot_rows` (the **snapshot** path feeding ClickHouse) still reads snake_case from a camelCase API response — so it would write empty wallets / zero volume.

## Context (evidence)
- The `/v1/leaderboard` response uses camelCase: `rank` (string), `proxyWallet`, `userName`, `xUsername`, `verifiedBadge`, `vol`, `pnl`, `profileImage`. (Verified live, 2026-06-04.)
- DR-2a fix: export now reads `proxyWallet` with `proxy_wallet` fallback; rank sort uses `int()`.
- `to_snapshot_rows(raw_entries, fetch_run_id, snapshot_ts, order_by, time_period, category, prior_wallets)` converts raw entries → `LeaderboardSnapshotRow` → ClickHouse `leaderboard_snapshots`. It was **deliberately out of DR-2a scope** and still has the mismatch.
- Impact: `leaderboard_snapshots` rows written with empty wallet + zero vol. This is the **leading hypothesis for the Grafana "no user information" symptom** (if panels read this table) and would also starve the DR-3 status card.

## Scope
1. **Map every field, not just the wallet.** Inspect `to_snapshot_rows` + the `LeaderboardSnapshotRow` model + the ClickHouse insert. For EACH API field used (`proxyWallet`, `userName`, `vol`, `pnl`, `rank`, optionally `xUsername`/`verifiedBadge`/`profileImage`), confirm the read key matches the camelCase response. Fix each mismatch with the same additive pattern as DR-2a (camelCase first, snake_case fallback) so existing fixtures still pass. CC reported "empty wallets / zero volume" → at minimum `proxyWallet` AND `vol` are wrong; verify the rest.
2. **Rank coercion.** If rank is stored/sorted, coerce `int(e.get("rank") or 0)` (string in the API).
3. **Regression test** mirroring the live camelCase shape (reuse the DR-2a fixture).

## Steps
1. Read `to_snapshot_rows`, the model, and the ClickHouse write path; build the full API-field → row-field map.
2. Apply additive camelCase reads for every mismatched field; int-coerce rank.
3. Add/extend a regression test asserting a camelCase entry yields a row with non-empty wallet, username, and non-zero vol/pnl.
4. If a one-shot Loop A / snapshot-write path exists (e.g. a `discovery` run-once), run it and verify `leaderboard_snapshots` now has real wallet + username + vol. If not runnable without the full scheduler, document how to verify and assert via the test only.
5. Dev log + `CURRENT_STATE.md`.

## Definition of Done
- [ ] Every API field read in `to_snapshot_rows` matches the camelCase response (additive fallback; fixtures pass).
- [ ] Rank int-coerced.
- [ ] Regression test asserts non-empty wallet/username + non-zero vol/pnl from a camelCase entry.
- [ ] Snapshot write verified to contain real data (live one-shot if available, else documented + test-asserted).
- [ ] Dev log `docs/dev_logs/2026-06-04_loop-a-snapshot-camelcase-fix.md`; `CURRENT_STATE.md` touched.

## Acceptance Gates
1. **Full field map, not just wallet.** Fixing only `proxyWallet` and missing `vol`/`pnl`/`userName` is a fail.
2. **Additive reads.** Existing fixtures/tests stay green.
3. **Diagnose before fixing** the field map (read the model + insert first).
4. **Denylist untouched** (kill switch, signing, order/price paths, risk manager). This is research-side.

## Non-Goals
No Grafana dashboard edits (that's the Grafana packet); no scheduler revival; no export-path changes (DR-2a done); no new dependencies.

## Dependencies
None hard. **Independent of the foreground corpus run** — does not block it and can run in a separate session.

## Sequencing note
Single Claude Code session, no sub-agents. Independent of the corpus run, so it may run alongside it. Run this **before** the Grafana diagnosis packet — it's that packet's prime suspect.

## Cross-References
- [[claude-memory/work-packets/work-packet-dr-2a-leaderboard-fetch-fix]] — sibling, same root cause, first site
- [[claude-memory/work-packets/work-packet-grafana-user-info-diagnosis]] — this is its leading suspect
- [[claude-memory/work-packets/work-packet-dr-3-discord-status]] — same `userName` dependency
- [[claude-memory/session-notes/2026-06-04-scan-day-run-readiness-scoping]]
- repo `docs/dev_logs/2026-06-04_leaderboard-fetch-fix.md` — where the follow-up was flagged

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
