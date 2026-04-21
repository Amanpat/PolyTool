---
tags: [decision, workflow, tooling]
date: 2026-04-21
status: accepted
---
# Decision — Workflow Harness Refresh 2026-04

## Context
A workflow review session on 2026-04-21 surfaced five compounding issues in the Desktop → Architect → Claude Code/Codex pipeline:

1. **Features don't finish.** Parallel development across 3+ features produces half-built systems because no Director-level gate prevents feature N+1 from starting before N is complete.
2. **AGENTS.md is stale.** ~70 lines, says "Python (future)", missing the triple-track strategy, the ClickHouse auth rule, tape tier definitions, Codex Review Policy, and multi-agent awareness. Codex was running on stale info every session.
3. **GSD `/gsd-quick` is redundant with the Architect.** The Architect already produces specified prompts; GSD's planner subagent re-plans already-planned work. Confirmed overhead: 600 SKILL.md files across 10 worktree clones, 6+ hooks per session.
4. **Docs sprawl.** 651 markdown files, 325 dev logs, three live roadmap versions in `docs/reference/`, CURRENT_STATE.md at 106KB. The Architect's "read all project docs at session start" rule is infeasible at this scale.
5. **No skills infrastructure.** Project-local `.claude/skills/` is empty. Claude Code needs to be able to create and update skills as patterns emerge.

## Decision
Adopt a six-part workflow harness change, executed in priority order.

- **Rebuild AGENTS.md** to mirror CLAUDE.md's operational detail. Codex gets its own canonical source that does not depend on reading CLAUDE.md. Draft complete 2026-04-21; lives in repo root.
- **Introduce `docs/CURRENT_DEVELOPMENT.md`** as a living multi-feature state doc. Max 3 Active features. Per-feature Definition of Done. Explicit three-step completion protocol (feature doc + INDEX update + move to Recently Completed). Architect reads this at top of every chat and refuses to design for features not listed as Active without Director acknowledgment.
- **Update Architect instructions** to read CURRENT_DEVELOPMENT.md at session start, enforce the Active-features gate, and emit a skill-creation trigger when it notices a repeating prompt pattern across 3+ sessions.
- **Archive superseded roadmaps.** Move `POLYTOOL_MASTER_ROADMAP_v4.2.md` and `POLYTOOL_MASTER_ROADMAP_v5.md` from `docs/reference/` to `docs/archive/reference/` with a SUPERSEDED header.
- **Shrink CURRENT_STATE.md** from 106KB to a navigation page linking to topic-specific state docs under `docs/state/` (benchmark, track, blockers).
- **Resolve docs/obsidian-vault duplication.** Canonical vault path is `docs/obsidian-vault/`. Delete any separate copy.

GSD stays installed for `/gsd-map-codebase`, `/gsd-debug`, `/gsd-forensics`. Stop using `/gsd-quick` in favor of `/gsd-fast` for architect-driven prompts.

## Alternatives Considered
- **Light RAG over `docs/`** — rejected. The existing [[RIS]] Chroma collection covers this use case and is partially built. Adding another half-built RAG would repeat the stalling pattern that motivated this refresh.
- **Replace GSD entirely** — rejected for now. Keep the non-redundant commands.
- **Install `skills-directory/skill-codex` or `klaudworks/universal-skills`** — rejected. `codex@openai-codex` (`codex-plugin-cc`) is already installed; adding another Codex bridge would conflict.
- **Install a kanban tool** (`alessiocol/claude-kanban`, `BloopAI/vibe-kanban`) — rejected. A markdown file plus an architect-prompt update solves the WIP problem without a new runtime dependency. Consistent with the Tsinghua harness engineering paper's preference for natural-language constraints over runtime hooks.
- **Install Token Savior / qmd / Turbo Index** — deferred (not rejected). Real category, measurable benefit for a 145K LOC repo, but sequenced after docs and workflow fixes land. Revisit after CURRENT_DEVELOPMENT.md is in use.

## Impact
- Codex starts every session with accurate operational context instead of reconstructing it from stale AGENTS.md.
- Feature-in-flight becomes observable and enforceable. The Architect can refuse new work until an Active slot frees up, which is the specific forcing function needed for the "features don't finish" symptom.
- `docs/` becomes navigable. Archive of two superseded roadmaps removes the most frequent source of Architect confusion.
- GSD overhead drops without losing the commands that still earn their keep.
- Skill auto-creation becomes a documented trigger, so CC can codify repeating patterns instead of re-discovering them.

## Open Questions
- Document priority position of the Architect's prompt (AGENTS.md lists it last). Is docs-win the correct hierarchy, or should the prompt win over static docs? Current default: docs-win.
- Final list of Active features for CURRENT_DEVELOPMENT.md. Three candidates inferred from dev logs and CLAUDE.md: Gate 2 Crypto Gold Capture, Track 2 Paper Soak Hardening, Wallet Discovery Loop B+D. Director confirmation pending.
- Staleness limit (7 vs 14 days) for Active features without updates.

## Next Actions
- [ ] Drop AGENTS.md into repo root (file produced 2026-04-21)
- [ ] Finalize and save `docs/CURRENT_DEVELOPMENT.md`
- [ ] Draft and review updated Architect instructions
- [ ] Archive two superseded roadmaps (Claude Code, 10-min task)
- [ ] Plan CURRENT_STATE.md decomposition (separate session)
- [ ] Revisit Token Savior evaluation after the above lands

See [[RIS]], `docs/AGENTS.md`, `docs/CLAUDE.md`.
