---
title: "Work Packet — Scan Day-Run Sprint (Overview)"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-06-04
lifecycle: draft
tags: [work-packet, wallet-discovery, ingestion, day-run, scheduler, discord, sprint, overview]
target_agent: architect
acceptance_criteria:
  - See per-packet Definition of Done
---
# Work Packet — Scan Day-Run Sprint (Overview)

**Status: DRAFT — pending architect review.** Grounded in the Codex audit (repo `docs/dev_logs/2026-06-04_day-run-readiness-audit.md`) and scoping ([[claude-memory/session-notes/2026-06-04-scan-day-run-readiness-scoping]]). Hand each packet to Claude Code/Codex as a single-session unit.

## Goal
Get the user-scanner layer to a state where the operator can **seed a top-200 corpus, then run the scheduler unattended with a one-command on/off and an on-demand Discord status window** — without risking data on stop/start. LLM analysis stays manual/offline; the deliverable is accumulated scans + a ranked PnL export to hand an LLM by hand.

## Why (audit headline)
The pieces run, but: the scheduled drain is **silent on Discord**, scheduler volume is **trickle-only** (the firehose is the `wallet-scan` batch, which already emits the ranked export), there is **no graceful shutdown** and ClickHouse volume persistence is **unverified** (a stop/`down -v` could lose data), and the **bulk scan path has no rate pacing** (200 wallets back-to-back is the "aggressive bulk" case retry/backoff alone doesn't cover).

## Operator decisions baked in (2026-06-04)
- **Batch-seed = top 200.** First corpus via `wallet-scan`, not the scheduler.
- **On/off = scanner-service toggle only.** ON: `up -d clickhouse api discovery-scheduler`; OFF: `stop discovery-scheduler`. `down -v` FORBIDDEN. ClickHouse + API stay up when scans are off.
- **Discord `/status`:** read-only, on-demand, over the Vera gateway, author-guarded (operator-only invokes; output public — channel is a private 2-person server). Reuse the shipped Phase-B author-guard.
- **Status layout:** wallet ID and username are SEPARATE columns.
- **Retention cap, no-resurrect guard, Grafana cleanup = fast-follow** (after first run / before sustained running). Grafana-in-Discord rejected (overengineering).

## Packets & dependency order
Suggested order routes to the actual goal fastest, then makes ongoing running safe.
1. **DR-2 — Batch-seed top-200 corpus.** Independent of the scheduler. Produces the corpus + ranked `leaderboard.json` (the actual goal). Includes bulk-path rate pacing.
2. **DR-0 — Start/stop safety (verify + patch).** Gate for any unattended scheduler run.
3. **DR-1 — One-command on/off toggle.** Depends on DR-0 (clean stop).
4. **DR-3 — Discord `/status` window.** Independent; needed to watch the scheduler once it's on.

Active WIP ≤ 3 per `CURRENT_DEVELOPMENT.md` — these are sequential, not concurrent.

## Global non-goals (OUT of this sprint)
Automated wallet-LLM hypotheses; no-resurrect guard; retention cap; Grafana dashboard build/cleanup; Grafana-in-Discord; Loops B/D; off-leaderboard discovery; insider scoring; Kalshi; n8n.

## Global guards (every packet)
- **Hard denylist — do not touch:** kill switch, EIP-712/signing, order execution paths, risk-manager pre-trade checks, the live trading bot. Wallet-ingestion is research-side.
- **Codex adversarial review** is mandatory only for any write-surface change (DR-3 is read-only → not required; DR-0's shutdown handler touches lifecycle → review recommended).
- Mandatory dev log per session at `docs/dev_logs/YYYY-MM-DD_<packet>.md`.
- Secrets (`DISCORD_BOT_TOKEN`, `CLICKHOUSE_PASSWORD`, API keys) are operator-set via `.env` — the agent never handles them.
- One packet per Claude Code session. Update `CURRENT_STATE.md` / `CURRENT_DEVELOPMENT.md` after each.
- Commit selectively (never `git add .`; never commit `.obsidian/*`). Reconcile the dirty tree + push a clean baseline before any unattended run.

## Cross-References
- repo `docs/dev_logs/2026-06-04_day-run-readiness-audit.md` — verified state (source of truth)
- [[claude-memory/session-notes/2026-06-04-scan-day-run-readiness-scoping]] — scoping + decisions
- [[claude-memory/work-packets/work-packet-dr-0-start-stop-safety]]
- [[claude-memory/work-packets/work-packet-dr-1-onoff-toggle]]
- [[claude-memory/work-packets/work-packet-dr-2-batch-seed-top200]]
- [[claude-memory/work-packets/work-packet-dr-3-discord-status]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
