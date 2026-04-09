---
phase: quick-260409-min
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/runbooks/RIS_DISCORD_ALERTS.md
  - docs/runbooks/RIS_N8N_OPERATOR_SOP.md
  - infra/n8n/README.md
autonomous: true
requirements: [DOCS-01]
must_haves:
  truths:
    - "Operator can look up the intended format for every RIS Discord alert type in one place"
    - "Operator can run exact commands to test each alert path after a workflow change"
    - "Operator knows what severity levels mean and when each alert fires"
    - "No content is duplicated between the new doc and the SOP"
  artifacts:
    - path: "docs/runbooks/RIS_DISCORD_ALERTS.md"
      provides: "Discord alert style guide and verification procedure"
      min_lines: 40
  key_links:
    - from: "docs/runbooks/RIS_N8N_OPERATOR_SOP.md"
      to: "docs/runbooks/RIS_DISCORD_ALERTS.md"
      via: "cross-link in Related Docs table"
      pattern: "RIS_DISCORD_ALERTS"
    - from: "infra/n8n/README.md"
      to: "docs/runbooks/RIS_DISCORD_ALERTS.md"
      via: "cross-link in Related Docs section"
      pattern: "RIS_DISCORD_ALERTS"
---

<objective>
Create a compact operator-facing Discord alert style guide and verification procedure for the RIS n8n pilot.

Purpose: Lock in the intended Discord message format, alert types, severity meaning, and exact verification steps so future workflow changes do not silently degrade alert quality. Operators get a single reference doc for alert testing.

Output: `docs/runbooks/RIS_DISCORD_ALERTS.md` plus minimal cross-links from SOP and n8n README.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/dev_logs/2026-04-09_discord_alert_integration_debug.md
@docs/runbooks/RIS_N8N_OPERATOR_SOP.md
@infra/n8n/README.md

Key context from codebase analysis:

All RIS Discord alerts are sent via a shared `Operator: Send Webhook` n8n node that
POSTs `{ "content": "<plain text or markdown>" }` to the Discord webhook URL injected
at import time from `DISCORD_WEBHOOK_URL` in `.env`.

Four alert categories exist in the unified workflow (`ris-unified-dev.json`):

1. **Health alert** (Section 1, every 30 min) -- fires only for RED or actionable YELLOW.
   Format: `RIS health {status} | runs=N | docs=N | claims=N | new=N | cached=N | ingest_errors=N`
   followed by `- {STATUS} {checkName}: {message}` lines, optional `families:` line.

2. **Pipeline section errors** (Sections 2-7: academic, reddit, blog, youtube, github, freshness)
   -- fires on non-zero exit code from the Execute Command node.
   Format: `**RIS Pipeline Error: {job_name}**\n\nExit code: N\n\n**stderr:**\n```\n...\n```\n\n**stdout (last 500):**\n```\n...\n```\`

3. **Daily summary** (Section 8, 08:00 UTC, schedule disabled by default)
   Format: `RIS daily summary | health={status} | runs=N | docs=N | claims=N | new=N | cached=N | ingest_errors=N`
   followed by `actionable:` line, `families:` line, `prechecks: GO=N, CAUTION=N, STOP=N`.

4. **Ingest failure** (Section 9, webhook POST to /webhook/ris-ingest)
   Format: `RIS ingest failed | family={family} | exit={code}\nurl: {url}\nerror: {error_text}`
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create RIS_DISCORD_ALERTS.md style guide and verification runbook</name>
  <files>docs/runbooks/RIS_DISCORD_ALERTS.md</files>
  <action>
Create `docs/runbooks/RIS_DISCORD_ALERTS.md` with these sections (keep total doc under ~120 lines):

**Header:** Title, last-verified date (2026-04-09), one-line purpose.

**Prerequisites (3 lines max):** `DISCORD_WEBHOOK_URL` in `.env`, n8n running, workflows imported via `python infra/n8n/import_workflows.py`. Link to SOP for full setup.

**Alert Types table:** One table with columns: Type, Trigger, Frequency, Format Summary. Four rows:
- Health alert: schedule, every 30 min (RED/YELLOW only), single-line header + check bullets
- Pipeline error: exit code != 0, per-section (academic/reddit/blog/youtube/github/freshness), bold markdown with stderr/stdout blocks
- Daily summary: schedule (disabled by default), 08:00 UTC, single-line header + actionable + families + prechecks
- Ingest failure: webhook POST failure, on-demand, single-line header + url + error

**Message Format Reference:** For each alert type, show one concrete example message exactly as it would appear in Discord (use a fenced code block). These are the "golden" reference formats. Extract them from the workflow JS code analysis in the context section above. Mark clearly: "These are the intended formats. If a workflow change produces messages that do not match, the workflow change has a formatting regression."

**Severity Meaning:** Short table:
- RED: Operational failure requiring action (pipeline down, all providers failing)
- YELLOW: Degraded state, monitor closely (queue growing, accept rate drifting)
- GREEN: Healthy (never sent to Discord -- health alerts only fire for RED/YELLOW)
- Note: Pipeline errors and ingest failures have no severity level -- they always fire on failure.

**Verification Procedure:** Exact steps to test each alert path after any workflow or webhook change:

1. Health alert test:
   - Ensure n8n is running and workflows imported
   - Open n8n UI at http://localhost:5678
   - Find `RIS -- Research Intelligence System` workflow
   - Click the `Health: Schedule` trigger node, click "Test workflow" from that node
   - If health status is GREEN (no actionable checks), the alert branch is skipped (this is correct behavior)
   - To force an alert: temporarily break a health check (e.g. stop the ris-scheduler container so `no_new_docs_48h` fires YELLOW)
   - Check Discord channel for message matching the Health Alert format above

2. Ingest failure test (easiest, recommended first):
   ```bash
   curl -X POST "http://localhost:5678/webhook/ris-ingest" \
     -H "Content-Type: application/json" \
     -d '{"url":"http://127.0.0.1:9/discord-format-test","source_family":"blog"}'
   ```
   - This hits an unreachable URL, forcing the failure path
   - Check Discord channel for message matching Ingest Failure format above
   - In n8n UI: open latest execution, verify `Operator: Send Webhook` ran with no `json.error`

3. Daily summary test:
   - In n8n UI, find the `Summary: Schedule` trigger node, click "Test workflow" from that node
   - Check Discord for message matching Daily Summary format above

4. Pipeline error test:
   - In n8n UI, find any section trigger (e.g. `Academic: Manual`), click "Test workflow"
   - If the underlying CLI command fails (e.g. no network), check Discord for pipeline error format

**After DISCORD_WEBHOOK_URL change:** Must re-import workflows. The URL is injected at import time, not read at runtime.
```bash
python infra/n8n/import_workflows.py
# Verify: CLI should print "DISCORD_WEBHOOK_URL: configured (.env)"
```

**Common Failures:** Short bullet list:
- Alert not sent: placeholder `__RIS_OPERATOR_WEBHOOK_URL__` still in workflow -- re-import
- `EAI_AGAIN` error in Send Webhook node: transient DNS -- retry once, check container DNS
- Health alert never fires: all checks GREEN -- this is correct, not a bug
- Discord message truncated: `content` field has a 2000-char Discord limit; stderr/stdout are already pre-truncated in the workflow code

Do NOT duplicate the full SOP startup procedure, import steps, or health check command reference. Reference `docs/runbooks/RIS_N8N_OPERATOR_SOP.md` for those.
  </action>
  <verify>
    <automated>python -c "p='docs/runbooks/RIS_DISCORD_ALERTS.md'; f=open(p); lines=f.readlines(); f.close(); assert len(lines) >= 40, f'Too short: {len(lines)} lines'; assert any('Health' in l and 'Pipeline' in l or 'Alert' in l for l in lines[:5]), 'Missing title'; assert any('127.0.0.1:9' in l for l in lines), 'Missing ingest failure test command'; assert any('import_workflows' in l for l in lines), 'Missing re-import step'; print(f'OK: {len(lines)} lines, key sections present')"</automated>
  </verify>
  <done>
    - `docs/runbooks/RIS_DISCORD_ALERTS.md` exists with all 4 alert types documented
    - Each alert type has a concrete example message format
    - Severity meaning table present
    - Exact verification commands for all 4 alert paths
    - Re-import procedure after webhook URL change documented
    - Common failures listed
    - No duplication of SOP content
    - Doc is under 150 lines total
  </done>
</task>

<task type="auto">
  <name>Task 2: Add cross-links from SOP and n8n README</name>
  <files>docs/runbooks/RIS_N8N_OPERATOR_SOP.md, infra/n8n/README.md</files>
  <action>
1. In `docs/runbooks/RIS_N8N_OPERATOR_SOP.md`:
   - In the "Discord Alert Troubleshooting" section (around line 89), add a line at the end:
     `For the complete alert format reference and verification steps, see [`docs/runbooks/RIS_DISCORD_ALERTS.md`](RIS_DISCORD_ALERTS.md).`
   - In the "Related Docs" table at the bottom, add a new row:
     `| [`docs/runbooks/RIS_DISCORD_ALERTS.md`](RIS_DISCORD_ALERTS.md) | Discord alert style guide and verification procedure |`

2. In `infra/n8n/README.md`:
   - In the "Related Docs" section at the bottom, add a new bullet:
     `- Discord alerts: `docs/runbooks/RIS_DISCORD_ALERTS.md``

These are minimal additions -- one line each. Do not rewrite or restructure either file.
  </action>
  <verify>
    <automated>python -c "ok=True; f1=open('docs/runbooks/RIS_N8N_OPERATOR_SOP.md').read(); f2=open('infra/n8n/README.md').read(); ok = ok and 'RIS_DISCORD_ALERTS' in f1; ok = ok and 'RIS_DISCORD_ALERTS' in f2; assert ok, 'Cross-links missing'; print('OK: cross-links present in both files')"</automated>
  </verify>
  <done>
    - SOP has cross-link in both the Discord troubleshooting section and the Related Docs table
    - n8n README has cross-link in Related Docs section
    - No other content in either file was changed
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries applicable -- this is a docs-only change with no code, no secrets, and no runtime behavior.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-min-01 | I (Info Disclosure) | RIS_DISCORD_ALERTS.md | accept | Doc contains no secrets. Webhook URL is referenced as an env var name only, never a value. Repo is private. |
</threat_model>

<verification>
1. `docs/runbooks/RIS_DISCORD_ALERTS.md` exists and is between 40-150 lines
2. All 4 alert types documented with example formats
3. Verification steps include exact curl commands
4. Cross-links present in SOP and n8n README
5. No code files were modified
6. No SOP content was duplicated (only referenced)
</verification>

<success_criteria>
- One new doc at `docs/runbooks/RIS_DISCORD_ALERTS.md` that an operator can use as the single reference for Discord alert formatting and testing
- Existing docs (SOP, n8n README) link to it with minimal additions
- Doc is compact (under 150 lines), durable, and does not duplicate the SOP
</success_criteria>

<output>
After completion, create `.planning/quick/260409-min-lock-in-ris-discord-alert-style-guide-an/260409-min-SUMMARY.md`
</output>
