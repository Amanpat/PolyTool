---
phase: quick-260411-ime
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .claude/settings.local.json (index only)
  - .claude/worktrees/agent-a0429840 (index only)
  - .claude/worktrees/agent-a1473bf4 (index only)
  - .claude/worktrees/agent-a2bc9420 (index only)
  - .claude/worktrees/agent-a40a102d (index only)
  - .claude/worktrees/agent-a4825598 (index only)
  - .claude/worktrees/agent-a4b6596f (index only)
  - .claude/worktrees/agent-a524066d (index only)
  - .claude/worktrees/agent-a5f16228 (index only)
  - .claude/worktrees/agent-a89f032a (index only)
  - .claude/worktrees/agent-ab086539 (index only)
  - .claude/worktrees/agent-ac10cce2 (index only)
  - .claude/worktrees/agent-ac7c51a9 (index only)
  - .claude/worktrees/agent-ae6a0800 (index only)
  - .claude/worktrees/agent-aff2e2a0 (index only)
  - docs/dev_logs/2026-04-11_claude_local_state_deindex_pass.md (new)
autonomous: true
requirements: []

must_haves:
  truths:
    - "All 14 tracked .claude/worktrees/agent-* gitlink entries are removed from the git index"
    - ".claude/settings.local.json is removed from the git index"
    - "All deindexed paths still exist on the local filesystem"
    - "No filesystem deletions occurred"
    - "No .gitignore edits were made"
    - "A dev log documents the full audit trail"
  artifacts:
    - path: "docs/dev_logs/2026-04-11_claude_local_state_deindex_pass.md"
      provides: "Audit trail of deindex decisions and results"
      min_lines: 40
  key_links:
    - from: "git index"
      to: ".claude/settings.local.json"
      via: "git rm --cached"
      pattern: "removed from index, preserved on disk"
    - from: "git index"
      to: ".claude/worktrees/agent-*"
      via: "git rm --cached"
      pattern: "14 gitlinks removed from index, filesystem untouched"
---

<objective>
Safely deindex confirmed-local .claude paths from the git index while preserving all
filesystem contents.

Purpose: The git index currently tracks 15 paths that are classified as "Local-only
tooling/workspace state" per docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md:
.claude/settings.local.json (machine-local Claude Code permissions) and 14
.claude/worktrees/agent-* gitlink entries (disposable agent workspace references left
over from the branch consolidation in quick-260406-lnp). These should not be tracked
in the repo but their on-disk contents must be preserved.

Output: Clean git index with 15 fewer tracked entries, all filesystem contents intact,
dev log with full audit trail.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md
@docs/adr/0014-public-docs-surface-and-repo-hygiene-boundaries.md
@.gitignore

## Pre-Audit Findings (from planning)

### .claude/settings.local.json
- Mode: 100644 (regular file)
- Content: Machine-local Claude Code permissions (allow list, MCP server toggles)
- Classification: "Local-only tooling/workspace state" per LOCAL_STATE_AND_TOOLING_BOUNDARY.md
- Active dependencies: None. No doc, config, or code references this as tracked repo truth.
- Safety verdict: CLEAR TO DEINDEX

### .claude/worktrees/agent-* (14 entries)
- Mode: 160000 (gitlinks / submodule-like references)
- All point to exactly 2 commit SHAs: 117a86b2 (3 entries) and 9225250a (11 entries)
- These are remnants from the branch consolidation (quick-260406-lnp removed 54 worktrees;
  these 14 gitlinks remained in the index)
- Classification: "Local-only tooling/workspace state" per LOCAL_STATE_AND_TOOLING_BOUNDARY.md
- Active dependencies: None. Referenced only in historical dev log narratives.
- Safety verdict: CLEAR TO DEINDEX

### Paths NOT in .gitignore
Neither .claude/settings.local.json nor .claude/worktrees/ appear in .gitignore.
This plan does NOT edit .gitignore (per constraints). A future task may add ignore rules.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Audit, deindex confirmed-local paths, and verify</name>
  <files>.claude/settings.local.json, .claude/worktrees/agent-*, docs/dev_logs/2026-04-11_claude_local_state_deindex_pass.md</files>
  <action>
Execute the following steps in order:

**Step 1 — Pre-audit snapshot.** Capture the full pre-state for the dev log:
```bash
git ls-files --stage .claude/settings.local.json .claude/worktrees
```
Record the output (15 entries expected: 1 regular file + 14 gitlinks).

**Step 2 — Confirm filesystem existence.** For each tracked path, verify it exists on
disk before deindexing. Record the existence check results.

**Step 3 — Confirm no active dependencies.** Run:
```bash
git grep -n "\.claude/worktrees\|settings\.local\.json" -- ':!docs/dev_logs' ':!docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md' ':!.planning'
```
If any matches appear in active code, configs, or non-historical docs, STOP and document
the blocker. Do NOT deindex paths with active dependencies. (Planning found zero active
dependencies; this is the executor's confirmation step.)

**Step 4 — Deindex .claude/settings.local.json:**
```bash
git rm --cached .claude/settings.local.json
```
Verify: `git ls-files .claude/settings.local.json` returns empty. Verify the file still
exists on disk.

**Step 5 — Deindex all 14 .claude/worktrees/agent-* entries:**
```bash
git rm --cached .claude/worktrees/agent-a0429840
git rm --cached .claude/worktrees/agent-a1473bf4
git rm --cached .claude/worktrees/agent-a2bc9420
git rm --cached .claude/worktrees/agent-a40a102d
git rm --cached .claude/worktrees/agent-a4825598
git rm --cached .claude/worktrees/agent-a4b6596f
git rm --cached .claude/worktrees/agent-a524066d
git rm --cached .claude/worktrees/agent-a5f16228
git rm --cached .claude/worktrees/agent-a89f032a
git rm --cached .claude/worktrees/agent-ab086539
git rm --cached .claude/worktrees/agent-ac10cce2
git rm --cached .claude/worktrees/agent-ac7c51a9
git rm --cached .claude/worktrees/agent-ae6a0800
git rm --cached .claude/worktrees/agent-aff2e2a0
```
Verify: `git ls-files .claude/worktrees` returns empty. Verify the worktree directories
still exist on disk.

**Step 6 — Post-deindex verification:**
```bash
git ls-files --stage .claude/settings.local.json .claude/worktrees
# Expected: no output (empty)

git status --short -- .claude
# Expected: D entries for settings.local.json and all 14 worktrees (staged deletions from index)

# Filesystem existence checks:
test -f .claude/settings.local.json && echo "settings.local.json EXISTS on disk"
test -d .claude/worktrees && echo "worktrees dir EXISTS on disk"
```

**Step 7 — Create dev log** at `docs/dev_logs/2026-04-11_claude_local_state_deindex_pass.md`
with:
- Date and objective
- Pre-audit snapshot (full `git ls-files --stage` output)
- Safety bar evaluation for each path class (settings.local.json and worktree gitlinks)
- Dependency check results
- Deindex commands executed and results
- Post-deindex verification output
- Filesystem existence confirmation
- Any ambiguous paths that were left untouched (expected: none)
- Constraints honored: no filesystem deletion, no .gitignore edits, no vault edits,
  no .opencode changes

**Step 8 — Commit** with message:
```
chore: deindex confirmed-local .claude paths from git index

Remove .claude/settings.local.json (machine-local permissions) and 14
.claude/worktrees/agent-* gitlink entries (disposable agent workspace
references) from the git index. Filesystem contents preserved.

Classified as "Local-only tooling/workspace state" per
docs/reference/LOCAL_STATE_AND_TOOLING_BOUNDARY.md.
```
Stage the deindex removals AND the new dev log together in one commit.
  </action>
  <verify>
    <automated>
cd "D:/Coding Projects/Polymarket/PolyTool" && \
  echo "=== Index check ===" && \
  git ls-files --stage .claude/settings.local.json .claude/worktrees | wc -l && \
  echo "=== Disk check ===" && \
  test -f .claude/settings.local.json && echo "settings.local.json ON DISK" && \
  test -d .claude/worktrees && echo "worktrees dir ON DISK" && \
  echo "=== Dev log exists ===" && \
  test -f docs/dev_logs/2026-04-11_claude_local_state_deindex_pass.md && echo "DEV LOG EXISTS" && \
  echo "=== No .gitignore edits ===" && \
  git diff HEAD -- .gitignore | wc -l
    </automated>
  </verify>
  <done>
- `git ls-files --stage .claude/settings.local.json .claude/worktrees` returns 0 lines (all deindexed)
- .claude/settings.local.json still exists on disk
- .claude/worktrees/ directory still exists on disk
- docs/dev_logs/2026-04-11_claude_local_state_deindex_pass.md exists with full audit trail
- .gitignore has zero changes
- No filesystem deletions occurred
- Commit recorded with deindex + dev log
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| git index vs filesystem | `git rm --cached` must not delete on-disk files |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | Tampering | git rm (without --cached) | mitigate | Every git rm command MUST use --cached flag; verify file existence on disk after each deindex |
| T-quick-02 | Information Disclosure | settings.local.json permissions | accept | File is machine-local permissions allow-list (not secrets); already readable locally |
| T-quick-03 | Denial of Service | deindexing a shared config | mitigate | Pre-deindex dependency check confirms no active code/config references these paths |
</threat_model>

<verification>
1. `git ls-files --stage .claude/settings.local.json .claude/worktrees` returns 0 lines
2. `test -f .claude/settings.local.json` succeeds (file on disk)
3. `test -d .claude/worktrees` succeeds (directory on disk)
4. `git diff HEAD -- .gitignore` returns empty (no .gitignore edits)
5. `git status --short -- .claude` shows no unexpected changes beyond the deindex
6. Dev log exists at docs/dev_logs/2026-04-11_claude_local_state_deindex_pass.md
</verification>

<success_criteria>
- 15 confirmed-local paths removed from git index (1 settings file + 14 worktree gitlinks)
- All deindexed paths preserved on the local filesystem
- Zero filesystem deletions
- Zero .gitignore modifications
- Dev log documents the complete audit trail with pre/post snapshots
- Single clean commit with deindex + dev log
</success_criteria>

<output>
After completion, create `.planning/quick/260411-ime-safely-deindex-confirmed-local-claude-pa/260411-ime-SUMMARY.md`
</output>
