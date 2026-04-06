---
phase: quick-260406-ovg
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
  - workflows/n8n/workflow_ids.env
  - workflows/n8n/README.md
  - docs/dev_logs/2026-04-06_ris_n8n_workflow_system.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "7 sub-workflows exist in n8n, each tagged with RIS"
    - "1 orchestrator workflow exists in n8n with 3 paths (Health Monitor, Manual Pipeline Trigger, URL Ingest), tagged RIS"
    - "All 8 workflows are deployed to n8n instance via REST API"
    - "All 8 workflows have been test-executed via API before activation"
    - "All workflow IDs are recorded in workflows/n8n/workflow_ids.env"
    - "All workflow JSON source files are saved to workflows/n8n/"
  artifacts:
    - path: "workflows/n8n/ris_sub_academic.json"
      provides: "Academic ingest sub-workflow (every 12h)"
    - path: "workflows/n8n/ris_sub_reddit.json"
      provides: "Reddit ingest sub-workflow (every 6h)"
    - path: "workflows/n8n/ris_sub_blog_rss.json"
      provides: "Blog/RSS ingest sub-workflow (every 4h)"
    - path: "workflows/n8n/ris_sub_youtube.json"
      provides: "YouTube ingest sub-workflow (weekly Mon 04:00)"
    - path: "workflows/n8n/ris_sub_github.json"
      provides: "GitHub ingest sub-workflow (weekly Wed 04:00)"
    - path: "workflows/n8n/ris_sub_weekly_digest.json"
      provides: "Weekly digest sub-workflow (Sun 08:00)"
    - path: "workflows/n8n/ris_sub_freshness_refresh.json"
      provides: "Freshness refresh sub-workflow (Sun 02:00)"
    - path: "workflows/n8n/ris_orchestrator.json"
      provides: "Orchestrator with Health Monitor, Manual Pipeline Trigger, URL Ingest"
    - path: "workflows/n8n/workflow_ids.env"
      provides: "Mapping of workflow names to n8n IDs"
    - path: "workflows/n8n/README.md"
      provides: "Documentation for the workflow system"
  key_links:
    - from: "ris_orchestrator.json"
      to: "sub-workflow IDs"
      via: "Execute Workflow nodes referencing sub-workflow IDs"
      pattern: "executeWorkflow"
---

<objective>
Build and deploy the complete RIS workflow system in n8n: 7 sub-workflows for each ingestion/maintenance job + 1 orchestrator with 3 paths (Health Monitor, Manual Pipeline Trigger, URL Ingest). All workflows tagged "RIS", deployed via n8n REST API, tested, and activated.

Purpose: Replace the simple single-command workflow templates in infra/n8n/workflows/ with a structured sub-workflow + orchestrator system that provides centralized control, health monitoring with Discord alerting, webhook-based manual triggering, and URL ingestion.

Output: 8 deployed n8n workflows, JSON source files in workflows/n8n/, workflow_ids.env, README.md, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docker-compose.yml (lines 130-229 — n8n + ris-scheduler services)
@D:/Coding Projects/Polymarket/PolyTool/infra/n8n/Dockerfile (n8n image with docker-cli)
@D:/Coding Projects/Polymarket/PolyTool/infra/n8n/import-workflows.sh (reference for container naming pattern)

<interfaces>
<!-- Existing n8n workflow JSON pattern — follow this structure for all new workflows -->
<!-- From infra/n8n/workflows/ris_academic_ingest.json (representative example): -->

Key structural elements:
- `"type": "n8n-nodes-base.manualTrigger"` — typeVersion 1, no parameters
- `"type": "n8n-nodes-base.scheduleTrigger"` — typeVersion 1, rule.interval[] for periodic or rule.cronExpression for cron
- `"type": "n8n-nodes-base.executeCommand"` — typeVersion 1, command string
- `"type": "n8n-nodes-base.webhook"` — typeVersion 1, POST, path, responseMode
- `"type": "n8n-nodes-base.set"` — typeVersion 2, values.string[] for output formatting
- connections use node name strings as keys, main[0][] array of {node, type:"main", index:0}
- active: false (always deploy inactive first)
- settings: { "executionOrder": "v1" }
- meta: { "instanceId": "polytool-ris-pilot", "templateCredsSetupCompleted": true }
- tags: [] (will use RIS tag ID after creation)
- All commands use: `docker exec polytool-ris-scheduler python -m polytool <command>`

Docker exec target container: `polytool-ris-scheduler` (from docker-compose.yml line 136)
- The n8n container has docker-cli and /var/run/docker.sock mounted
- n8n env var N8N_EXEC_CONTAINER defaults to polytool-ris-scheduler

n8n REST API base: http://localhost:5678
- Auth header: X-N8N-API-KEY from .env N8N_API_KEY
- API docs: /api/v1/workflows, /api/v1/tags, /api/v1/executions
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Build and deploy 7 sub-workflows + create RIS tag</name>
  <files>
    workflows/n8n/ris_sub_academic.json
    workflows/n8n/ris_sub_reddit.json
    workflows/n8n/ris_sub_blog_rss.json
    workflows/n8n/ris_sub_youtube.json
    workflows/n8n/ris_sub_github.json
    workflows/n8n/ris_sub_weekly_digest.json
    workflows/n8n/ris_sub_freshness_refresh.json
  </files>
  <action>
**Step 0: Verify n8n API access and discover the polytool exec container name.**

Read N8N_API_KEY from .env:
```
N8N_API_KEY=$(grep N8N_API_KEY .env | cut -d'=' -f2)
```

Test API access:
```
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows | head -c 200
```

Discover the exec container name (should be polytool-ris-scheduler):
```
docker ps --filter "name=polytool-ris" --format "{{.Names}}"
```
If container is not running, note it and use `polytool-ris-scheduler` as the hardcoded default per docker-compose.yml line 136 + N8N_EXEC_CONTAINER env var.

**Step 1: Create "RIS" tag in n8n via REST API.**

```
curl -s -X POST http://localhost:5678/api/v1/tags \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "RIS"}'
```

Capture the returned tag ID. If tag already exists (409), GET /api/v1/tags and find the RIS tag ID.

**Step 2: Use n8n-mcp tools to look up correct node types.**

Before writing any JSON, use the n8n MCP server to verify the correct node types, property names, and typeVersions for:
- Schedule Trigger (scheduleTrigger) — confirm typeVersion and rule format for both interval and cron
- Execute Command (executeCommand) — confirm typeVersion and command property
- Execute Workflow (for later orchestrator reference) — confirm how sub-workflow IDs are referenced
- Webhook trigger — confirm typeVersion and path/httpMethod properties
- IF node — confirm how conditional logic works for string contains checks
- Code node (or Function node) — confirm how to run JavaScript for stdout parsing
- HTTP Request node — confirm how to POST to Discord webhook URL

**Step 3: Create `workflows/n8n/` directory and build 7 sub-workflow JSON files.**

mkdir -p workflows/n8n

Each sub-workflow follows the established pattern from infra/n8n/workflows/ but with the RIS tag applied. Each has:
- A Manual Trigger node (for testing)
- A Schedule Trigger node (per schedule below)
- An Execute Command node calling `docker exec ${EXEC_CONTAINER} python -m polytool <command>`
- tags: [{"id": "<RIS_TAG_ID>", "name": "RIS"}] (use the ID from Step 1)
- active: false
- settings: { "executionOrder": "v1" }
- NO custom id field (let n8n assign IDs on import)

Sub-workflow specifications:

1. **ris_sub_academic.json** — "RIS Sub: Academic"
   - Schedule: Every 12 hours (rule.interval, field: "hours", hoursInterval: 12)
   - Command: `research-scheduler run-job academic_ingest`

2. **ris_sub_reddit.json** — "RIS Sub: Reddit"
   - Schedule: Every 6 hours (rule.interval, field: "hours", hoursInterval: 6)
   - Command: `research-scheduler run-job reddit_polymarket`

3. **ris_sub_blog_rss.json** — "RIS Sub: Blog/RSS"
   - Schedule: Every 4 hours (rule.interval, field: "hours", hoursInterval: 4)
   - Command: `research-scheduler run-job blog_ingest`

4. **ris_sub_youtube.json** — "RIS Sub: YouTube"
   - Schedule: Weekly Monday 04:00 UTC (rule.cronExpression: "0 4 * * 1")
   - Command: `research-scheduler run-job youtube_ingest`

5. **ris_sub_github.json** — "RIS Sub: GitHub"
   - Schedule: Weekly Wednesday 04:00 UTC (rule.cronExpression: "0 4 * * 3")
   - Command: `research-scheduler run-job github_ingest`

6. **ris_sub_weekly_digest.json** — "RIS Sub: Weekly Digest"
   - Schedule: Weekly Sunday 08:00 UTC (rule.cronExpression: "0 8 * * 0")
   - Command: TWO Execute Command nodes chained sequentially:
     - First: `research-report digest --window 7`
     - Second: `research-stats summary`
   - After both commands, add an HTTP Request node that always POSTs to Discord:
     - URL: Use expression `{{ $env.DISCORD_WEBHOOK_URL }}` (or use a placeholder string "DISCORD_WEBHOOK_URL_PLACEHOLDER" in the JSON with a note to replace)
     - POST body: JSON with content field containing the combined stdout from both commands
     - This node fires regardless of command exit codes (the digest always sends)

7. **ris_sub_freshness_refresh.json** — "RIS Sub: Freshness Refresh"
   - Schedule: Weekly Sunday 02:00 UTC (rule.cronExpression: "0 2 * * 0")
   - Command: `research-scheduler run-job freshness_refresh`

All command strings follow the pattern:
```
docker exec polytool-ris-scheduler python -m polytool <command>
```

**Step 4: Deploy each sub-workflow to n8n via REST API.**

For each of the 7 JSON files:
```
curl -s -X POST http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @workflows/n8n/<filename>.json
```

Capture the returned workflow ID from each response. Record all 7 IDs — these are needed for the orchestrator in Task 2.

If any deployment fails, inspect the error, fix the JSON, and retry.

**Step 5: Record sub-workflow IDs.**

Write each returned ID to `workflows/n8n/workflow_ids.env` (append mode, will be completed in Task 2):
```
RIS_SUB_ACADEMIC_ID=<id>
RIS_SUB_REDDIT_ID=<id>
RIS_SUB_BLOG_RSS_ID=<id>
RIS_SUB_YOUTUBE_ID=<id>
RIS_SUB_GITHUB_ID=<id>
RIS_SUB_WEEKLY_DIGEST_ID=<id>
RIS_SUB_FRESHNESS_REFRESH_ID=<id>
```
  </action>
  <verify>
    <automated>
# Verify all 7 sub-workflows are in n8n:
N8N_API_KEY=$(grep N8N_API_KEY .env | cut -d'=' -f2)
COUNT=$(curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows | python3 -c "import sys,json; wfs=json.load(sys.stdin)['data']; print(len([w for w in wfs if any(t['name']=='RIS' for t in w.get('tags',[]))]))")
echo "RIS-tagged workflows: $COUNT (expect >= 7)"
# Verify JSON files exist:
ls -1 workflows/n8n/ris_sub_*.json | wc -l
    </automated>
  </verify>
  <done>
7 sub-workflow JSON files saved to workflows/n8n/. All 7 deployed to n8n via REST API with RIS tag. Sub-workflow IDs recorded in workflows/n8n/workflow_ids.env. Each sub-workflow has Manual Trigger + Schedule Trigger + Execute Command node(s).
  </done>
</task>

<task type="auto">
  <name>Task 2: Build orchestrator, test all workflows, activate, write docs</name>
  <files>
    workflows/n8n/ris_orchestrator.json
    workflows/n8n/workflow_ids.env
    workflows/n8n/README.md
    docs/dev_logs/2026-04-06_ris_n8n_workflow_system.md
  </files>
  <action>
**Step 1: Build the orchestrator workflow JSON.**

The orchestrator has 3 independent paths, each with its own trigger. Build `workflows/n8n/ris_orchestrator.json` with name "RIS Orchestrator".

Use n8n-mcp tools to confirm Execute Workflow node type and how to reference sub-workflow IDs.

**Path A: Health Monitor (every 30 min)**
- Schedule Trigger: every 30 minutes (rule.interval, field: "minutes", minutesInterval: 30)
- Execute Command 1: `docker exec polytool-ris-scheduler python -m polytool research-health`
- Execute Command 2: `docker exec polytool-ris-scheduler python -m polytool research-stats summary`
- Code/Function node: Parse the stdout from research-health. Check if any line contains "RED" or "CRITICAL" or "FAIL". Set a boolean `hasAlert` on the output item.
  - Use n8n-mcp to confirm the correct Code node type (n8n-nodes-base.code or n8n-nodes-base.function)
- IF node: Check `hasAlert === true`
  - True branch: HTTP Request node → POST to Discord webhook URL (use `{{ $env.DISCORD_WEBHOOK_URL }}` or placeholder). Body: JSON with `content` field containing a formatted alert message with the health check output.
  - False branch: (nothing, execution ends)

**Path B: Manual Pipeline Trigger (webhook)**
- Webhook Trigger: POST /webhook/ris-trigger
  - Accepts JSON body: `{ "pipeline": "<job_name>" }`
- Switch node (or IF chain): Branch on `{{ $json.body.pipeline }}` value:
  - "academic" -> Execute Workflow node referencing RIS_SUB_ACADEMIC_ID
  - "reddit" -> Execute Workflow node referencing RIS_SUB_REDDIT_ID
  - "blog" -> Execute Workflow node referencing RIS_SUB_BLOG_RSS_ID
  - "youtube" -> Execute Workflow node referencing RIS_SUB_YOUTUBE_ID
  - "github" -> Execute Workflow node referencing RIS_SUB_GITHUB_ID
  - "digest" -> Execute Workflow node referencing RIS_SUB_WEEKLY_DIGEST_ID
  - "freshness" -> Execute Workflow node referencing RIS_SUB_FRESHNESS_REFRESH_ID
  - Use n8n-mcp to confirm the Switch node type and how to configure routing rules
  - Each Execute Workflow node uses the sub-workflow ID from Task 1

**Path C: URL Ingest (webhook)**
- Webhook Trigger: POST /webhook/ris-ingest
  - Accepts JSON body: `{ "url": "<url>", "source_family": "<family>" }`
- Execute Command node: `docker exec polytool-ris-scheduler python -m polytool research-acquire --url "{{ $json.body.url }}" --source-family "{{ $json.body.source_family }}" --no-eval`
- Set node: Format output with result, exit_code, url_ingested, source_family fields (same pattern as existing ris_manual_acquire.json)

All 3 paths are independent branches from their respective trigger nodes. They do not connect to each other.

- tags: [{"id": "<RIS_TAG_ID>", "name": "RIS"}]
- active: false
- settings: { "executionOrder": "v1" }

**Step 2: Deploy orchestrator to n8n.**

```
curl -s -X POST http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @workflows/n8n/ris_orchestrator.json
```

Capture orchestrator workflow ID. Append to workflow_ids.env:
```
RIS_ORCHESTRATOR_ID=<id>
```

**Step 3: Test each workflow via API.**

For each of the 8 workflows, trigger a test execution via the n8n API. Use the manual trigger path or the API test endpoint. Use n8n-mcp to confirm the correct API call for triggering a workflow execution.

The goal is to confirm each workflow can be triggered without n8n errors (the polytool commands may fail if the ris-scheduler container is not running, but the n8n workflow execution itself should succeed — the Execute Command node should run and capture the exit code).

For webhook-based paths in the orchestrator, test with curl:
```
# Path B test:
curl -s -X POST http://localhost:5678/webhook/ris-trigger \
  -H "Content-Type: application/json" \
  -d '{"pipeline": "academic"}'

# Path C test:
curl -s -X POST http://localhost:5678/webhook/ris-ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://arxiv.org/abs/2106.01345", "source_family": "academic"}'
```

Record test results. If any workflow has structural errors (wrong node types, bad connections), fix and redeploy.

**Step 4: Activate all 8 workflows.**

For each workflow ID in workflow_ids.env:
```
curl -s -X PATCH http://localhost:5678/api/v1/workflows/<id> \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"active": true}'
```

**Step 5: Write workflows/n8n/README.md.**

Include:
- Overview of the 7+1 workflow system
- Table of sub-workflows with name, schedule, polytool command
- Orchestrator paths (A, B, C) description
- How to deploy (API method + reference to workflow_ids.env)
- How to test via webhook
- Mutual exclusion warning about APScheduler (same as in existing infra/n8n/README.md)
- Link to ADR 0013

**Step 6: Write dev log.**

`docs/dev_logs/2026-04-06_ris_n8n_workflow_system.md` with:
- What was built (7 sub-workflows + 1 orchestrator)
- Workflow IDs and RIS tag
- Test results
- Any issues encountered
- Relationship to existing infra/n8n/workflows/ templates
  </action>
  <verify>
    <automated>
# Verify all 8 workflows deployed and active:
N8N_API_KEY=$(grep N8N_API_KEY .env | cut -d'=' -f2)
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
ris = [w for w in data if any(t['name']=='RIS' for t in w.get('tags',[]))]
print(f'RIS-tagged workflows: {len(ris)} (expect 8)')
active = [w for w in ris if w.get('active')]
print(f'Active: {len(active)} (expect 8)')
for w in ris:
    print(f'  {w[\"name\"]:40s} active={w.get(\"active\",False)}  id={w[\"id\"]}')
"
# Verify files exist:
ls -1 workflows/n8n/*.json workflows/n8n/workflow_ids.env workflows/n8n/README.md
# Verify dev log exists:
ls docs/dev_logs/2026-04-06_ris_n8n_workflow_system.md
    </automated>
  </verify>
  <done>
Orchestrator deployed with 3 paths (Health Monitor every 30min, Manual Pipeline Trigger webhook, URL Ingest webhook). All 8 workflows RIS-tagged, tested, and activated. workflow_ids.env has all 8 IDs. README.md documents the system. Dev log written.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Webhook -> n8n | External HTTP requests hit webhook endpoints; untrusted input |
| n8n -> Docker socket | n8n executes commands via docker exec; container escape risk |
| n8n -> Discord | Outbound HTTP to Discord webhook URL; URL is a secret |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-ovg-01 | Spoofing | Webhook endpoints | accept | n8n webhook URLs contain random token path segments; treat URLs as secrets per existing pattern |
| T-ovg-02 | Tampering | Webhook body.url | mitigate | polytool research-acquire validates URL format and source_family enum before fetching; no shell injection because docker exec does not use shell expansion |
| T-ovg-03 | Information Disclosure | Discord webhook URL | mitigate | Use $env.DISCORD_WEBHOOK_URL expression in n8n (not hardcoded); URL stored in n8n environment only |
| T-ovg-04 | Elevation of Privilege | Docker socket | accept | Pre-existing risk documented in ADR-0013; n8n can only exec into polytool-ris-scheduler container |
</threat_model>

<verification>
1. `curl -s -H "X-N8N-API-KEY: $KEY" http://localhost:5678/api/v1/workflows` shows 8 RIS-tagged workflows, all active
2. `curl -s -H "X-N8N-API-KEY: $KEY" http://localhost:5678/api/v1/tags` shows RIS tag exists
3. `ls workflows/n8n/*.json | wc -l` returns 8
4. `cat workflows/n8n/workflow_ids.env` shows 8 workflow IDs
5. Webhook test: POST to /webhook/ris-trigger with {"pipeline":"academic"} returns a response (even if command fails due to container state)
</verification>

<success_criteria>
- 7 sub-workflow JSON files in workflows/n8n/ matching the specification table
- 1 orchestrator JSON file with 3 paths (Health Monitor, Manual Trigger, URL Ingest)
- All 8 workflows deployed to n8n instance via REST API
- All 8 workflows tagged with "RIS"
- All 8 workflows tested via API (at minimum, no structural/node errors)
- All 8 workflows activated
- workflow_ids.env contains all 8 workflow IDs
- README.md documents the system
- Dev log written to docs/dev_logs/
</success_criteria>

<output>
After completion, create `.planning/quick/260406-ovg-build-ris-workflow-system-in-n8n/260406-ovg-SUMMARY.md`
</output>
