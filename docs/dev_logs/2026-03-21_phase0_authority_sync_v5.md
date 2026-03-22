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
| CLAUDE.md | Fixed v5 path in priority list (added `docs/reference/` prefix); updated benchmark pipeline section to reflect closure; added Track 2 standalone note with Phase 1A/1B framing. |
| docs/PLAN_OF_RECORD.md | Authority header, section 0 table header, track alignment section, and cross-reference updated from v4.2 to v5. |
| docs/ARCHITECTURE.md | Authority header, roadmap authority table header, and database rule attribution updated from v4.2 to v5. |
| docs/CURRENT_STATE.md | Authority header, section header ("Roadmap v4 Items Not Yet Implemented" → "Roadmap Items Not Yet Implemented (v5 framing)"), and gate-status cross-reference updated from v4.2 to v5. |
| docs/ROADMAP.md | Authority header, Authority Notes table (renamed and updated to v5 framing with Phase 1A/1B), and stale TODO-next line updated to Gate 2 sweep / Phase 2 framing. |
| docs/TODO.md | Stale v4.1 "next chat: start Candidate Scanner CLI" line replaced with accurate Phase 2 / Gate 2 sweep framing. |

## What Is Still True After This Change

- benchmark_v1 is CLOSED (tape_manifest, lock, audit all exist).
- Gate 2 is OPEN — scenario sweep against benchmark_v1 manifest is Phase 2.
- Gate 3, Stage 0, Stage 1 remain blocked behind Gate 2.
- Track 2 (Crypto Pair Bot, Phase 1A) is standalone — not blocked on Gate 2 or Gate 3.
- No gate language was weakened.
- Gate 2 acceptance criterion unchanged: ≥ 70% of benchmark tapes show positive
  net PnL after fees and realistic-retail assumptions.
