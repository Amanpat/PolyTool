---
title: "Work Packet — Wallet Ingestion v1 Sprint (Overview)"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-29
lifecycle: draft
tags: [work-packet, wallet-discovery, ingestion, sprint, overview]
target_agent: architect
acceptance_criteria:
  - See per-packet Definition of Done
---
# Work Packet — Wallet Ingestion v1 Sprint (Overview)

**Status: DRAFT — pending architect review.** Grounded in the verified Codex audit ([[claude-memory/session-notes/2026-05-29-wallet-ingestion-audit-results]]). Hand each packet to Claude Code/Codex as a single-session unit.

## Goal
Wire the built-but-disconnected wallet-ingestion pieces into a continuously-running v1 pipeline: **discover → scan → dossier → RIS**, with rescan hygiene, a two-tier watchlist, a Discord human gate, and corrected MVF inputs. The algorithmic parts already exist and are tested; v1 is connective tissue + data-integrity + the human-gate interface.

## Why (audit headline)
Today the pieces do not run end to end: Loop A enqueues wallets but **nothing consumes the queue**; the discovery→scan handoff is broken (`--wallet` vs `--user`); there is **no scheduler**; and rescanning would accumulate non-decaying duplicate claims because `source_documents` has no supersede path. These four facts define the core packets.

## Operator decisions baked in (2026-05-29)
- **maker/taker:** preserve it *only if the scan's data source already returns it* (lossless capture); do NOT build on-chain enrichment in v1.
- **Supersede retention:** mark prior dossier findings superseded (clean retrieval) + keep prior interpretive report on disk as "previous results" + compress (not delete) prior raw scan.
- **Discord:** IN v1 (not deferred), sequenced after the watchlist/criteria packet (it needs real candidates + evidence to render).
- **Format:** full self-contained packets.

## Packets & dependency order
1. **WP-WI-1 — Queue consumer + arg-seam fix** (+ maker/taker preserve rider). Foundation. Turns parts into a pipeline.
2. **WP-WI-2 — Dossier supersede + schema.** Must land before frequent rescanning. Depends on WP-1.
3. **WP-WI-3 — Discovery + rescan scheduler.** Depends on WP-1 + WP-2.
4. **WP-WI-4 — Two-tier watchlist + promotion criteria + CLI review utility.** Depends on WP-1. Produces the evidence-summary logic WP-5 consumes.
5. **WP-WI-5 — Discord two-way approval.** Depends on WP-4 + a running pipeline producing candidates.
6. **WP-WI-6 — MVF input fix.** Independent — run any time, parallelizable.

## Global non-goals (OUT of v1)
Off-leaderboard discovery (category leaderboards + CLV/skill archive screen); insider scoring; LLM hypotheses + exemplar selector; Loops B/D (live monitoring); wallet-discovery Grafana dashboard; on-chain maker/taker log enrichment; n8n orchestration; any Kalshi work.

## Global guards (every packet)
- **Hard denylist — do not touch:** kill switch, EIP-712/signing, order execution paths, risk manager pre-trade checks, the live trading bot. Wallet-ingestion is research-side; none of these are in scope.
- Mandatory dev log per session at `docs/dev_logs/YYYY-MM-DD_<packet>.md`.
- Secrets (Discord bot token, API keys) are operator-set via `.env` — the agent never handles them.
- One packet per Claude Code session. Update `CURRENT_STATE.md` after each.

## Cross-References
- [[claude-memory/session-notes/2026-05-29-wallet-ingestion-audit-results]] — verified build state (source of truth)
- [[claude-memory/session-notes/2026-05-29-user-ingestion-v1-scoping]] — scoping decisions
- [[claude-memory/research/research-wallet-discovery-roadmap]] — four-loop roadmap (this is the A+C operational core)

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
