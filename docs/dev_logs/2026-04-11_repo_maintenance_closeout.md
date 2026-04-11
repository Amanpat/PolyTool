# 2026-04-11 Repo Maintenance Closeout

## Scope

Final closeout of the PolyTool repo-maintenance cleanup stream. This log
documents verification of durable state, correction of two stale "pending"
references in documentation, and a retry pass on previously blocked scratch
residue paths.

## Prior Work Packets Referenced

- **quick-260410 series** — initial policy definition, scratch cleanup, .gitignore
  hardening for local-only hidden tooling paths.
- **quick-260411-im0** — tooling boundary hardening phase 3b; automatic deindexing
  of `.claude/worktrees/` (14 gitlink entries) occurred during staging (commit f24600a).
- **quick-260411-ime** — explicit Claude local-state deindex audit pass; confirmed
  `.claude/settings.local.json` and all `.claude/worktrees/` entries removed from git
  index (commit 79fe441).

## Verification Evidence

### 1. .gitignore durable patterns (all 6 required)

Command:
```
git grep -n "\.claude/settings\.local\.json\|\.claude/worktrees/\|\.claude/skills/\|\.opencode/package\.json\|\.opencode/bun\.lock\|\.opencode/node_modules/" .gitignore
```

Result:
```
.gitignore:87:# NOTE: .claude/settings.local.json and .claude/worktrees/ are already tracked from
.gitignore:90:.claude/settings.local.json
.gitignore:91:.claude/worktrees/
.gitignore:92:.claude/skills/
.gitignore:95:.opencode/package.json
.gitignore:96:.opencode/bun.lock
.gitignore:97:.opencode/node_modules/
```

PASS — All 6 patterns present at lines 90-92 and 95-97.

### 2. Git index clean for deindexed paths

Command:
```
git ls-files --stage .claude/settings.local.json .claude/worktrees
```

Result: (empty output)

PASS — Zero entries in git index for both paths.

### 3. Boundary doc enumerates same paths

Command:
```
git grep -n "\.claude/settings\.local\.json\|\.claude/worktrees/\|\.opencode/package\.json\|\.opencode/bun\.lock\|\.opencode/node_modules/" docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md
```

Result:
```
LOCAL_STATE_AND_TOOLING_BOUNDARY.md:26: ...`.claude/worktrees/**`, `.claude/settings.local.json`...`.opencode/node_modules/**`...
LOCAL_STATE_AND_TOOLING_BOUNDARY.md:57: - `.claude/settings.local.json`...
LOCAL_STATE_AND_TOOLING_BOUNDARY.md:58: - `.claude/worktrees/`...
LOCAL_STATE_AND_TOOLING_BOUNDARY.md:79: - `.opencode/package.json`...
LOCAL_STATE_AND_TOOLING_BOUNDARY.md:80: - `.opencode/bun.lock`...
LOCAL_STATE_AND_TOOLING_BOUNDARY.md:81: - `.opencode/node_modules/`...
```

PASS — Boundary doc enumerates all relevant paths.

## Stale Reference Fixes

Two documentation files had stale "pending" language that was not updated after
the deindex was completed in quick-260411-im0 and quick-260411-ime.

### Fix A: docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md (lines 61-64)

**Before (stale):**
```
**Tracked worktree cleanup:** `.claude/worktrees/` and `.claude/settings.local.json`
were committed in prior sessions and remain tracked despite the new .gitignore rules.
Deindexing is deferred pending per-path safety inspection in a future explicit cleanup
pass. The .gitignore rules prevent new files from being tracked going forward.
```

**After (accurate):**
```
**Tracked worktree cleanup (RESOLVED):** `.claude/worktrees/` (14 gitlink entries)
and `.claude/settings.local.json` were deindexed in quick-260411-im0 (commit
f24600a, automatic during staging) and quick-260411-ime (commit 79fe441, explicit
audit). The files remain on disk; only git index tracking was removed. The
.gitignore rules prevent new files from being tracked going forward.
```

**Why:** The deindex had already completed, but this note still said "deferred".

### Fix B: docs/CURRENT_STATE.md (line 30)

**Before (stale):**
```
place; tracked .claude worktree cleanup is still pending per-path safety review.
```

**After (accurate):**
```
place; tracked .claude worktree and settings.local.json deindexing is complete
(quick-260411-im0 commit f24600a + quick-260411-ime commit 79fe441).
```

**Why:** Same issue — deindex was complete but CURRENT_STATE.md was not updated.

Both fixes committed in quick-260411-j6z commit a44d9ad.

## Scratch Residue Retry Results

The following 7 paths were retried individually with `rm -rf`. No `takeown` or
ACL changes were used.

| Path | Result |
|------|--------|
| `.tmp/pip-build-tracker-fcy4ypmd` | REMOVED (exit 0) |
| `.tmp/pip-ephem-wheel-cache-_rgr5nmi` | REMOVED (exit 0) |
| `.tmp/pip-wheel-fn9s3qb3` | REMOVED (exit 0) |
| `.tmp/pytest-basetemp/081ea328a47145a79ef75f8d6acd0cc4/test_packaged_schema_resource_0/wheelhouse/.tmp-1pulnpfh` | REMOVED (exit 0) |
| `.tmp/test-workspaces/897a0d2343ea4b928d42606fe2b4d18a/cache/pip-build-tracker-28v8oug4` | REMOVED (exit 0) |
| `kb/tmp_tests/tmpl_im8641` | REMOVED (exit 0) |
| `kb/tmp_tests/tmpyuk_p6f9` | REMOVED (exit 0) |

All 7 previously blocked paths were successfully removed. No paths remain blocked.

**Post-retry state:**
- `.tmp/` still exists and contains `pytest-basetemp/` and `test-workspaces/` with
  many test session subdirectories. These are not in scope for this cleanup task;
  they are disposable scratch that will be cleaned in future targeted passes.
- `kb/tmp_tests/` directory is now empty (both targeted entries removed).

## Final State Summary

The repo-maintenance cleanup stream is now complete. The stream covered: (1)
classification of root-level hidden tooling into public vs. local-only categories
via the LOCAL_STATE_AND_TOOLING_BOUNDARY.md policy doc; (2) .gitignore hardening
with 6 durable patterns for local-only paths across `.claude/` and `.opencode/`
roots; (3) git index deindexing of `.claude/worktrees/` (14 gitlink entries) and
`.claude/settings.local.json`, which were accidentally tracked from prior sessions;
(4) scratch cleanup of pip, pytest, and kb temp residue under `.tmp/` and
`kb/tmp_tests/`; and (5) this closeout pass correcting two stale "pending"
references in documentation to accurately reflect the completed deindex state.
The durable policies are now in place: correct gitignore rules prevent new
local-only files from being tracked, the git index is clean, and documentation
accurately reflects the completed state.

## Remaining Known Issues

None from the targeted cleanup scope. The `.tmp/pytest-basetemp/` and
`.tmp/test-workspaces/` directories contain a large number of test session
subdirectories (100+) that were not targeted by this cleanup. These are disposable
scratch under the boundary classification and can be cleaned in a future explicit
pass. They do not affect repo cleanliness metrics per the boundary policy.

## Codex Review Tier

Skip — this plan touches only documentation files and disposable scratch
directories. No execution code, strategy code, or risk-sensitive paths are
involved.
