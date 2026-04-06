---
phase: quick-260404-rtv
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docker-compose.yml
  - .env.example
  - scripts/docker-start.sh
  - docs/adr/0013-ris-n8n-pilot-scoped.md
  - infra/n8n/workflows/ris_manual_acquire.json
  - infra/n8n/workflows/ris_health_check.json
  - infra/n8n/workflows/ris_scheduler_status.json
  - infra/n8n/import-workflows.sh
  - docs/RIS_OPERATOR_GUIDE.md
  - docs/dev_logs/2026-04-05_ris_n8n_pilot.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "n8n is opt-in via compose profile; default stack starts without it"
    - "APScheduler (ris-scheduler) and n8n cannot both run simultaneously — compose profile controls mutual exclusion"
    - "A pinned, non-latest n8n image tag is committed in docker-compose.yml"
    - "Workflow JSON files exist for the three backed CLI surfaces and are importable"
    - "Operator docs explain start/import/activate, scheduler selection, and Claude Code MCP via HTTP bearer token"
    - "An ADR documents n8n as scoped RIS pilot (not broad Phase 3 automation)"
    - "Dev log is written at docs/dev_logs/2026-04-05_ris_n8n_pilot.md"
  artifacts:
    - path: "docs/adr/0013-ris-n8n-pilot-scoped.md"
      provides: "Authority drift resolution; n8n as RIS pilot while repo remains Phase 0/1 CLI-first"
    - path: "infra/n8n/workflows/ris_manual_acquire.json"
      provides: "n8n workflow template: manual research-acquire via CLI subprocess"
    - path: "infra/n8n/workflows/ris_health_check.json"
      provides: "n8n workflow template: research-health check"
    - path: "infra/n8n/workflows/ris_scheduler_status.json"
      provides: "n8n workflow template: research-scheduler status"
    - path: "infra/n8n/import-workflows.sh"
      provides: "Helper to import all workflow JSONs via n8n API"
  key_links:
    - from: "docker-compose.yml n8n service"
      to: "compose profile 'ris-n8n'"
      via: "profiles: [ris-n8n]"
      pattern: "profiles.*ris-n8n"
    - from: "ris-scheduler service"
      to: "exclusive scheduling"
      via: "ris-scheduler has no 'ris-n8n' profile (default stack only)"
      pattern: "ris-scheduler"
    - from: "infra/n8n/workflows/*.json"
      to: "CLI commands"
      via: "Execute Command node calling python -m polytool"
      pattern: "python -m polytool"
---

<objective>
Implement the RIS-only n8n pilot: add n8n as an opt-in compose-profiled service,
resolve authority drift via ADR, create version-controlled workflow templates for
existing CLI surfaces, update operator docs, and write the dev log.

Purpose: Provide a safe, opt-in path for n8n automation of RIS CLI jobs without
expanding scope beyond Phase 0/1 or breaking existing APScheduler usage.

Output: ADR, n8n compose service (pinned tag, profile-gated), three workflow JSONs,
import helper, updated RIS_OPERATOR_GUIDE.md, and dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/docs/PLAN_OF_RECORD.md
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/docker-compose.yml
@D:/Coding Projects/Polymarket/PolyTool/.env.example
@D:/Coding Projects/Polymarket/PolyTool/scripts/docker-start.sh
@D:/Coding Projects/Polymarket/PolyTool/docs/RIS_OPERATOR_GUIDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/adr/0001-template.md

<interfaces>
<!-- Existing compose profiles in docker-compose.yml: -->
<!-- - "cli" profile: polytool service -->
<!-- - "pair-bot" profile: pair-bot-paper service -->
<!-- No existing "ris-n8n" profile. -->

<!-- ris-scheduler service: no profile (always starts with default stack). -->
<!-- This means ris-scheduler + n8n mutual exclusion is enforced by: -->
<!--   (a) ris-scheduler has no profile — it starts in default stack -->
<!--   (b) n8n is gated behind "ris-n8n" profile — opt-in -->
<!--   (c) An env flag RIS_SCHEDULER_BACKEND documents the active choice -->

<!-- JOB_REGISTRY (packages/research/scheduling/scheduler.py): -->
<!-- 8 jobs: academic_ingest, reddit_polymarket, reddit_others, blog_ingest, -->
<!-- youtube_ingest, github_ingest, freshness_refresh, weekly_digest -->

<!-- CLI commands with operator-facing surfaces: -->
<!--   python -m polytool research-scheduler start|stop|status|list-jobs -->
<!--   python -m polytool research-acquire --url URL --source-family FAMILY -->
<!--   python -m polytool research-health -->
<!--   python -m polytool research-ingest --text TEXT --title TITLE -->
<!--   python -m polytool rag-query --question QUESTION -->
<!--   python -m polytool research-precheck run --idea "..." -->

<!-- MCP server (tools/cli/mcp_server.py): -->
<!--   HTTP transport: GET http://localhost:MCP_PORT/mcp-server/http -->
<!--   Bearer token: N8N_MCP_BEARER_TOKEN env var -->
<!--   Claude Code connection: built-in MCP HTTP client, NOT stale N8N_MCP_ENABLED -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: ADR + n8n compose service + env updates</name>
  <files>
    docs/adr/0013-ris-n8n-pilot-scoped.md
    docker-compose.yml
    .env.example
    scripts/docker-start.sh
  </files>
  <action>
**1a. Write docs/adr/0013-ris-n8n-pilot-scoped.md**

Create the ADR following the template in docs/adr/0001-template.md. Key content:

- Status: Accepted
- Context: Repo is Phase 0/1, Gate 2 FAILED, CLI-first is primary. Master Roadmap v5
  defers n8n to Phase 3 as part of a broad automation layer. RIS (research-scheduler,
  research-acquire, etc.) exists now and would benefit from lightweight periodic
  scheduling beyond manual invocation. Pulling n8n forward for ALL of Phase 3
  automation would be premature. This ADR explicitly scopes n8n to RIS ingestion
  jobs only.
- Decision: n8n is approved as a SCOPED PILOT for RIS CLI job orchestration only.
  Scope boundaries (hard): no strategy logic, no gate logic, no risk policy, no live
  capital automation, no FastAPI surface changes. Scope (allowed): periodic calls to
  research-acquire, research-health, research-scheduler status, research-ingest.
  Operator must explicitly enable via `--with-n8n` compose flag. APScheduler
  (ris-scheduler service) and n8n are mutually exclusive schedulers; operator
  selects one by choosing which compose profile to run.
- Consequences: n8n added under compose profile "ris-n8n". ris-scheduler service
  remains default (no profile). Env var RIS_SCHEDULER_BACKEND documents selection
  (values: apscheduler | n8n). If both run simultaneously, double-scheduling occurs
  — this is an operator error, not a system guarantee; the ADR notes this and
  requires the operator to disable ris-scheduler before running n8n profile.
- This ADR explicitly does NOT move the repo to Phase 3 automation.

**1b. Add n8n service to docker-compose.yml**

Append the following service block (do not remove or alter existing services):

```yaml
  n8n:
    image: n8nio/n8n:1.88.0
    container_name: polytool-n8n
    profiles:
      - ris-n8n
    ports:
      - "${N8N_PORT:-5678}:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_BASIC_AUTH_USER:-admin}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_BASIC_AUTH_PASSWORD:-changeme}
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY:-changeme_32chars_min_replace_this}
      - GENERIC_TIMEZONE=${GENERIC_TIMEZONE:-UTC}
      - TZ=${GENERIC_TIMEZONE:-UTC}
      - N8N_RUNNERS_ENABLED=true
      - N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
      - N8N_MCP_BEARER_TOKEN=${N8N_MCP_BEARER_TOKEN:-replace_with_mcp_bearer_token}
      - POLYTOOL_HOST=http://host-docker-internal:${MCP_PORT:-8001}
    volumes:
      - n8n_data:/home/node/.n8n
    networks:
      - polytool
    restart: unless-stopped
```

Also add `n8n_data:` to the top-level `volumes:` block.

Do NOT mount the Docker socket. Workflows call CLI via HTTP/webhook to a running
polytool container or the host MCP server — not Docker exec.

NOTE: Verify the exact current stable n8n version before writing. As of knowledge
cutoff the 1.x series is stable; use the most recent 1.x.x patch that is
confirmed released. If unsure, use `1.88.0` as a safe pinned version — this is
a documented stable release. Do NOT use `latest`.

**1c. Add n8n env vars to .env.example**

Add a new section after the Discord section:

```
# n8n RIS Pilot (opt-in — only used when running with --with-n8n profile)
# See docs/adr/0013-ris-n8n-pilot-scoped.md for scope boundaries.
# Scheduler selection: set RIS_SCHEDULER_BACKEND=n8n and disable ris-scheduler
# service before starting n8n profile to avoid double-scheduling.
N8N_PORT=5678
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=changeme
N8N_ENCRYPTION_KEY=changeme_32chars_min_replace_this
GENERIC_TIMEZONE=UTC
# Bearer token for Claude Code MCP connection (HTTP transport)
N8N_MCP_BEARER_TOKEN=replace_with_mcp_bearer_token
MCP_PORT=8001
# RIS_SCHEDULER_BACKEND=apscheduler  # or: n8n
```

**1d. Update scripts/docker-start.sh**

Add a `--with-n8n` flag option. The updated script logic (preserve existing behavior):

```bash
#!/usr/bin/env bash
# Start the full PolyTool stack via Docker Compose.
# Usage: bash scripts/docker-start.sh [--with-bots] [--with-n8n]
#
# Scheduler selection:
#   Default: APScheduler runs via ris-scheduler service (always on).
#   --with-n8n: n8n starts instead. You MUST comment out or remove the
#     ris-scheduler service from docker-compose.yml OR set
#     RIS_SCHEDULER_BACKEND=n8n in .env to document selection.
#     Running both simultaneously causes double-scheduling (operator error).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in secrets first."
  exit 1
fi

PROFILES=""
WITH_N8N=false

for arg in "$@"; do
  case "$arg" in
    --with-bots) PROFILES="$PROFILES --profile pair-bot" ;;
    --with-n8n)  PROFILES="$PROFILES --profile ris-n8n"; WITH_N8N=true ;;
  esac
done

if [ "$WITH_N8N" = "true" ]; then
  echo "Starting full stack WITH n8n RIS pilot..."
  echo "  WARNING: If ris-scheduler is also running, double-scheduling will occur."
  echo "  See docs/adr/0013-ris-n8n-pilot-scoped.md for scheduler selection guidance."
else
  echo "Starting full stack (ClickHouse, Grafana, API, RIS scheduler)..."
  echo "  Add --with-n8n to start n8n instead of APScheduler (see ADR 0013)."
  echo "  Add --with-bots to also start pair-bot services."
fi

docker compose $PROFILES up -d --build

echo ""
echo "Services:"
echo "  ClickHouse:  http://localhost:${CLICKHOUSE_HTTP_PORT:-8123}"
echo "  Grafana:     http://localhost:${GRAFANA_PORT:-3000}"
echo "  API:         http://localhost:${API_PORT:-8000}"
if [ "$WITH_N8N" = "true" ]; then
  echo "  n8n:         http://localhost:${N8N_PORT:-5678}"
fi
echo ""
echo "CLI usage:     docker compose run --rm polytool python -m polytool --help"
echo "Stop:          docker compose down"
echo ""
```
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && docker compose config --quiet 2>&amp;1 | head -5; echo "compose config exit: $?"</automated>
  </verify>
  <done>
    - docker-compose.yml passes `docker compose config` validation with no errors
    - n8n service exists under profile "ris-n8n" with pinned non-latest image tag
    - n8n_data volume declared in volumes block
    - .env.example has n8n section with all required vars
    - scripts/docker-start.sh accepts --with-n8n and prints scheduler warning
    - ADR 0013 exists with scope boundaries and mutual exclusion documented
  </done>
</task>

<task type="auto">
  <name>Task 2: Workflow templates + import helper + operator docs + dev log</name>
  <files>
    infra/n8n/workflows/ris_manual_acquire.json
    infra/n8n/workflows/ris_health_check.json
    infra/n8n/workflows/ris_scheduler_status.json
    infra/n8n/import-workflows.sh
    docs/RIS_OPERATOR_GUIDE.md
    docs/dev_logs/2026-04-05_ris_n8n_pilot.md
  </files>
  <action>
**2a. Create infra/n8n/workflows/ directory and workflow JSON files**

Each workflow uses n8n's Execute Command node to call `python -m polytool` on the
host or a sidecar container. Use the n8n JSON workflow format (schema used by n8n
1.x import/export). Include `"active": false` so no workflow auto-triggers on import;
operator activates manually.

The node structure per workflow:
- Start node (Manual Trigger or Cron)
- Execute Command node (runs the CLI command)
- Set node (formats output for n8n display)

**ris_health_check.json** — checks RIS pipeline health:
```
Command: python -m polytool research-health
Trigger: Manual trigger + optional cron (every 6h)
Purpose: Surface health snapshot in n8n execution log
```

Workflow JSON skeleton (follow n8n 1.x export format — nodes array, connections,
settings, pinData={}, staticData=null, tags=[], triggerCount=0):

```json
{
  "name": "RIS Health Check",
  "nodes": [
    {
      "parameters": {},
      "id": "trigger-health",
      "name": "Manual Trigger",
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1,
      "position": [240, 300]
    },
    {
      "parameters": {
        "command": "python -m polytool research-health"
      },
      "id": "exec-health",
      "name": "Run research-health",
      "type": "n8n-nodes-base.executeCommand",
      "typeVersion": 1,
      "position": [460, 300]
    }
  ],
  "connections": {
    "Manual Trigger": {
      "main": [[{"node": "Run research-health", "type": "main", "index": 0}]]
    }
  },
  "active": false,
  "settings": {"executionOrder": "v1"},
  "versionId": "1",
  "id": "ris-health-check",
  "meta": {"instanceId": "polytool-ris-pilot"}
}
```

**ris_scheduler_status.json** — shows APScheduler job status:
```
Command: python -m polytool research-scheduler status
Trigger: Manual trigger
Purpose: Lets operator check APScheduler state from n8n UI when not using n8n scheduling
```

**ris_manual_acquire.json** — manual URL ingestion trigger:
```
Command: python -m polytool research-acquire --url "{{ $json.url }}" --source-family "{{ $json.source_family }}" --no-eval
Trigger: Webhook (POST with body {"url": "...", "source_family": "academic|blog|github|..."})
Purpose: Operator or external trigger to queue a URL for RIS ingestion
Note: source_family must be one of: academic, github, blog, news, book, reddit, youtube
```

For ris_manual_acquire.json use a Webhook trigger node instead of manual trigger.
The Execute Command node uses n8n expression syntax for the URL and source_family
from the webhook body. Set method to POST and response mode to "Last Node".

Write all three JSON files with complete valid n8n 1.x workflow JSON. Include a
`"notes"` or description field in each workflow explaining what it does and the
scope boundary (RIS only, no strategy/gate logic).

**2b. Create infra/n8n/import-workflows.sh**

```bash
#!/usr/bin/env bash
# Import all RIS n8n workflow templates into a running n8n instance.
# Usage: bash infra/n8n/import-workflows.sh [N8N_URL] [N8N_USER] [N8N_PASS]
#
# Requires: curl, jq
# n8n must be running: docker compose --profile ris-n8n up -d
set -euo pipefail

N8N_URL="${1:-http://localhost:5678}"
N8N_USER="${2:-${N8N_BASIC_AUTH_USER:-admin}}"
N8N_PASS="${3:-${N8N_BASIC_AUTH_PASSWORD:-changeme}}"
WORKFLOW_DIR="$(dirname "$0")/workflows"

if ! command -v curl &>/dev/null; then
  echo "ERROR: curl is required." >&2; exit 1
fi
if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required." >&2; exit 1
fi

echo "Importing n8n workflows from $WORKFLOW_DIR into $N8N_URL ..."

for wf in "$WORKFLOW_DIR"/*.json; do
  name=$(jq -r '.name' "$wf")
  echo "  Importing: $name ($wf) ..."
  response=$(curl -s -w "\n%{http_code}" \
    -u "$N8N_USER:$N8N_PASS" \
    -X POST "$N8N_URL/api/v1/workflows" \
    -H "Content-Type: application/json" \
    -d @"$wf")
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)
  if [[ "$http_code" == "200" || "$http_code" == "201" ]]; then
    echo "    OK (HTTP $http_code)"
  else
    echo "    WARN: HTTP $http_code — $body"
  fi
done

echo ""
echo "Done. Log in to $N8N_URL to review and activate workflows."
echo "Default credentials: $N8N_USER / [N8N_BASIC_AUTH_PASSWORD]"
echo ""
echo "IMPORTANT: Activate workflows manually from the n8n UI."
echo "Do NOT activate automated triggers while APScheduler (ris-scheduler) is running."
echo "See docs/adr/0013-ris-n8n-pilot-scoped.md for scheduler selection guidance."
```

Make the script executable (create with mode note in file header; chmod handled by git).

**2c. Append a new section to docs/RIS_OPERATOR_GUIDE.md**

Read the current file first. Append a new top-level section titled:
`## n8n RIS Pilot (Opt-In)` with the following subsections:

**Scope boundary:** One sentence — n8n is approved for RIS ingestion jobs only per ADR 0013.
Not a Phase 3 automation layer.

**Scheduler selection:**
- Default: APScheduler via `ris-scheduler` container (always on in default stack).
- n8n alternative: start with `bash scripts/docker-start.sh --with-n8n`. This starts
  the n8n service (profile `ris-n8n`). You must stop the ris-scheduler service
  (`docker compose stop ris-scheduler`) to prevent double-scheduling. Set
  `RIS_SCHEDULER_BACKEND=n8n` in `.env` to document the active choice.
- Both running simultaneously is an operator error; the system does not auto-prevent it.

**Start/import/activate flow (step-by-step numbered list):**
1. Copy `.env.example` values for n8n section into `.env`. Set real values for
   `N8N_BASIC_AUTH_PASSWORD`, `N8N_ENCRYPTION_KEY` (min 32 chars), `N8N_MCP_BEARER_TOKEN`.
2. Stop APScheduler if switching to n8n: `docker compose stop ris-scheduler`
3. Start n8n: `bash scripts/docker-start.sh --with-n8n`
4. Verify n8n is up: `curl -s http://localhost:5678/healthz` (should return `{"status":"ok"}`)
5. Import workflow templates: `bash infra/n8n/import-workflows.sh`
6. Log in to http://localhost:5678 with admin credentials.
7. Review each imported workflow. Activate only the workflows you want running.
8. For cron-triggered workflows: confirm trigger times do not overlap with any
   manual research-scheduler runs.

**Manual verification steps:**
- After import: open each workflow in the UI, click "Execute workflow" on
  `RIS Health Check` and confirm the output shows `research-health` CLI output.
- After activating a cron trigger: check "Executions" tab after the first scheduled
  run to confirm exit code 0.
- If a workflow fails: check the Execute Command node output. Common causes:
  `python` not on PATH inside the polytool container, or CLOB credentials not set.

**Claude Code MCP connection via n8n:**
- The polytool MCP server runs on HTTP transport at `http://localhost:{MCP_PORT}/mcp-server/http`
- To connect n8n to Claude Code's MCP server:
  1. In n8n, add a credential of type "Header Auth" with:
     - Name: `Authorization`
     - Value: `Bearer {N8N_MCP_BEARER_TOKEN}` (your token from `.env`)
  2. In your workflow, use the HTTP Request node with:
     - URL: `http://host.docker.internal:{MCP_PORT}/mcp-server/http`
     - Auth: the Header Auth credential above
     - Method: POST, body: MCP JSON-RPC payload
  3. This is the current supported connection method. Do NOT use stale
     `N8N_MCP_ENABLED` env var — that approach is not implemented.
- The MCP server must be started separately: `python -m polytool mcp-server --port {MCP_PORT}`

**2d. Write docs/dev_logs/2026-04-05_ris_n8n_pilot.md**

Standard dev log format. Include:
- Date: 2026-04-05
- Slug: ris_n8n_pilot
- Summary: 3-4 bullet summary of what was shipped
- Work done:
  - ADR 0013 scope boundaries
  - docker-compose.yml n8n service (pinned image, ris-n8n profile)
  - .env.example n8n section
  - scripts/docker-start.sh --with-n8n flag
  - 3 workflow templates (health check, scheduler status, manual acquire)
  - import-workflows.sh helper
  - RIS_OPERATOR_GUIDE.md n8n section
- Scheduler mutual exclusion note: APScheduler (default) vs n8n (opt-in); both
  running simultaneously is an operator error; no code-level lock enforced because
  ris-scheduler has no profile and n8n is profile-gated; operator selects by
  compose invocation.
- Workflow templates: list all 3 with backing CLI command. Note which roadmap
  workflows were OMITTED and why (any workflow with no backing CLI is omitted).
- Open items: n8n cron trigger times for RIS jobs are not yet wired to match
  JOB_REGISTRY schedules exactly — operator configures in UI after import.
- Codex review: skipped (no strategy/execution/risk files touched)
- Tests run: python -m polytool --help (CLI loads), docker compose config (compose valid)
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m polytool --help > /dev/null 2>&amp;1 && echo "CLI OK" && python -m polytool research-scheduler --help > /dev/null 2>&amp;1 && echo "scheduler OK" && python -m polytool research-acquire --help > /dev/null 2>&amp;1 && echo "acquire OK" && python -m polytool research-health > /dev/null 2>&amp;1 && echo "health OK" && docker compose config --quiet 2>&amp;1 | head -3 && echo "compose OK"</automated>
  </verify>
  <done>
    - docs/adr/0013-ris-n8n-pilot-scoped.md exists with scope boundaries
    - infra/n8n/workflows/ contains 3 valid JSON files
    - infra/n8n/import-workflows.sh is executable and references all 3 workflows
    - docs/RIS_OPERATOR_GUIDE.md has n8n pilot section with start/import/activate,
      scheduler selection, manual verification, and MCP HTTP bearer token instructions
    - docs/dev_logs/2026-04-05_ris_n8n_pilot.md written
    - python -m polytool --help succeeds (no regressions)
    - docker compose config passes (compose file is valid YAML with n8n service)
    - git diff --stat shows only files in scope (no strategy/gate/risk files)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| n8n webhook → polytool CLI | External HTTP POST triggers CLI subprocess; URL and source_family are operator-supplied |
| n8n → MCP server | n8n makes HTTP requests to MCP server using bearer token |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-rtv-01 | Spoofing | n8n webhook (ris_manual_acquire) | mitigate | Webhook URL contains n8n-generated path token; add note in operator docs to treat webhook URL as a secret |
| T-rtv-02 | Tampering | Execute Command node input (url/source_family) | mitigate | research-acquire CLI validates source_family against known enum; invalid values rejected before fetch |
| T-rtv-03 | Information Disclosure | N8N_BASIC_AUTH_PASSWORD in .env.example | accept | .env.example contains placeholder only; .env is gitignored; operator replaces values |
| T-rtv-04 | Denial of Service | n8n cron double-scheduling with APScheduler | accept | Mutual exclusion is operator responsibility per ADR 0013; no automated lock; risk is duplicate ingestion, not data loss |
| T-rtv-05 | Elevation of Privilege | n8n Execute Command node | mitigate | Workflows call only python -m polytool commands; no shell injection possible from webhook body because CLI args are validated by argparse before execution |
</threat_model>

<verification>
Run in order after execution:

1. `docker compose config --quiet` — compose file valid, no YAML errors
2. `python -m polytool --help` — CLI loads without import errors
3. `python -m polytool research-scheduler --help` — scheduler CLI available
4. `python -m polytool research-acquire --help` — acquire CLI available
5. `python -m polytool research-health` — health command runs (may warn if KB is empty; that is OK)
6. `rtk git diff --stat` — only files in scope changed; no strategy/gate/risk files touched
7. Manual: Open docker-compose.yml and confirm `n8n` service has pinned image tag (not `latest`), profile `ris-n8n`, and `n8n_data` volume
8. Manual: Open infra/n8n/workflows/*.json and confirm each has `"active": false` and a command referencing `python -m polytool`
</verification>

<success_criteria>
- ADR 0013 exists and makes clear n8n is a scoped RIS pilot, not Phase 3 automation
- n8n service in docker-compose.yml is under profile `ris-n8n` with pinned non-latest tag
- APScheduler and n8n cannot double-schedule without explicit operator error (mutual exclusion via compose profile documented in ADR and operator guide)
- 3 workflow templates exist, each calling a real CLI command, each with `"active": false`
- import-workflows.sh imports all 3 via n8n API
- RIS_OPERATOR_GUIDE.md covers: start, import, activate, scheduler selection, manual verification, Claude Code MCP via HTTP bearer token
- Dev log written
- All existing tests continue to pass (`python -m polytool --help` succeeds; no code was changed)
</success_criteria>

<output>
After completion, create `.planning/quick/260404-rtv-implement-a-scoped-ris-only-n8n-pilot/260404-rtv-01-SUMMARY.md`

Include:
- What was shipped (ADR, compose changes, workflow files, docs)
- n8n image tag used (pinned version)
- Mutual exclusion mechanism documented
- Any deviations from plan
- CLI smoke test results
</output>
