---
phase: quick-260409-khd
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - infra/n8n/workflows/ris-unified-dev.json
  - infra/n8n/workflows/ris-health-webhook.json
  - infra/n8n/workflows/workflow_ids.env
  - infra/n8n/import_workflows.py
  - infra/n8n/README.md
  - scripts/smoke_ris_n8n.py
  - workflows/n8n/README.md
  - docs/RIS_OPERATOR_GUIDE.md
  - docs/CURRENT_STATE.md
  - docs/adr/0013-ris-n8n-pilot-scoped.md
  - docs/runbooks/RIS_N8N_SMOKE_TEST.md
  - docs/dev_logs/2026-04-09_n8n_workflow_location_migration.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "infra/n8n/workflows/ is the single canonical source for active n8n workflow JSON"
    - "import_workflows.py reads workflow JSON from infra/n8n/workflows/"
    - "No active workflow JSON remains in workflows/n8n/"
    - "All operator docs point to infra/n8n/workflows/ as the canonical location"
    - "smoke_ris_n8n.py validates infra/n8n/workflows/ and expects the active canonical files there"
    - "Legacy/superseded JSON files are deleted, not duplicated"
  artifacts:
    - path: "infra/n8n/workflows/ris-unified-dev.json"
      provides: "Canonical unified RIS workflow"
    - path: "infra/n8n/workflows/ris-health-webhook.json"
      provides: "Canonical health webhook workflow"
    - path: "infra/n8n/workflows/workflow_ids.env"
      provides: "Deployed workflow ID tracking"
    - path: "docs/dev_logs/2026-04-09_n8n_workflow_location_migration.md"
      provides: "Migration audit trail"
  key_links:
    - from: "infra/n8n/import_workflows.py"
      to: "infra/n8n/workflows/"
      via: "WORKFLOW_DIR constant"
      pattern: 'WORKFLOW_DIR.*=.*infra.*n8n.*workflows'
    - from: "scripts/smoke_ris_n8n.py"
      to: "infra/n8n/workflows/"
      via: "WORKFLOW_DIR constant"
      pattern: 'WORKFLOW_DIR.*=.*infra.*n8n.*workflows'
---

<objective>
Migrate the canonical n8n workflow JSON source from `workflows/n8n/` to `infra/n8n/workflows/`,
eliminating dual-canonical ambiguity. After this plan, `infra/n8n/workflows/` is the single
source of truth for active workflow JSON, and all import tooling, smoke scripts, and operator
docs point there consistently.

Purpose: The repo currently has workflow JSON split across two directories (`workflows/n8n/`
and `infra/n8n/workflows/`) with confusing "legacy" labels on both depending on which doc
you read. The Codex migration safety test (2026-04-08 dev log) patched operator-facing docs
but left code paths and status docs unpatched. This plan finishes the migration.

Output: Single canonical workflow location at `infra/n8n/workflows/`, updated tooling,
updated docs, stub README at old location, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/dev_logs/2026-04-08_n8n_operator_path_cleanup.md
@infra/n8n/import_workflows.py
@scripts/smoke_ris_n8n.py
@infra/n8n/README.md
@workflows/n8n/README.md
@docs/RIS_OPERATOR_GUIDE.md
@docs/adr/0013-ris-n8n-pilot-scoped.md
@docs/runbooks/RIS_N8N_SMOKE_TEST.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Move active workflow JSON and delete all legacy/superseded files</name>
  <files>
    infra/n8n/workflows/ris-unified-dev.json
    infra/n8n/workflows/ris-health-webhook.json
    infra/n8n/workflows/workflow_ids.env
    workflows/n8n/ris-unified-dev.json (deleted)
    workflows/n8n/ris-health-webhook.json (deleted)
    workflows/n8n/workflow_ids.env (deleted)
    workflows/n8n/ris_orchestrator.json (deleted)
    workflows/n8n/ris_global_error_watcher.json (deleted)
    workflows/n8n/ris_sub_academic.json (deleted)
    workflows/n8n/ris_sub_blog_rss.json (deleted)
    workflows/n8n/ris_sub_freshness_refresh.json (deleted)
    workflows/n8n/ris_sub_github.json (deleted)
    workflows/n8n/ris_sub_reddit.json (deleted)
    workflows/n8n/ris_sub_weekly_digest.json (deleted)
    workflows/n8n/ris_sub_youtube.json (deleted)
    infra/n8n/workflows/ris_academic_ingest.json (deleted)
    infra/n8n/workflows/ris_blog_ingest.json (deleted)
    infra/n8n/workflows/ris_freshness_refresh.json (deleted)
    infra/n8n/workflows/ris_github_ingest.json (deleted)
    infra/n8n/workflows/ris_health_check.json (deleted)
    infra/n8n/workflows/ris_manual_acquire.json (deleted)
    infra/n8n/workflows/ris_reddit_others.json (deleted)
    infra/n8n/workflows/ris_reddit_polymarket.json (deleted)
    infra/n8n/workflows/ris_scheduler_status.json (deleted)
    infra/n8n/workflows/ris_weekly_digest.json (deleted)
    infra/n8n/workflows/ris_youtube_ingest.json (deleted)
    workflows/n8n/README.md (replaced with stub)
  </files>
  <action>
    1. Delete ALL 11 legacy JSON files currently in `infra/n8n/workflows/` (the initial pilot
       templates: ris_academic_ingest.json, ris_blog_ingest.json, ris_freshness_refresh.json,
       ris_github_ingest.json, ris_health_check.json, ris_manual_acquire.json,
       ris_reddit_others.json, ris_reddit_polymarket.json, ris_scheduler_status.json,
       ris_weekly_digest.json, ris_youtube_ingest.json). These are fully superseded by the
       unified workflow and have been "legacy/reference-only" since 2026-04-07.

    2. Copy the 2 active canonical JSON files from `workflows/n8n/` into `infra/n8n/workflows/`:
       - `ris-unified-dev.json`
       - `ris-health-webhook.json`
       Also copy `workflow_ids.env`.

    3. Delete ALL JSON files from `workflows/n8n/` (both the 2 active files just copied and
       the 7 legacy multi-workflow rebuild files: ris_orchestrator.json,
       ris_global_error_watcher.json, ris_sub_academic.json, ris_sub_blog_rss.json,
       ris_sub_freshness_refresh.json, ris_sub_github.json, ris_sub_reddit.json,
       ris_sub_weekly_digest.json, ris_sub_youtube.json).
       Also delete `workflow_ids.env` from `workflows/n8n/`.

    4. Replace `workflows/n8n/README.md` with a short stub:
       ```
       # workflows/n8n/ -- MOVED

       Canonical n8n workflow source has moved to `infra/n8n/workflows/`.

       See `infra/n8n/README.md` for the operator quickstart and workflow layout.

       This directory is retained as a stub to prevent broken links. No workflow
       JSON files live here anymore.
       ```

    5. Verify the moved files are byte-identical to the originals using a diff or checksum.

    Use `git mv` where possible (for the active files) to preserve history, then `git rm`
    for the legacy files. If `git mv` from `workflows/n8n/` to `infra/n8n/workflows/`
    encounters conflicts with existing legacy files in the target, delete the legacy files
    first, then move.
  </action>
  <verify>
    <automated>ls infra/n8n/workflows/*.json && ls infra/n8n/workflows/workflow_ids.env && python -c "import json; [json.load(open(f'infra/n8n/workflows/{f}')) for f in ['ris-unified-dev.json','ris-health-webhook.json']]; print('JSON valid')" && test ! -f workflows/n8n/ris-unified-dev.json && echo "Old location cleaned" && test -f workflows/n8n/README.md && echo "Stub README exists"</automated>
  </verify>
  <done>
    - `infra/n8n/workflows/` contains exactly: ris-unified-dev.json, ris-health-webhook.json, workflow_ids.env
    - `workflows/n8n/` contains only the stub README.md (no JSON, no .env)
    - All legacy JSON files from both directories are deleted
    - JSON files in new location parse successfully
  </done>
</task>

<task type="auto">
  <name>Task 2: Update import tooling, smoke script, and all operator docs</name>
  <files>
    infra/n8n/import_workflows.py
    scripts/smoke_ris_n8n.py
    infra/n8n/README.md
    docs/RIS_OPERATOR_GUIDE.md
    docs/CURRENT_STATE.md
    docs/adr/0013-ris-n8n-pilot-scoped.md
    docs/runbooks/RIS_N8N_SMOKE_TEST.md
    docs/dev_logs/2026-04-09_n8n_workflow_location_migration.md
  </files>
  <action>
    **A. Update `infra/n8n/import_workflows.py`:**
    - Change line 19 from `WORKFLOW_DIR = ROOT_DIR / "workflows" / "n8n"` to
      `WORKFLOW_DIR = ROOT_DIR / "infra" / "n8n" / "workflows"`
    - Change line 20 from `WORKFLOW_IDS_PATH = WORKFLOW_DIR / "workflow_ids.env"` --
      this will now automatically resolve to `infra/n8n/workflows/workflow_ids.env` (correct).
    - Update the comment in `write_workflow_ids()` line 67 from
      `"# Canonical import file: workflows/n8n/ris-unified-dev.json"` to
      `"# Canonical import file: infra/n8n/workflows/ris-unified-dev.json"`

    **B. Update `scripts/smoke_ris_n8n.py`:**
    - Line 37: `WORKFLOW_DIR` already points to `REPO_ROOT / "infra" / "n8n" / "workflows"` (correct).
    - Line 38: Change `ORPHAN_DIR = REPO_ROOT / "workflows" / "n8n"` -- keep this variable
      but update the check at lines 182-189: instead of checking that `workflows/n8n/` does not
      exist at all (which would fail because the stub README remains), change the orphan check
      to verify that no JSON files remain in `workflows/n8n/`:
      ```python
      orphan_jsons = list(ORPHAN_DIR.glob("*.json")) if ORPHAN_DIR.exists() else []
      if orphan_jsons:
          check("orphan-json-removed", "FAIL",
                f"{len(orphan_jsons)} JSON file(s) still in {ORPHAN_DIR}")
      else:
          check("orphan-json-removed", "PASS", "No workflow JSON in workflows/n8n/")
      ```
    - The smoke script now validates the **canonical** location (infra/n8n/workflows/) which
      contains the 2 active files. It should find and PASS on ris-unified-dev.json and
      ris-health-webhook.json.

    **C. Update `infra/n8n/README.md`:**
    - In the "Operator Quickstart" notes section (around line 65), change
      `Canonical workflow source: \`workflows/n8n/ris-unified-dev.json\`` to
      `Canonical workflow source: \`infra/n8n/workflows/ris-unified-dev.json\``
    - Same for `ris-health-webhook.json` reference on the next line.
    - In the "Workflow Source Layout" section (lines 74-94), rewrite the table:
      - `infra/n8n/workflows/ris-unified-dev.json` = Active canonical source
      - `infra/n8n/workflows/ris-health-webhook.json` = Active canonical support workflow
      - `infra/n8n/workflows/workflow_ids.env` = Active metadata
      - `workflows/n8n/` = Stub redirect only (no JSON files)
      - Remove the `Other workflows/n8n/*.json` and `infra/n8n/workflows/*.json` legacy rows
    - Update text below the table that references `workflows/n8n/ris-unified-dev.json` to
      `infra/n8n/workflows/ris-unified-dev.json`.
    - Update the alert setup note about the importer injecting webhook URL to reference
      `infra/n8n/workflows/ris-unified-dev.json`.

    **D. Update `docs/RIS_OPERATOR_GUIDE.md`:**
    - In the "n8n RIS Pilot" section, step 5 (around line 660-666): change
      `workflows/n8n/ris-unified-dev.json` to `infra/n8n/workflows/ris-unified-dev.json`
      and `workflows/n8n/ris-health-webhook.json` to `infra/n8n/workflows/ris-health-webhook.json`
      and `workflows/n8n/workflow_ids.env` to `infra/n8n/workflows/workflow_ids.env`.
    - Same for the "Unified Workflow Sections" subsection (around line 720) where it says
      `workflows/n8n/ris-unified-dev.json`.
    - The line about `infra/n8n/workflows/*.json` being legacy reference-only should be updated
      to say `workflows/n8n/` is a stub redirect only.
    - Around line 736: change "Historical multi-file JSONs in `workflows/n8n/*.json` and
      `infra/n8n/workflows/*.json`" to "Historical multi-file JSONs have been deleted.
      `workflows/n8n/` contains only a stub README redirecting to `infra/n8n/workflows/`."

    **E. Update `docs/CURRENT_STATE.md`:**
    - Find the "RIS n8n Pilot Roadmap Complete" section (around line 1490-1498).
    - Change `workflows/n8n/ris-unified-dev.json` to `infra/n8n/workflows/ris-unified-dev.json`.
    - Change `bash infra/n8n/import-workflows.sh` to `python infra/n8n/import_workflows.py`.
    - Change "which now reads from `workflows/n8n`" to "which reads from `infra/n8n/workflows/`".
    - Change "`infra/n8n/workflows/` is retained as legacy reference only" to
      "`workflows/n8n/` is a stub redirect only; all active JSON lives in `infra/n8n/workflows/`".

    **F. Update `docs/adr/0013-ris-n8n-pilot-scoped.md`:**
    - In the "Workflow sources" subsection (around line 113): change
      `workflows/n8n/ris-unified-dev.json` to `infra/n8n/workflows/ris-unified-dev.json`.
    - Change `bash infra/n8n/import-workflows.sh [container_name]` to
      `python infra/n8n/import_workflows.py`.
    - Update the legacy references note at the bottom of that section: replace
      `workflows/n8n/*.json from the superseded multi-workflow rebuild` with
      "Legacy JSONs have been deleted from both `workflows/n8n/` and `infra/n8n/workflows/`."
    - Keep `infra/n8n/` for Docker/image/tooling statement, but clarify that
      `infra/n8n/workflows/` now also holds the canonical active workflow JSON.

    **G. Update `docs/runbooks/RIS_N8N_SMOKE_TEST.md`:**
    - Around line 9: change `workflows/n8n/ris-unified-dev.json` to
      `infra/n8n/workflows/ris-unified-dev.json`.
    - Around lines 55-57: update the three `workflows/n8n/` references to `infra/n8n/workflows/`.
    - Around line 139: update the README reference from `workflows/n8n/README.md` to
      `infra/n8n/README.md` (the real workflow docs live there, not in the stub).

    **H. Create dev log `docs/dev_logs/2026-04-09_n8n_workflow_location_migration.md`:**
    Write a dev log covering:
    - Objective: eliminate dual-canonical ambiguity for n8n workflow JSON
    - Files changed table (file | why)
    - Commands run + output (git mv, git rm, verification diffs)
    - Test results (import_workflows.py --help, smoke_ris_n8n.py, JSON parse check)
    - Final canonical folder: `infra/n8n/workflows/`
    - Files deleted: list all 18 legacy JSON files removed (11 from infra/n8n/workflows/ + 7 from workflows/n8n/)
    - Files moved: 2 active JSON + workflow_ids.env from workflows/n8n/ to infra/n8n/workflows/
    - Remaining legacy references: note any that were intentionally left (e.g., git history)
  </action>
  <verify>
    <automated>python infra/n8n/import_workflows.py --help && python scripts/smoke_ris_n8n.py 2>&1 | tail -20 && rtk git grep -c "workflows/n8n/ris-unified-dev" -- "*.py" "*.md" | grep -v ".planning/" | grep -v "dev_logs/" | grep -v ".claude/"</automated>
  </verify>
  <done>
    - `python infra/n8n/import_workflows.py --help` exits 0 and references the correct import path
    - `python scripts/smoke_ris_n8n.py` passes all checks (workflow-files-exist, JSON parse, container references, orphan-json-removed)
    - No active operator docs (outside dev_logs and .planning) reference `workflows/n8n/ris-unified-dev.json` as the canonical source
    - Dev log exists at docs/dev_logs/2026-04-09_n8n_workflow_location_migration.md with all required sections
    - `docs/CURRENT_STATE.md` and `docs/adr/0013-ris-n8n-pilot-scoped.md` are updated (the two docs the 04-08 cleanup intentionally skipped)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No new trust boundaries introduced. This is a file relocation and doc update -- no runtime
behavior changes, no new endpoints, no credential handling changes.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-khd-01 | T (Tampering) | Workflow JSON during move | accept | git mv preserves history; byte-identical verification in Task 1 |
| T-khd-02 | I (Info Disclosure) | workflow_ids.env relocation | accept | Contains n8n-internal IDs only (not secrets); same gitignore behavior |
</threat_model>

<verification>
1. `ls infra/n8n/workflows/` shows exactly: ris-unified-dev.json, ris-health-webhook.json, workflow_ids.env
2. `ls workflows/n8n/` shows exactly: README.md (stub only)
3. `python infra/n8n/import_workflows.py --help` exits 0
4. `python scripts/smoke_ris_n8n.py` exits 0 with all PASS (or SKIP for docker)
5. `git grep "workflows/n8n/ris-unified-dev" -- "*.py" "*.md"` returns only: dev_logs, .planning, and the stub README (no active operator docs)
</verification>

<success_criteria>
- Single canonical source: `infra/n8n/workflows/` contains the 2 active workflow JSON files and workflow_ids.env
- No active workflow JSON in `workflows/n8n/` (only stub README)
- All 18 legacy/superseded JSON files deleted from both directories
- Import tooling (`import_workflows.py`) reads from `infra/n8n/workflows/`
- Smoke script (`smoke_ris_n8n.py`) validates `infra/n8n/workflows/` and passes
- All operator docs (`infra/n8n/README.md`, `docs/RIS_OPERATOR_GUIDE.md`, `docs/CURRENT_STATE.md`, `docs/adr/0013-ris-n8n-pilot-scoped.md`, `docs/runbooks/RIS_N8N_SMOKE_TEST.md`) point to `infra/n8n/workflows/`
- Dev log created with full migration audit trail
</success_criteria>

<output>
After completion, create `.planning/quick/260409-khd-migrate-canonical-n8n-workflow-source-in/260409-khd-SUMMARY.md`
</output>
