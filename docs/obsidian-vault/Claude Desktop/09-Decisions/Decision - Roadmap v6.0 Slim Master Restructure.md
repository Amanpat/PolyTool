---
tags: [decision, roadmap, architecture, meta]
date: 2026-04-22
status: proposed
---

# Decision — Roadmap v6.0 Slim Master Restructure

**Status:** Proposed · **Supersedes:** `POLYTOOL_MASTER_ROADMAP_v5_1.md` as active master (archived, not deleted).

---

## Context

`POLYTOOL_MASTER_ROADMAP_v5_1.md` grew to ~900 lines trying to be five documents at once — strategic vision, per-phase implementation plans, architecture reference, team workflow, and open-source integration notes. Parts of it are now strategically wrong (not just stale):

- Phase 1A describes snapshot pair accumulation as the core edge. That thesis was invalidated by the gabagool22 wallet analysis; the real strategy is directional with partial hedges. The `Phase-1A-Crypto-Pair-Bot.md` phase file already reflects this, but the master still doesn't.
- The Research Intelligence System (RIS) — fully designed, implemented, and near-operational — does not appear in v5.1 at all.
- The four-loop wallet intelligence architecture (Loops A/B/C/D) does not appear in v5.1.
- The SimTrader fee formula v5.1 references was found to be wrong on 2026-04-10; a rewrite work packet exists but isn't reflected in the master.
- Phase 1B Gate 2 status (currently 7/50 = 14% pass, pending benchmark_v2 decision) is not captured.

Meanwhile, per-phase files in `PolyTool/05-Roadmap/` already exist, are reasonably current, and are being maintained by Claude Code. The structural problem is not missing files — it's that v5.1 is still acting as the master when it has drifted from reality.

## Alternatives Considered

**Surgical edits to v5.1.** Rejected. Because several sections are strategically wrong (not just incomplete), patching around them leaves the surrounding prose reading as if the old strategy is alive. Readers three weeks from now would be confused about current truth.

**Separate roadmap-only vault.** Rejected. Would add a context-switching cost without solving the real problem. The issue isn't document location; it's purpose-overloading inside one document.

**Rewrite v5.1 in place as a single large doc.** Rejected. The per-document purpose problem would return within two months.

## Decision

1. **Archive v5.1, do not mutate it.** `POLYTOOL_MASTER_ROADMAP_v5_1.md` moves to `PolyTool/05-Roadmap/_archive/v5.1.md` with no content changes. It retains historical value — it shows what we believed in March 2026.

2. **New slim master: `PolyTool/05-Roadmap/00-MASTER.md`.** Target ~150 lines. Strategic spine only: vision, triple-track summary, phase order table, principles, capital progression, human-in-the-loop policy, risk framework overview, cross-cutting systems pointer table. No implementation detail. No CLI listings. No open-source repo extraction notes.

3. **Existing phase files in `PolyTool/05-Roadmap/` remain the living detail docs.** One per phase. Where implementation reality lives. Updated whenever phase status changes.

4. **Cross-cutting systems get their own docs in appropriate Zone A folders.** RIS, four-loop wallet intelligence, fee model, Market Selection Engine, and other systems that span phases belong in `PolyTool/01-Architecture/` or `PolyTool/02-Modules/` — not inside a phase plan. The master links to them.

5. **`00-MASTER.md` is the single navigation entry point for roadmap questions.** Every other roadmap-adjacent doc is linked from it.

## Why This Works

- Master = strategic direction. Changes rarely. Small enough to read in one sitting.
- Phase files = implementation reality. Change often. Don't contaminate the master when they do.
- Cross-cutting docs = architectural detail. Each has one clear job.
- No document pretends to be more than it is.
- Claude Code, Claude Project, the architect, and the partner can each find the right level of detail without reading 900 lines.

## Work Packet for Claude Code

Draft content is at `Claude Desktop/08-Research/10-Roadmap-v6.0-Master-Draft.md`. After Aman reviews and edits:

1. **Install the draft content** at `PolyTool/05-Roadmap/00-MASTER.md`.
2. **Archive v5.1.** Move `POLYTOOL_MASTER_ROADMAP_v5_1.md` (currently in project files) to `PolyTool/05-Roadmap/_archive/v5.1.md`. No content changes.
3. **Rename the Phase 1A file.** `PolyTool/05-Roadmap/Phase-1A-Crypto-Pair-Bot.md` → `Phase-1A-Crypto-Directional.md` to reflect the post-pivot strategy. Grep for `Phase-1A-Crypto-Pair-Bot` across the entire vault and repo, update every cross-reference, and update the wikilink in the newly installed `00-MASTER.md`.
4. **Resolve Zone A → Zone B wikilinks (decide policy before install).** The draft master links into `Claude Desktop/08-Research/` and `Claude Desktop/09-Decisions/` for RIS, Wallet Discovery Pipeline, Metrics Engine MVF, and related cross-cutting system docs. Pick one policy and apply consistently:
   - **(a) Create Zone A mirrors.** New stub docs under `PolyTool/02-Modules/` or `PolyTool/01-Architecture/` for each cross-cutting system. Master points at those. Stubs may summarize and link back to Zone B for detail.
   - **(b) Document the exception.** Add a note to `PolyTool/00-Index/Vault-System-Guide.md` stating that system-level research docs are allowed as Zone A → Zone B exceptions. Keep the master's Zone B links as-is.
   Do not improvise a hybrid.
5. **Audit each `Phase-*.md` file** against the most recent dev logs. Priority order: Phase 1A (crypto pivot + fee model), Phase 1B (Gate 2 status + benchmark_v2 decision), Phase 2 (add RIS + four-loop wallet intelligence), Phase 4 (autoresearch alignment with RIS).
6. **Update `PolyTool/00-Index/Dashboard.md`** to reference `05-Roadmap/00-MASTER.md` as the roadmap entry point.
7. **Dev log the whole operation** at `docs/dev_logs/YYYY-MM-DD_roadmap-v6-restructure.md`.
8. **Flip this decision's frontmatter `status: proposed` → `status: accepted`** once install completes. That closes the loop.

## Rules Going Forward

- **Pivots update the phase file immediately.** The master is updated only if strategic direction actually changed (new track, phase reorder, principle shift).
- **No implementation detail in the master.** If a section grows past a paragraph with bullets, it belongs in a phase file or system doc.
- **Cross-cutting systems always get their own doc.** They never hide inside a phase plan.
- **The master carries a `last_reviewed` date.** If it hasn't been looked at in 90 days, assume drift and audit.

---

## Related

- [[08-Research/10-Roadmap-v6.0-Master-Draft|Draft of v6.0 content awaiting review]]
- [[Vault-System-Guide]] — Two-zone architecture this decision respects
- `PolyTool/05-Roadmap/` — Target installation location (Zone A, Claude Code only)
