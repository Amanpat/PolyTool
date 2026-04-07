---
phase: quick-260407-inu
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - workflows/n8n/ris_sub_academic.json
  - workflows/n8n/ris_sub_reddit.json
  - workflows/n8n/ris_sub_blog_rss.json
  - workflows/n8n/ris_sub_youtube.json
  - workflows/n8n/ris_sub_github.json
  - workflows/n8n/ris_sub_weekly_digest.json
  - workflows/n8n/ris_sub_freshness_refresh.json
  - workflows/n8n/ris_orchestrator.json
  - workflows/n8n/ris_global_error_watcher.json
  - workflows/n8n/workflow_ids.env
  - workflows/n8n/README.md
  - docs/dev_logs/2026-04-07_n8n-workflow-rebuild.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "All 8 old RIS workflows deleted from n8n via API before deploying new ones"
    - "7 rebuilt sub-workflows each have: continueOnFail on Execute Command, exit code check via IF node, success metrics parse, Discord error alert on failure"
    - "Orchestrator has 3 sections: health monitor (30min), webhook pipeline trigger (Switch->Execute sub-workflow), URL ingest (research-acquire)"
    - "Global error watcher workflow deployed and set as error workflow on all RIS workflows"
    - "All Execute Command and Discord HTTP Request nodes have continueOnFail: true"
    - "All workflows use $env.DISCORD_WEBHOOK_URL (not hardcoded) and discover POLYTOOL_CONTAINER dynamically or via $env"
    - "All 9 workflows deployed inactive, tested via API, then activated"
    - "workflow_ids.env updated with all new IDs including error watcher"
  artifacts:
    - path: "workflows/n8n/ris_sub_academic.json"
      provides: "Academic sub-workflow with full error handling + Discord alerts"
    - path: "workflows/n8n/ris_sub_reddit.json"
      provides: "Reddit sub-workflow with full error handling + Discord alerts"
    - path: "workflows/n8n/ris_sub_blog_rss.json"
      provides: "Blog/RSS sub-workflow with full error handling + Discord alerts"
    - path: "workflows/n8n/ris_sub_youtube.json"
      provides: "YouTube sub-workflow with full error handling + Discord alerts"
    - path: "workflows/n8n/ris_sub_github.json"
      provides: "GitHub sub-workflow with full error handling + Discord alerts"
    - path: "workflows/n8n/ris_sub_weekly_digest.json"
      provides: "Weekly digest sub-workflow with full error handling + always-send Discord"
    - path: "workflows/n8n/ris_sub_freshness_refresh.json"
      provides: "Freshness refresh sub-workflow with full error handling + Discord alerts"
    - path: "workflows/n8n/ris_orchestrator.json"
      provides: "Orchestrator: health monitor + webhook trigger + URL ingest, all with error handling"
    - path: "workflows/n8n/ris_global_error_watcher.json"
      provides: "Global error workflow catching unhandled errors across all RIS workflows"
    - path: "workflows/n8n/workflow_ids.env"
      provides: "All 9 new workflow IDs"
    - path: "workflows/n8n/README.md"
      provides: "Updated documentation reflecting new architecture"
    - path: "docs/dev_logs/2026-04-07_n8n-workflow-rebuild.md"
      provides: "Dev log documenting the rebuild"
  key_links:
    - from: "ris_orchestrator.json"
      to: "sub-workflow IDs"
      via: "Execute Workflow nodes referencing sub-workflow IDs"
      pattern: "executeWorkflow"
    - from: "ris_global_error_watcher.json"
      to: "all 8 RIS workflows"
      via: "errorWorkflow setting on each workflow"
      pattern: "settings.errorWorkflow"
    - from: "all sub-workflows"
      to: "Discord"
      via: "HTTP Request node to $env.DISCORD_WEBHOOK_URL on failure"
      pattern: "httpRequest.*DISCORD_WEBHOOK_URL"
---

<objective>
Delete all 8 existing skeletal RIS n8n workflows and rebuild them from scratch with proper
error handling, stdout parsing, Discord alerting, retry logic, sticky note documentation,
and visual organization. Add a 9th workflow (Global Error Watcher) as a catch-all. Deploy
all 9, test, and activate.

Purpose: Current workflows are trigger->command only. No error handling, no alerts, no
metrics parsing. Production-grade workflows need exit code checks, failure alerts, success
metrics extraction, and a global error safety net.

Output: 9 production-grade n8n workflow JSON files, deployed and activated, with updated
docs and dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@workflows/n8n/workflow_ids.env
@workflows/n8n/README.md
@.planning/quick/260406-ovg-build-ris-workflow-system-in-n8n/260406-ovg-SUMMARY.md

<interfaces>
<!-- n8n API patterns confirmed in prior deployment (quick-260406-ovg) -->

n8n REST API (base: http://localhost:5678/api/v1):
- DELETE /workflows/{id} - Delete a workflow
- POST /workflows - Create workflow (returns {id, ...})
- PUT /workflows/{id} - Update workflow (strip: notes, meta, tags, triggerCount, active)
- PUT /workflows/{id}/tags - Set tags: [{"id": "lsdE5zgirb6IHxH5"}] (RIS tag)
- POST /workflows/{id}/activate - Activate workflow
- POST /workflows/{id}/deactivate - Deactivate workflow
- Header: X-N8N-API-KEY from N8N_API_KEY env var

n8n 2.x confirmed behaviors:
- NODES_EXCLUDE=[] already set in docker-compose.yml (executeCommand re-enabled)
- 6-field cron: rule.interval[{field:"cronExpression", expression:"0 0 4 * * 1"}]
- Interval: rule.interval[{field:"hours", hoursInterval:12}]
- Switch V2: typeVersion:2, mode:"rules", outputKey per rule, fallbackOutput:-1
- Expression prefix: "=" required on executeCommand fields with {{ }} interpolation
- Container target: polytool-ris-scheduler (for docker exec commands)
- Existing RIS tag ID: lsdE5zgirb6IHxH5

Existing workflow IDs to delete:
- RIS_SUB_ACADEMIC_ID=wGZFmbBk5TuKeiu4
- RIS_SUB_REDDIT_ID=66DODhOnrEdqc0Tk
- RIS_SUB_BLOG_RSS_ID=xhv5Dnru2nW7TchB
- RIS_SUB_YOUTUBE_ID=e6P3lkcJdwlRPgfj
- RIS_SUB_GITHUB_ID=ZJFoRcDFNdgzKP7m
- RIS_SUB_WEEKLY_DIGEST_ID=Nes9RKXadMsYcHE8
- RIS_SUB_FRESHNESS_REFRESH_ID=SrEdvxt5sRFRQYrV
- RIS_ORCHESTRATOR_ID=pvoP1evtPWTp5LPh
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Delete old workflows + Build all 9 workflow JSON files locally</name>
  <files>
    workflows/n8n/ris_sub_academic.json
    workflows/n8n/ris_sub_reddit.json
    workflows/n8n/ris_sub_blog_rss.json
    workflows/n8n/ris_sub_youtube.json
    workflows/n8n/ris_sub_github.json
    workflows/n8n/ris_sub_weekly_digest.json
    workflows/n8n/ris_sub_freshness_refresh.json
    workflows/n8n/ris_orchestrator.json
    workflows/n8n/ris_global_error_watcher.json
  </files>
  <action>
**Step 1: Delete all 8 existing workflows from n8n.**

Load API key and workflow IDs:
```bash
N8N_API_KEY=$(grep N8N_API_KEY .env | cut -d'=' -f2)
source workflows/n8n/workflow_ids.env
```

For each ID in workflow_ids.env, first deactivate then DELETE via n8n API:
```bash
curl -s -X POST "http://localhost:5678/api/v1/workflows/${ID}/deactivate" -H "X-N8N-API-KEY: $N8N_API_KEY"
curl -s -X DELETE "http://localhost:5678/api/v1/workflows/${ID}" -H "X-N8N-API-KEY: $N8N_API_KEY"
```

Confirm all 8 deleted. If any 404, that is fine (already gone).

**Step 2: Use n8n-mcp tools to look up EVERY node type BEFORE writing JSON.**

Use n8n-instance-mcp (or n8n-mcp if available) to look up current node schemas for:
scheduleTrigger, manualTrigger, executeCommand, if (v2), code (v2), httpRequest, stickyNote, set, executeWorkflow, webhook, switch (v2/v3), respondToWebhook, noOp, errorTrigger.

This is CRITICAL -- do NOT assume node parameter shapes from training data. Fetch actual
schemas from the running n8n instance to get correct typeVersion, parameter names, and
required fields for n8n 2.x.

**Step 3: Build 7 sub-workflow JSON files.**

Each sub-workflow follows this exact node pattern:

```
Sticky Note (top, documents purpose/schedule/command)
  |
Manual Trigger ---+
                  +--> Execute Command [continueOnFail: true]
Schedule Trigger -+         |
                        IF exit code == 0?
                       /              \
                    true              false
                     |                  |
               Parse Metrics     Format Error Message
               (Code node)       (Code node)
                     |                  |
               Success Note      Discord Alert
               (noOp or Set)     [continueOnFail: true]
                                 (HTTP Request POST to
                                  $env.DISCORD_WEBHOOK_URL)
```

Node implementation details for ALL 7 sub-workflows:

- **Sticky Note**: typeVersion 1, position top-left. Content: workflow name, schedule, command, error handling description.

- **Manual Trigger**: n8n-nodes-base.manualTrigger, typeVersion 1.

- **Schedule Trigger**: n8n-nodes-base.scheduleTrigger, typeVersion 1.
  - Interval-based (academic 12h, reddit 6h, blog 4h): `rule.interval[{field:"hours", hoursInterval: N}]`
  - Cron-based (youtube Mon 04:00, github Wed 04:00, freshness Sun 02:00, digest Sun 08:00): `rule.interval[{field:"cronExpression", expression:"0 0 H * * D"}]` using 6-field format.

- **Execute Command**: n8n-nodes-base.executeCommand, typeVersion 1, `continueOnFail: true`.
  - Command: `docker exec polytool-ris-scheduler python -m polytool research-scheduler run-job JOB_ID`
  - Exception: weekly_digest runs `docker exec polytool-ris-scheduler python -m polytool research-report digest --window 7` THEN `docker exec polytool-ris-scheduler python -m polytool research-stats summary` (two sequential Execute Command nodes, both continueOnFail: true).

- **IF node**: n8n-nodes-base.if, typeVersion 2.
  - Condition: `$json.exitCode` equals 0 (number comparison).
  - IMPORTANT: n8n IF v2 uses `conditions.options.caseSensitive` + `conditions.conditions` array format, NOT the v1 `conditions.boolean` format. Look up the actual v2 schema via MCP.

- **Parse Metrics (Code node)**: n8n-nodes-base.code, typeVersion 2.
  - JS: Parse stdout for key metrics (items ingested, errors, duration). Return structured JSON:
    ```js
    const stdout = $('Execute Command Node Name').first().json.stdout || '';
    const lines = stdout.split('\n');
    // Extract metrics from stdout
    return [{ json: { status: 'success', stdout: stdout.substring(0, 1500), job: 'JOB_NAME', timestamp: new Date().toISOString() } }];
    ```

- **Format Error (Code node)**: n8n-nodes-base.code, typeVersion 2.
  - JS: Build Discord-formatted error message:
    ```js
    const execNode = $('Execute Command Node Name').first().json;
    const stderr = execNode.stderr || '';
    const stdout = execNode.stdout || '';
    const exitCode = execNode.exitCode;
    const content = `**RIS Pipeline Error: JOB_NAME**\n\nExit code: ${exitCode}\n\n**stderr:**\n\`\`\`\n${stderr.substring(0, 1500)}\n\`\`\`\n\n**stdout (last 500 chars):**\n\`\`\`\n${stdout.substring(stdout.length - 500)}\n\`\`\``;
    return [{ json: { content } }];
    ```

- **Discord Alert (HTTP Request)**: n8n-nodes-base.httpRequest, typeVersion 4.2 (verify via MCP), `continueOnFail: true`.
  - Method: POST
  - URL: `={{ $env.DISCORD_WEBHOOK_URL }}`
  - Send Body: true, JSON, specify body: `{ "content": "={{ $json.content }}" }`
  - Alternatively, send body as JSON with `content` field from the Format Error node.

- **Success terminal**: n8n-nodes-base.noOp, typeVersion 1. Named "Success" with green color note.

**Sub-workflow table:**

| # | File | Name | Schedule | Job ID |
|---|------|------|----------|--------|
| 1 | ris_sub_academic.json | RIS Sub: Academic | Every 12h | academic_ingest |
| 2 | ris_sub_reddit.json | RIS Sub: Reddit | Every 6h | reddit_polymarket |
| 3 | ris_sub_blog_rss.json | RIS Sub: Blog/RSS | Every 4h | blog_ingest |
| 4 | ris_sub_youtube.json | RIS Sub: YouTube | Weekly Mon 04:00 (cron: 0 0 4 * * 1) | youtube_ingest |
| 5 | ris_sub_github.json | RIS Sub: GitHub | Weekly Wed 04:00 (cron: 0 0 4 * * 3) | github_ingest |
| 6 | ris_sub_freshness_refresh.json | RIS Sub: Freshness Refresh | Weekly Sun 02:00 (cron: 0 0 2 * * 0) | freshness_refresh |
| 7 | ris_sub_weekly_digest.json | RIS Sub: Weekly Digest | Weekly Sun 08:00 (cron: 0 0 8 * * 0) | SPECIAL (see below) |

**Special: Weekly Digest** has a different flow:
```
Manual/Schedule -> Exec research-report [continueOnFail] -> Exec research-stats [continueOnFail]
  -> Code: Format Digest Message (combine report + stats output, always send)
  -> HTTP Request: Discord (always-send digest, not just on error) [continueOnFail]
  -> IF either command failed -> Format Error -> Discord Error Alert [continueOnFail]
```
The weekly digest ALWAYS sends a Discord message with the digest content, plus an additional
error alert if either command failed. This is the "always-send" behavior.

**Step 4: Build orchestrator JSON (ris_orchestrator.json).**

Three visual sections separated by Sticky Notes:

**Section 1: Health Monitor (top)**
```
Sticky Note: "Section 1: Health Monitor - Every 30min"
Schedule (30min) -> Exec research-health [continueOnFail] -> Exec research-stats [continueOnFail]
  -> Code: Parse health + stats output, detect RED/CRITICAL/FAIL/pipeline_failed/ERROR
  -> IF hasAlert -> Format alert message -> Discord Alert [continueOnFail]
```

**Section 2: Manual Pipeline Control (middle)**
```
Sticky Note: "Section 2: Manual Pipeline Trigger - POST /webhook/ris-trigger"
Webhook (POST /webhook/ris-trigger) -> Switch V2 on $json.body.pipeline (7 rules + fallback)
  -> 7x Execute Workflow nodes (one per sub-workflow, IDs injected in Task 2)
  -> Respond to Webhook (200 OK with {pipeline, status, triggered_at})
  Fallback -> Respond to Webhook (400 with {error: "Unknown pipeline"})
```

Switch rules map pipeline values: academic, reddit, blog, youtube, github, digest, freshness.
Each Execute Workflow node targets the corresponding sub-workflow ID (placeholder "PLACEHOLDER_ID"
to be replaced in Task 2 after sub-workflows are deployed and IDs captured).

**Section 3: URL Ingest (bottom)**
```
Sticky Note: "Section 3: URL Ingest - POST /webhook/ris-ingest"
Webhook (POST /webhook/ris-ingest)
  -> Execute Command [continueOnFail]:
     "=docker exec polytool-ris-scheduler python -m polytool research-acquire --url \"{{ $json.body.url }}\" --source-family \"{{ $json.body.source_family }}\" --no-eval"
  -> IF exitCode == 0
     true: Respond 200 {status:"ingested", url, source_family, stdout}
     false: Code: format error -> Discord Alert [continueOnFail] -> Respond 500 {error, stderr, exitCode}
```

Use expression prefix `=` on ALL executeCommand command fields that contain `{{ }}` interpolation.

**Step 5: Build global error watcher (ris_global_error_watcher.json).**

```
Error Trigger (n8n-nodes-base.errorTrigger)
  -> Code: Format error context
     JS: Extract workflow name, error message, execution ID from $json
     Build Discord message: "**RIS Unhandled Error**\nWorkflow: {name}\nError: {message}\nExecution: {id}"
  -> HTTP Request: Discord [continueOnFail]
```

This workflow uses `n8n-nodes-base.errorTrigger` (typeVersion 1). It will be set as the
`settings.errorWorkflow` on all 8 RIS workflows after deployment in Task 2.

**Visual layout guidelines for ALL workflows:**
- Nodes flow left to right, top to bottom.
- Triggers at x=240. Execute Command at x=500. IF at x=760. Branches at x=1020. Discord at x=1280.
- Sticky Notes positioned above the flow they document (y offset -120 from first node).
- Use distinct node colors where supported (green for success path, red for error path).
- Every workflow has `"active": false` in JSON (activated via API in Task 2).
- Every workflow has `"settings": {}` initially (errorWorkflow injected in Task 2).

Write all 9 JSON files to `workflows/n8n/`, overwriting the old skeletal versions.
  </action>
  <verify>
    <automated>ls -la workflows/n8n/*.json | wc -l</automated>
    9 JSON files exist in workflows/n8n/. Each file is valid JSON (use `python -c "import json; json.load(open('workflows/n8n/FILE.json'))"` for each). Each sub-workflow JSON contains nodes: manualTrigger, scheduleTrigger, executeCommand (with onError/continueOnFail), if, code (x2), httpRequest, noOp or stickyNote. Orchestrator contains webhook, switch, executeWorkflow, respondToWebhook nodes. Error watcher contains errorTrigger node.
  </verify>
  <done>
    - 8 old workflows deleted from n8n (confirmed via API or 404)
    - 7 sub-workflow JSON files written with full error handling chain
    - 1 orchestrator JSON written with 3 sections + error handling
    - 1 global error watcher JSON written
    - All 9 files are valid JSON with correct n8n 2.x node schemas
    - All Execute Command nodes have continueOnFail: true
    - All HTTP Request (Discord) nodes have continueOnFail: true
    - All workflows set to active: false in JSON
  </done>
</task>

<task type="auto">
  <name>Task 2: Deploy all 9 workflows to n8n, inject IDs, test, activate, and update docs</name>
  <files>
    workflows/n8n/ris_orchestrator.json
    workflows/n8n/workflow_ids.env
    workflows/n8n/README.md
    docs/dev_logs/2026-04-07_n8n-workflow-rebuild.md
  </files>
  <action>
**Step 1: Deploy 7 sub-workflows first (capture IDs).**

Load API key:
```bash
N8N_API_KEY=$(grep N8N_API_KEY .env | cut -d'=' -f2)
```

For each of the 7 sub-workflow JSON files, POST to create:
```bash
NEW_ID=$(curl -s -X POST "http://localhost:5678/api/v1/workflows" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @workflows/n8n/ris_sub_XXXX.json | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

Record all 7 new IDs. Write them immediately to `workflows/n8n/workflow_ids.env`.

**Step 2: Deploy global error watcher.**

POST `ris_global_error_watcher.json` via API. Capture its ID. Add to workflow_ids.env as `RIS_GLOBAL_ERROR_WATCHER_ID`.

**Step 3: Inject sub-workflow IDs into orchestrator.**

Read `workflows/n8n/ris_orchestrator.json`. Replace all `PLACEHOLDER_ID` values in
Execute Workflow nodes with the actual sub-workflow IDs captured in Step 1. The mapping:
- academic -> RIS_SUB_ACADEMIC_ID
- reddit -> RIS_SUB_REDDIT_ID
- blog -> RIS_SUB_BLOG_RSS_ID
- youtube -> RIS_SUB_YOUTUBE_ID
- github -> RIS_SUB_GITHUB_ID
- digest -> RIS_SUB_WEEKLY_DIGEST_ID
- freshness -> RIS_SUB_FRESHNESS_REFRESH_ID

Write updated orchestrator JSON back to disk.

**Step 4: Deploy orchestrator.**

POST the updated orchestrator JSON. Capture its ID. Add to workflow_ids.env as `RIS_ORCHESTRATOR_ID`.

**Step 5: Set error workflow on all 8 RIS workflows.**

For each of the 8 workflows (7 subs + 1 orchestrator), PUT to update settings:
```bash
curl -s -X PUT "http://localhost:5678/api/v1/workflows/${WF_ID}" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"settings": {"errorWorkflow": "ERROR_WATCHER_ID"}}'
```

Remember: strip `notes`, `meta`, `tags`, `triggerCount`, `active` from PUT body.
Read the workflow first via GET, modify settings.errorWorkflow, strip disallowed fields, then PUT.

**Step 6: Tag all 9 workflows with RIS tag.**

```bash
curl -s -X PUT "http://localhost:5678/api/v1/workflows/${WF_ID}/tags" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '[{"id": "lsdE5zgirb6IHxH5"}]'
```

**Step 7: Test each workflow via API before activating.**

For each workflow, trigger a manual test execution via n8n API or use the manual trigger.
At minimum, verify the workflow can be loaded and activated without "Unrecognized node type"
or schema validation errors.

If any workflow fails activation due to node type issues, fix the JSON and redeploy.

**Step 8: Activate all 9 workflows.**

```bash
curl -s -X POST "http://localhost:5678/api/v1/workflows/${WF_ID}/activate" \
  -H "X-N8N-API-KEY: $N8N_API_KEY"
```

Confirm all 9 return `"active": true`.

**Step 9: Update workflow_ids.env with final IDs.**

```
RIS_SUB_ACADEMIC_ID=<new_id>
RIS_SUB_REDDIT_ID=<new_id>
RIS_SUB_BLOG_RSS_ID=<new_id>
RIS_SUB_YOUTUBE_ID=<new_id>
RIS_SUB_GITHUB_ID=<new_id>
RIS_SUB_WEEKLY_DIGEST_ID=<new_id>
RIS_SUB_FRESHNESS_REFRESH_ID=<new_id>
RIS_ORCHESTRATOR_ID=<new_id>
RIS_GLOBAL_ERROR_WATCHER_ID=<new_id>
```

**Step 10: Update workflows/n8n/README.md.**

Add the error watcher to the workflow table. Document the new error handling pattern
(sub-workflow template: trigger -> exec [continueOnFail] -> IF exit code -> success/error ->
Discord alert). Document the global error watcher. Update the architecture diagram sections.
Add a "Rebuild History" note referencing this task replacing the quick-260406-ovg originals.

**Step 11: Write dev log `docs/dev_logs/2026-04-07_n8n-workflow-rebuild.md`.**

Include:
- What: Rebuilt all 8 RIS n8n workflows + added global error watcher (9 total)
- Why: Original workflows were skeletal (trigger->command only, no error handling)
- What changed: Full error handling chain, Discord alerts on failure, metrics parsing, global error catch-all
- All 9 workflow IDs
- Any deviations from plan or bugs encountered
- n8n node type lookup results (what MCP revealed about actual schemas)
- Verification results (activation success, routing checks)
  </action>
  <verify>
    <automated>source workflows/n8n/workflow_ids.env && N8N_API_KEY=$(grep N8N_API_KEY .env | cut -d'=' -f2) && echo "Checking 9 workflows..." && for ID in $RIS_SUB_ACADEMIC_ID $RIS_SUB_REDDIT_ID $RIS_SUB_BLOG_RSS_ID $RIS_SUB_YOUTUBE_ID $RIS_SUB_GITHUB_ID $RIS_SUB_WEEKLY_DIGEST_ID $RIS_SUB_FRESHNESS_REFRESH_ID $RIS_ORCHESTRATOR_ID $RIS_GLOBAL_ERROR_WATCHER_ID; do STATUS=$(curl -s "http://localhost:5678/api/v1/workflows/$ID" -H "X-N8N-API-KEY: $N8N_API_KEY" | python -c "import sys,json; d=json.load(sys.stdin); print(f'{d[\"name\"]}: active={d[\"active\"]}')" 2>/dev/null); echo "$STATUS"; done</automated>
    All 9 workflows exist in n8n, all show active=true. workflow_ids.env has 9 entries. README.md references all 9 workflows. Dev log exists at docs/dev_logs/2026-04-07_n8n-workflow-rebuild.md.
  </verify>
  <done>
    - 7 sub-workflows deployed with new IDs
    - 1 global error watcher deployed
    - Sub-workflow IDs injected into orchestrator, orchestrator deployed
    - Error workflow set on all 8 RIS workflows (points to error watcher)
    - All 9 tagged with RIS
    - All 9 activated (active=true confirmed via API)
    - workflow_ids.env has 9 entries (7 subs + orchestrator + error watcher)
    - README.md documents all 9 workflows with error handling architecture
    - Dev log written at docs/dev_logs/2026-04-07_n8n-workflow-rebuild.md
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| n8n -> Docker socket | executeCommand runs docker exec on host containers |
| Webhook -> n8n | External HTTP can trigger pipeline runs and URL ingest |
| n8n -> Discord | Outbound webhook posts (low risk, no secrets in payload) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | S (Spoofing) | Webhook endpoints | accept | Webhooks are localhost-only (n8n bound to 127.0.0.1 or Docker network); no external exposure in current deployment |
| T-quick-02 | T (Tampering) | URL ingest webhook | mitigate | research-acquire already validates URL and source_family; n8n expression interpolation uses quotes around {{ }} values to prevent shell injection |
| T-quick-03 | I (Info Disclosure) | Discord alerts | accept | Alerts contain only command stdout/stderr (no secrets); DISCORD_WEBHOOK_URL stored in n8n env, not in workflow JSON |
| T-quick-04 | D (DoS) | Webhook flood | accept | Localhost-only; no rate limiting needed for operator-only access |
| T-quick-05 | E (Elevation) | Docker exec | accept | polytool-ris-scheduler container already has restricted permissions; docker exec runs as container user, not host root |
</threat_model>

<verification>
1. All 8 old workflow IDs return 404 from GET /api/v1/workflows/{id}
2. All 9 new workflows return 200 with active=true from GET /api/v1/workflows/{id}
3. Each sub-workflow JSON contains: manualTrigger, scheduleTrigger, executeCommand (with continueOnFail), if, code, httpRequest nodes
4. Orchestrator JSON contains: scheduleTrigger, webhook (x2), switch (v2), executeWorkflow (x7), respondToWebhook, httpRequest nodes
5. Error watcher JSON contains: errorTrigger, code, httpRequest nodes
6. workflow_ids.env has exactly 9 lines (7 subs + orchestrator + error watcher)
7. All executeCommand nodes have `"onError": "continueRegularOutput"` or equivalent continueOnFail setting
8. All httpRequest Discord nodes have continueOnFail: true
9. No hardcoded Discord URLs -- all use `$env.DISCORD_WEBHOOK_URL`
</verification>

<success_criteria>
- 9 production-grade n8n workflows deployed and active
- Every sub-workflow has: trigger -> execute [continueOnFail] -> IF exit code -> success metrics / error alert pattern
- Orchestrator has 3 functional sections: health monitor, webhook trigger, URL ingest
- Global error watcher catches unhandled errors from all 8 RIS workflows
- All Discord alerts use $env.DISCORD_WEBHOOK_URL (not hardcoded)
- workflow_ids.env, README.md, and dev log all updated
</success_criteria>

<output>
After completion, create `.planning/quick/260407-inu-rebuild-ris-n8n-workflows-full-error-han/260407-inu-SUMMARY.md`
</output>
