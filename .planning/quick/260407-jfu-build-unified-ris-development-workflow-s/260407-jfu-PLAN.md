---
quick_id: 260407-jfu
title: Build Unified RIS n8n Development Workflow
type: quick-execute
autonomous: true
files_modified:
  - workflows/n8n/ris-unified-dev.json
  - workflows/n8n/workflow_ids.env
  - workflows/n8n/README.md
  - docs/dev_logs/2026-04-07_n8n-unified-workflow.md
---

<objective>
Build a single unified n8n workflow called "RIS -- Research Intelligence System" that
consolidates ALL 9 existing RIS workflows (7 sub-workflows + orchestrator + error watcher)
onto one canvas with ~87 nodes across 9 horizontal sections. This replaces the multi-workflow
architecture with a single-workflow-per-canvas approach for easier visual development.

Purpose: Eliminate cross-workflow ID wiring, simplify deployment to a single POST, and provide
a single-pane development view of all RIS pipelines.

Output: `workflows/n8n/ris-unified-dev.json` deployed and activated in n8n.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@workflows/n8n/ris_orchestrator.json (existing orchestrator -- reference node patterns, connection format, IF v2 conditions schema)
@workflows/n8n/ris_sub_academic.json (existing sub-workflow -- reference source pipeline template)
@workflows/n8n/ris_sub_weekly_digest.json (existing digest -- reference two-command + always-discord pattern)
@workflows/n8n/workflow_ids.env (current deployed IDs -- need to delete these)
@workflows/n8n/README.md (current inventory docs)

<interfaces>
<!-- n8n REST API patterns (from existing deployment scripts) -->
Create workflow:  POST /api/v1/workflows  (body = workflow JSON, NO "active" field)
Activate:         PATCH /api/v1/workflows/{id}  (body = {"active": true})
List workflows:   GET /api/v1/workflows
Delete workflow:  DELETE /api/v1/workflows/{id}
Auth header:      X-N8N-API-KEY: $N8N_API_KEY

<!-- n8n node type versions used in existing workflows -->
scheduleTrigger:    typeVersion 1
manualTrigger:      typeVersion 1
webhook:            typeVersion 1
executeCommand:     typeVersion 1
if:                 typeVersion 2
code:               typeVersion 2
httpRequest:        typeVersion 4.2
stickyNote:         typeVersion 1
set:                typeVersion 3.4
noOp:               typeVersion 1
respondToWebhook:   typeVersion 1

<!-- Docker exec pattern -->
Command template: docker exec CONTAINER python -m polytool COMMAND 2>&1
CONTAINER discovered at runtime: docker compose ps --format "{{.Name}}" | grep polytool | grep -v n8n | grep -v grafana | grep -v clickhouse | grep -v pair | head -1

<!-- Discord webhook pattern -->
URL: ={{ $env.DISCORD_WEBHOOK_URL }}
Body: ={{ JSON.stringify({ content: $json.content }) }}
All Discord httpRequest nodes: continueOnFail: true

<!-- IF node v2 conditions schema (from existing orchestrator) -->
exitCode check: { leftValue: "={{ $json.exitCode }}", rightValue: 0, operator: { type: "number", operation: "equals" } }
boolean check:  { leftValue: "={{ $json.hasAlert }}", operator: { type: "boolean", operation: "true" } }
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Environment discovery and cleanup of existing RIS workflows</name>
  <files>workflows/n8n/workflow_ids.env</files>
  <action>
  Step 0: Discover runtime environment.
  ```bash
  N8N_API_KEY=$(grep N8N_API_KEY .env | cut -d'=' -f2)
  CONTAINER=$(docker compose ps --format "{{.Name}}" | grep -m1 "polytool" | grep -v n8n | grep -v grafana | grep -v clickhouse | grep -v pair)
  ```
  Confirm both values are non-empty. If N8N_API_KEY missing, check `.env`. If CONTAINER
  missing, try `docker compose ps` to see what is running.

  Step 1: Query n8n for all existing workflows.
  ```bash
  curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows
  ```
  From the response, find ALL workflows whose name contains "RIS" (case-insensitive).
  Extract each workflow ID.

  Step 2: DELETE each RIS workflow.
  ```bash
  curl -s -X DELETE -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows/$WF_ID
  ```
  Iterate through all found IDs. Log each deletion. Expect ~9 workflows to delete
  (7 subs + orchestrator + error watcher). Some may have already been deleted -- 404 is fine.

  Step 3: Verify cleanup.
  ```bash
  curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows | python3 -c "import sys,json; wfs=json.load(sys.stdin)['data']; ris=[w for w in wfs if 'RIS' in w.get('name','').upper()]; print(f'{len(ris)} RIS workflows remain')"
  ```
  Must show "0 RIS workflows remain".
  </action>
  <verify>
  curl to list workflows returns zero RIS-named entries. Both N8N_API_KEY and CONTAINER
  env vars are set and validated.
  </verify>
  <done>All existing RIS workflows deleted from n8n. CONTAINER name and N8N_API_KEY captured for subsequent tasks.</done>
</task>

<task type="auto">
  <name>Task 2: Build the unified workflow JSON file</name>
  <files>workflows/n8n/ris-unified-dev.json</files>
  <action>
  Create `workflows/n8n/ris-unified-dev.json` -- a single n8n workflow JSON with ~87 nodes
  across 9 horizontal sections. Use CONTAINER name discovered in Task 1 via the expression
  pattern (but note: executeCommand nodes use a hardcoded string since n8n executeCommand
  does not support expressions in `command` field -- use the CONTAINER name from Task 1).

  IMPORTANT: The docker exec container name must NOT be hardcoded as a literal. Instead,
  use the actual container name discovered from `docker compose ps` in Task 1. Store it
  and use it consistently in all executeCommand nodes.

  **Layout: 9 sections stacked vertically, ~350px Y gaps between sections.**

  Use unique node IDs with section prefix (e.g., `s1-health-cron`, `s2-acad-schedule`).
  Use unique descriptive node names with section prefix (e.g., "Health: Schedule", "Academic: Run Job").

  ---

  **SECTION 1 -- Health Monitor (y=0)**
  Sticky note at (150, 0), w=1700, h=50, content="## Section 1: Health Monitor -- Every 30min"

  Nodes (all at y=120 except where noted):
  1. "Health: Schedule" (scheduleTrigger, 250,120) -- minutesInterval: 30
  2. "Health: Run research-health" (executeCommand, 550,120) -- continueOnFail:true
     command: `docker exec CONTAINER python -m polytool research-health 2>&1`
  3. "Health: Run research-stats" (executeCommand, 850,120) -- continueOnFail:true
     command: `docker exec CONTAINER python -m polytool research-stats summary 2>&1`
  4. "Health: Parse Output" (code, 1150,120) -- jsCode checks stdout of both commands
     for "RED", "CRITICAL", "FAIL", "ERROR", "pipeline_failed", or non-zero exitCode.
     Returns { hasRed, healthOutput (1200 chars), statsOutput (800 chars), healthExit, statsExit }.
  5. "Health: RED?" (if, 1450,120) -- boolean check: $json.hasRed equals true
  6. "Health: Alert Discord" (httpRequest, 1700,60) -- Discord red embed, continueOnFail:true
     Format alert as: `**RIS Health Alert**\n\nHealth exit: {healthExit} | Stats exit: {statsExit}\n\n**Health:**\n```\n{healthOutput}\n```\n\n**Stats:**\n```\n{statsOutput}\n````
  7. "Health: OK" (noOp, 1700,200)

  Connections:
  Schedule -> research-health -> research-stats -> Parse -> RED? -> [true: Format Alert code node -> Discord] [false: OK]

  Note: Add a "Health: Format Alert" code node at (1700,60) BEFORE the Discord httpRequest
  at (1950,60) to format the content string. The Discord node sends $json.content.

  ---

  **SECTIONS 2-7 -- Source Pipelines**
  Each follows an identical template. Use section-prefixed unique names.

  Template for section S at y=Y, with name NAME, job JOB, schedule config SCHED:

  Sticky note at (150, Y), w=1700, h=50, content="## Section S: NAME Pipeline -- SCHEDULE_DESC"

  Nodes:
  1. "NAME: Schedule" (scheduleTrigger, 250, Y+120) -- SCHED params
  2. "NAME: Manual" (manualTrigger, 250, Y+240) -- no params
  3. "NAME: Run Job" (executeCommand, 550, Y+170) -- continueOnFail:true
     command: `docker exec CONTAINER python -m polytool research-scheduler run-job JOB 2>&1`
  4. "NAME: Exit OK?" (if, 850, Y+170) -- exitCode == 0
  5. "NAME: Parse Metrics" (code, 1150, Y+80) -- success path
     jsCode: parse stdout, return { status:'success', job:'JOB', stdout (1500), lineCount, timestamp }
  6. "NAME: Done" (set, 1450, Y+80) -- set { section:'NAME', status:'complete' }
  7. "NAME: Format Error" (code, 1150, Y+260) -- failure path
     jsCode: extract stderr (1500 chars), exitCode, format Discord content string
  8. "NAME: Alert Discord" (httpRequest, 1450, Y+260) -- Discord, continueOnFail:true

  Connections:
  Schedule -> Run Job
  Manual -> Run Job
  Run Job -> Exit OK?
  Exit OK? true -> Parse Metrics -> Done
  Exit OK? false -> Format Error -> Alert Discord

  Section specs:
  | Sec | Y    | NAME      | JOB               | SCHED                                    | SCHEDULE_DESC        |
  |-----|------|-----------|--------------------|------------------------------------------|----------------------|
  |  2  |  350 | Academic  | academic_ingest    | hoursInterval: 12                        | Every 12h            |
  |  3  |  700 | Reddit    | reddit_polymarket  | hoursInterval: 6                         | Every 6h             |
  |  4  | 1050 | Blog      | blog_ingest        | hoursInterval: 4                         | Every 4h             |
  |  5  | 1400 | YouTube   | youtube_ingest     | cronExpression: "0 0 4 * * 1"            | Weekly Mon 04:00 UTC |
  |  6  | 1750 | GitHub    | github_ingest      | cronExpression: "0 0 4 * * 3"            | Weekly Wed 04:00 UTC |
  |  7  | 2100 | Freshness | freshness_refresh  | cronExpression: "0 0 2 * * 0"            | Weekly Sun 02:00 UTC |

  ---

  **SECTION 8 -- Weekly Digest (y=2450)**
  Sticky note at (150, 2450), w=1700, h=50, content="## Section 8: Weekly Digest -- Sunday 08:00 UTC"

  Nodes:
  1. "Digest: Schedule" (scheduleTrigger, 250, 2570) -- cronExpression: "0 0 8 * * 0"
  2. "Digest: Manual" (manualTrigger, 250, 2690)
  3. "Digest: Run Report" (executeCommand, 550, 2620) -- continueOnFail:true
     command: `docker exec CONTAINER python -m polytool research-report digest --window 7 2>&1`
  4. "Digest: Report OK?" (if, 850, 2620) -- exitCode == 0
  5. TRUE path:
     - "Digest: Run Stats" (executeCommand, 1150, 2530) -- continueOnFail:true
       command: `docker exec CONTAINER python -m polytool research-stats summary 2>&1`
     - "Digest: Parse" (code, 1450, 2530) -- combine report + stats stdout, format green Discord embed
     - "Digest: Discord Report" (httpRequest, 1750, 2530) -- Discord green embed, continueOnFail:true
  6. FALSE path:
     - "Digest: Format Error" (code, 1150, 2710) -- extract stderr, format red Discord content
     - "Digest: Alert Discord" (httpRequest, 1450, 2710) -- Discord red embed, continueOnFail:true

  Connections:
  Schedule -> Run Report
  Manual -> Run Report
  Run Report -> Report OK?
  Report OK? true -> Run Stats -> Parse -> Discord Report
  Report OK? false -> Format Error -> Alert Discord

  ---

  **SECTION 9 -- URL Ingestion (y=2800)**
  Sticky note at (150, 2800), w=1700, h=50, content="## Section 9: URL Ingestion -- POST /webhook/ris-ingest"

  Nodes:
  1. "Ingest: Webhook" (webhook, 250, 2920) -- POST, path="ris-ingest", responseMode="responseNode"
  2. "Ingest: Run Acquire" (executeCommand, 550, 2920) -- continueOnFail:true
     command: `=docker exec CONTAINER python -m polytool research-acquire --url "{{ $json.body.url }}" --source-family "{{ $json.body.source_family }}" --no-eval 2>&1`
     NOTE: This command starts with `=` to enable n8n expressions for dynamic URL/family.
  3. "Ingest: OK?" (if, 850, 2920) -- exitCode == 0
  4. TRUE path:
     - "Ingest: Format Success" (code, 1150, 2830) -- format success response JSON
     - "Ingest: Respond 200" (respondToWebhook, 1450, 2830) -- respondWith: json, status 200
  5. FALSE path:
     - "Ingest: Format Fail" (code, 1150, 3010) -- format error content for Discord + response
     - "Ingest: Respond 500" (respondToWebhook, 1450, 3010) -- respondWith: json, status 500

  Connections:
  Webhook -> Run Acquire -> OK?
  OK? true -> Format Success -> Respond 200
  OK? false -> Format Fail -> Respond 500

  ---

  **Top-level JSON structure:**
  ```json
  {
    "name": "RIS -- Research Intelligence System",
    "nodes": [ ... all ~87 nodes ... ],
    "connections": { ... all connections by node name ... },
    "settings": { "executionOrder": "v1" }
  }
  ```
  Do NOT include "active", "id", or "tags" fields at the top level (n8n rejects them on POST).

  **Validation before writing:**
  - Count total nodes. Should be ~87 (+/- 5 is fine).
  - Every node has: id (unique), name (unique), type, typeVersion, position, parameters.
  - Every executeCommand and httpRequest node has continueOnFail: true.
  - Every connection references node names that exist in the nodes array.
  - No duplicate node names.
  </action>
  <verify>
  ```bash
  python3 -c "
  import json
  with open('workflows/n8n/ris-unified-dev.json') as f:
      wf = json.load(f)
  nodes = wf['nodes']
  names = [n['name'] for n in nodes]
  ids = [n['id'] for n in nodes]
  assert len(names) == len(set(names)), f'Duplicate names: {[n for n in names if names.count(n)>1]}'
  assert len(ids) == len(set(ids)), f'Duplicate ids: {[i for i in ids if ids.count(i)>1]}'
  exec_cmd = [n for n in nodes if n['type'] == 'n8n-nodes-base.executeCommand']
  for n in exec_cmd:
      assert n.get('continueOnFail', False), f'{n[\"name\"]} missing continueOnFail'
  http_req = [n for n in nodes if n['type'] == 'n8n-nodes-base.httpRequest']
  for n in http_req:
      assert n.get('continueOnFail', False), f'{n[\"name\"]} missing continueOnFail'
  conn_names = set()
  for src, conns in wf['connections'].items():
      conn_names.add(src)
      for output in conns.get('main', []):
          for c in output:
              conn_names.add(c['node'])
  missing = conn_names - set(names)
  assert not missing, f'Connections reference missing nodes: {missing}'
  print(f'OK: {len(nodes)} nodes, {len(exec_cmd)} executeCommand (all continueOnFail), {len(http_req)} httpRequest (all continueOnFail), 0 broken connections')
  "
  ```
  </verify>
  <done>
  `workflows/n8n/ris-unified-dev.json` exists, is valid JSON, has ~87 unique-named nodes across
  9 sections, all executeCommand/httpRequest have continueOnFail:true, and all connection
  references resolve to existing node names.
  </done>
</task>

<task type="auto">
  <name>Task 3: Deploy, test webhook, activate, and update tracking files</name>
  <files>workflows/n8n/workflow_ids.env, workflows/n8n/README.md</files>
  <action>
  Step 1: Deploy the workflow to n8n.
  ```bash
  RESULT=$(curl -s -X POST -H "X-N8N-API-KEY: $N8N_API_KEY" -H "Content-Type: application/json" \
    -d @workflows/n8n/ris-unified-dev.json http://localhost:5678/api/v1/workflows)
  WF_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  echo "Deployed with ID: $WF_ID"
  ```
  If the POST returns an error (e.g., "active" field rejected, duplicate names), fix the JSON
  and retry. Common issues:
  - Remove any "active" field from the JSON before POST
  - Ensure no duplicate node names
  - Ensure all typeVersions match what n8n expects

  Step 2: Activate the workflow.
  ```bash
  curl -s -X PATCH -H "X-N8N-API-KEY: $N8N_API_KEY" -H "Content-Type: application/json" \
    -d '{"active":true}' http://localhost:5678/api/v1/workflows/$WF_ID
  ```

  Step 3: Test the webhook endpoint.
  ```bash
  curl -s -X POST http://localhost:5678/webhook/ris-ingest \
    -H "Content-Type: application/json" \
    -d '{"url":"https://arxiv.org/abs/2510.15205","source_family":"academic"}'
  ```
  This should return a JSON response (200 or 500 depending on whether the container can
  actually run the command -- either response proves the webhook is wired correctly).
  If "webhook not registered" error, the workflow may need to be activated first or the
  webhook path may be wrong.

  Step 4: Update workflow_ids.env.
  Replace the entire file content with:
  ```
  # RIS n8n Workflow IDs
  # Updated 2026-04-07 -- unified single-canvas workflow
  # Previous architecture: 9 separate workflows (see git history for old IDs)

  UNIFIED_DEV_ID={WF_ID}
  ```

  Step 5: Update workflows/n8n/README.md.
  Rewrite to document the new unified workflow architecture. Include:
  - New single-workflow approach (1 workflow, ~87 nodes, 9 sections)
  - Section inventory table (section number, name, trigger type, schedule, node count)
  - Error handling pattern (continueOnFail on all executeCommand/httpRequest)
  - Webhook endpoints (/webhook/ris-ingest)
  - Docker exec command pattern
  - Discord alerting pattern
  - Deployment instructions (single POST + PATCH activate)
  - Re-deployment instructions
  - Environment variables required
  </action>
  <verify>
  ```bash
  # Verify workflow is active in n8n
  N8N_API_KEY=$(grep N8N_API_KEY .env | cut -d'=' -f2)
  UNIFIED_ID=$(grep UNIFIED_DEV_ID workflows/n8n/workflow_ids.env | cut -d'=' -f2)
  STATUS=$(curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows/$UNIFIED_ID | python3 -c "import sys,json; print(json.load(sys.stdin).get('active', False))")
  echo "Workflow $UNIFIED_ID active: $STATUS"
  # Verify exactly 1 RIS workflow exists
  COUNT=$(curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows | python3 -c "import sys,json; wfs=json.load(sys.stdin)['data']; print(len([w for w in wfs if 'RIS' in w.get('name','').upper()]))")
  echo "RIS workflow count: $COUNT"
  ```
  Must show: active=True, count=1.
  </verify>
  <done>
  Unified RIS workflow deployed and activated in n8n. Webhook endpoint responds.
  workflow_ids.env updated with UNIFIED_DEV_ID. README.md rewritten for new architecture.
  Exactly 1 RIS workflow exists in n8n (the unified one).
  </done>
</task>

<task type="auto">
  <name>Task 4: Write dev log and SUMMARY</name>
  <files>docs/dev_logs/2026-04-07_n8n-unified-workflow.md</files>
  <action>
  Write `docs/dev_logs/2026-04-07_n8n-unified-workflow.md` with:

  - **What:** Consolidated 9 separate RIS n8n workflows into 1 unified single-canvas workflow.
  - **Why:** Multi-workflow architecture required cross-workflow ID wiring, had 9 separate
    deployments, and the orchestrator's executeWorkflow nodes were fragile. Single canvas
    gives a unified development view and simpler deployment.
  - **Architecture change:** 7 sub-workflows + 1 orchestrator + 1 error watcher replaced by
    1 workflow with 9 horizontal sections (~87 nodes).
  - **Sections:** List all 9 sections with their schedules and node counts.
  - **What was removed:** The orchestrator's webhook dispatcher (Section 2 of old orchestrator)
    is removed because each pipeline now has its own schedule + manual trigger directly.
    The global error watcher is removed because each section handles its own errors inline.
  - **What was preserved:** All schedules, all docker exec commands, all Discord alerting,
    continueOnFail patterns, URL ingest webhook.
  - **Deployment:** Single POST + PATCH. ID in workflow_ids.env.
  - **Testing:** Webhook test result.
  - **Files changed:** ris-unified-dev.json (new), workflow_ids.env (updated), README.md (rewritten).
  - **Old files:** ris_sub_*.json, ris_orchestrator.json, ris_global_error_watcher.json are
    still in the repo as historical reference but no longer deployed.

  Then write `.planning/quick/260407-jfu-build-unified-ris-development-workflow-s/260407-jfu-SUMMARY.md`
  following the summary template.
  </action>
  <verify>test -f docs/dev_logs/2026-04-07_n8n-unified-workflow.md && echo "Dev log exists"</verify>
  <done>Dev log written documenting the architectural change. SUMMARY.md created.</done>
</task>

</tasks>

<verification>
1. `workflows/n8n/ris-unified-dev.json` is valid JSON with ~87 nodes, unique names/IDs, all
   executeCommand/httpRequest have continueOnFail:true, all connections resolve.
2. Exactly 1 RIS workflow in n8n (unified), active=true.
3. Webhook endpoint /webhook/ris-ingest responds to POST.
4. `workflow_ids.env` has UNIFIED_DEV_ID.
5. Dev log at `docs/dev_logs/2026-04-07_n8n-unified-workflow.md`.
</verification>

<success_criteria>
- Single unified workflow deployed and active in n8n
- All 9 sections present: Health, Academic, Reddit, Blog, YouTube, GitHub, Freshness, Digest, URL Ingest
- All old RIS workflows deleted from n8n
- Webhook endpoint functional
- Zero duplicate node names in the JSON
- All executeCommand and httpRequest nodes have continueOnFail:true
- Dev log and SUMMARY written
</success_criteria>

<output>
After completion, create `.planning/quick/260407-jfu-build-unified-ris-development-workflow-s/260407-jfu-SUMMARY.md`
</output>
