---
title: "Decision — Descope Vera two-way Discord approval from wallet-ingestion v1"
type: decision
status: active
source_zone: claude_memory
last_updated: 2026-06-02
lifecycle: ratified
decision_date: 2026-06-02
tags: [decision, wallet-discovery, ingestion, discord, vera, scope, v1]
---
# Decision — Descope Vera two-way Discord approval from wallet-ingestion v1

## Decision (ratified by operator, 2026-06-02)
Wallet-ingestion **v1 ships without** the Vera/Hermes two-way Discord approval. v1's operator surface is:
- **Notifications** → existing shipped outbound webhook (`packages/polymarket/notifications/discord.py` → `post_message`, `DISCORD_WEBHOOK_URL`, Vera-free, 29 tests).
- **Approvals** → the CLI gate `discovery review --approve/--deny` (routes through the enforced `validate_transition`).

The Vera two-way approval (reply `approve <addr>` in Discord → agent invokes the CLI) is **parked**, revisited only if reply-from-phone proves necessary — and from a clean start if so.

## Why
- The approval gate is **independently verified working** (Codex e2e, 2026-06-02 — see completion note): approve/deny transition correctly, truncated-address guard holds, no gate bypass.
- The Vera integration cost ~a week of environment failures, **none of which touched PolyTool code**: retired fallback LLM (`gemini-2.0-flash-001` 404), skill profile-dir vs `external_dirs` snapshot mismatch, `python` vs `python3`, stale `.skills_prompt_snapshot.json` not regenerating on restart, and a **systemd-detached gateway nobody was actually restarting** (the root of the loop).
- It is the ~10%-of-value / ~90%-of-effort piece. At one operator and a handful of wallets, outbound notify + CLI approve delivers the operator workflow without the agent-integration surface.

## Authorized follow-ups (this session)
1. **One CC packet** — (a) compute `summarize_evidence()` at `--list-pending`/display time so every pending candidate shows real evidence (PnL/win-rate/CLV) regardless of which path advanced it, replacing the generic worker reason; (b) on a candidate entering pending, post via `post_message` a notification carrying the address, `summarize_evidence()` body, and exact approve/deny CLI commands — reusing the WI-5 `--mark-notified`/dedup so each candidate notifies once; notify must never raise. Then **Codex audits**.

## Pre-scheduler-hot items (not v1 blockers)
- Confirm the scheduler re-scan won't resurrect a `rejected` wallet as `pending` (deny leaves lifecycle `scanned`, review_status `rejected`).
- Retention cap for unbounded archive/superseded-row growth.

## Cross-References
- [[claude-memory/session-notes/2026-05-31-wallet-ingestion-sprint-completion]] — v1 closure + 2026-06-02 verification addendum
- [[claude-memory/decisions/decision-roadmap-narrowed-v1]] — v1 scope
- [[repo-docs/features/feature-discord-alerting-tracka]] — the outbound webhook being reused

## Connections
- [[claude-memory/decisions/_index]]
- [[index|Vault Home]]
