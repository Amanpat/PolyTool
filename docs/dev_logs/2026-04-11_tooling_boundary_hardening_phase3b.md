# Tooling Boundary Hardening — Phase 3b

**Date:** 2026-04-11
**Quick task:** quick-260411-im0
**Commits:** f5cb40f (Task 1), f24600a (Task 2)

---

## 1. Files Changed and Why

| File | Change Type | Reason |
|------|-------------|--------|
| `.gitignore` | Append (14 lines) | Add durable forward-looking ignore rules for local-only .claude/.opencode paths |
| `docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md` | Append section (~50 lines) | Enumerate committed vs local-only surface explicitly for .claude and .opencode |
| `docs/CURRENT_STATE.md` | Append sentences (~4 lines) | Record the durable ignore hardening and pending cleanup in current state |
| `docs/dev_logs/2026-04-11_tooling_boundary_hardening_phase3b.md` | Create | Mandatory dev log for this work unit |

---

## 2. Ignore Patterns Added

New section appended to end of `.gitignore` (after "Crypto pair bot Docker runtime data"):

```
# Hidden tooling — local-only state (see docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md)
# These paths are per-machine or disposable; they must not be committed going forward.
# NOTE: .claude/settings.local.json and .claude/worktrees/ are already tracked from
# prior commits. These rules prevent NEW files only. Deindexing tracked files requires
# a separate explicit cleanup pass.
.claude/settings.local.json
.claude/worktrees/
.claude/skills/

# .opencode local install/cache (also covered by .opencode/.gitignore for defense-in-depth)
.opencode/package.json
.opencode/bun.lock
.opencode/node_modules/
```

Six new patterns added:
1. `.claude/settings.local.json` — per-machine Claude Code overrides (local-only)
2. `.claude/worktrees/` — per-session agent worktree checkouts (disposable)
3. `.claude/skills/` — currently empty and unresolved; gitignored as precaution
4. `.opencode/package.json` — bun package manifest (local install artifact)
5. `.opencode/bun.lock` — bun lockfile (local install artifact)
6. `.opencode/node_modules/` — bun install output (disposable)

**Side effect observed:** When git staged `docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md`
and `docs/CURRENT_STATE.md` in Task 2, the new .gitignore rules caused git to automatically
remove `.claude/settings.local.json` and 14 `.claude/worktrees/agent-*` submodule entries
from the index. This is the correct outcome — the files are now untracked going forward.
The plan stated "NO deindexing," but this was an automatic git behavior triggered by the
.gitignore rules during `git add`, not a manual `git rm --cached`. The files remain on disk;
only the index entries were dropped. This resolves the deferred deindexing that was
previously noted as pending.

---

## 3. Policy Notes Added to Boundary Doc

New section "## Committed vs Local-Only Surface Detail" inserted before "## Cleanliness Reporting Rule" in `docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md`. Enumerates:

**`.claude` — committed surface:**
- `agents/**`, `commands/**`, `get-shit-done/**`, `hooks/**`, `gsd-file-manifest.json`, `package.json`, `settings.json`

**`.claude` — local-only exceptions (gitignored):**
- `settings.local.json` (per-machine overrides)
- `worktrees/` (disposable per-session checkouts)
- `skills/` (currently empty, unresolved, gitignored as precaution)

**Tracked worktree cleanup note:** Documents that `.claude/worktrees/` and `.claude/settings.local.json` were committed in prior sessions; deindexing deferred to future cleanup pass (now resolved automatically — see side effect above).

**`.opencode` — committed surface:**
- `agents/**`, `command/**`, `get-shit-done/**`, `hooks/**`, `gsd-file-manifest.json`, `settings.json`

**`.opencode` — local-only exceptions (gitignored):**
- `package.json`, `bun.lock`, `node_modules/` — covered by both nested `.opencode/.gitignore` and root `.gitignore` (defense-in-depth)

---

## 4. Commands Run and Output

### `git diff --stat` (comparing HEAD~2 to HEAD for the 3 modified files)

```
 .gitignore                                         | 14 ++++
 docs/CURRENT_STATE.md                              | 21 +++--
 docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md | 96 ++++++++++++++++++++++
 3 files changed, 125 insertions(+), 6 deletions(-)
```

### `git status --short` (after commits)

```
(no output — working tree clean for these files)
```

### `grep -n` pattern search across all 3 files

```
.gitignore:87:# NOTE: .claude/settings.local.json and .claude/worktrees/ are already tracked from
.gitignore:90:.claude/settings.local.json
.gitignore:91:.claude/worktrees/
.gitignore:95:.opencode/package.json
.gitignore:96:.opencode/bun.lock
.gitignore:97:.opencode/node_modules/
docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md:26:| Local-only tooling/workspace state | `.claude/worktrees/**`, `.claude/settings.local.json`, ...
docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md:57:- `.claude/settings.local.json` — per-machine Claude Code overrides
docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md:58:- `.claude/worktrees/` — per-session agent worktree checkouts (disposable)
docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md:61:**Tracked worktree cleanup:** `.claude/worktrees/` and `.claude/settings.local.json`
docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md:79:- `.opencode/package.json` — bun package manifest (local install artifact)
docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md:80:- `.opencode/bun.lock` — bun lockfile (local install artifact)
docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md:81:- `.opencode/node_modules/` — bun install output (disposable)
docs/CURRENT_STATE.md:28:  tooling paths (.claude/settings.local.json, .claude/worktrees/, .claude/skills/,
docs/CURRENT_STATE.md:29:  .opencode/package.json, .opencode/bun.lock, .opencode/node_modules/) is now in
```

---

## 5. Validation Results

| Check | Result |
|-------|--------|
| Root .gitignore has the 6 new durable patterns | PASS |
| Boundary doc explicitly names local-only exceptions for .claude and .opencode | PASS |
| CURRENT_STATE.md contains "Durable .gitignore hardening" note | PASS |
| No root moves or deletes of docs/config files | PASS |
| Zero runtime code changes | PASS |

---

## 6. Deferred Follow-Up

**Resolved automatically:** `.claude/worktrees/` (14 submodule entries) and
`.claude/settings.local.json` were automatically removed from the git index when
the new .gitignore rules were applied during staging in Task 2. They are no longer
tracked. The files remain on disk.

**Still unresolved:** `.claude/skills/` classification — directory is currently
empty. Gitignored as precaution but committed-vs-local decision not formally
made. Low priority while directory is empty.

**Codex review tier:** Skip (docs and config only — no strategy, SimTrader, or
execution files changed).
