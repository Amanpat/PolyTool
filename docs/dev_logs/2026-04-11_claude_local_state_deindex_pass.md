# 2026-04-11 — Claude Local State Deindex Pass

**Work packet:** quick-260411-ime  
**Objective:** Safely deindex confirmed-local .claude paths from the git index while
preserving all filesystem contents.

---

## Background

The git index tracked 15 paths classified as "Local-only tooling/workspace state" per
`docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md`:

- `.claude/settings.local.json` — machine-local Claude Code permissions (allow list,
  MCP server toggles). Not secrets; not shared across machines.
- `.claude/worktrees/agent-*` — 14 gitlink entries (mode 160000, submodule-like
  references) left over from the branch consolidation in quick-260406-lnp when 54
  worktrees were removed but these 14 gitlink index entries remained.

These should not be tracked in the repo. Their on-disk contents must be preserved.

---

## Pre-Audit Snapshot

Full `git ls-files --stage .claude/settings.local.json .claude/worktrees` output
before any changes:

```
100644 50a2e06f5bfd7813a46dbec156a965d1db9af648 0	.claude/settings.local.json
160000 117a86b21ceb22d2293671f6625e2b5ac4cdcf45 0	.claude/worktrees/agent-a0429840
160000 9225250add373d0ddf01f454cc045a6a790fdedf 0	.claude/worktrees/agent-a1473bf4
160000 9225250add373d0ddf01f454cc045a6a790fdedf 0	.claude/worktrees/agent-a2bc9420
160000 9225250add373d0ddf01f454cc045a6a790fdedf 0	.claude/worktrees/agent-a40a102d
160000 117a86b21ceb22d2293671f6625e2b5ac4cdcf45 0	.claude/worktrees/agent-a4825598
160000 9225250add373d0ddf01f454cc045a6a790fdedf 0	.claude/worktrees/agent-a4b6596f
160000 117a86b21ceb22d2293671f6625e2b5ac4cdcf45 0	.claude/worktrees/agent-a524066d
160000 9225250add373d0ddf01f454cc045a6a790fdedf 0	.claude/worktrees/agent-a5f16228
160000 9225250add373d0ddf01f454cc045a6a790fdedf 0	.claude/worktrees/agent-a89f032a
160000 117a86b21ceb22d2293671f6625e2b5ac4cdcf45 0	.claude/worktrees/agent-ab086539
160000 9225250add373d0ddf01f454cc045a6a790fdedf 0	.claude/worktrees/agent-ac10cce2
160000 9225250add373d0ddf01f454cc045a6a790fdedf 0	.claude/worktrees/agent-ac7c51a9
160000 9225250add373d0ddf01f454cc045a6a790fdedf 0	.claude/worktrees/agent-ae6a0800
160000 9225250add373d0ddf01f454cc045a6a790fdedf 0	.claude/worktrees/agent-aff2e2a0
```

**Total: 15 entries** — 1 regular file (mode 100644) + 14 gitlinks (mode 160000).

Gitlink SHA breakdown:
- `117a86b2...` — 3 entries (agent-a0429840, agent-a4825598, agent-ab086539) plus agent-a524066d
- `9225250a...` — 11 entries

---

## Safety Bar Evaluation

### .claude/settings.local.json

| Criterion | Verdict |
|-----------|---------|
| Classification | Local-only tooling/workspace state |
| Contains secrets? | No — allow list and MCP server toggles only |
| Filesystem existence before deindex | YES |
| Active code dependencies (Python, CLI)? | None found |
| Active config dependencies? | None found |
| Workflow doc references? | 2 mentions in `.claude/get-shit-done/workflows/manager.md` — both instruct agent workflows to *write to* the file; the file must exist on disk (it does) but need not be git-tracked |
| Safe to deindex? | CLEAR |

The two references found in `manager.md` are in GSD orchestration instructions:
```
.claude/get-shit-done/workflows/manager.md:307:  - "Add permission and retry": Use
  `Skill(skill="update-config")` to add the permission to `settings.local.json` ...
```
These describe runtime agent behavior that writes to the file on disk. Git-tracking the
file is not required for this to work. The file remains on disk after deindexing.

### .claude/worktrees/agent-* (14 gitlinks)

| Criterion | Verdict |
|-----------|---------|
| Classification | Local-only tooling/workspace state (disposable agent workspace references) |
| Mode | 160000 (gitlinks / submodule-like) |
| Origin | Remnants from quick-260406-lnp branch consolidation |
| Filesystem existence before deindex | YES (.claude/worktrees/ directory exists) |
| Active code dependencies? | None found |
| Active config dependencies? | None found |
| Safe to deindex? | CLEAR |

---

## Dependency Check Results

Command run:
```bash
git grep -n "\.claude/worktrees\|settings\.local\.json" \
  -- ':!docs/dev_logs' ':!docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md' ':!.planning'
```

Output:
```
.claude/get-shit-done/workflows/manager.md:307:  - **question:** "Phase {N} failed — permission denied for `{tool_or_command}`. Want me to add it to settings.local.json so it's allowed?"
.claude/get-shit-done/workflows/manager.md:309:  - "Add permission and retry": Use `Skill(skill="update-config")` to add the permission to `settings.local.json`, then re-spawn the background agent. Loop to dashboard.
```

**Assessment:** These are GSD orchestration workflow instructions, not active code, tests,
or config that require git-tracking. No blocker. Proceeding with deindex.

---

## Deindex Commands and Results

### Step 1 — Deindex .claude/settings.local.json

```bash
git rm --cached .claude/settings.local.json
# Output: rm '.claude/settings.local.json'
```

Verification: `git ls-files .claude/settings.local.json` → empty (deindexed)  
Disk: `test -f .claude/settings.local.json` → EXISTS

### Step 2 — Deindex all 14 .claude/worktrees/agent-* entries

```bash
git rm --cached .claude/worktrees/agent-a0429840   # rm '.claude/worktrees/agent-a0429840'
git rm --cached .claude/worktrees/agent-a1473bf4   # rm '.claude/worktrees/agent-a1473bf4'
git rm --cached .claude/worktrees/agent-a2bc9420   # rm '.claude/worktrees/agent-a2bc9420'
git rm --cached .claude/worktrees/agent-a40a102d   # rm '.claude/worktrees/agent-a40a102d'
git rm --cached .claude/worktrees/agent-a4825598   # rm '.claude/worktrees/agent-a4825598'
git rm --cached .claude/worktrees/agent-a4b6596f   # rm '.claude/worktrees/agent-a4b6596f'
git rm --cached .claude/worktrees/agent-a524066d   # rm '.claude/worktrees/agent-a524066d'
git rm --cached .claude/worktrees/agent-a5f16228   # rm '.claude/worktrees/agent-a5f16228'
git rm --cached .claude/worktrees/agent-a89f032a   # rm '.claude/worktrees/agent-a89f032a'
git rm --cached .claude/worktrees/agent-ab086539   # rm '.claude/worktrees/agent-ab086539'
git rm --cached .claude/worktrees/agent-ac10cce2   # rm '.claude/worktrees/agent-ac10cce2'
git rm --cached .claude/worktrees/agent-ac7c51a9   # rm '.claude/worktrees/agent-ac7c51a9'
git rm --cached .claude/worktrees/agent-ae6a0800   # rm '.claude/worktrees/agent-ae6a0800'
git rm --cached .claude/worktrees/agent-aff2e2a0   # rm '.claude/worktrees/agent-aff2e2a0'
```

All 14 returned `rm` confirmations. No errors.

---

## Post-Deindex Verification

```bash
git ls-files --stage .claude/settings.local.json .claude/worktrees
# Output: (empty) — 0 lines
```

```bash
test -f .claude/settings.local.json && echo "ON DISK: YES"
# Output: ON DISK: YES

test -d .claude/worktrees && echo "ON DISK: YES"
# Output: ON DISK: YES
```

```bash
git diff HEAD -- .gitignore | wc -l
# Output: 0 (no .gitignore modifications)
```

---

## Filesystem Existence Confirmation

| Path | On Disk Before | On Disk After |
|------|---------------|---------------|
| .claude/settings.local.json | YES | YES |
| .claude/worktrees/ (directory) | YES | YES |

No filesystem deletions occurred. The `--cached` flag was used for all `git rm` calls,
which removes from the index only.

---

## Ambiguous Paths Left Untouched

None. All 15 targeted paths were unambiguously classified as local-only and were deindexed.

No additional .claude paths were touched beyond the 15 enumerated in this plan.

---

## Constraints Honored

| Constraint | Status |
|------------|--------|
| No filesystem deletion | HONORED — only `git rm --cached` used |
| No .gitignore edits | HONORED — `git diff HEAD -- .gitignore` returns 0 lines |
| No vault edits | HONORED — no vault files touched |
| No .opencode changes | HONORED — not in scope |
| All --cached flags used | HONORED — verified each git rm command |

---

## Codex Review Note

Tier: Skip (git index hygiene + docs only, no execution/strategy/broker code).

---

## Summary

- 15 confirmed-local paths removed from git index (1 settings file + 14 gitlink entries)
- All deindexed paths preserved on the local filesystem
- Zero filesystem deletions
- Zero .gitignore modifications
- Dependency check found 2 GSD workflow doc references to settings.local.json; assessed
  as non-blocking (runtime write behavior, not git-tracking dependency)
- Single clean commit staged with deindex changes + this dev log
