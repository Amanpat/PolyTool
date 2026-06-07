---
title: "Work Packet — DR-3 Discord /status Window"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-06-04
lifecycle: draft
tags: [work-packet, wallet-discovery, day-run, discord, vera, status]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — DR-3 Discord /status Window

**Status: DRAFT — pending architect review.**

## Goal
An on-demand, read-only `/status` slash command in Discord that shows a live scan-status window so the operator can watch the scheduler without opening a terminal. Operator-only invocation; output visible in the (private, 2-person) channel.

## Context (audit evidence)
- The Vera gateway bot is proven for interactions: `/ping` and approve/deny buttons fired over the gateway. It was descoped from v1 for approvals due to operator-environment friction, not code failure.
- Author-guard pattern already shipped: public cards + operator-only action (commit c66f375 "make /pending cards public, keep author-guard").
- Data sources: scan-queue depth + watchlist counts (`packages/polymarket/discovery/clickhouse_writer.py:291-355`, `read_pending_candidates` filters `tier='candidate'`, `review_status='pending'`, `locked=0`, `lifecycle_state='scanned'`); realized PnL from `polytool.user_pnl_bucket.realized_pnl` via `argMax(realized_pnl, computed_at)` (`infra/clickhouse/initdb/06_pnl_tables.sql`; Grafana query at `infra/grafana/dashboards/polyttool_user_overview.json:402`); username from the dossier handle stamp / watchlist row.
- Evidence display already routes through `summarize_evidence()` / `_row_evidence()` (`packages/polymarket/discovery/pending_notify.py`).

## Scope
1. **`/status` command (read-only)** on the Vera gateway. No writes, no DB mutations.
2. **Author-guard.** Only the operator's invocation is honored (reuse the existing author-guard); other members are ignored/denied. Output posts to the channel (public within the private server).
3. **Card content** (embed), matching the agreed layout:
   - Header + timestamp; health line (scheduler up duration, last drain, error count).
   - Metric tiles: in-queue, scanned today, pending review, failed.
   - Top-N by realized PnL with **wallet ID and username as SEPARATE columns**, plus net PnL and positions.
   - Footer: throughput (scans/hr), RIS docs added today.
4. **Data assembly** via existing ClickHouse readers (queue, watchlist, `user_pnl_bucket`) — counts + one ranked query. No new tables.
5. **Env hygiene note (operator-facing, not code):** use a current gateway model (not the retired `gemini-2.0-flash-001`); skills live in the profile dir; restart via `systemctl --user restart hermes-gateway.service` and force a snapshot re-index. Capture in the dev log so reviving the gateway for `/status` doesn't re-hit the 6/2 environment loop.

## Steps
1. Add the `/status` handler (read-only) + author-guard on invocation.
2. Build the status assembler (queue depth, watchlist counts, top-N PnL) from existing readers.
3. Build the embed with wallet ID + username as separate columns.
4. Tests: correct counts on seeded data; top-N ordering; non-operator invocation is ignored; no write path reachable.
5. Live-verify a real `/status` in the channel; dev log + CURRENT_STATE.

## Definition of Done
- [ ] `/status` returns the card with correct queue/scanned/pending/failed counts on seeded data.
- [ ] Top-N by realized PnL renders with wallet ID and username in separate columns.
- [ ] Non-operator invocation is ignored/denied (author-guard); operator invocation works.
- [ ] No write/mutation path exists in the command.
- [ ] Live-verified in the channel; dev log written.

## Acceptance Gates
1. **Read-only.** No DB writes, no lifecycle changes — Codex adversarial review NOT required (but confirm no write surface).
2. **Author-guard enforced.** Only the operator can invoke; reuse the shipped pattern, don't reinvent.
3. **Reuse readers.** No new ClickHouse tables; use existing queue/watchlist/PnL readers.
4. **Denylist untouched.**

## Non-Goals
No approve/deny buttons here (that's the existing `/pending` path); no auto-push digest (on-demand only this sprint); no Grafana embedding.

## Dependencies
A running gateway bot. Best demoed against a seeded corpus (DR-2) so the top-N is non-empty.

## Cross-References
- [[claude-memory/work-packets/work-packet-scan-day-run-sprint]]
- [[claude-memory/work-packets/work-packet-wi-5-discord-approval]] — prior Discord/Vera work + author-guard
- [[claude-memory/session-notes/2026-06-04-scan-day-run-readiness-scoping]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
