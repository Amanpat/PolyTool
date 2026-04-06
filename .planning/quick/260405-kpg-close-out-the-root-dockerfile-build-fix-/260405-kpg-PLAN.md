---
phase: quick-260405-kpg
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/dev_logs/2026-04-05_root_dockerfile_build_fix_closeout.md
  - docs/CURRENT_STATE.md
autonomous: true
requirements:
  - verify-default-compose-build
must_haves:
  truths:
    - "docker compose build completes with exit 0 for the default stack (api + ris-scheduler)"
    - "python -m polytool --help runs without import errors inside the built ris-scheduler image"
    - "CURRENT_STATE.md reflects the layer-order fix and full default-stack verification"
    - "A dev log records the exact commands run and their pass/fail result"
  artifacts:
    - path: "docs/dev_logs/2026-04-05_root_dockerfile_build_fix_closeout.md"
      provides: "Close-out dev log with build output and verification result"
    - path: "docs/CURRENT_STATE.md"
      provides: "Updated infrastructure section noting the layer-order fix is verified"
  key_links:
    - from: "Dockerfile (stub RUN layer)"
      to: "docker compose build ris-scheduler"
      via: "BuildKit multi-stage build"
      pattern: "BUILD EXIT: 0"
---

<objective>
Verify the full default-compose stack builds cleanly after the root Dockerfile layer-order fix
(quick-260405-kh2), then record the result and close out the task.

Purpose: quick-260405-kh2 only built the ris-scheduler service in isolation. The default
compose stack also builds the `api` service (services/api/Dockerfile). A full
`docker compose build` (no profile flags) exercises both buildable services in one shot
and confirms nothing regressed. This is a verification + documentation task only.

Output:
- Verified build pass/fail for the default compose stack
- Dev log recording exact commands, output, and result
- CURRENT_STATE.md updated with one bullet for the layer-order fix verification
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-05_fix-root-dockerfile-layer-order.md

<!-- Default compose stack (no profile) builds two images:
     - api        → services/api/Dockerfile (no layer-order change; already verified in quick-260405-gef)
     - ris-scheduler → Dockerfile (the fixed layer-order file)
     clickhouse, grafana, migrate use pre-built images (no build step)
     polytool, pair-bot-*, n8n are profile-gated (excluded from default build) -->
</context>

<tasks>

<task type="auto">
  <name>Task 1: Run full default-compose build and python --help smoke test</name>
  <files>docs/dev_logs/2026-04-05_root_dockerfile_build_fix_closeout.md</files>
  <action>
Run the following commands in order and capture the exact output for the dev log:

1. Verify compose config is clean:
   ```
   rtk docker compose config --quiet
   ```
   Expected: exit 0, no errors.

2. Build the default stack (no profile flags):
   ```
   rtk docker compose build
   ```
   This builds: `api` (services/api/Dockerfile) and `ris-scheduler` (Dockerfile).
   Expected: exit 0, both services show "Built" or "CACHED".

3. Smoke-test the ris-scheduler image:
   ```
   docker compose run --rm --no-deps ris-scheduler python -m polytool --help
   ```
   Expected: exit 0, help text printed, no import errors.

If all three exit 0, create the dev log at:
  docs/dev_logs/2026-04-05_root_dockerfile_build_fix_closeout.md

Dev log content:
- Date: 2026-04-05
- Task: quick-260405-kpg
- Branch: feat/ws-clob-feed
- Summary: "Close out root Dockerfile layer-order fix — full default-compose verification"
- Context section: reference quick-260405-kh2 as the prior fix task; note this task is
  verification-only (no code changes)
- Commands run: exact commands from steps 1-3 above
- Output (abbreviated): key lines from build output (stage numbers, timings, "Built"/"CACHED")
  and the --help exit code
- Result: PASS (all 3 exit 0) or FAIL (describe the new error exactly)
- Files changed: none (verification-only) OR list any file if a new concrete error required a fix
- Codex review: tier skip (verification + docs only, no execution logic)

If step 2 fails with a NEW concrete error (not the layer-order bug that was already fixed):
- Record the exact error in the dev log
- If the error is in the root Dockerfile: apply the minimal targeted fix, then re-run step 2
- Do NOT make speculative or optimization changes; fix only the concrete failure
  </action>
  <verify>
    <automated>rtk docker compose build && docker compose run --rm --no-deps ris-scheduler python -m polytool --help</automated>
  </verify>
  <done>
    docker compose build exits 0 (both api and ris-scheduler built or cached);
    python -m polytool --help exits 0 inside the ris-scheduler container;
    dev log exists at docs/dev_logs/2026-04-05_root_dockerfile_build_fix_closeout.md
  </done>
</task>

<task type="auto">
  <name>Task 2: Update CURRENT_STATE.md and commit</name>
  <files>docs/CURRENT_STATE.md</files>
  <action>
Add a single bullet to the "Infrastructure Fixes" section of docs/CURRENT_STATE.md
(immediately after the existing ris-scheduler / root Dockerfile layer-order bullets).

Bullet text (adapt if build result was PASS):

```
- **Root Dockerfile layer-order fix verified (quick-260405-kpg, 2026-04-05)**:
  Full default-compose build (`docker compose build`) passes with exit 0 after the
  stub-RUN layer fix from quick-260405-kh2. Both `api` and `ris-scheduler` services
  build cleanly. `python -m polytool --help` exits 0 inside the ris-scheduler container.
  Dev log: `docs/dev_logs/2026-04-05_root_dockerfile_build_fix_closeout.md`.
```

If the build produced a new error that required a code fix, adjust the bullet to describe
what was fixed and what file was changed.

Then commit:
  rtk git add docs/dev_logs/2026-04-05_root_dockerfile_build_fix_closeout.md docs/CURRENT_STATE.md
  rtk git commit -m "docs(quick-260405-kpg): close out root Dockerfile build-fix — full default-compose verified"

If a Dockerfile fix was required, include the changed file in the git add command.
  </action>
  <verify>
    <automated>rtk git log --oneline -3</automated>
  </verify>
  <done>
    CURRENT_STATE.md has a bullet for the quick-260405-kpg close-out;
    commit appears in git log with the correct message
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| docker build context | Only pre-committed source enters the build image; no secrets in layers |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-kpg-01 | Information Disclosure | Dockerfile stub layer | accept | Stub __init__.py files contain no code or secrets; overwritten by real COPY layers |
| T-kpg-02 | Tampering | docker compose run --rm | accept | --no-deps and --rm ensure no persistent state change; read-only verification only |
</threat_model>

<verification>
All three verification commands must exit 0:
1. `rtk docker compose config --quiet` — compose YAML is valid
2. `rtk docker compose build` — both buildable default-stack services succeed
3. `docker compose run --rm --no-deps ris-scheduler python -m polytool --help` — CLI loads

Dev log and CURRENT_STATE.md update are committed to git.
</verification>

<success_criteria>
- docker compose build exits 0 with no errors for the default stack
- python -m polytool --help exits 0 inside the ris-scheduler image
- docs/dev_logs/2026-04-05_root_dockerfile_build_fix_closeout.md exists with commands + result
- CURRENT_STATE.md has a close-out bullet for quick-260405-kpg
- All changes committed; no test regressions (no code changes expected so no test run needed
  unless a Dockerfile fix was applied, in which case run: rtk vitest run OR
  python -m pytest tests/ -x -q --tb=short to confirm 0 regressions)
</success_criteria>

<output>
After completion, create `.planning/quick/260405-kpg-close-out-the-root-dockerfile-build-fix-/260405-kpg-SUMMARY.md`
</output>
