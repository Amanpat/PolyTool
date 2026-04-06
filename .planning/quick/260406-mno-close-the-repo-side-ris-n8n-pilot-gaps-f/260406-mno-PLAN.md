---
phase: quick-260406-mno
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - infra/n8n/workflows/ris_manual_acquire.json
  - workflows/n8n/README.md
  - docker-compose.yml
  - .env.example
  - scripts/docker-start.sh
  - scripts/smoke_ris_n8n.py
  - docs/runbooks/RIS_N8N_SMOKE_TEST.md
  - docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "All infra/n8n/workflows/*.json parse as valid JSON and reference the correct container name (polytool-ris-scheduler)"
    - "No workflow command field starts with the spurious = prefix"
    - "docker compose --profile ris-n8n config renders without errors"
    - "smoke_ris_n8n.py validates workflow JSON, CLI entrypoints, and compose profile in a single non-destructive run"
    - "The orphaned workflows/n8n/ directory is removed or documented as deprecated"
    - ".env.example clearly explains ris-n8n as opt-in and safe"
  artifacts:
    - path: "scripts/smoke_ris_n8n.py"
      provides: "Automated repo-side validation for RIS n8n pilot assets"
    - path: "docs/runbooks/RIS_N8N_SMOKE_TEST.md"
      provides: "Operator runbook for Phase N4 smoke validation"
    - path: "docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md"
      provides: "Audit trail of all changes made"
  key_links:
    - from: "infra/n8n/workflows/*.json"
      to: "docker-compose.yml"
      via: "container_name in docker exec commands must match ris-scheduler container_name"
      pattern: "docker exec polytool-ris-scheduler"
    - from: "scripts/smoke_ris_n8n.py"
      to: "infra/n8n/workflows/*.json"
      via: "JSON parse + command field validation"
---

<objective>
Close the repo-side RIS n8n pilot gaps for Phase N4 by fixing known drift in workflow
JSON templates, removing the orphaned v2 workflow directory, creating a smoke test
script, and writing a concise operator runbook.

Purpose: Make the n8n pilot assets internally consistent, testable via a single script,
and safe to run locally -- without touching unrelated services or code.

Output: Patched workflow JSON, smoke script, runbook, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/PLAN_OF_RECORD.md
@docs/ARCHITECTURE.md
@docker-compose.yml
@.env.example
@scripts/docker-start.sh
@infra/n8n/Dockerfile
@infra/n8n/README.md
@infra/n8n/import-workflows.sh
@docs/dev_logs/2026-04-05_ris_n8n_pilot.md
@docs/dev_logs/2026-04-05_ris_n8n_runtime_fix.md
@docs/dev_logs/2026-04-06_n8n_instance_mcp_repo_prep.md

<interfaces>
<!-- Key findings from audit — executor needs these to understand current state -->

The docker-compose.yml n8n service builds from infra/n8n/Dockerfile and runs under
profile: ris-n8n. The ris-scheduler service has container_name: polytool-ris-scheduler
and NO profile (always-on in default stack).

Container name in docker-compose.yml:
  ris-scheduler: container_name: polytool-ris-scheduler
  n8n env var: N8N_EXEC_CONTAINER=${N8N_EXEC_CONTAINER:-polytool-ris-scheduler}

Registered CLI jobs (from `research-scheduler status`):
  academic_ingest, reddit_polymarket, reddit_others, blog_ingest,
  youtube_ingest, github_ingest, freshness_refresh, weekly_digest

research-report subcommands: save, list, search, digest (NOT --topic)
research-scheduler subcommands: status, start, run-job

KNOWN BUGS found during audit:
1. infra/n8n/workflows/ris_manual_acquire.json: command starts with "=docker exec..."
   (leading = prefix causes runtime failure). Fix: remove the leading =.
2. workflows/n8n/ (v2 set, 8 files): uses wrong container name "polytool-polytool-1"
   which does not match any container_name in docker-compose.yml. This directory was
   created on a feature branch (feat/ws-clob-feed) with stale assumptions. The v1 set
   in infra/n8n/workflows/ is the canonical location per ADR-0013 and the import script.
   Action: delete workflows/n8n/ entirely.
3. workflows/n8n/ris-manual-ingest.json also has the leading = bug.
4. workflows/n8n/ris-weekly-digest.json uses "research-report --topic" which is not a
   valid CLI invocation (research-report requires a subcommand: save/list/search/digest).

APScheduler (ris-scheduler) CANNOT safely be put behind a profile without risk --
it has no profile today and adding one would change default-stack behavior for existing
operators. Document this blocker clearly; do NOT move it behind a profile.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix workflow drift and remove orphaned v2 directory</name>
  <files>
    infra/n8n/workflows/ris_manual_acquire.json,
    docker-compose.yml,
    .env.example,
    scripts/docker-start.sh
  </files>
  <action>
1. Fix the leading `=` in infra/n8n/workflows/ris_manual_acquire.json:
   - Open the file, find the executeCommand node's `command` field.
   - It currently reads: `=docker exec polytool-ris-scheduler python -m polytool research-acquire --url "{{ $json.body.url }}" --source-family "{{ $json.body.source_family }}" --no-eval`
   - Change to: `docker exec polytool-ris-scheduler python -m polytool research-acquire --url "{{ $json.body.url }}" --source-family "{{ $json.body.source_family }}" --no-eval`
   - The `=` prefix is an n8n expression prefix that causes the entire string to be evaluated as a JS expression, which breaks the docker exec invocation.

2. Delete the entire `workflows/n8n/` directory tree (8 JSON files + README.md).
   These are orphaned v2 templates from feat/ws-clob-feed that reference the wrong
   container name (`polytool-polytool-1`) and have additional CLI bugs. The canonical
   workflow location is `infra/n8n/workflows/` per ADR-0013, the import script, and
   all dev logs. Run: `rm -rf workflows/n8n/` and also `rmdir workflows/` if now empty.

3. Add a comment block to the `ris-scheduler` service in docker-compose.yml explaining
   that it runs in the default stack intentionally (no profile). Add a one-line comment:
   ```
   # APScheduler RIS scheduler -- always-on in default stack (no compose profile).
   # To use n8n instead: docker compose stop ris-scheduler && docker compose --profile ris-n8n up -d n8n
   # See docs/adr/0013-ris-n8n-pilot-scoped.md for scheduler mutual exclusion.
   ```
   Place this comment block directly above the `ris-scheduler:` service definition.
   Do NOT add a `profiles:` key to ris-scheduler -- that would break the default stack.

4. In .env.example, under the existing "n8n RIS Pilot" comment section, add a clear note:
   ```
   # APScheduler (ris-scheduler container) runs by default in `docker compose up`.
   # To switch to n8n scheduling: stop ris-scheduler, start n8n profile.
   # Both running simultaneously = double-scheduling (not harmful, but wasteful).
   ```

5. In scripts/docker-start.sh, update the `--with-n8n` branch to also print:
   `echo "  Tip: docker compose stop ris-scheduler  (prevents double-scheduling)"`
   after the existing WARNING line.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -c "
import json, glob, sys
errors = []
# Check all v1 workflows parse and have no leading =
for f in sorted(glob.glob('infra/n8n/workflows/*.json')):
    with open(f) as fh:
        data = json.load(fh)
    for n in data.get('nodes', []):
        if n.get('type') == 'n8n-nodes-base.executeCommand':
            cmd = n.get('parameters', {}).get('command', '')
            if cmd.startswith('='):
                errors.append(f'{f}: command starts with =')
            if 'polytool-ris-scheduler' not in cmd:
                errors.append(f'{f}: wrong container name in command')
# Check v2 directory is gone
import os
if os.path.exists('workflows/n8n'):
    errors.append('workflows/n8n/ still exists')
# Check compose parses
import subprocess
r = subprocess.run(['docker', 'compose', '--profile', 'ris-n8n', 'config', '--quiet'], capture_output=True, text=True)
if r.returncode != 0:
    errors.append(f'docker compose config failed: {r.stderr[:200]}')
if errors:
    print('ERRORS:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('ALL CHECKS PASSED')
"</automated>
  </verify>
  <done>
    - ris_manual_acquire.json command field no longer has leading = prefix
    - workflows/n8n/ directory is fully removed
    - docker-compose.yml has scheduler mutual exclusion comment on ris-scheduler service
    - .env.example has APScheduler default-on note
    - docker-start.sh prints tip to stop ris-scheduler when --with-n8n is used
    - docker compose --profile ris-n8n config still renders cleanly
  </done>
</task>

<task type="auto">
  <name>Task 2: Create smoke script and operator runbook</name>
  <files>
    scripts/smoke_ris_n8n.py,
    docs/runbooks/RIS_N8N_SMOKE_TEST.md
  </files>
  <action>
1. Create `scripts/smoke_ris_n8n.py` -- a non-destructive, repo-only validation script.
   The script should:
   a) Parse all `infra/n8n/workflows/*.json` files and verify:
      - Each file is valid JSON
      - Each file has a `name` field
      - Each file has a `nodes` array
      - Each executeCommand node's `command` field does NOT start with `=`
      - Each executeCommand node's `command` references `polytool-ris-scheduler`
      - Extract the `python -m polytool <subcommand>` from each command and verify
        the subcommand is in the known-good set: {research-health, research-acquire,
        research-scheduler, research-report, research-stats}
   b) Verify CLI entrypoints respond to --help:
      - `python -m polytool research-health --help`
      - `python -m polytool research-stats --help`
      - `python -m polytool research-scheduler --help`
      - `python -m polytool research-acquire --help`
      - `python -m polytool research-report --help`
      Each must exit 0.
   c) Verify compose profile renders:
      - Run `docker compose --profile ris-n8n config --quiet` and check exit 0.
      - If docker is not available, print SKIP with reason (not a failure).
   d) Print a summary table: check name, status (PASS/FAIL/SKIP), detail.
   e) Print curl examples for operator reference (webhook test, health check manual trigger).
      These are informational only, not executed.
   f) Exit 0 if all checks pass (or SKIP), exit 1 if any FAIL.

   The script should use only stdlib (json, subprocess, glob, pathlib, sys, os).
   No external dependencies. Should work on Windows (the dev environment) and Linux.
   Add `#!/usr/bin/env python3` shebang. Add a docstring explaining purpose and usage.

2. Create `docs/runbooks/RIS_N8N_SMOKE_TEST.md` with:
   - Title: RIS n8n Pilot -- Smoke Test Runbook
   - Purpose: one paragraph explaining this validates repo-side n8n assets
   - Prerequisites: Python 3.11+, Docker (optional, for compose check)
   - Quick start: `python scripts/smoke_ris_n8n.py`
   - What it checks (bulleted list matching the smoke script sections)
   - Manual follow-up steps (for after smoke passes):
     1. Start n8n: `docker compose --profile ris-n8n up -d n8n`
     2. Import workflows: `bash infra/n8n/import-workflows.sh`
     3. Open n8n UI at http://localhost:5678, complete owner setup wizard
     4. Activate desired workflows in the UI
     5. Stop APScheduler to avoid double-scheduling: `docker compose stop ris-scheduler`
     6. Test health check workflow manually in n8n UI (click "Test workflow")
     7. Test webhook with curl:
        ```
        curl -X POST http://localhost:5678/webhook/<webhook-id> \
          -H "Content-Type: application/json" \
          -d '{"url": "https://arxiv.org/abs/2301.00001", "source_family": "academic"}'
        ```
   - Troubleshooting section: common issues (Docker not running, compose profile not found,
     n8n container not started, double-scheduling symptoms)
   - Link to ADR-0013 and RIS_OPERATOR_GUIDE.md
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python scripts/smoke_ris_n8n.py</automated>
  </verify>
  <done>
    - scripts/smoke_ris_n8n.py exists and runs successfully (exit 0)
    - Smoke script validates all 11 workflow JSONs without errors
    - Smoke script verifies all 5 CLI entrypoints respond to --help
    - Smoke script checks compose profile (or SKIPs gracefully if no Docker)
    - docs/runbooks/RIS_N8N_SMOKE_TEST.md exists with complete operator instructions
  </done>
</task>

<task type="auto">
  <name>Task 3: Write dev log documenting all changes and remaining gaps</name>
  <files>
    docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md
  </files>
  <action>
Create `docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md` with:

- **Header**: date, quick task ID (quick-260406-mno), branch (main)
- **Summary**: 3-4 bullet points covering what was done
- **Audit Findings** section:
  List all 7 gaps discovered during audit:
  1. Leading `=` prefix in ris_manual_acquire.json command field (both v1 and v2)
  2. Orphaned workflows/n8n/ directory (v2) with wrong container name (polytool-polytool-1)
  3. v2 ris-weekly-digest.json uses invalid CLI invocation (research-report --topic)
  4. v2 ris-reddit-ingestion.json only covers reddit_polymarket, missing reddit_others
  5. No smoke test script existed
  6. No operator runbook for Phase N4 validation
  7. APScheduler ris-scheduler has no profile (always-on by design)

- **Changes Made** section: table of file | change for each modified file
- **APScheduler Profile Assessment** section:
  Document why ris-scheduler was NOT moved behind a profile:
  - It runs in the default stack today. Adding a profile would mean `docker compose up`
    no longer starts the scheduler, breaking existing operator workflows.
  - The safe path is documented mutual exclusion (stop ris-scheduler when using n8n).
  - A future ADR could propose making both schedulers profile-gated, but that requires
    updating all operator docs and the docker-start.sh default behavior.
  - Status: BLOCKER DOCUMENTED, no code change made.

- **Test Commands Run** section: list every command run and its result
  - `python scripts/smoke_ris_n8n.py` -- PASS
  - `python -m polytool --help` -- loads, no import errors
  - `python -m polytool research-health --help` -- exit 0
  - `docker compose --profile ris-n8n config --quiet` -- exit 0
  - `python -m pytest tests/ -x -q --tb=short` -- report exact count

- **Remaining Manual UI Steps** (for operator, not automatable):
  1. Import workflows via `bash infra/n8n/import-workflows.sh`
  2. Complete n8n owner setup wizard at http://localhost:5678/setup
  3. Activate desired workflows in n8n UI
  4. Configure DISCORD_WEBHOOK_URL in n8n Settings > Variables (for v2 alerting)
  5. Optionally register n8n MCP in Claude Code (requires Enterprise or community MCP backend)

- **Codex Review**: Skip (infra config, workflow JSON, docs, smoke script -- no strategy/execution/risk code)
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -c "
import os, sys
path = 'docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md'
if not os.path.exists(path):
    print(f'FAIL: {path} does not exist'); sys.exit(1)
with open(path) as f:
    content = f.read()
required = ['Audit Findings', 'Changes Made', 'APScheduler', 'Test Commands', 'Remaining Manual']
missing = [r for r in required if r not in content]
if missing:
    print(f'FAIL: missing sections: {missing}'); sys.exit(1)
print(f'PASS: dev log exists ({len(content)} chars, all required sections present)')
"</automated>
  </verify>
  <done>
    - Dev log exists at docs/dev_logs/2026-04-06_ris_n8n_phase_n4_repo_hardening.md
    - Contains all required sections: Audit Findings, Changes Made, APScheduler assessment,
      Test Commands, Remaining Manual steps
    - Documents the APScheduler profile blocker with clear rationale
    - Lists exact test commands and their results
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| n8n container -> host Docker socket | n8n can execute arbitrary commands on any container via docker exec |
| Webhook endpoint -> n8n | External HTTP can trigger workflow execution |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-n4-01 | Tampering | infra/n8n/workflows/*.json | accept | Workflow JSONs are committed to git; operator imports them manually. No runtime modification path from outside the repo. |
| T-n4-02 | Elevation of Privilege | docker.sock mount | accept | Documented in ADR-0013 security section. The n8n container intentionally has docker exec capability. This is the designed integration pattern. |
| T-n4-03 | Information Disclosure | webhook URL | mitigate | Runbook documents that webhook URLs contain auth tokens and must be treated as secrets. Not logged in smoke script output. |
</threat_model>

<verification>
1. `python scripts/smoke_ris_n8n.py` exits 0 with all checks PASS or SKIP
2. `docker compose --profile ris-n8n config --quiet` exits 0
3. No workflow JSON in infra/n8n/workflows/ has a command starting with `=`
4. `workflows/n8n/` directory no longer exists
5. `python -m pytest tests/ -x -q --tb=short` shows no regressions
6. Dev log exists with all required sections
</verification>

<success_criteria>
- All 11 infra/n8n/workflows/*.json files parse cleanly and reference the correct container
- The leading = bug in ris_manual_acquire.json is fixed
- The orphaned workflows/n8n/ directory is removed
- smoke_ris_n8n.py validates all workflow assets, CLI entrypoints, and compose profile
- Operator runbook provides clear Phase N4 validation path
- Dev log documents all changes, the APScheduler profile blocker, and remaining manual steps
- Existing tests still pass (no regressions)
</success_criteria>

<output>
After completion, create `.planning/quick/260406-mno-close-the-repo-side-ris-n8n-pilot-gaps-f/260406-mno-SUMMARY.md`
</output>
