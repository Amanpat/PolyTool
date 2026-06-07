---
title: "Work Packet — Grafana User-Info Display Diagnosis"
type: work_packet
status: blocked
source_zone: claude_memory
last_updated: 2026-06-04
lifecycle: draft
tags: [work-packet, grafana, clickhouse, dashboards, diagnose-first, fast-follow]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — Grafana User-Info Display Diagnosis

**Status: BLOCKED / GATED. Do NOT run until a real corpus scan has populated ClickHouse.** This is the Grafana fast-follow from Decision #8 of [[claude-memory/session-notes/2026-06-04-scan-day-run-readiness-scoping]] ("after the run produces real data to design against"). Per that decision it is OUT of the current handoff. It exists so it is ready the moment data lands.

## Hard prerequisite (gate)
Before starting, confirm ClickHouse actually has user rows:
```
-- via clickhouse client or docker exec
SELECT count() FROM user_pnl_bucket;
SELECT count() FROM leaderboard_snapshots;
```
If both are **0**, STOP — there is no Grafana bug to fix; the tables are empty because no scan has run. Go run DR-2a → DR-2 first. Only proceed when at least one of these has rows.

## Why this is gated, not a blind fix
The reported symptom — "Grafana dashboards don't display user information" — is the **expected behavior of empty tables**. The leaderboard fetch was returning 0, so `leaderboard_snapshots` (usernames) and `user_pnl_bucket` (PnL) were never populated. Fixing the fetch (DR-2a) and running the corpus (DR-2) may resolve the symptom with zero dashboard changes. Designing dashboard fixes against empty tables is guesswork and risks "fixing" panels that work fine once data exists.

## DIAGNOSE in order (stop at the first real cause; fix only that)
Run AFTER the gate passes. For each panel that should show user info, walk these in order and record findings before changing anything:

1. **Is the data actually there?** Confirm the specific tables/columns the panels query have rows for the time window shown. If the panel queries `user_pnl_bucket` but the scan wrote elsewhere, that's the bug → trace the scan's ClickHouse write path.
2. **Username persistence specifically.** "User information" likely means handles, not just addresses. Confirm whether the scan/discovery path persists `userName` (it IS present in the `/v1/leaderboard` response and in `leaderboard_snapshots`). If dossiers/ClickHouse store only the `0x` address and drop `userName`, then both Grafana AND the future DR-3 status card lack names → fix is in the write path, not the dashboard. This is the most likely *real* cause if data exists but names don't.
3. **Panel query vs schema drift.** Compare each panel's SQL (dashboard JSON under the Grafana provisioning/dashboards dir) against the live ClickHouse schema — table names, column names, database. A renamed column since the dashboard was authored shows as a blank/error panel.
4. **Datasource + time range.** Confirm the ClickHouse datasource is configured and selected, and that the panel's `$__timeFilter` / time range isn't excluding all rows (e.g. scan timestamps outside the dashboard window).

## FIX
Apply only the confirmed cause from the ordered diagnosis. If it's a write-path gap (cause 1 or 2), the fix is in the scan/ingest code (persist the missing field) — flag that this is research-side, denylist untouched. If it's dashboard-side (cause 3 or 4), edit the dashboard JSON / provisioning only.

## Definition of Done
- [ ] Gate confirmed (tables non-empty) and recorded.
- [ ] Ordered diagnosis findings written to the dev log (which cause, with evidence).
- [ ] Only the confirmed cause fixed.
- [ ] At least one panel verified showing real user info (address + username) against live data.
- [ ] Dev log `docs/dev_logs/YYYY-MM-DD_grafana-user-info.md`; `CURRENT_STATE.md` touched.

## Acceptance Gates
1. **Gate-first.** No work on empty tables.
2. **Diagnose before fixing.** Findings in the dev log before any edit.
3. **Right layer.** If the gap is missing persisted data, fix the write path — do not paper over it with a dashboard hack.
4. **Denylist untouched** (kill switch, signing, order/price paths, risk manager).

## Non-Goals
No new dashboards; no Grafana-in-Discord (rejected as overengineering); no retention cap; no scheduler work.

## Dependencies
HARD: DR-2a (fetch fix) + DR-2 (a corpus scan that populates ClickHouse) must have run.

## Sequencing note
Single Claude Code session, AFTER the corpus run. **No sub-agents.** This is a read-then-fix diagnosis, not parallel work.

## Cross-References
- [[claude-memory/work-packets/work-packet-dr-2a-leaderboard-fetch-fix]] — must run first
- [[claude-memory/work-packets/work-packet-dr-2-batch-seed-top200]] — populates the data
- [[claude-memory/work-packets/work-packet-dr-3-discord-status]] — same `userName` persistence dependency (status card wants address + username as separate columns)
- [[claude-memory/session-notes/2026-06-04-scan-day-run-readiness-scoping]] — Decision #8 (Grafana = fast-follow)

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]


---

## UPDATE (2026-06-04) — Prime suspect identified before this packet runs

DR-2a's diagnosis surfaced the likely root cause of "no user information" without needing the gate yet: `to_snapshot_rows` (the Loop A → ClickHouse `leaderboard_snapshots` writer) has the **same camelCase `proxyWallet` bug** the export path had — so any snapshot rows are written with **empty wallets / zero volume**. That is precisely a "dashboard renders, but no user info" symptom *if the panels read `leaderboard_snapshots`*.

Fix packet: [[claude-memory/work-packets/work-packet-loop-a-snapshot-wallet-field-fix]] — run it FIRST.

Revised first diagnosis step for this packet (when un-gated): **determine which table each user-info panel reads** — `leaderboard_snapshots` (Loop A discovery; fixed by the sibling packet, but only populated if Loop A actually runs) vs `user_pnl_bucket` (foreground `wallet-scan` corpus; populated by the live run). The fix path differs:
- Panels read `leaderboard_snapshots` → sibling packet fix + a Loop A snapshot write is the cure; the foreground corpus alone won't populate this table.
- Panels read `user_pnl_bucket` → the corpus run should populate it; confirm `wallet-scan` persists `userName` there (it may store only the address).

So the gate ("are the tables non-empty?") still holds, but the diagnosis now starts from a named suspect instead of cold.
