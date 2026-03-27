---
phase: quick-030
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/test_hypothesis_validator.py
  - .claudeignore
  - docs/CURRENT_STATE.md
  - docs/archive/CURRENT_STATE_HISTORY.md
  - docs/dev_logs/DEVLOG_LEGACY.md
  - docs/archive/roadmap3_completion.md
  - docs/archive/TODO_SIMTRADER_STUDIO.md
  - pyproject.toml
  - tools/guard/check_file_sizes.py
  - config/watchlist_usernames.txt
  - README.md
  - docs/dev_logs/2026-03-27_repo_cleanup.md
autonomous: true
requirements: [CLEANUP-01]
must_haves:
  truths:
    - "test_hypothesis_validator.py is under 50KB and all its tests pass"
    - ".claudeignore exists at repo root with the specified ignore patterns"
    - "CURRENT_STATE.md active portion is under 650 lines (history moved to archive)"
    - "pyproject.toml packages list includes all missing simtrader subpackages"
    - "file size guard script exists and runs cleanly"
    - "dev log captures all changes made"
  artifacts:
    - path: "tests/test_hypothesis_validator.py"
      provides: "Cleaned test file — no corrupted mojibake lines"
    - path: ".claudeignore"
      provides: "Claude Code ignore patterns for token savings"
    - path: "docs/CURRENT_STATE.md"
      provides: "Active state doc under 650 lines"
    - path: "docs/archive/CURRENT_STATE_HISTORY.md"
      provides: "Historical records moved from CURRENT_STATE.md"
    - path: "tools/guard/check_file_sizes.py"
      provides: "Pre-commit file size guard"
    - path: "docs/dev_logs/2026-03-27_repo_cleanup.md"
      provides: "Dev log for all cleanup changes"
  key_links:
    - from: "docs/CURRENT_STATE.md"
      to: "docs/archive/CURRENT_STATE_HISTORY.md"
      via: "footer reference link"
      pattern: "CURRENT_STATE_HISTORY"
---

<objective>
Repo hygiene sprint: fix the 26MB corrupted test file that poisons Claude sessions, add
.claudeignore to prevent future token burns, split CURRENT_STATE.md into active + archive,
consolidate stale docs, patch pyproject.toml package list, add a file-size guard, and
clean up root clutter.

Purpose: Eliminate the single largest context-destroying file in the repo and establish
lightweight hygiene tooling to prevent recurrence.
Output: Clean repo with no file over ~500KB, .claudeignore in place, trimmed active docs.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/.planning/STATE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix corrupted test file and create .claudeignore</name>
  <files>tests/test_hypothesis_validator.py, .claudeignore</files>
  <action>
**Fix tests/test_hypothesis_validator.py (CRITICAL — 26MB corrupted file):**

The file is 677 lines but 26MB because multiple lines contain millions of characters of
mojibake (corrupted Unicode garbage). ALL corrupted lines start with `# Ã` and are over
1000 characters long. Real comment lines and code lines are all under 200 characters.

Steps:
1. Read the file line by line
2. Drop every line whose length exceeds 1000 characters (these are ALL corrupted comment
   lines — no real Python line is that long)
3. Write the cleaned content back to the same path
4. Verify: `python -c "import ast; ast.parse(open('tests/test_hypothesis_validator.py').read()); print('OK')"`
5. Verify: `python -m pytest tests/test_hypothesis_validator.py -x -q --tb=short`
6. Confirm file size is now under 50KB

Do NOT rewrite any test logic. Only remove lines over 1000 characters.

**Create .claudeignore at repo root:**

Create the file with exactly this content:

```
# Tests — only read when explicitly working on tests
tests/

# Dev logs — historical, never needed for coding
docs/dev_logs/
docs/devlog/

# Archived docs — superseded
docs/archive/
docs/debug/
docs/pdr/

# Agent config dirs — GSD framework, not project code
.claude/
.gemini/
.opencode/
.planning/

# Large generated/config files
config/benchmark_v1.audit.json
config/benchmark_v1_gap_fill.targets.json
config/benchmark_v1_new_market_capture.targets.json

# Services — legacy/placeholder, not active development
services/

# Feature docs — reference only, not needed for coding
docs/features/
```
  </action>
  <verify>
    <automated>python -c "import ast; ast.parse(open('tests/test_hypothesis_validator.py').read()); print('AST OK')" && python -m pytest tests/test_hypothesis_validator.py -x -q --tb=short && python -c "import os; sz=os.path.getsize('tests/test_hypothesis_validator.py'); print(f'Size: {sz//1024}KB'); assert sz < 50*1024, 'Still too large'" && test -f .claudeignore && echo ".claudeignore exists"</automated>
  </verify>
  <done>
    - tests/test_hypothesis_validator.py parses as valid Python, all tests pass, file is under 50KB
    - .claudeignore exists at repo root with all specified patterns
  </done>
</task>

<task type="auto">
  <name>Task 2: Split CURRENT_STATE.md, consolidate stale docs, patch pyproject.toml</name>
  <files>
    docs/CURRENT_STATE.md,
    docs/archive/CURRENT_STATE_HISTORY.md,
    docs/dev_logs/DEVLOG_LEGACY.md,
    docs/archive/roadmap3_completion.md,
    docs/archive/TODO_SIMTRADER_STUDIO.md,
    pyproject.toml
  </files>
  <action>
**Split docs/CURRENT_STATE.md:**

The file is 1072 lines. Line 641 begins "## Historical checkpoint: 2026-03-05 Track A code
complete" — this is the archive boundary.

1. Read the full CURRENT_STATE.md
2. Create `docs/archive/CURRENT_STATE_HISTORY.md` with:
   - Header: `# CURRENT_STATE — Historical Archive\n\nMoved from CURRENT_STATE.md on 2026-03-27. Reference only.\n\n`
   - Then lines 641 through end of file (the historical section)
3. Truncate CURRENT_STATE.md to lines 1–640, then append:
   `\n---\n\n> **Historical details** (pre-Phase-1 implementation records) moved to \`docs/archive/CURRENT_STATE_HISTORY.md\`.\n`
4. Verify active file is now under 650 lines

**Consolidate devlog directory:**

1. Move `docs/devlog/DEVLOG.md` → `docs/dev_logs/DEVLOG_LEGACY.md`
   Use: `cp docs/devlog/DEVLOG.md docs/dev_logs/DEVLOG_LEGACY.md`
2. Remove the directory: `rm -rf docs/devlog/`

**Clean up stale top-level docs:**

Run these moves/deletes:
- `mv docs/roadmap3_completion.md docs/archive/roadmap3_completion.md`
- `rm docs/GDRIVE_CONNECTOR_TEST_2026-03-25.md` (test artifact — delete)
- `rm docs/GDRIVE_SYNC_TEST_2026-03-25.md` (test artifact — delete)
- `mv docs/TODO_SIMTRADER_STUDIO.md docs/archive/TODO_SIMTRADER_STUDIO.md`

**Patch pyproject.toml — add missing packages and fix URLs:**

1. Fix URLs (lines near `[project.urls]`):
   - Change `"https://github.com/polymarket/polytool"` → `"https://github.com/Amanpat/PolyTool"`
   - Change `"https://github.com/polymarket/polytool/tree/main/docs"` → `"https://github.com/Amanpat/PolyTool/tree/main/docs"`

2. Add missing packages to the `packages = [...]` list under `[tool.setuptools]`.
   The current list ends with `"packages.polymarket.simtrader.broker"` and then
   `"tools", "tools.cli", "tools.guard"`.
   Insert these BEFORE the `"tools"` entry:
   ```
   "packages.polymarket.crypto_pairs",
   "packages.polymarket.simtrader.batch",
   "packages.polymarket.simtrader.execution",
   "packages.polymarket.simtrader.portfolio",
   "packages.polymarket.simtrader.shadow",
   "packages.polymarket.simtrader.strategies",
   "packages.polymarket.simtrader.strategy",
   "packages.polymarket.simtrader.sweeps",
   ```

3. Verify pyproject.toml still parses: `python -c "import tomllib; tomllib.loads(open('pyproject.toml').read()); print('TOML OK')"` (Python 3.11+). If tomllib not available, use: `python -c "import tomli; tomli.loads(open('pyproject.toml').read()); print('OK')"` — or just run `python -m pytest --collect-only -q 2>&1 | head -5` to confirm the package is importable.
  </action>
  <verify>
    <automated>python -c "lines=open('docs/CURRENT_STATE.md').readlines(); count=len(lines); print(f'Active CURRENT_STATE: {count} lines'); assert count < 650, f'Too many lines: {count}'" && test -f docs/archive/CURRENT_STATE_HISTORY.md && echo "Archive exists" && test -f docs/dev_logs/DEVLOG_LEGACY.md && echo "Legacy devlog moved" && test ! -d docs/devlog && echo "devlog dir removed" && test -f docs/archive/roadmap3_completion.md && test ! -f docs/roadmap3_completion.md && echo "roadmap3 archived" && test ! -f "docs/GDRIVE_CONNECTOR_TEST_2026-03-25.md" && test ! -f "docs/GDRIVE_SYNC_TEST_2026-03-25.md" && echo "test artifacts deleted" && grep -q "Amanpat" pyproject.toml && echo "URLs fixed" && grep -q "simtrader.execution" pyproject.toml && echo "packages patched"</automated>
  </verify>
  <done>
    - CURRENT_STATE.md active portion is under 650 lines with archive footer
    - docs/archive/CURRENT_STATE_HISTORY.md contains the historical records
    - docs/devlog/ directory is gone; contents moved to docs/dev_logs/DEVLOG_LEGACY.md
    - roadmap3_completion.md and TODO_SIMTRADER_STUDIO.md moved to docs/archive/
    - GDRIVE test files deleted
    - pyproject.toml URLs point to Amanpat/PolyTool and packages list includes all simtrader subpackages
  </done>
</task>

<task type="auto">
  <name>Task 3: File size guard, users.txt migration, README update, dev log</name>
  <files>
    tools/guard/check_file_sizes.py,
    config/watchlist_usernames.txt,
    README.md,
    docs/dev_logs/2026-03-27_repo_cleanup.md
  </files>
  <action>
**Create tools/guard/check_file_sizes.py:**

Create the file with exactly this content:

```python
#!/usr/bin/env python3
"""Pre-commit guard: reject files over 500KB."""
import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-kb", type=int, default=500)
    args = parser.parse_args()

    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True, check=True
    )
    violations = []
    for path in result.stdout.strip().split("\n"):
        if not path:
            continue
        try:
            import os
            size_kb = os.path.getsize(path) / 1024
            if size_kb > args.max_kb:
                violations.append((path, size_kb))
        except FileNotFoundError:
            continue

    if violations:
        print(f"ERROR: {len(violations)} file(s) exceed {args.max_kb}KB:")
        for path, size in sorted(violations, key=lambda x: -x[1]):
            print(f"  {size:,.0f}KB  {path}")
        return 1
    print(f"OK: all tracked files under {args.max_kb}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Then run it: `python tools/guard/check_file_sizes.py`

Note any files it flags — include them in the dev log. Do NOT fix flagged files beyond what
is already addressed in Tasks 1 and 2. Just document.

**Migrate users.txt:**

1. Read `users.txt`
2. Create `config/watchlist_usernames.txt` with content:
   ```
   # Polymarket usernames for wallet watchlist — see Phase 2 candidate-scan
   ```
   followed by the original content of users.txt
3. Delete `users.txt` from repo root: `rm users.txt`

**Update README.md status section:**

Find the block starting with `## Current Status (as of 2026-03-07)` and replace the entire
paragraph/table that follows it (through the next `---` or `##` heading) with:

```markdown
## Current Status (as of 2026-03-27)

> **Current Status (as of 2026-03-27):** Phase 1A (crypto pair bot) is
> code-complete and awaiting 24-hour paper soak. Phase 1B (market maker
> gate closure) is in active development — Gate 2 sweep tooling is complete,
> Gate 2 verdict pending. See `docs/CURRENT_STATE.md` for full details.
```

Be careful to preserve the rest of README.md. Read the full file first, make the targeted
replacement, write it back.

**Write dev log docs/dev_logs/2026-03-27_repo_cleanup.md:**

Include:
- Summary of each task completed (Tasks 1–3 of this plan)
- File size before/after for test_hypothesis_validator.py (before: ~26MB / 677 lines;
  after: record actual KB and line count after cleanup)
- Line count before/after for CURRENT_STATE.md (before: 1072 lines; after: record actual)
- List of files moved/deleted
- Output of `python tools/guard/check_file_sizes.py` (copy the actual output)
- Any remaining flagged files not addressed in this cleanup and why
  </action>
  <verify>
    <automated>python tools/guard/check_file_sizes.py; test -f tools/guard/check_file_sizes.py && echo "guard exists" && test -f config/watchlist_usernames.txt && echo "watchlist moved" && test ! -f users.txt && echo "users.txt removed" && grep -q "2026-03-27" README.md && echo "README updated" && test -f docs/dev_logs/2026-03-27_repo_cleanup.md && echo "dev log written"</automated>
  </verify>
  <done>
    - tools/guard/check_file_sizes.py exists and runs without Python errors
    - config/watchlist_usernames.txt has comment header + original content; users.txt is gone
    - README.md status section updated to 2026-03-27 with current Phase 1A/1B state
    - docs/dev_logs/2026-03-27_repo_cleanup.md documents all changes, before/after sizes, guard output
  </done>
</task>

</tasks>

<verification>
Run after all tasks complete:

```bash
# Critical: corrupted file is gone
python -c "sz=__import__('os').path.getsize('tests/test_hypothesis_validator.py'); print(f'{sz//1024}KB'); assert sz < 50*1024"

# Tests still pass
python -m pytest tests/test_hypothesis_validator.py -x -q --tb=short

# .claudeignore in place
test -f .claudeignore && wc -l .claudeignore

# Active CURRENT_STATE under 650 lines
wc -l docs/CURRENT_STATE.md

# pyproject.toml has new packages
grep -c "simtrader\." pyproject.toml

# Guard runs clean (after Tasks 1-2 clean up the big file)
python tools/guard/check_file_sizes.py

# Smoke test: CLI still loads
python -m polytool --help
```
</verification>

<success_criteria>
- tests/test_hypothesis_validator.py: under 50KB, parses as valid Python, all existing tests pass
- .claudeignore: exists at repo root with all 8 ignore blocks specified
- docs/CURRENT_STATE.md: under 650 lines; footer references archive
- docs/archive/CURRENT_STATE_HISTORY.md: exists with pre-Phase-1 historical records
- docs/devlog/: directory removed; DEVLOG.md moved to docs/dev_logs/DEVLOG_LEGACY.md
- docs/archive/: contains roadmap3_completion.md and TODO_SIMTRADER_STUDIO.md
- GDRIVE test files: deleted from docs/
- pyproject.toml: Amanpat/PolyTool URLs; 8 additional simtrader packages listed
- tools/guard/check_file_sizes.py: exists, runs, documents any remaining oversized files
- config/watchlist_usernames.txt: has comment header + original users.txt content
- users.txt: deleted from repo root
- README.md: status section updated to 2026-03-27
- docs/dev_logs/2026-03-27_repo_cleanup.md: complete dev log with before/after metrics
- python -m polytool --help: no import errors (regression check)
</success_criteria>

<output>
After completion, create `.planning/quick/30-polytool-repo-cleanup-fix-corrupted-test/30-SUMMARY.md`
with a record of what was done, file sizes before/after, and any remaining issues.
</output>
