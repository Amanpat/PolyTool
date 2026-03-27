---
phase: quick-030
plan: "01"
subsystem: repo-hygiene
tags: [cleanup, corrupted-file, claudeignore, docs, pyproject]
dependency_graph:
  requires: []
  provides:
    - clean test corpus (no mojibake)
    - .claudeignore for token savings
    - split CURRENT_STATE.md (active + archive)
    - complete pyproject.toml package list
    - file size guard script
  affects:
    - tests/test_hypothesis_validator.py
    - docs/CURRENT_STATE.md
    - docs/archive/CURRENT_STATE_HISTORY.md
    - pyproject.toml
    - README.md
tech_stack:
  added: []
  patterns:
    - Python script-based pre-commit guard (tools/guard/check_file_sizes.py)
    - .claudeignore for Claude Code context filtering
key_files:
  created:
    - .claudeignore
    - docs/archive/CURRENT_STATE_HISTORY.md
    - docs/dev_logs/DEVLOG_LEGACY.md
    - docs/archive/roadmap3_completion.md
    - docs/archive/TODO_SIMTRADER_STUDIO.md
    - tools/guard/check_file_sizes.py
    - config/watchlist_usernames.txt
    - docs/dev_logs/2026-03-27_repo_cleanup.md
  modified:
    - tests/test_hypothesis_validator.py
    - docs/CURRENT_STATE.md
    - pyproject.toml
    - README.md
decisions:
  - "Drop lines >1000 chars from test file — all corrupted lines are mojibake comment lines; no real Python line exceeds 1000 chars"
  - "Archive boundary at line 641 of CURRENT_STATE.md (Historical checkpoint: 2026-03-05) — separates active Phase 1B status from pre-Phase-1 historical records"
  - "Preserve 644-line active CURRENT_STATE.md with footer link to archive"
  - "tools/guard/ already existed — added check_file_sizes.py alongside existing guard scripts"
metrics:
  duration: "~15 minutes"
  completed: "2026-03-27T18:33:00Z"
  tasks_completed: 3
  files_modified: 13
---

# Phase quick-030 Plan 01: Repo Cleanup — Fix Corrupted Test File Summary

Repo hygiene sprint: stripped 26MB mojibake from test file to 22KB, added .claudeignore for token savings, split CURRENT_STATE.md into active (644 lines) + archive, consolidated devlogs, patched pyproject.toml with 8 missing simtrader packages and correct URLs, added file size guard, migrated users.txt to config/.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Fix corrupted test file + create .claudeignore | 54f6a59 | tests/test_hypothesis_validator.py, .claudeignore |
| 2 | Split CURRENT_STATE.md, consolidate docs, patch pyproject.toml | 50379e9 | docs/CURRENT_STATE.md, docs/archive/CURRENT_STATE_HISTORY.md, pyproject.toml |
| 3 | File size guard, users.txt migration, README update, dev log | 0e63faf | tools/guard/check_file_sizes.py, config/watchlist_usernames.txt, README.md, docs/dev_logs/2026-03-27_repo_cleanup.md |

## Key Metrics

### File Size Changes

| File | Before | After | Reduction |
|------|--------|-------|-----------|
| tests/test_hypothesis_validator.py | 26MB (677 lines) | 22KB (664 lines) | 99.9% |
| docs/CURRENT_STATE.md | 70KB (1,072 lines) | ~36KB (644 lines) | ~48% |
| docs/archive/CURRENT_STATE_HISTORY.md | (new) | ~34KB (433 lines) | — |

### Corrupted Lines Removed

14 lines stripped from test_hypothesis_validator.py (all over 1,000 chars):
- Largest: 1,585,866 chars (line 54)
- All started with `# Ã` — mojibake pattern
- 60 tests pass post-cleanup; AST parse OK

### Guard Output (post-cleanup)

```
OK: all tracked files under 500KB
```

No remaining violations after Task 1 fixed the corrupted file.

## Files Created

- `.claudeignore` — 28 lines, 8 ignore blocks covering tests, dev_logs, archive, agent config dirs, large config files, services, and feature docs
- `docs/archive/CURRENT_STATE_HISTORY.md` — 433 lines of pre-Phase-1 implementation records
- `docs/dev_logs/DEVLOG_LEGACY.md` — moved from docs/devlog/DEVLOG.md
- `docs/archive/roadmap3_completion.md` — moved from docs/
- `docs/archive/TODO_SIMTRADER_STUDIO.md` — moved from docs/
- `tools/guard/check_file_sizes.py` — pre-commit guard, 500KB threshold
- `config/watchlist_usernames.txt` — 20 usernames with comment header
- `docs/dev_logs/2026-03-27_repo_cleanup.md` — complete dev log with before/after metrics

## Files Deleted

- `docs/GDRIVE_CONNECTOR_TEST_2026-03-25.md` — test artifact
- `docs/GDRIVE_SYNC_TEST_2026-03-25.md` — test artifact
- `users.txt` — migrated to config/watchlist_usernames.txt

## pyproject.toml Changes

URLs corrected:
- `github.com/polymarket/polytool` → `github.com/Amanpat/PolyTool`

8 packages added:
- `packages.polymarket.crypto_pairs`
- `packages.polymarket.simtrader.batch`
- `packages.polymarket.simtrader.execution`
- `packages.polymarket.simtrader.portfolio`
- `packages.polymarket.simtrader.shadow`
- `packages.polymarket.simtrader.strategies`
- `packages.polymarket.simtrader.strategy`
- `packages.polymarket.simtrader.sweeps`

## Final Verification

- `tests/test_hypothesis_validator.py`: 22KB, 60 passed
- `.claudeignore`: exists, 28 lines
- `docs/CURRENT_STATE.md`: 644 lines (under 650)
- `pyproject.toml`: 12 occurrences of `simtrader.`; TOML OK
- `python tools/guard/check_file_sizes.py`: OK: all tracked files under 500KB
- `python -m polytool --help`: no import errors

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

All created files verified to exist:
- `.claudeignore`: exists
- `docs/archive/CURRENT_STATE_HISTORY.md`: exists
- `tools/guard/check_file_sizes.py`: exists
- `config/watchlist_usernames.txt`: exists
- `docs/dev_logs/2026-03-27_repo_cleanup.md`: exists

All commits verified:
- 54f6a59: fix(quick-030): remove 26MB corrupted mojibake from test file; add .claudeignore
- 50379e9: chore(quick-030): split CURRENT_STATE, consolidate devlogs, patch pyproject.toml
- 0e63faf: chore(quick-030): add file size guard, migrate users.txt, update README, write dev log
