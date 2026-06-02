# Repo Hygiene: Commit Splitting After 4788871

**Date:** 2026-05-25  
**Author:** Claude Code (Sonnet 4.6)  
**Scope:** git history repair only — no feature logic changed

---

## Problem

Commit `4788871` was created for L2.1 Deliverable B (offline-safe semantic fallback) but
accidentally bundled 124 unrelated `docs/obsidian-vault/legacy/` files alongside the 3 actual
L2.1 files. The mixed commit made the L2.1 code change hard to audit and left unrelated vault
content in the history without Director review.

---

## Branch and Push Status

- Branch: `main`
- Remote: `origin/main` — commit `4788871` was **NOT pushed** (main was 7 commits ahead of origin at start of session)
- History rewrite was safe under repo policy

---

## Files in 4788871 Grouped by Scope

### L2.1 Deliverable B (3 files — the intended change)
| Status | Path |
|--------|------|
| A | `docs/dev_logs/2026-05-25_l2-1-semantic-fallback-offline-safe-fix.md` |
| M | `packages/research/synthesis/academic_query.py` |
| M | `tests/test_research_query.py` |

### Unrelated vault/legacy additions (124 files — should not have been staged)
All files under `docs/obsidian-vault/legacy/` covering:
- `Claude Desktop/08-Research/` — 13 files
- `Claude Desktop/09-Decisions/` — 14 files
- `Claude Desktop/10-Session-Notes/` — 9 files
- `Claude Desktop/11-Prompt-Archive/` — 14 files
- `Claude Desktop/12-Ideas/` — 16 files
- `Claude Desktop/` root (Dashboard, Current-Focus) — 2 files
- `PolyTool/00-Index/` — 5 files
- `PolyTool/01-Architecture/` — 7 files
- `PolyTool/02-Modules/` — 12 files
- `PolyTool/03-Strategies/` — 3 files
- `PolyTool/04-CLI/` — 1 file
- `PolyTool/05-Roadmap/` — 9 files
- `PolyTool/06-Dev-Log/` — 1 file
- `PolyTool/07-Issues/` — 9 files

Total vault/legacy files: 124 additions, all under `docs/obsidian-vault/legacy/`

---

## Action Taken

1. **Inspected** commit `4788871` with `git show --stat --name-status 4788871` — confirmed 127 file entries (3 L2.1 + 124 vault/legacy)
2. **Confirmed not pushed** — `main` was 7 commits ahead of `origin/main`
3. **Soft reset** to parent commit `15ef471`:
   ```
   git reset --soft HEAD~1
   ```
4. **Verified index** with `git diff --cached --name-status` — 127 entries as expected
5. **Unstaged vault directory** from index:
   ```
   git restore --staged "docs/obsidian-vault/"
   ```
6. **Verified clean index** — exactly 3 L2.1 files remained staged
7. **Re-committed** only L2.1 files under new SHA `7fc6bf2` with original commit message preserved

---

## Commands and Output

```
$ git show --stat --name-status 4788871
# → 127 files including 124 docs/obsidian-vault/legacy/* additions

$ git status -sb | head -2
## main...origin/main [ahead 7]

$ git reset --soft HEAD~1
# (no output)

$ git diff --cached --name-status | wc -l
127

$ git restore --staged "docs/obsidian-vault/"
# (no output)

$ git diff --cached --name-status
A   docs/dev_logs/2026-05-25_l2-1-semantic-fallback-offline-safe-fix.md
M   packages/research/synthesis/academic_query.py
M   tests/test_research_query.py

$ git commit -m "fix(ris): L2.1 Deliverable B — offline-safe semantic fallback, resolves Codex BLOCK"
[main 7fc6bf2] ... 3 files changed, 669 insertions(+), 89 deletions(-)

$ python -m pytest tests/test_research_query.py tests/test_ris_marker_queue.py -q --tb=short
299 passed, 1 skipped in 6.07s
```

---

## Final Git State

### History (HEAD)
```
7fc6bf2  fix(ris): L2.1 Deliverable B — offline-safe semantic fallback, resolves Codex BLOCK  [3 files only]
15ef471  docs(ris): repo hygiene before L2.1 Deliverable A — closeout log
3348e79  feat(ris): L2.1 Deliverable C — display-only snippet sanitation
...
```

### Index (staged)
Empty — nothing staged.

### Working tree dirty files (unstaged, need Director review before committing)
- `AGENTS.md` — modified
- `claude.md` — modified
- `docs/obsidian-vault/.obsidian/` — several config files modified
- `docs/obsidian-vault/.obsidian/plugins/smart-connections*/` — deleted (plugin removed)
- `docs/obsidian-vault/.smart-env/` — modified event logs
- `docs/obsidian-vault/AGENT.md` — deleted
- `docs/obsidian-vault/Claude Desktop/08-Research/` — ~12 files deleted (pre-existed commit 4788871, these are separate legacy-move deletions)
- `docs/obsidian-vault/legacy/` — **124 untracked files** (the files from the mixed commit, now sitting unstaged for Director review)

---

## L2.1 Acceptance Repair: Safe to Start?

**YES.** The L2.1 code is cleanly isolated in commit `7fc6bf2` with its own dev log. The vault/legacy
files are in the working tree, unstaged, and require a separate Director-reviewed vault commit before
being pushed. L2.1 acceptance testing can proceed without touching vault state.

---

## Open Questions for Director

1. **`docs/obsidian-vault/legacy/`** — 124 files. Should these be committed as a separate vault-hygiene commit (e.g., `chore(vault): archive legacy Claude Desktop and PolyTool notes to legacy/`)? Or discarded?
2. **`docs/obsidian-vault/Claude Desktop/08-Research/` deletions** — the originals at the non-legacy path were deleted in the working tree (pre-existing change from prior session). These deletions are consistent with the legacy-move pattern.
3. **`AGENTS.md` and `claude.md` modifications** — appear unrelated to both L2.1 and the vault legacy move; Director should confirm before staging.
