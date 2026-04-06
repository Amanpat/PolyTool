---
phase: quick-260406-nbe
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - claude.md
  - workflows/n8n/README.md
  - workflows/n8n/ris-academic-ingestion.json
  - workflows/n8n/ris-blog-ingestion.json
  - workflows/n8n/ris-github-ingestion.json
  - workflows/n8n/ris-health-monitor.json
  - workflows/n8n/ris-manual-ingest.json
  - workflows/n8n/ris-reddit-ingestion.json
  - workflows/n8n/ris-weekly-digest.json
  - workflows/n8n/ris-youtube-ingestion.json
  - docs/dev_logs/2026-04-05_n8n-workflows.md
  - docs/dev_logs/2026-04-06_ris_n8n_git_surface_cleanup.md
  - .planning/quick/260401-o1q-ris-phase-2-operator-feedback-loop-and-r/PLAN.md
  - .planning/quick/260401-o1q-ris-phase-2-operator-feedback-loop-and-r/SUMMARY.md
  - .planning/quick/260402-rm1-ris-phase-5-live-source-acquisition-adap/PLAN.md
  - .planning/quick/260402-rm1-ris-phase-5-live-source-acquisition-adap/SUMMARY.md
  - .planning/quick/260404-rtv-implement-a-scoped-ris-only-n8n-pilot/260404-rtv-PLAN.md
  - .planning/quick/260404-rtv-implement-a-scoped-ris-only-n8n-pilot/260404-rtv-SUMMARY.md
  - .planning/quick/260404-sb4-close-the-ris-n8n-pilot-to-roadmap-compl/260404-sb4-PLAN.md
  - .planning/quick/260404-sb4-close-the-ris-n8n-pilot-to-roadmap-compl/260404-sb4-SUMMARY.md
  - .planning/quick/260404-t5l-fix-ris-n8n-runtime-path-and-smoke-test-/260404-t5l-PLAN.md
  - .planning/quick/260404-t5l-fix-ris-n8n-runtime-path-and-smoke-test-/260404-t5l-SUMMARY.md
  - .planning/quick/260404-uav-ris-n8n-docs-reconciliation-fix-5-doc-dr/PLAN.md
  - .planning/quick/260404-uav-ris-n8n-docs-reconciliation-fix-5-doc-dr/SUMMARY.md
  - .planning/quick/260405-jyv-root-image-final-slimming-narrow-extras-/260405-jyv-PLAN.md
  - .planning/quick/260405-jyv-root-image-final-slimming-narrow-extras-/260405-jyv-SUMMARY.md
  - .planning/quick/260405-kpg-close-out-the-root-dockerfile-build-fix-/260405-kpg-PLAN.md
  - .planning/quick/260405-kpg-close-out-the-root-dockerfile-build-fix-/260405-kpg-SUMMARY.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "git status shows no untracked .planning/quick/26040* artifacts"
    - "git status shows no unstaged workflows/n8n/* deletions"
    - "git status shows no modified claude.md entry"
    - "No live (non-historical) references to workflows/n8n/ remain in committed files"
    - "Dev log documents every blocker and its resolution"
  artifacts:
    - path: "docs/dev_logs/2026-04-06_ris_n8n_git_surface_cleanup.md"
      provides: "Audit trail for all git surface cleanup decisions"
  key_links:
    - from: "scripts/smoke_ris_n8n.py"
      to: "workflows/n8n/ (deleted)"
      via: "asserts absence (PASS when missing)"
      pattern: "orphan-v2-removed.*PASS.*not present"
---

<objective>
Resolve the three categories of git surface blockers that prevent clean Phase N4 sign-off:
(1) unstaged `workflows/n8n/` deletions from the repo hardening session,
(2) modified lowercase `claude.md` carrying intentional N4 truth-doc edits,
(3) 8 untracked `.planning/quick/26040*` directories with generated PLAN/SUMMARY artifacts.

Purpose: Clean the working tree so only intentional, documented N4-related changes remain.
Nothing changes behavior -- this is staging, committing, and documenting what already happened.

Output: A single commit with all three blocker categories resolved, plus a dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md
@docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md
@scripts/smoke_ris_n8n.py (lines 180-189 -- asserts workflows/n8n/ absence)
@docs/runbooks/RIS_N8N_SMOKE_TEST.md (line 45 -- documents workflows/n8n/ should not exist)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Audit git surface, classify each blocker, and resolve all three categories</name>
  <files>
    claude.md
    workflows/n8n/README.md
    workflows/n8n/ris-academic-ingestion.json
    workflows/n8n/ris-blog-ingestion.json
    workflows/n8n/ris-github-ingestion.json
    workflows/n8n/ris-health-monitor.json
    workflows/n8n/ris-manual-ingest.json
    workflows/n8n/ris-reddit-ingestion.json
    workflows/n8n/ris-weekly-digest.json
    workflows/n8n/ris-youtube-ingestion.json
    .planning/quick/260401-o1q-ris-phase-2-operator-feedback-loop-and-r/PLAN.md
    .planning/quick/260401-o1q-ris-phase-2-operator-feedback-loop-and-r/SUMMARY.md
    .planning/quick/260402-rm1-ris-phase-5-live-source-acquisition-adap/PLAN.md
    .planning/quick/260402-rm1-ris-phase-5-live-source-acquisition-adap/SUMMARY.md
    .planning/quick/260404-rtv-implement-a-scoped-ris-only-n8n-pilot/260404-rtv-PLAN.md
    .planning/quick/260404-rtv-implement-a-scoped-ris-only-n8n-pilot/260404-rtv-SUMMARY.md
    .planning/quick/260404-sb4-close-the-ris-n8n-pilot-to-roadmap-compl/260404-sb4-PLAN.md
    .planning/quick/260404-sb4-close-the-ris-n8n-pilot-to-roadmap-compl/260404-sb4-SUMMARY.md
    .planning/quick/260404-t5l-fix-ris-n8n-runtime-path-and-smoke-test-/260404-t5l-PLAN.md
    .planning/quick/260404-t5l-fix-ris-n8n-runtime-path-and-smoke-test-/260404-t5l-SUMMARY.md
    .planning/quick/260404-uav-ris-n8n-docs-reconciliation-fix-5-doc-dr/PLAN.md
    .planning/quick/260404-uav-ris-n8n-docs-reconciliation-fix-5-doc-dr/SUMMARY.md
    .planning/quick/260405-jyv-root-image-final-slimming-narrow-extras-/260405-jyv-PLAN.md
    .planning/quick/260405-jyv-root-image-final-slimming-narrow-extras-/260405-jyv-SUMMARY.md
    .planning/quick/260405-kpg-close-out-the-root-dockerfile-build-fix-/260405-kpg-PLAN.md
    .planning/quick/260405-kpg-close-out-the-root-dockerfile-build-fix-/260405-kpg-SUMMARY.md
  </files>
  <action>
    Resolve all three git surface blocker categories. Do NOT touch `.claude/*`.

    **Blocker A: `workflows/n8n/*` -- 9 tracked deletions, unstaged**

    These files were deleted from disk by quick-260406-mno (repo hardening session) because
    they were an orphaned v2 set with wrong container name (`polytool-polytool-1`). The
    canonical workflows live at `infra/n8n/workflows/`. The smoke script
    (`scripts/smoke_ris_n8n.py` line 182-189) already asserts this directory should NOT exist.
    The runbook (`docs/runbooks/RIS_N8N_SMOKE_TEST.md` line 45) documents the same.

    Action: Stage the deletions with `git add workflows/n8n/`. This completes the intentional
    removal that was started in the hardening session.

    Reference check: Search committed files (excluding `.planning/`, `.claude/`, worktrees)
    for live references to `workflows/n8n/` that assume the directory EXISTS (not historical
    mentions or absence-assertions). The known references are:
    - `docs/runbooks/RIS_N8N_SMOKE_TEST.md:45` -- asserts absence (correct, no fix needed)
    - `scripts/smoke_ris_n8n.py:189` -- asserts absence (correct, no fix needed)
    - `docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md` -- historical (correct)
    - `docs/dev_logs/2026-04-05_n8n-workflows.md` -- historical dev log from the dead
      `feat/ws-clob-feed` branch describing what was built before it was consolidated and
      the v2 directory was deleted. This is historical record. However, it claims
      `workflows/n8n/` is the "new canonical location" which is now false.
      Add a 3-line header note to `docs/dev_logs/2026-04-05_n8n-workflows.md`:
      ```
      > **SUPERSEDED:** The `workflows/n8n/` directory described below was deleted on 2026-04-06
      > (quick-260406-mno). The canonical workflow location is `infra/n8n/workflows/`.
      > See `docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md`.
      ```
      Insert this blockquote immediately after the YAML-style header (after line 4, before
      "## What"). Do NOT change any other content in the file.

    **Blocker B: `claude.md` -- modified, unstaged**

    Git tracks the project instructions file as lowercase `claude.md` (original commit used
    that case). On Windows case-insensitive filesystem, the on-disk file shows as `CLAUDE.md`
    but git sees it as `claude.md`. The 2-line diff is the intentional N4 truth-doc edit from
    quick-260406-mnu (lines 38 and 116: n8n pilot qualification).

    Action: Stage the modification with `git add claude.md`. The case mismatch (lowercase in
    git index vs uppercase on disk) is a pre-existing Windows artifact and NOT a blocker to
    fix in this task. Attempting `git mv claude.md CLAUDE.md` on a case-insensitive FS is
    risky and outside scope. The content change is intentional and correct.

    **Blocker C: `.planning/quick/26040*` -- 8 untracked directories (16 files)**

    These are PLAN.md and SUMMARY.md pairs from completed quick-task sessions. The existing
    repo pattern tracks all `.planning/quick/` artifacts (50+ directories already committed).
    `.planning/` is NOT in `.gitignore`.

    Action: Stage all 8 directories with:
    ```
    git add .planning/quick/260401-o1q-ris-phase-2-operator-feedback-loop-and-r/
    git add .planning/quick/260402-rm1-ris-phase-5-live-source-acquisition-adap/
    git add .planning/quick/260404-rtv-implement-a-scoped-ris-only-n8n-pilot/
    git add .planning/quick/260404-sb4-close-the-ris-n8n-pilot-to-roadmap-compl/
    git add .planning/quick/260404-t5l-fix-ris-n8n-runtime-path-and-smoke-test-/
    git add .planning/quick/260404-uav-ris-n8n-docs-reconciliation-fix-5-doc-dr/
    git add .planning/quick/260405-jyv-root-image-final-slimming-narrow-extras-/
    git add .planning/quick/260405-kpg-close-out-the-root-dockerfile-build-fix-/
    ```
    This follows existing repo convention. These are execution records, not debris.

    **After staging all three categories**, run `git status --short` and confirm:
    - No `?? .planning/quick/26040*` entries remain
    - No ` D workflows/n8n/*` entries remain
    - No ` M claude.md` entry remains
    - The `.claude/*` entries are UNTOUCHED (still showing as modified/untracked -- that is
      correct and outside scope)
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && git status --porcelain -- claude.md workflows/ ".planning/quick/26040*" | grep -c "^[? D M]" || echo "0 -- all clean"</automated>
  </verify>
  <done>
    All three blocker categories are staged. `git status --porcelain` for `claude.md`,
    `workflows/`, and `.planning/quick/26040*` shows only staged (green) entries or nothing.
    No unstaged modifications, no untracked files, no unstaged deletions for these paths.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create dev log and commit all staged changes</name>
  <files>docs/dev_logs/2026-04-06_ris_n8n_git_surface_cleanup.md</files>
  <action>
    Create `docs/dev_logs/2026-04-06_ris_n8n_git_surface_cleanup.md` documenting every
    blocker found and the action taken. Use this structure:

    ```markdown
    # RIS n8n Git Surface Cleanup -- 2026-04-06

    **Quick task:** quick-260406-nbe
    **Branch:** main

    ## Purpose

    Resolve the three categories of git-surface blockers that Codex flagged during Phase N4
    sign-off review. All changes in this commit were already on disk from prior sessions --
    this task stages, commits, and documents them.

    ## Blockers Found and Actions Taken

    ### A. `workflows/n8n/*` -- 9 tracked deletions (unstaged)

    | File | Action | Why Safe |
    |------|--------|----------|
    | workflows/n8n/README.md | Staged deletion | Orphaned v2 dir, deleted by quick-260406-mno |
    | workflows/n8n/ris-academic-ingestion.json | Staged deletion | Same -- wrong container name |
    | workflows/n8n/ris-blog-ingestion.json | Staged deletion | Same |
    | workflows/n8n/ris-github-ingestion.json | Staged deletion | Same |
    | workflows/n8n/ris-health-monitor.json | Staged deletion | Same |
    | workflows/n8n/ris-manual-ingest.json | Staged deletion | Same |
    | workflows/n8n/ris-reddit-ingestion.json | Staged deletion | Same |
    | workflows/n8n/ris-weekly-digest.json | Staged deletion | Same |
    | workflows/n8n/ris-youtube-ingestion.json | Staged deletion | Same |

    Canonical location: `infra/n8n/workflows/` (per ADR-0013).
    Smoke script already asserts absence: `scripts/smoke_ris_n8n.py:189`.

    **Reference repair:** Added SUPERSEDED header to
    `docs/dev_logs/2026-04-05_n8n-workflows.md` (line 5) which previously claimed
    `workflows/n8n/` was the canonical location. No other live references found.

    ### B. `claude.md` -- modified (unstaged)

    | File | Action | Why Safe |
    |------|--------|----------|
    | claude.md (line 38) | Staged modification | Intentional N4 n8n pilot qualification (quick-260406-mnu) |
    | claude.md (line 116) | Staged modification | Same session, APScheduler default + pilot note |

    Note: Git tracks as lowercase `claude.md` (original commit case). On-disk file is
    `CLAUDE.md`. This is a pre-existing Windows case-insensitive FS artifact. NOT fixed
    in this task -- renaming via git on case-insensitive FS is fragile and out of scope.

    ### C. `.planning/quick/26040*` -- 8 untracked directories (16 files)

    | Directory | Contents | Action | Why Safe |
    |-----------|----------|--------|----------|
    | 260401-o1q-... | PLAN.md, SUMMARY.md | Tracked (git add) | Follows existing convention |
    | 260402-rm1-... | PLAN.md, SUMMARY.md | Tracked (git add) | Same |
    | 260404-rtv-... | PLAN.md, SUMMARY.md | Tracked (git add) | Same |
    | 260404-sb4-... | PLAN.md, SUMMARY.md | Tracked (git add) | Same |
    | 260404-t5l-... | PLAN.md, SUMMARY.md | Tracked (git add) | Same |
    | 260404-uav-... | PLAN.md, SUMMARY.md | Tracked (git add) | Same |
    | 260405-jyv-... | PLAN.md, SUMMARY.md | Tracked (git add) | Same |
    | 260405-kpg-... | PLAN.md, SUMMARY.md | Tracked (git add) | Same |

    50+ other `.planning/quick/` directories are already tracked. These 8 were simply
    never git-added after their sessions completed.

    ## Reference Search for `workflows/n8n`

    Searched all committed files (excluding `.planning/`, `.claude/`, `.claude/worktrees/`)
    for references to `workflows/n8n/`:

    | File | Line | Type | Action |
    |------|------|------|--------|
    | scripts/smoke_ris_n8n.py | 189 | Asserts absence | None needed |
    | docs/runbooks/RIS_N8N_SMOKE_TEST.md | 45 | Asserts absence | None needed |
    | docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md | 12,34,35,40,65 | Historical audit | None needed |
    | docs/dev_logs/2026-04-05_n8n-workflows.md | 10,42-50,55 | Historical but claimed canonical | Added SUPERSEDED note |

    ## Remaining Non-N4 Dirt

    The `.claude/*` directory has ~150+ modified/deleted/untracked entries from a GSD
    framework update. These are OUTSIDE SCOPE per task constraints ("Do not touch .claude/*").
    They will be addressed separately.

    ## Verification Commands

    ```
    git status --short -- claude.md workflows/ ".planning/quick/26040*"
    # Expected: only staged (A/D/M in col 1) entries, no unstaged or untracked
    ```

    ## Codex Review

    Tier: Skip (git staging, dev log, no strategy/execution/risk code changed).
    ```

    Then stage the dev log and commit everything in a single commit:

    ```bash
    git add docs/dev_logs/2026-04-06_ris_n8n_git_surface_cleanup.md
    git add docs/dev_logs/2026-04-05_n8n-workflows.md
    git commit -m "docs(quick-260406-nbe): resolve git-surface blockers for Phase N4 sign-off

    - Stage workflows/n8n/ deletion (9 files, orphaned v2 set from quick-260406-mno)
    - Stage claude.md modification (N4 truth-doc edits from quick-260406-mnu)
    - Track 8 untracked .planning/quick/26040* session artifacts (16 files)
    - Add SUPERSEDED note to 2026-04-05_n8n-workflows.md dev log
    - Create cleanup audit dev log

    Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
    ```

    After commit, run `git status --short` to confirm the three blocker categories
    no longer appear as dirty. The `.claude/*` entries will still be present -- that
    is expected and out of scope.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && git status --porcelain -- claude.md workflows/ ".planning/quick/26040*" 2>/dev/null | wc -l</automated>
  </verify>
  <done>
    Single commit created. `git status` for `claude.md`, `workflows/`, and
    `.planning/quick/26040*` returns 0 dirty entries. Dev log exists at
    `docs/dev_logs/2026-04-06_ris_n8n_git_surface_cleanup.md` documenting
    every blocker, action, and safety rationale.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries crossed. This task stages and commits already-existing local changes.
No network, no external services, no runtime behavior changes.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-nbe-01 | Tampering | claude.md content | accept | Diff is 2 lines, both verified as intentional N4 edits from quick-260406-mnu |
| T-nbe-02 | Information Disclosure | .planning/quick/ artifacts | accept | Planning artifacts contain no secrets; same pattern as 50+ already-tracked dirs |
</threat_model>

<verification>
After both tasks complete:
1. `git status --short -- claude.md workflows/ ".planning/quick/26040*"` returns empty
2. `git log -1 --oneline` shows the cleanup commit
3. `python scripts/smoke_ris_n8n.py` still passes (workflows/n8n/ absence check)
4. No `.claude/*` files were touched
</verification>

<success_criteria>
- Zero unstaged/untracked entries for claude.md, workflows/n8n/, and .planning/quick/26040*
- Dev log at docs/dev_logs/2026-04-06_ris_n8n_git_surface_cleanup.md with full audit trail
- Smoke script still passes
- .claude/* directory completely untouched
</success_criteria>

<output>
After completion, create `.planning/quick/260406-nbe-resolve-git-surface-blockers-for-phase-n/260406-nbe-SUMMARY.md`
</output>
