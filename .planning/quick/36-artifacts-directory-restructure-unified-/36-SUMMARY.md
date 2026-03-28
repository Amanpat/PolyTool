---
phase: quick-036
plan: 01
subsystem: infra
tags: [artifacts, paths, filesystem, refactor]

# Dependency graph
requires: []
provides:
  - "Unified artifacts/ directory layout: gold/silver/shadow/crypto tapes under artifacts/tapes/"
  - "All Python path constants updated to new layout (18 files)"
  - "CLAUDE.md artifacts directory reference section"
  - "Dev log documenting the restructure"
affects: [gate2, corpus-audit, simtrader, benchmark, crypto-pairs, mm-sweep]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tape tiers use artifacts/tapes/{tier}/ hierarchy (gold/silver/bronze/shadow/crypto)"
    - "Gate artifacts under artifacts/gates/gate2_sweep/ and artifacts/gates/manifests/"
    - "Debug/probe output under artifacts/debug/"

key-files:
  created:
    - docs/dev_logs/2026-03-28_artifacts_restructure.md
  modified:
    - CLAUDE.md
    - packages/polymarket/crypto_pairs/paper_runner.py
    - packages/polymarket/silver_reconstructor.py
    - tools/cli/batch_reconstruct_silver.py
    - tools/cli/capture_new_market_tapes.py
    - tools/cli/close_benchmark_v1.py
    - tools/cli/crypto_pair_run.py
    - tools/cli/gate2_preflight.py
    - tools/cli/make_session_pack.py
    - tools/cli/prepare_gate2.py
    - tools/cli/reconstruct_silver.py
    - tools/cli/scan_gate2_candidates.py
    - tools/cli/simtrader.py
    - tools/cli/summarize_gap_fill.py
    - tools/cli/tape_manifest.py
    - tools/cli/watch_arb_candidates.py
    - tools/gates/capture_status.py
    - tools/gates/corpus_audit.py
    - tools/gates/mm_sweep.py

key-decisions:
  - "artifacts/crypto_pairs/{live_runs,await_soak,backtests,scan,watch} left in place — no target in spec; only paper_runs migrated to tapes/crypto/"
  - "Filesystem restructure produces zero git diff (entire artifacts/ is gitignored); only Python source changes tracked"

patterns-established:
  - "Tape tier hierarchy: artifacts/tapes/{gold,silver,bronze,shadow,crypto}/"
  - "Gate outputs: artifacts/gates/gate2_sweep/, artifacts/gates/gate3_shadow/, artifacts/gates/manifests/"

requirements-completed: [INFRA-CLEANUP]

# Metrics
duration: 45min
completed: 2026-03-28
---

# Quick-036: Artifacts Directory Restructure Summary

**Unified 53MB of accumulated artifacts into a documented tier hierarchy — artifacts/tapes/{gold,silver,shadow,crypto}/ — and updated all 18 Python path constants to match.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-03-28T18:00:00Z
- **Completed:** 2026-03-28T18:45:00Z
- **Tasks:** 3
- **Files modified:** 19 (18 Python source files + CLAUDE.md; dev log created)

## Accomplishments
- Consolidated two competing tape directories (artifacts/silver/ and artifacts/simtrader/tapes/) into a single artifacts/tapes/{tier}/ hierarchy with gold, silver, bronze, shadow, and crypto sub-tiers
- Updated all DEFAULT_*_DIR, DEFAULT_*_PATH constants and help/docstring text across 18 Python files to match the new layout; 2717 tests passed with no regressions
- Documented the canonical layout in CLAUDE.md under a new "Artifacts directory layout" subsection and wrote a full dev log

## Task Commits

Each task was committed atomically:

1. **Task 1: Execute filesystem migration** - no commit (artifacts/ is gitignored)
2. **Task 2: Update hardcoded paths in Python source** - `4a0da5d` (chore)
3. **Task 3: Update CLAUDE.md and write dev log** - `c0be966` + `fcdc42e` (docs)

**Plan metadata:** pending (final docs commit)

## Files Created/Modified
- `docs/dev_logs/2026-03-28_artifacts_restructure.md` - dev log for restructure
- `CLAUDE.md` - added artifacts directory layout subsection and updated expected high-value paths
- `tools/gates/mm_sweep.py` - DEFAULT_MM_SWEEP_TAPES_DIR, DEFAULT_MM_SWEEP_OUT_DIR, DEFAULT_GATE2_MANIFEST_PATH
- `tools/gates/corpus_audit.py` - DEFAULT_TAPE_ROOTS list, docstring, and shortage report commands
- `tools/gates/capture_status.py` - help text print statement for --out flag
- `tools/cli/tape_manifest.py` - _DEFAULT_TAPES_DIR, _DEFAULT_OUT, docstring
- `tools/cli/simtrader.py` - 8 occurrences (print statements, help text, arg defaults)
- `tools/cli/gate2_preflight.py` - _DEFAULT_TAPES_DIR
- `tools/cli/prepare_gate2.py` - _DEFAULT_TAPES_BASE, docstring
- `tools/cli/scan_gate2_candidates.py` - docstring example
- `tools/cli/watch_arb_candidates.py` - _DEFAULT_TAPES_BASE, docstring
- `tools/cli/capture_new_market_tapes.py` - _DEFAULT_TAPES_ROOT
- `tools/cli/reconstruct_silver.py` - help text, docstring, _default_out_dir() function
- `tools/cli/batch_reconstruct_silver.py` - docstring example
- `tools/cli/summarize_gap_fill.py` - docstring examples
- `tools/cli/close_benchmark_v1.py` - print statement
- `tools/cli/make_session_pack.py` - _DEFAULT_OUTPUT_DIR, docstring
- `tools/cli/crypto_pair_run.py` - help text
- `packages/polymarket/crypto_pairs/paper_runner.py` - DEFAULT_PAPER_ARTIFACTS_DIR
- `packages/polymarket/silver_reconstructor.py` - docstring example

## Decisions Made
- Left `artifacts/crypto_pairs/{live_runs,await_soak,backtests,scan,watch}` in place; the plan spec only mapped `paper_runs` to `artifacts/tapes/crypto/paper_runs` — the other crypto_pairs subdirs have no target and were left unchanged.
- The filesystem restructure itself produces no git diff because the entire `artifacts/` tree is gitignored. Only Python source changes are tracked in version control.
- CLAUDE.md is tracked in git as lowercase `claude.md` on Windows (case-insensitive filesystem). Staged with `git add claude.md`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Correctness] Fixed `tools/cli/crypto_pair_run.py` not in original plan file list**
- **Found during:** Task 2 (grep sweep of all old path references)
- **Issue:** `tools/cli/crypto_pair_run.py` contained `artifacts/crypto_pairs/paper_runs in paper mode` in help text, referencing the old path. This file was not in the plan's explicit `files_modified` list.
- **Fix:** Updated help text to `artifacts/tapes/crypto/paper_runs in paper mode`
- **Files modified:** `tools/cli/crypto_pair_run.py`
- **Verification:** grep count returned 0 for old path; pytest passed
- **Committed in:** `4a0da5d` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing correctness)
**Impact on plan:** One file missed in the plan's file list; caught via grep sweep and fixed inline. No scope creep.

## Issues Encountered
- **Windows case-insensitive git tracking:** `git add CLAUDE.md` failed to stage the file because git tracks it as `claude.md` (lowercase). Resolved by using `git add claude.md`. This caused the CLAUDE.md update to land in a separate commit (`fcdc42e`) from the dev log (`c0be966`).
- **pytest --timeout=30 flag:** The plan's verify step included `--timeout=30` but the pytest-timeout plugin is not installed. Ran without the flag — 2717 tests passed.
- **Task 1 .gitkeep loop exit code:** The conditional `.gitkeep` loop exits 1 when directories are non-empty (expected behavior, not an error).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All CLI tools now point to the correct artifact paths under the unified layout
- Gate 2 scenario sweep (`python tools/gates/close_sweep_gate.py`) can proceed; the sweep output directory is `artifacts/gates/gate2_sweep/` and the manifest path is `artifacts/gates/manifests/gate2_tape_manifest.json`
- corpus_audit.py DEFAULT_TAPE_ROOTS now searches `artifacts/tapes/gold/`, `artifacts/tapes/silver/`, and `artifacts/tapes/` — correctly covers all tape tiers

---
*Phase: quick-036*
*Completed: 2026-03-28*

## Self-Check: PASSED

- FOUND: `.planning/quick/36-artifacts-directory-restructure-unified-/36-SUMMARY.md`
- FOUND: commit `4a0da5d` (Task 2 — Python path updates)
- FOUND: commit `c0be966` (Task 3 — dev log)
- FOUND: commit `fcdc42e` (Task 3 — CLAUDE.md)
