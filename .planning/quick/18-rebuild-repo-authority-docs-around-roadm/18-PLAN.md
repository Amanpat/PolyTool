---
phase: quick-018
plan: 18
type: execute
wave: 1
depends_on: []
files_modified:
  - CLAUDE.md
  - docs/PLAN_OF_RECORD.md
  - docs/ARCHITECTURE.md
  - docs/CURRENT_STATE.md
  - docs/ROADMAP.md
  - docs/TODO.md
  - docs/dev_logs/2026-03-21_phase0_authority_sync_v5.md
autonomous: true
requirements:
  - QUICK-018
must_haves:
  truths:
    - "No authority doc refers to 'Master Roadmap v4.2' as governing — only v5"
    - "CLAUDE.md benchmark pipeline section says benchmark_v1 IS closed (not 'never completed')"
    - "CLAUDE.md document priority path for v5 is correct (docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md)"
    - "Phase 0 / 1A / 1B framing from v5 is explicit in the docs that describe current direction"
    - "Track 2 (Crypto Pair Bot) standalone nature is recorded in CLAUDE.md"
    - "Gate 2 is still OPEN — no doc weakens gate language or implies it is passed"
    - "Dev log written at docs/dev_logs/2026-03-21_phase0_authority_sync_v5.md"
  artifacts:
    - path: "CLAUDE.md"
      provides: "Primary session context — must be authoritative on v5 and benchmark closure"
    - path: "docs/PLAN_OF_RECORD.md"
      provides: "Durable plan document — must state v5 governs, not v4.2"
    - path: "docs/ARCHITECTURE.md"
      provides: "Architecture reference — authority table must reference v5"
    - path: "docs/CURRENT_STATE.md"
      provides: "Current state authority — v4.2 cross-references must be removed"
    - path: "docs/ROADMAP.md"
      provides: "Milestone ledger — must not say 'v4.2 primary path'"
    - path: "docs/TODO.md"
      provides: "Deferred items — stale v4.1 next-step note must be corrected"
    - path: "docs/dev_logs/2026-03-21_phase0_authority_sync_v5.md"
      provides: "Mandatory closeout dev log per repo conventions"
  key_links:
    - from: "CLAUDE.md document priority list"
      to: "docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md"
      via: "correct path in priority list (rank 4)"
      pattern: "docs/reference/POLYTOOL_MASTER_ROADMAP_v5"
    - from: "docs/PLAN_OF_RECORD.md authority section"
      to: "v5 governing statement"
      via: "replace v4.2 references in section 0 and cross-references"
      pattern: "Master Roadmap v5"
---

<objective>
Rebuild all repo authority docs to treat Roadmap v5 as the active governing document.

Purpose: The prior docs-closeout session (2026-03-21) updated benchmark closure status in
CURRENT_STATE, ROADMAP, PLAN_OF_RECORD, and TODO — but every one of those docs still says
"Master Roadmap v4.2 is the governing roadmap as of 2026-03-16." That is incorrect.
Roadmap v5 (docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md) is now the active governing
document. CLAUDE.md also has a stale benchmark pipeline section that says the benchmark
has never completed and config/benchmark_v1.tape_manifest does not exist — both now false.

Output:
- Six authority docs updated (CLAUDE.md, PLAN_OF_RECORD, ARCHITECTURE, CURRENT_STATE, ROADMAP, TODO)
- One dev log created
- No source code, tests, specs, or config artifacts touched
</objective>

<execution_context>
This is a docs-only packet. Do not modify any file under packages/, tools/, tests/, or
docs/specs/. Do not modify config/benchmark_v1.tape_manifest, lock.json, or audit.json.
Do not weaken gate language or imply Gate 2 is passed — it is open.
</execution_context>

<context>
@CLAUDE.md
@docs/PLAN_OF_RECORD.md
@docs/ARCHITECTURE.md
@docs/CURRENT_STATE.md
@docs/ROADMAP.md
@docs/TODO.md
@docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md
@docs/dev_logs/2026-03-21_phase1_docs_closeout.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Audit stale v4.2 / benchmark statements across all six docs</name>
  <files>
    CLAUDE.md
    docs/PLAN_OF_RECORD.md
    docs/ARCHITECTURE.md
    docs/CURRENT_STATE.md
    docs/ROADMAP.md
    docs/TODO.md
  </files>
  <action>
Read every file listed and produce an internal audit list of every stale statement before
making any edit. Record exact line numbers and the replacement text for each.

**Exact changes required in each file:**

**CLAUDE.md**
1. Document priority list (rank 4): Change `POLYTOOL_MASTER_ROADMAP_v5.md` to
   `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md` (add the missing directory prefix).
2. "Benchmark pipeline" section (~lines 123-136): Replace the entire section body.
   Current stale text says: "end-to-end benchmark closure has never completed successfully"
   and "config/benchmark_v1.tape_manifest does not exist yet."
   Replace with: benchmark_v1 IS CLOSED as of 2026-03-21. The tape_manifest, lock.json,
   and audit.json all exist. 50 tapes across 5 buckets (politics=10, sports=15, crypto=10,
   near_resolution=10, new_market=5). Gate 2 scenario sweep is the next step (Phase 2).
   The silver reconstructor, manifest curator, gap-fill planner/executor, new-market capture,
   and closure orchestrator all exist and the full pipeline ran successfully. Finalization
   required --root artifacts/tapes/new_market (see dev log 2026-03-21_phase1_docs_closeout).
3. Track 2 / Crypto Pair Bot: Add a clear statement that Track 2 is STANDALONE — not blocked
   on SimTrader Gate 2 or Gate 3. The crypto pair bot (5m/15m BTC/ETH/SOL up-or-down markets)
   can be built and deployed independently. It is Phase 1A in v5 framing.
   Locate the existing Triple-Track Strategy Model section and add this standalone note
   to the Track 2 entry, or add a new subsection near "Current Direction" that says:
   "Phase 1A (crypto pair bot) is standalone. It does NOT wait for Gate 2 or Gate 3.
    Phase 1B is market-maker gate closure, benchmark sweep, shadow, staged live."

**docs/PLAN_OF_RECORD.md**
1. Lines 7-11 (authority header): Replace "Master Roadmap v4.2 ... is the governing roadmap
   document as of 2026-03-16" with "Master Roadmap v5 (docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md)
   is the governing roadmap document as of 2026-03-21 and supersedes v4.2."
2. Section 0 table header row: Change "Master Roadmap v4.1 direction" column to
   "Master Roadmap v5 direction".
3. Any remaining inline references to "v4.2" as the governing roadmap: update to v5.
4. Cross-reference at the bottom of the file (link to "Master Roadmap v4.2"): update to v5.
   Do NOT touch the Gate 2 row content (already updated for benchmark closure in prior session).

**docs/ARCHITECTURE.md**
1. Lines 4-9 (authority header): Replace "Master Roadmap v4.2 ... is the governing roadmap
   document as of 2026-03-16" with v5 equivalent.
2. Roadmap Authority table header: Change "Master Roadmap v4.2 north star" to
   "Master Roadmap v5 north star".
3. Any other "v4.2" as governing-roadmap references in this file: update to v5.
   Do NOT change "v4.1" references that are describing historical context (e.g., "supersedes v4.1").

**docs/CURRENT_STATE.md**
1. Lines 7-10 (authority header): Replace "Master Roadmap v4.2 ... is the governing roadmap
   document as of 2026-03-16" with v5 equivalent (as of 2026-03-21).
2. "Roadmap v4 Items Not Yet Implemented" section header: Rename to
   "Roadmap Items Not Yet Implemented (v5 framing)" or similar neutral phrasing.
3. Gate status section — any "See docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md"
   cross-references: change to v5 path.
4. Track A execution layer section — any "v4.2" governing-roadmap references: update to v5.
   Do NOT change benchmark closure content (already correct from prior session).

**docs/ROADMAP.md**
1. Lines 3-4 (authority header): Replace "Master Roadmap v4.2 ... is the governing roadmap
   document as of 2026-03-16" with v5 equivalent.
2. Lines 14-18 (Authority Notes table): Change v4.2 references to v5.
3. Track A status section: Remove "v4.2 primary path" phrasing; use "v5 primary path" or
   just "Track 1 primary path (Market Maker)".
4. TODO next line (~line 255): "Start Master Roadmap v4.1 Phase 2 Candidate Scanner CLI"
   is very stale — replace with "Gate 2 scenario sweep against benchmark_v1 manifest (Phase 2)."
   Do NOT change the benchmark CLOSED note (added in prior session).

**docs/TODO.md**
1. Hypothesis Validation Loop v0 section (line 80): Remove or update the stale line
   "Next chat: start Master Roadmap v4.1 Phase 2 `Candidate Scanner CLI`" since that work
   shipped. Mark the whole section as CLOSED if it isn't already, or reframe to:
   "Hypothesis Validation Loop v0 [CLOSED 2026-03-12] — shipped."
2. Track A Gate 2 Blocker: verify this section still accurately says benchmark_v1.tape_manifest
   now exists and the blocker is edge scarcity (not missing tapes or tooling). If it does,
   leave it. If any v4.x reference crept in, remove it.

**Do not:**
- Touch docs/specs/ files
- Touch packages/, tools/, tests/
- Touch config/benchmark_v1.tape_manifest, lock.json, or audit.json
- Weaken gate language (Gate 2 must still say ≥70% net PnL after fees)
- Remove Phase 0/1A/1B framing from any doc that correctly has it
</action>
  <verify>
    <automated>python -m polytool --help</automated>
  </verify>
  <done>
    All six files have been read. Internal audit list produced (exact lines + replacements).
    No edits made yet — audit output feeds Task 2.
  </done>
</task>

<task type="auto">
  <name>Task 2: Apply all doc updates and write dev log</name>
  <files>
    CLAUDE.md
    docs/PLAN_OF_RECORD.md
    docs/ARCHITECTURE.md
    docs/CURRENT_STATE.md
    docs/ROADMAP.md
    docs/TODO.md
    docs/dev_logs/2026-03-21_phase0_authority_sync_v5.md
  </files>
  <action>
Apply every edit identified in Task 1 to the six authority docs. Then write the mandatory
dev log.

**Editing rules:**
- Make surgical replacements only. Do not rewrite sections beyond what the stale statements
  require. Preserve existing voice, formatting, and surrounding context.
- Use the Read tool before every Write to get the current file contents. Never write a file
  you have not read in this session.
- After every write, do a quick grep to confirm no remaining "v4.2" references appear in
  positions where they should now say "v5" (cross-check: see audit from Task 1).

**Dev log to create at docs/dev_logs/2026-03-21_phase0_authority_sync_v5.md:**

```
# Phase 0 Authority Sync — Roadmap v5

**Date**: 2026-03-21
**Branch**: `phase-1`
**Type**: Docs-only — no source code, tests, or config changes.

## Purpose

Sync all repo authority docs to treat Master Roadmap v5
(docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md) as the governing document.
The prior session (2026-03-21_phase1_docs_closeout) updated benchmark closure
status but left "v4.2 is governing" language in place. This packet resolves that.

## Changes Made

| File | Change |
|---|---|
| CLAUDE.md | Fixed v5 path in priority list; updated benchmark pipeline section to reflect closure; added Track 2 standalone note. |
| docs/PLAN_OF_RECORD.md | Authority header, section 0 table, and cross-references updated from v4.2 to v5. |
| docs/ARCHITECTURE.md | Authority header and roadmap authority table updated from v4.2 to v5. |
| docs/CURRENT_STATE.md | Authority header, section header, and gate-status cross-references updated from v4.2 to v5. |
| docs/ROADMAP.md | Authority header, notes table, and stale TODO-next line updated to v5 and Phase 2 framing. |
| docs/TODO.md | Stale v4.1 "next chat" line removed; hypothesis validation section marked closed. |

## What Is Still True After This Change

- benchmark_v1 is CLOSED (tape_manifest, lock, audit all exist).
- Gate 2 is OPEN — scenario sweep against benchmark_v1 manifest is Phase 2.
- Gate 3, Stage 0, Stage 1 remain blocked behind Gate 2.
- Track 2 (Crypto Pair Bot, Phase 1A) is standalone — not blocked on Gate 2.
- No gate language was weakened.
```

**Verification after all writes:**
Run `python -m polytool --help` to confirm no import errors from accidental source
file modification. Then run `git diff --stat` to confirm only the expected docs were
changed.
</action>
  <verify>
    <automated>python -m polytool --help && git -C "D:/Coding Projects/Polymarket/PolyTool" diff --stat HEAD</automated>
  </verify>
  <done>
    - All six authority docs updated: no "Master Roadmap v4.2 is governing" statements remain.
    - CLAUDE.md benchmark pipeline section says benchmark_v1 IS closed (not "never completed").
    - CLAUDE.md document priority path for v5 includes the docs/reference/ prefix.
    - Track 2 standalone nature noted in CLAUDE.md.
    - Gate 2 still described as OPEN with ≥70% net PnL acceptance criterion.
    - Dev log exists at docs/dev_logs/2026-03-21_phase0_authority_sync_v5.md.
    - `python -m polytool --help` exits 0 (no source files touched).
    - `git diff --stat` shows only docs/ and CLAUDE.md files changed.
  </done>
</task>

</tasks>

<verification>
After both tasks complete:

1. `python -m polytool --help` exits 0 (confirms no source was accidentally modified).
2. `git diff --stat HEAD` shows only: CLAUDE.md, docs/PLAN_OF_RECORD.md, docs/ARCHITECTURE.md,
   docs/CURRENT_STATE.md, docs/ROADMAP.md, docs/TODO.md, and the new dev log.
3. Spot-check grep: `grep -rn "v4\.2" CLAUDE.md docs/PLAN_OF_RECORD.md docs/ARCHITECTURE.md docs/CURRENT_STATE.md docs/ROADMAP.md docs/TODO.md`
   should return zero hits where v4.2 appears as the governing roadmap (historical references
   like "supersedes v4.2" in the v5 authority declaration are acceptable).
4. Verify CLAUDE.md benchmark pipeline section contains "closed" or "CLOSED" (case-insensitive).
5. Verify CLAUDE.md document priority list contains `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`.
</verification>

<success_criteria>
- Zero docs still say "Master Roadmap v4.2 is the governing roadmap."
- CLAUDE.md benchmark pipeline section accurately reflects Phase 1 closure.
- CLAUDE.md document priority list has the correct v5 path with docs/reference/ prefix.
- Track 2 standalone nature explicitly noted.
- Gate 2 ≥70% net PnL acceptance criterion is unchanged.
- `python -m polytool --help` exits 0.
- Dev log written.
</success_criteria>

<output>
After completion, this is a quick packet — no SUMMARY file is required.
Record the completion in docs/CURRENT_STATE.md if a "Phase 0 authority sync" entry
is not already present there.
</output>
