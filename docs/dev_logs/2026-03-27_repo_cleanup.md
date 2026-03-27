# Dev Log — 2026-03-27 Repo Cleanup Sprint (quick-030)

## Summary

Repo hygiene sprint targeting the single largest context-destroying file in the
repo and establishing lightweight tooling to prevent recurrence. Three tasks
completed atomically.

---

## Task 1: Fix corrupted test file and create .claudeignore

### tests/test_hypothesis_validator.py — CRITICAL corruption fixed

**Before:** 677 lines / 26MB (27,197,087 bytes)

The file contained 14 lines of mojibake (corrupted Unicode garbage). All
corrupted lines started with `# Ã` and were over 1,000 characters long.
Largest offenders: Line 26 (1,518,860 chars), Line 54 (1,585,866 chars),
Line 321 (1,250,842 chars), Line 346 (1,206,172 chars). The corruption
predated this cleanup sprint — file mtime was 2026-03-23.

**Fix:** Read file line by line; drop every line whose length exceeds 1,000
characters. No test logic was modified — only the corrupted comment lines
were removed.

**After:** 664 lines / 22KB (22,729 bytes)

**Verification:**
- `python -c "import ast; ast.parse(...)` → AST OK
- `python -m pytest tests/test_hypothesis_validator.py -x -q` → 60 passed, 0 failed

### .claudeignore created

Created `.claudeignore` at repo root with 8 ignore blocks:
- `tests/` — only read when explicitly working on tests
- `docs/dev_logs/` + `docs/devlog/` — historical dev logs
- `docs/archive/`, `docs/debug/`, `docs/pdr/` — archived/superseded docs
- `.claude/`, `.gemini/`, `.opencode/`, `.planning/` — agent config dirs
- Three large generated config files (benchmark audit/targets JSONs)
- `services/` — legacy placeholder
- `docs/features/` — reference only

---

## Task 2: Split CURRENT_STATE.md, consolidate devlogs, patch pyproject.toml

### docs/CURRENT_STATE.md split

**Before:** 1,072 lines / 69,944 bytes

Archive boundary: line 641 (`## Historical checkpoint: 2026-03-05 Track A code complete`)

**Active portion:** Lines 1–640 + footer link → 644 lines
**Archive portion:** Created `docs/archive/CURRENT_STATE_HISTORY.md` with
lines 641–1,072 plus a header block. Contains pre-Phase-1 implementation
records (Track A completion, gate tooling history, Silver reconstruction
history, benchmark closure orchestration history).

Footer added to active CURRENT_STATE.md:
```
> **Historical details** (pre-Phase-1 implementation records) moved to `docs/archive/CURRENT_STATE_HISTORY.md`.
```

### Devlog directory consolidation

- Moved `docs/devlog/DEVLOG.md` → `docs/dev_logs/DEVLOG_LEGACY.md`
- Removed `docs/devlog/` directory entirely

### Stale top-level docs cleanup

Moved/deleted:
- `docs/roadmap3_completion.md` → `docs/archive/roadmap3_completion.md`
- `docs/TODO_SIMTRADER_STUDIO.md` → `docs/archive/TODO_SIMTRADER_STUDIO.md`
- `docs/GDRIVE_CONNECTOR_TEST_2026-03-25.md` — deleted (test artifact)
- `docs/GDRIVE_SYNC_TEST_2026-03-25.md` — deleted (test artifact)

### pyproject.toml patches

URL fix:
- `https://github.com/polymarket/polytool` → `https://github.com/Amanpat/PolyTool`
- `https://github.com/polymarket/polytool/tree/main/docs` → `https://github.com/Amanpat/PolyTool/tree/main/docs`

8 missing packages added to `packages = [...]` list:
- `packages.polymarket.crypto_pairs`
- `packages.polymarket.simtrader.batch`
- `packages.polymarket.simtrader.execution`
- `packages.polymarket.simtrader.portfolio`
- `packages.polymarket.simtrader.shadow`
- `packages.polymarket.simtrader.strategies`
- `packages.polymarket.simtrader.strategy`
- `packages.polymarket.simtrader.sweeps`

TOML validation: `python -c "import tomllib; tomllib.loads(...)"` → TOML OK

---

## Task 3: File size guard, users.txt migration, README update

### tools/guard/check_file_sizes.py created

New pre-commit guard script. Runs `git ls-files`, checks each tracked file's
size, reports violations over `--max-kb` (default 500KB).

**Guard output (2026-03-27, after Tasks 1+2):**
```
OK: all tracked files under 500KB
```

No remaining violations. The corrupted test file was the only offender and
was resolved in Task 1.

### users.txt → config/watchlist_usernames.txt

- Created `config/watchlist_usernames.txt` with comment header +
  original 20 usernames from `users.txt`
- Deleted `users.txt` from repo root

20 usernames migrated: @kch123, @blackwall, @FeatherLeather, @weflyhigh,
@gmpm, @everton4life, @MrSparklySimpsons, @czoyimsezblaznili, @swisstony,
@hioa, @BWArmageddon, @GamblingIsAllYouNeed, @tbs8t, @RN1, @gatorr,
@anoin123, @Vanchalkenstein, @C.SIN, @Supah9ga, @Tiger200

### README.md status section updated

Replaced stale 2026-03-07 status block (23 lines including table) with
concise 2026-03-27 status summary paragraph reflecting current Phase 1A/1B state.

---

## Before/After Summary

| File | Before | After |
|------|--------|-------|
| tests/test_hypothesis_validator.py | 26MB (677 lines) | 22KB (664 lines) |
| docs/CURRENT_STATE.md | 70KB (1,072 lines) | ~36KB (644 lines) |
| docs/archive/CURRENT_STATE_HISTORY.md | (did not exist) | ~34KB (433 lines) |

## Remaining Flagged Files

None — guard output was clean after Tasks 1 and 2. The corrupted test file
was the only file over 500KB and has been resolved.

## Open Questions / Deferred Items

None. All cleanup targets in the plan were addressed.
