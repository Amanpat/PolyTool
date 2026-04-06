---
phase: quick-260404-uav
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/RIS_OPERATOR_GUIDE.md
  - docs/CURRENT_STATE.md
  - docs/adr/0013-ris-n8n-pilot-scoped.md
  - docs/dev_logs/2026-04-05_ris_n8n_docs_reconcile.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "RIS_OPERATOR_GUIDE.md Last verified date reads 2026-04-05"
    - "import-workflows.sh step in the guide no longer claims it needs curl/jq and no longer describes a REST/basic-auth approach; it accurately describes the docker exec CLI path"
    - "Scheduled Job Workflows runtime verification note says workflows ARE verified, not that they have NOT been verified"
    - "python-on-n8n-PATH warning is replaced with an explanation of the docker-exec bridge pattern"
    - "MCP server start command reads `python -m polytool mcp` (no --port flag, no mcp-server suffix)"
    - "A dev log exists at docs/dev_logs/2026-04-05_ris_n8n_docs_reconcile.md"
  artifacts:
    - path: "docs/RIS_OPERATOR_GUIDE.md"
      provides: "Updated operator guide with all 5 drift fixes applied"
    - path: "docs/dev_logs/2026-04-05_ris_n8n_docs_reconcile.md"
      provides: "Closeout record of changes made and why"
  key_links:
    - from: "docs/RIS_OPERATOR_GUIDE.md"
      to: "infra/n8n/import-workflows.sh"
      via: "import step description"
      pattern: "docker exec.*n8n import:workflow"
    - from: "docs/RIS_OPERATOR_GUIDE.md"
      to: "python -m polytool mcp"
      via: "MCP server start command"
      pattern: "python -m polytool mcp$"
---

<objective>
Fix five documentation drifts in the RIS n8n pilot docs so that the operator guide,
ADR 0013, and CURRENT_STATE.md exactly match the shipped runtime path, manual steps,
and current CLI names established by quick-260404-t5l (runtime fix and smoke test).

Purpose: The runtime is already correct and smoke-tested (11/11 import pass,
docker exec bridge confirmed). This work closes the gap between what the docs say
and what is actually true, so operators following the guide get working results on
first attempt.

Output: Updated docs/RIS_OPERATOR_GUIDE.md (5 drift fixes), no-change-needed
confirmation or minor tightening for ADR 0013 and CURRENT_STATE.md, and a closeout
dev log.
</objective>

<execution_context>
Docs-only task. No code changes. Each task specifies the exact lines/sections to edit
and what the replacement text must say. Verify by reading the file after editing.
</execution_context>

<context>
@docs/RIS_OPERATOR_GUIDE.md
@docs/adr/0013-ris-n8n-pilot-scoped.md
@docs/CURRENT_STATE.md
@infra/n8n/import-workflows.sh
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix RIS_OPERATOR_GUIDE.md — drifts 1, 2, 3, 4, 5</name>
  <files>docs/RIS_OPERATOR_GUIDE.md</files>
  <action>
Apply all five drifts to docs/RIS_OPERATOR_GUIDE.md. Make only the changes described
below; do not rewrite surrounding prose or change anything else.

**Drift 1 — Last verified date (line 3)**
Change:
  `Last verified: 2026-04-04`
To:
  `Last verified: 2026-04-05`

**Drift 2 — import-workflows.sh usage note (step 5 of Start / import / activate)**
The current step 5 reads:
```
5. Import workflow templates:
   ```bash
   bash infra/n8n/import-workflows.sh
   ```
   Requires `curl` and `jq`. Pass alternative URL/user/pass as positional args if needed.
```

Replace with:
```
5. Import workflow templates:
   ```bash
   bash infra/n8n/import-workflows.sh
   ```
   The script uses `docker exec polytool-n8n n8n import:workflow --input=<file>` (no
   curl or REST API required). Pass an alternative container name as the first positional
   arg if you renamed the container.
```

The old annotation claimed curl/jq were required and implied a REST/basic-auth path.
The actual script (as of quick-260404-t5l) uses `docker cp` + `docker exec n8n import:workflow`.

**Drift 3 — Runtime verification note (Scheduled Job Workflows section)**
The current runtime verification note reads:
```
**Runtime verification note:** These workflows have NOT been runtime-verified against a
live n8n instance. Template import and activation was verified via `docker compose config`
and CLI help checks only. Runtime verification requires Docker and a running n8n container
(`bash scripts/docker-start.sh --with-n8n`).
```

Replace with:
```
**Runtime verification note:** These workflows ARE runtime-verified as of quick-260404-t5l
(2026-04-05). Smoke test results: build OK, docker-cli v27.3.1 confirmed inside n8n
container, exec bridge to `polytool-ris-scheduler` verified (research-health output
received), 11/11 workflows imported successfully via `bash infra/n8n/import-workflows.sh`.
```

**Drift 4 — python-on-n8n-PATH warning (Manual verification / troubleshooting block)**
The current troubleshooting block inside the Manual verification section reads:
```
  - `python` not found on PATH inside the container: ensure the workflow is running
    in the polytool container environment, or adjust the command to use the full path.
```

Replace that bullet with:
```
  - `python` not found: this is expected if the command runs directly in the n8n
    container. All workflow commands use the docker-exec bridge pattern:
    `docker exec polytool-ris-scheduler python -m polytool ...`. If a command is
    missing the `docker exec polytool-ris-scheduler` prefix, add it.
```

The old warning was written before the docker-beside-docker pattern was established.
Operators hitting this error need to know the correct pattern, not a vague hint.

**Drift 5 — MCP server start command (Claude Code MCP connection section)**
The current step 1 in the MCP section reads:
```
1. Start the MCP server separately (not bundled in Docker by default):
   ```bash
   python -m polytool mcp-server --port 8001
   ```
   Or set `MCP_PORT` in `.env` if using a different port.
```

Replace with:
```
1. Start the MCP server separately (not bundled in Docker by default):
   ```bash
   python -m polytool mcp
   ```
   Or set `MCP_PORT` in `.env` if using a different port. The subcommand is `mcp`
   (not `mcp-server`). Run `python -m polytool mcp --help` to confirm.
```

The old command `mcp-server` does not exist. The actual CLI subcommand is `mcp`
(confirmed via `python -m polytool --help` and `python -m polytool mcp --help`).
  </action>
  <verify>
After editing, run:
  grep "Last verified:" docs/RIS_OPERATOR_GUIDE.md
  grep "curl\|jq" docs/RIS_OPERATOR_GUIDE.md | grep -i "import"
  grep "runtime-verified\|NOT been runtime" docs/RIS_OPERATOR_GUIDE.md
  grep "mcp-server\|mcp_server" docs/RIS_OPERATOR_GUIDE.md
  grep "python.*PATH" docs/RIS_OPERATOR_GUIDE.md

Expected results:
- Last verified line shows 2026-04-05
- No import-related curl/jq annotation remains
- "NOT been runtime-verified" is gone; new verified statement is present
- mcp-server command is gone
- old PATH warning is gone
  </verify>
  <done>
All five drifts corrected in docs/RIS_OPERATOR_GUIDE.md. The file remains valid
markdown. No other lines changed.
  </done>
</task>

<task type="auto">
  <name>Task 2: Check ADR 0013 and CURRENT_STATE.md for contradictions</name>
  <files>docs/adr/0013-ris-n8n-pilot-scoped.md, docs/CURRENT_STATE.md</files>
  <action>
Read both files and verify they do NOT contain contradictory wording about the five
drifts fixed in Task 1. Specific things to check:

**ADR 0013 (docs/adr/0013-ris-n8n-pilot-scoped.md):**
- Import section says `bash infra/n8n/import-workflows.sh [container_name]` — this is
  accurate (the script accepts an optional container name arg). No change needed for
  the import description.
- The ADR documents the docker-beside-docker runtime pattern (already correct per the
  audit). Confirm the MCP command is not mentioned in the ADR (it is not — the ADR
  covers only orchestration scope). No change expected.
- If any line says `mcp-server` or references the old REST-based import approach,
  fix it with the same corrections as Task 1. Otherwise, document "no change needed."

**CURRENT_STATE.md:**
- The quick-260404-t5l section (around line 1454) already accurately describes the
  runtime fix. Confirm it does not contain `mcp-server` or the old import approach.
- The quick-260404-sb4 section (around line 1433) says "Runtime smoke test requires
  Docker and a running n8n container." This is a setup prerequisite note, not a claim
  that smoke tests have NOT been run — it is not contradictory. No change needed.
- If any line says `mcp-server --port` or "NOT been runtime-verified," fix it.
  Otherwise, document "no change needed" in the dev log.

Only edit these files if a contradiction is found. Record findings (change or
no-change) for the dev log in Task 3.
  </action>
  <verify>
  grep "mcp-server" docs/adr/0013-ris-n8n-pilot-scoped.md docs/CURRENT_STATE.md
  grep "NOT been runtime-verified" docs/adr/0013-ris-n8n-pilot-scoped.md docs/CURRENT_STATE.md
  grep "curl.*import\|jq.*import" docs/adr/0013-ris-n8n-pilot-scoped.md docs/CURRENT_STATE.md

All three greps should return no matches (or empty output).
  </verify>
  <done>
ADR 0013 and CURRENT_STATE.md confirmed clean (or any found contradictions fixed).
Outcome recorded for the dev log.
  </done>
</task>

<task type="auto">
  <name>Task 3: Write closeout dev log</name>
  <files>docs/dev_logs/2026-04-05_ris_n8n_docs_reconcile.md</files>
  <action>
Create docs/dev_logs/2026-04-05_ris_n8n_docs_reconcile.md. Keep it short and
factual. Structure:

```markdown
# RIS n8n Docs Reconciliation — 2026-04-05

**Quick ID:** 260404-uav
**Scope:** Docs-only. No code, config, or workflow JSON changed.

## Why This Was Needed

quick-260404-t5l fixed the n8n runtime path and ran a smoke test (11/11 workflows
imported, docker exec bridge confirmed). The docs were written before or during that
fix and contained five drifts from the final runtime state.

## Changes Made

### docs/RIS_OPERATOR_GUIDE.md

1. **Last verified date**: Updated from 2026-04-04 to 2026-04-05.

2. **import-workflows.sh usage note (step 5)**: Replaced "Requires curl and jq"
   annotation with accurate description: the script uses
   `docker exec polytool-n8n n8n import:workflow --input=<file>` (docker CLI, no REST
   API). Old note implied basic-auth REST approach (deprecated in n8n 1.88.0).

3. **Runtime verification note (Scheduled Job Workflows section)**: Replaced
   "NOT been runtime-verified" warning with the actual smoke test results:
   build OK, docker-cli v27.3.1 in n8n container, exec bridge verified,
   11/11 workflows imported.

4. **python-on-n8n-PATH warning (troubleshooting block)**: Replaced vague warning
   about `python` not on PATH with an explanation of the docker-exec bridge pattern
   (`docker exec polytool-ris-scheduler python -m polytool ...`). The old warning
   predated the docker-beside-docker architecture decision.

5. **MCP server start command**: Changed `python -m polytool mcp-server --port 8001`
   to `python -m polytool mcp`. The subcommand `mcp-server` does not exist; the
   actual CLI entry is `mcp` (confirmed via `python -m polytool --help`).

### docs/adr/0013-ris-n8n-pilot-scoped.md

[Either: No changes. Checked for mcp-server references and old import approach — none found.]
[Or: describe any actual change made.]

### docs/CURRENT_STATE.md

[Either: No changes. quick-260404-t5l section already accurate — does not contain
mcp-server or NOT-been-runtime-verified language.]
[Or: describe any actual change made.]

## Codex Review

Docs-only changes. Skip tier — no review required per Codex review policy.
```

Fill in the ADR 0013 and CURRENT_STATE.md sections with the actual outcome from Task 2
(either "No changes" or a description of what was changed).
  </action>
  <verify>
  ls -la docs/dev_logs/2026-04-05_ris_n8n_docs_reconcile.md

File must exist and be non-empty.
  </verify>
  <done>
Dev log exists at docs/dev_logs/2026-04-05_ris_n8n_docs_reconcile.md with all five
changes recorded and accurate Task 2 outcomes filled in.
  </done>
</task>

</tasks>

<verification>
After all tasks complete, run these checks:

```bash
# Drift 1: date
grep "Last verified:" docs/RIS_OPERATOR_GUIDE.md
# Expected: Last verified: 2026-04-05

# Drift 2: import note is accurate
grep -A3 "Import workflow templates" docs/RIS_OPERATOR_GUIDE.md | grep -i "curl\|jq"
# Expected: no output

# Drift 3: runtime verified
grep -i "NOT been runtime-verified" docs/RIS_OPERATOR_GUIDE.md
# Expected: no output

# Drift 4: PATH warning gone, bridge explanation present
grep "docker exec polytool-ris-scheduler" docs/RIS_OPERATOR_GUIDE.md | head -5
# Expected: at least one line (the bridge explanation in the troubleshooting block)

# Drift 5: correct MCP command
grep "mcp-server" docs/RIS_OPERATOR_GUIDE.md
# Expected: no output

grep "python -m polytool mcp$" docs/RIS_OPERATOR_GUIDE.md
# Expected: the corrected start command line

# Dev log exists
ls docs/dev_logs/2026-04-05_ris_n8n_docs_reconcile.md
# Expected: file present
```
</verification>

<success_criteria>
- docs/RIS_OPERATOR_GUIDE.md has all five drifts corrected with no unintended prose changes
- ADR 0013 and CURRENT_STATE.md are confirmed clean or any found contradictions fixed
- docs/dev_logs/2026-04-05_ris_n8n_docs_reconcile.md exists and accurately describes all changes
- No code, Docker config, workflow JSON, or strategy files were touched
- RIS-only pilot framing preserved throughout (no Phase 3 language added)
</success_criteria>

<output>
After completion, create `.planning/quick/260404-uav-ris-n8n-docs-reconciliation-fix-5-doc-dr/SUMMARY.md`
documenting:
- What was changed in each file
- Whether ADR 0013 and CURRENT_STATE.md required changes
- Any surprises found during the reconciliation
</output>
