---
tags: [session-note, workflow, tooling, docs-cleanup]
date: 2026-04-21
status: in-progress
topics: [agents-md, current-development, docs-cleanup, gsd, architect]
---
# Workflow Harness Refresh — Session 1

## What Happened

Multi-hour review of the Desktop → Architect → Claude Code/Codex pipeline, triggered by two observations: (1) features don't finish, (2) GSD's `/gsd-quick` uses excess tokens. Session branched into workflow-harness changes (PEV pattern, feature-in-flight tracking, WIP limit), AGENTS.md rebuild, and a docs cleanup pass.

Covered a lot of ground. Ended mid-stream with user fatigue on A.2 Phase 2 decisions — stopped rather than push through.

## Key Outcomes

### Saved to Vault
- [[09-Decisions/Decision - Workflow Harness Refresh 2026-04]] — six-part harness change with context, alternatives, impact, open questions, next actions
- This session note

### Produced as Files (in `/mnt/user-data/outputs/`, need to drop into repo)
- **AGENTS.md** — full rebuild mirroring CLAUDE.md's operational detail. ~320 lines. Codex gets its own canonical source.

### Drafted In-Chat (awaiting user decisions before save)
- **CURRENT_DEVELOPMENT.md** — multi-feature living state doc. Seeded with real active features from repo dev logs. Three user decisions outstanding (see Pending Decisions below).
- **CURRENT_STATE.md decomposition plan** — 45-row classification table produced by Claude Code. Four user decisions outstanding.

### A.1 Docs Cleanup — Executed, Staged (not yet committed)
- Archived `POLYTOOL_MASTER_ROADMAP_v4.2.md` and `POLYTOOL_MASTER_ROADMAP_v5.md` to `docs/archive/reference/` with SUPERSEDED frontmatter
- Updated 7 active-doc references across `config/seed_manifest.json`, `docs/ARCHITECTURE.md`, 3 specs, a runbook, a feature doc
- All changes staged in git; commit pending
- Dev logs: `docs/dev_logs/2026-04-21_archive_old_roadmaps.md`, `docs/dev_logs/2026-04-21_roadmap_reference_fixups.md`
- Post-fix sweep confirmed zero remaining stale references in active docs

## Decisions Made

- **GSD:** keep installed for `/gsd-map-codebase`, `/gsd-debug`, `/gsd-forensics`. Drop `/gsd-quick` in favor of `/gsd-fast` for architect-driven prompts. Not yet executed in architect template.
- **Vault is stale vs repo** — vault folders 00-07 last updated 2026-04-10; repo dev logs go to 2026-04-15. Sync from repo → vault is lagging. Flagged but not fixed this session.
- **Research tooling rejected:** skill-codex, universal-skills (redundant with `codex@openai-codex`); kanban tools (`claude-kanban`, `vibe-kanban`) — markdown file plus architect-prompt update solves WIP problem without new runtime dependency.
- **Light RAG over `docs/`:** deferred. Existing `polytool_brain` Chroma collection covers this use case; adding another half-built RAG would repeat the stalling pattern we're trying to fix.
- **Token Savior / qmd / Turbo Index:** deferred until workflow fixes land. Real category, real benefit for 145K LOC repo, but not now.
- **Docs decomposition direction:** Option D — CHANGELOG (dated entries) + thin topical state docs. CURRENT_STATE.md becomes a navigation page.

## Pending Decisions

### On CURRENT_DEVELOPMENT.md (before saving the draft)
1. Is SimTrader Fee Model Overhaul (PMXT Deliverable A) actually being picked up this sprint, or speculative?
2. Is Gate 2 Option 3 (Track 2 focus) de facto decided, or still genuinely awaiting decision?
3. Completion-doc debt: backfill as work packet, or track as checklist in the file?

### On A.2 Phase 2 (CURRENT_STATE.md decomposition)
Four operator questions flagged by the Claude Code plan. Claude Desktop proposed answers but user accepted under fatigue. Should be re-reviewed before Phase 2 runs:
1. Authority — CLAUDE.md stays authoritative for rules; state docs derived for live values. Needs user confirmation.
2. Section 5 split boundary at line 205 — Claude Code self-flagged; user should verify before Phase 2.
3. Section 7 ("Phase 1B — Corpus Recovery Tooling") fully superseded, moves to CHANGELOG wholesale.
4. TRACK1B / BLOCKERS structure — Desktop recommended dropping both `state/TRACK1B.md` and `state/BLOCKERS.md`; route "Roadmap Items Not Yet Implemented" to `PLAN_OF_RECORD.md` instead. Q4b pushed back against Claude Code's initial classification; worth re-reading.

## What's Committed vs Staged vs Drafted

| State | Items |
|-------|-------|
| **Saved to vault** | Decision record; this session note |
| **Ready to drop in repo** | AGENTS.md (file in /mnt/user-data/outputs/) |
| **Staged, not committed** | A.1 changes (2 dev logs + 9 file updates for roadmap archival) |
| **Drafted, pending decisions** | CURRENT_DEVELOPMENT.md (3 open Qs); A.2 Phase 2 prompt (4 open Qs) |
| **Not started** | Architect instructions update; tools/MCP cleanup; GSD switch; A.2 Phase 2 execution; A.3 dev log organization |

## Pickup for Next Session

Immediate (before anything else):
- Commit staged A.1 work: `git add . && git commit -m "docs: archive superseded roadmaps + fix active references"`
- Drop AGENTS.md into repo root

Then choose one path:
1. **Answer CURRENT_DEVELOPMENT.md's 3 pending questions** → save to vault + produce repo file → move to Architect instructions update
2. **Answer A.2 Phase 2's 4 pending questions** → produce Phase 2 prompt → execute docs decomposition
3. **Quick wins first:** drop `sequential-thinking` and `code-review-graph` MCPs, switch `/gsd-quick` → `/gsd-fast` in architect template (~15 min total)

Strong recommendation: path 1. Finishes what was started (pattern this whole refresh exists to fix). A.2 Phase 2 can wait until the next fresh session — it's the highest-risk remaining item and shouldn't be run tired.

## Cross-References

- [[09-Decisions/Decision - Workflow Harness Refresh 2026-04]]
- Repo: `docs/dev_logs/2026-04-21_archive_old_roadmaps.md`
- Repo: `docs/dev_logs/2026-04-21_roadmap_reference_fixups.md`
- Repo: `docs/dev_logs/2026-04-21_current_state_decomposition_plan.md`
- Research from session: 2026-04-21 GLM research on AI-coding workflow tooling (not saved; in chat history)
- Videos reviewed: "Top 10 Claude Code Skills, Plugins & CLIs (April 2026)"; "Rethinking AI Agents: The Rise of Harness Engineering"


---

## Update 2026-04-21 — CURRENT_DEVELOPMENT.md Finalized

Director answered the three pending questions:

1. **SimTrader Fee Model Overhaul:** Active (not On Deck). Wallet Discovery v1 is shipped; no real dependency blocking pickup.
2. **Gate 2 Path Forward:** Paused — Option 3 (Track 2 focus) de facto accepted per 2026-04-15 operator runbook. Resume trigger: Track 2 outcome known.
3. **Completion-doc debt:** Backfill now as single CC work packet (~2 hours). Sets precedent for the completion protocol.

### Final CURRENT_DEVELOPMENT.md structure

- **Active (2 of 3):** Track 2 Paper Soak (24h Run), SimTrader Fee Model Overhaul (PMXT Deliverable A). Third slot empty.
- **Awaiting Decision:** (empty — Gate 2 moved to Paused)
- **Completion-Doc Debt:** 4 items, backfill scheduled as standalone CC session
- **Paused:** Gate 2 Path Forward, Gold Tape Resumption, Loop B/C/D, RIS audit follow-up, PMXT Deliverables B/C, pmxt sidecar, Phase 1A WebSocket CLOB, Phase 1C

File saved to `/mnt/user-data/outputs/CURRENT_DEVELOPMENT.md` for repo drop at `docs/CURRENT_DEVELOPMENT.md`.

### Why two Active at once

Rule 6 added to the file: two Active OK when they don't compete for attention. Track 2 soak is passive monitoring on partner machine; Fee Model Overhaul is design-intensive code work on dev machine. They don't share files, machines, or meaningful attention.


---

## Session Closed 2026-04-21

### Final Active roster (locked)
- **Feature 1:** Track 2 Paper Soak — 24h Run (no blockers, launch via runbook)
- **Feature 2:** SimTrader Fee Model Overhaul (PMXT Deliverable A) — no blockers; next step is Architect session to resolve FEE_CURVE_EXPONENT + maker rebate Option A vs B
- **Slot 3:** intentionally empty

### Chat pointers for continued development
- **Fee Model Overhaul work:** `https://claude.ai/chat/342ff53d-dba1-43ad-9119-4184be42a475` (Evaluating PMXT tools for project integration). Contains the Unified Open Source Integration work packet and GLM-5 verified fee formula corrections.
- **Track 2 Paper Soak launch:** no dedicated chat needed; execute `docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md`. If something breaks, open a fresh chat with CURRENT_DEVELOPMENT.md + runbook + failure context.
- **Meta-workflow items remaining (this chat):** Architect instructions update, A.2 Phase 2, quick-wins (MCP cleanup + GSD switch), completion-doc debt work packet.

### Immediate next-step checklist (before PMXT chat)
1. `git add . && git commit -m "docs: archive superseded roadmaps + fix active references"` — commits staged A.1 work
2. Drop `AGENTS.md` (from `/mnt/user-data/outputs/`) into repo root; `git add AGENTS.md && git commit -m "docs: rebuild AGENTS.md mirroring CLAUDE.md"`
3. Drop `CURRENT_DEVELOPMENT.md` at `docs/CURRENT_DEVELOPMENT.md`; `git add docs/CURRENT_DEVELOPMENT.md && git commit -m "docs: add CURRENT_DEVELOPMENT.md living state doc"`
4. **Update ChatGPT Architect custom instructions** so the Architect reads AGENTS.md + CURRENT_DEVELOPMENT.md and enforces the Active-features gate. (Pending — see below.)
5. Move to PMXT chat for Fee Model Architect session

### Critical pending item: Architect instructions update

This was part of the original "all three" commitment (AGENTS.md + CURRENT_DEVELOPMENT.md + Architect update). The first two shipped. The third is still pending. **Without updating the Architect's custom instructions, the Fee Model PMXT session won't enforce the Active-features gate or reference the new docs** — the whole workflow refresh stays theoretical.

This must be resolved in the current workflow chat before the PMXT session, or the refresh is neutralized.
