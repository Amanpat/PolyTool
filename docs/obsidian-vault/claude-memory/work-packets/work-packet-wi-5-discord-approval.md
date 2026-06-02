---
title: "Work Packet — WI-5 Vera Text-Bridge Approval"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-06-01
lifecycle: draft
tags: [work-packet, wallet-discovery, ingestion, discord, vera, human-gate]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — WI-5 Vera Text-Bridge Approval

**Status: DRAFT — pending architect review.** Supersedes the prior standalone-bot/buttons WI-5 spec. Unblocked: Vera's Discord integration is live.

## Goal
Implement the human-gate approval interface as a **text-command flow through the existing Vera (`vera-hermes-agent`) Discord integration**, bridged to PolyTool's already-built `discovery review` gated CLI. No standalone bot, no buttons.

## Verified state (2026-06-01)
- Vera is integrated with Discord and **confirmed to send AND receive text** (operator → Vera, Vera → channel). Buttons/component interactions are NOT built and Hermes support is unconfirmed — the text path is sufficient, so buttons are out of scope (later upgrade).
- Vera's SOUL.md is **read-only**: no gate writes, no bot control, no secret access. The approval *action* must therefore go through PolyTool's gated CLI, never a direct Vera write.
- WI-4 shipped `discovery review --approve/--deny <wallet>` over the enforced gate (`validate_transition`) and `summarize_evidence()` (the message body contract).

## Scope
1. **PolyTool emit side.** Add `discovery review --list-pending` (READ-ONLY) if not already present — lists candidate-tier wallets awaiting the human gate, each with its `summarize_evidence()` string and **full** wallet address. Build the approval-request message formatter: evidence body + reply syntax (`approve <full_address>` / `deny <full_address>`). Dedup so the same pending item isn't re-posted (PolyTool-side `notified_at` flag preferred; Vera-local dedup acceptable fallback).
2. **Vera Hermes skill** — new `SKILL.md` at `/home/patel/.hermes/profiles/vera-hermes-agent/skills/polytool-approvals/`:
   - Pulls pending candidates via `discovery review --list-pending` on a cadence (or operator command); posts each as an approval request to the approval DM/locked channel.
   - Listens for operator replies; parses `approve <addr>` / `deny <addr>`.
   - **Author-ID gate (mandatory):** acts ONLY on commands from the authenticated operator's Discord user ID; ignores all others.
   - **Full-address requirement (mandatory):** rejects any command that does not resolve to exactly one full wallet address (no truncated prefixes).
   - Invokes `discovery review --approve/--deny <full_address>`; reports the outcome (promoted / denied / error) back to Discord.
3. **Allowlist.** Grant Vera exactly the `discovery review` command (list-pending/approve/deny) in its command allowlist. No other commands. SOUL.md read-only prohibitions otherwise unchanged.
4. **Secrets.** Discord token + channel/operator IDs live in Vera's `.env` (operator-set). The agent never reads, prints, logs, or commits them.

## Steps
1. Add/confirm `discovery review --list-pending` (read) + confirm `--approve/--deny` route through `validate_transition`.
2. Build the approval-request formatter (evidence + reply syntax) + dedup.
3. Write the `polytool-approvals` SKILL.md (poll → post → listen → author-ID + full-address checks → invoke CLI → report).
4. Add `discovery review` to Vera's allowlist; leave SOUL.md otherwise read-only.
5. Tests (below) + a manual live smoke (operator approves a real pending candidate end-to-end via Discord).
6. Dev log + DoD ticks + vault + STATUS log.

## Definition of Done
- [ ] `discovery review --list-pending` lists pending candidate-tier wallets with evidence + full address (read-only).
- [ ] Vera posts an approval request (evidence + reply syntax) for a pending candidate; no duplicate re-posts.
- [ ] `approve <full_address>` promotes through `validate_transition`; `deny` records denial; Vera reports the outcome.
- [ ] Only the authenticated operator's Discord ID is honored; other users' commands are ignored.
- [ ] Truncated/ambiguous identifiers are rejected (full address required).
- [ ] Vera allowlisted for `discovery review` only; SOUL.md read-only otherwise intact.
- [ ] Tests pass (offline PolyTool + handler logic + gate enforcement + author-ID + full-address rejection); manual live smoke documented.
- [ ] Dev log + DoD ticks + STATUS log entry.

## Acceptance Gates
1. **No gate bypass.** All promotions/denials go through `discovery review` → `validate_transition`. Vera never writes the DB/gate directly.
2. **Authorization.** Non-operator Discord users cannot approve (author-ID enforced); run over DM or a locked channel.
3. **Unambiguous target.** No action on a non-unique/truncated wallet identifier.
4. **Minimal privilege.** Vera gains exactly `discovery review`; SOUL.md read-only prohibitions otherwise unchanged.
5. **Secrets.** Token/channel/operator IDs from `.env`; agent never handles them.
6. **Regression.** Existing tests pass; WI-4 gate/CLI behavior unchanged; existing outbound webhook alerts untouched.

## Non-Goals
Buttons / Discord component interactions (later upgrade once Hermes support is confirmed); a standalone PolyTool Discord bot (superseded); broadening Vera's scope beyond `discovery review`; auto/self-approval; replacing the existing outbound webhook alerts.

## Dependencies
WI-4 (`discovery review` CLI + `summarize_evidence()`); Vera's confirmed Discord send+receive. Spans two surfaces: the PolyTool repo (emit + CLI) and Vera's Hermes profile skills dir.

## Cross-References
- [[claude-memory/work-packets/work-packet-wallet-ingestion-v1-sprint]]
- [[claude-memory/work-packets/work-packet-wi-4-two-tier-watchlist]]
- [[claude-memory/session-notes/2026-05-31-wallet-ingestion-sprint-completion]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
