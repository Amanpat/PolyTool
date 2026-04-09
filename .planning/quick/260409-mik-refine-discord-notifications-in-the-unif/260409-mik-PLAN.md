---
phase: quick-260409-mik
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - infra/n8n/workflows/ris-unified-dev.json
  - docs/dev_logs/2026-04-09_discord_alert_layout_refinement.md
autonomous: true
must_haves:
  truths:
    - "Health alerts arrive in Discord with RED/YELLOW color-coded embeds, structured fields, and footer metadata"
    - "Section pipeline errors (academic, reddit, blog, youtube, github, freshness) arrive as RED embeds with job name, exit code, and truncated stderr"
    - "Ingest failure alerts arrive as RED embeds with URL, family, and error detail"
    - "Daily summary messages arrive as INFO-colored embeds with stats fields and precheck counts"
    - "Summary error messages arrive as YELLOW embeds with exit code detail"
    - "All notifications use the same embed design system: title, color, fields, footer"
    - "Notification delivery remains optional and controlled by DISCORD_WEBHOOK_URL presence"
  artifacts:
    - path: "infra/n8n/workflows/ris-unified-dev.json"
      provides: "All 9 format nodes produce embed payloads; sender node posts embed JSON"
    - path: "docs/dev_logs/2026-04-09_discord_alert_layout_refinement.md"
      provides: "Dev log with before/after payload shapes, commands run, test results"
  key_links:
    - from: "All format nodes (Health/Summary/Ingest/Section errors)"
      to: "Operator: Send Webhook"
      via: "embeds array in $json"
      pattern: "embeds.*title.*color.*fields"
---

<objective>
Refine all Discord notification payloads in the unified RIS n8n workflow from
plain-text `{ content: "..." }` to Discord embed format with severity-aware
colors, structured fields, compact titles, and footer metadata.

Purpose: Make operator alerts scannable at a glance on desktop and mobile --
RED for failures, YELLOW for warnings, GREEN for healthy summaries, BLUE for
info/success.

Output: Updated `ris-unified-dev.json` with all 9 format nodes and the sender
node producing Discord embeds. Dev log documenting the change.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@infra/n8n/workflows/ris-unified-dev.json
@infra/n8n/import_workflows.py
@docs/dev_logs/2026-04-09_discord_alert_integration_debug.md
@docs/dev_logs/2026-04-08_unified_n8n_alerts_and_summary.md

<interfaces>
<!-- Current notification contract (all 9 format nodes produce this): -->
```javascript
// Every format node returns:
return [{ json: { content: string, webhookUrl: string, notifyEnabled: boolean } }];
// Some nodes (Ingest: Format Fail) also include: status, url, source_family, error, exitCode, timestamp
```

<!-- Sender node (Operator: Send Webhook) currently sends: -->
```javascript
// jsonBody expression:
"={{ JSON.stringify({ content: $json.content }) }}"
// Target: change to embed payload
```

<!-- Discord Webhook Embed payload shape (target): -->
```javascript
{
  embeds: [{
    title: "RIS Health Alert",           // Short, scannable
    description: "Brief summary line",    // Optional 1-liner
    color: 0xFF0000,                      // RED=0xFF0000, YELLOW=0xFFA500, GREEN=0x2ECC71, BLUE=0x3498DB
    fields: [                             // 3-6 max, inline where sensible
      { name: "Status", value: "RED", inline: true },
      { name: "Runs", value: "43", inline: true },
    ],
    footer: { text: "RIS n8n | ris-unified-dev" },
    timestamp: "2026-04-09T12:00:00.000Z"
  }]
}
```

<!-- Nodes to modify (9 format nodes + 1 sender): -->
<!-- Format nodes: -->
<!--   Health: Format Alert (line ~125, id s1-alert-fmt) -->
<!--   Academic: Format Error (line ~285, id s2-format-err) -->
<!--   Reddit: Format Error (line ~434, id s3-format-err) -->
<!--   Blog: Format Error (line ~583, id s4-format-err) -->
<!--   YouTube: Format Error (line ~730, id s5-format-err) -->
<!--   GitHub: Format Error (line ~880, id s6-format-err) -->
<!--   Freshness: Format Error (line ~1030, id s7-format-err) -->
<!--   Summary: Format Message (line ~1149, id s8-format-msg) -->
<!--   Summary: Format Error (line ~1162, id s8-format-err) -->
<!--   Ingest: Format Fail (line ~1278, id s9-fmt-err) -->
<!-- Sender node: -->
<!--   Operator: Send Webhook (line ~1337, id operator-notify-send) -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Convert all format nodes and sender to Discord embed payloads</name>
  <files>infra/n8n/workflows/ris-unified-dev.json</files>
  <action>
Modify the unified workflow JSON to change all notification payloads from plain-text
`{ content: "..." }` to Discord embed format. This is a single-file change touching
10 nodes inside the JSON.

**Design system (consistent across all alert types):**

Color constants (Discord embed color as decimal integer):
- RED: 16711680 (0xFF0000) -- failures, RED health, pipeline errors
- YELLOW: 16744448 (0xFFA500) -- warnings, YELLOW health
- GREEN: 3066993 (0x2ECC71) -- healthy summary, success
- BLUE: 3447003 (0x3498DB) -- info-only

Footer text on all embeds: `"RIS | ris-unified-dev"`
Timestamp on all embeds: `new Date().toISOString()`

**1. Operator: Send Webhook (id: operator-notify-send)**

Change the `jsonBody` expression from:
```
={{ JSON.stringify({ content: $json.content }) }}
```
to:
```
={{ JSON.stringify({ embeds: $json.embeds }) }}
```

This is the single sender change -- all format nodes will now produce an `embeds` array.

**2. Health: Format Alert (id: s1-alert-fmt)**

Replace the jsCode. The node receives parsed health/stats data from `Health: Parse Output`.
New logic:
- Title: `"RIS Health: {overallStatus}"` (e.g., "RIS Health: RED")
- Color: RED if overallStatus is RED, YELLOW if YELLOW
- Description: one-line headline like `"43 runs | 15 docs | 4 ingest errors"`
- Fields (inline where marked):
  - `Runs` (inline) = runCount
  - `Docs` (inline) = totalDocs
  - `New` (inline) = acquisitionNew
  - `Cached` (inline) = acquisitionCached
  - `Errors` (inline) = acquisitionErrors
  - `Top Families` (not inline) = comma-separated top 3 families (e.g. "academic=6, github=4, manual=3")
  - `Actionable Checks` (not inline) = bullet list of up to 3 checks formatted as `STATUS check_name: message`, with "+N more" if truncated
- If healthExitCode or statsExitCode is nonzero, add a field `Command Exit` showing exit codes
- Footer: `"RIS | ris-unified-dev"`
- Timestamp: ISO string

Return shape: `[{ json: { embeds: [embedObject], webhookUrl, notifyEnabled } }]`

Preserve the existing webhookUrl/notifyEnabled resolution boilerplate.

**3. Six section Format Error nodes (Academic, Reddit, Blog, YouTube, GitHub, Freshness)**

All six use an identical pattern. Replace each jsCode with:
- Title: `"RIS Pipeline Error: {section_name}"` (e.g. "RIS Pipeline Error: academic_ingest")
- Color: RED (16711680)
- Description: `"Exit code: {exitCode}"`
- Fields:
  - `stderr` (not inline) = truncated to 300 chars max (Discord field value limit is 1024; keep compact). If empty, show "none"
  - `stdout (tail)` (not inline) = last 200 chars of stdout. If empty, show "none"
- Footer: `"RIS | ris-unified-dev | {section_name}"`
- Timestamp: ISO string

Return shape: `[{ json: { embeds: [embedObject], webhookUrl, notifyEnabled } }]`

Section names by node:
- Academic: Format Error -> "academic_ingest"
- Reddit: Format Error -> "reddit_polymarket"
- Blog: Format Error -> "blog_ingest"
- YouTube: Format Error -> "youtube_ingest"
- GitHub: Format Error -> "github_ingest"
- Freshness: Format Error -> "freshness_refresh"

**4. Ingest: Format Fail (id: s9-fmt-err)**

Replace jsCode:
- Title: `"RIS Ingest Failed"`
- Color: RED (16711680)
- Description: `"Family: {source_family} | Exit: {exitCode}"`
- Fields:
  - `URL` (not inline) = the URL that was submitted (truncate to 200 chars)
  - `Error` (not inline) = error text truncated to 300 chars
- Footer: `"RIS | ris-unified-dev | ingest"`
- Timestamp: ISO string

IMPORTANT: This node also returns status/url/source_family/error/exitCode/timestamp
for the `Ingest: Respond 500` node downstream. Preserve those fields in the returned
json alongside the new `embeds` array. The final return shape must be:
`[{ json: { ...statusPayload, embeds: [embedObject], webhookUrl, notifyEnabled } }]`

**5. Summary: Format Message (id: s8-format-msg)**

Replace jsCode:
- Title: `"RIS Daily Summary"` (normal path) or `"RIS Daily Summary Error"` (stats error path)
- Color: GREEN (3066993) for healthy summary, YELLOW (16744448) if there are actionable checks, RED (16711680) for stats error
- Description: `"Health: {summary} | {total_docs} docs | {run_count} runs"`
- Fields (normal path):
  - `Docs` (inline) = total_docs
  - `Runs` (inline) = run_count
  - `New` (inline) = acquisition_new
  - `Ingest Errors` (inline) = acquisition_errors
  - `Top Families` (not inline) = top 3 comma-separated
  - `Prechecks` (not inline) = `"GO={n}, CAUTION={n}, STOP={n}"`
  - If actionable checks exist: `Actionable` (not inline) = top 2 checks
- For stats error path: single `Error Detail` field with exit code and truncated stderr
- Footer: `"RIS | ris-unified-dev | daily-summary"`
- Timestamp: ISO string

**6. Summary: Format Error (id: s8-format-err)**

Replace jsCode:
- Title: `"RIS Summary Error"`
- Color: YELLOW (16744448)
- Description: `"Health command exit code: {exitCode}"`
- Fields:
  - `stderr` (not inline) = truncated to 300 chars, or "none"
- Footer: `"RIS | ris-unified-dev | daily-summary"`
- Timestamp: ISO string

**Implementation notes:**
- Work directly in the JSON file. Each node's jsCode is a single string value.
- Escape all quotes and newlines correctly for JSON string embedding.
- Use `\n` for newlines inside field values (Discord renders these).
- Do NOT use markdown code blocks in embed fields -- they render poorly on mobile. Use plain text with truncation instead.
- Keep individual field values under 300 chars to stay well within Discord's 1024 char field limit.
- Validate the JSON after editing: `python -m json.tool infra/n8n/workflows/ris-unified-dev.json > /dev/null`
  </action>
  <verify>
    <automated>python -m json.tool "D:/Coding Projects/Polymarket/PolyTool/infra/n8n/workflows/ris-unified-dev.json" > /dev/null 2>&1 && echo "JSON valid" || echo "JSON INVALID"</automated>
  </verify>
  <done>
All 9 format nodes produce `{ embeds: [{...}], webhookUrl, notifyEnabled }` with
severity-aware colors, structured fields, and footer metadata. The sender node
posts `{ embeds: $json.embeds }`. JSON validates. No workflow logic changes outside
notification formatting.
  </done>
</task>

<task type="auto">
  <name>Task 2: Re-import workflow into n8n and verify Discord delivery</name>
  <files>docs/dev_logs/2026-04-09_discord_alert_layout_refinement.md</files>
  <action>
**Step 1: Re-import the updated workflow.**

```bash
python infra/n8n/import_workflows.py
```

Confirm output shows `ris-unified-dev.json: ... (updated ...)` and
`DISCORD_WEBHOOK_URL: configured`.

**Step 2: Trigger an ingest failure to test the failure path.**

```bash
curl -s -X POST "http://localhost:5678/webhook/ris-ingest" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://127.0.0.1:9/embed-test","source_family":"blog"}'
```

Check the Discord channel for a RED embed titled "RIS Ingest Failed" with
structured fields for URL and Error.

**Step 3: Trigger the health path (manual execution).**

In the n8n UI, open the unified workflow and click "Test Workflow" on the
`Health: Manual` trigger. Alternatively, use:

```bash
docker exec polytool-n8n sh -lc 'N8N_RUNNERS_BROKER_PORT=5680 n8n execute --id $(cat infra/n8n/workflows/workflow_ids.env | grep UNIFIED_DEV_ID | cut -d= -f2) --rawOutput' 2>/dev/null
```

Check Discord for a YELLOW or RED colored health embed with structured fields.

**Step 4: Trigger the summary path.**

In the n8n UI, click "Test Workflow" on the `Summary: Manual` trigger.
Check Discord for a GREEN/YELLOW summary embed with stats fields.

If n8n CLI execution only triggers the first manual trigger (documented behavior),
use the n8n UI for summary path verification instead.

**Step 5: Write the dev log.**

Create `docs/dev_logs/2026-04-09_discord_alert_layout_refinement.md` with:
- Files changed and why (just ris-unified-dev.json)
- The before/after payload shape:
  - Before: `{ content: "plain text string" }`
  - After: `{ embeds: [{ title, description, color, fields, footer, timestamp }] }`
- Commands run and their output
- Test results for each alert path (ingest fail, health, summary)
- Design choices made:
  - Color coding: RED=failure, YELLOW=warning, GREEN=healthy, BLUE=info
  - Field layout: inline for numeric metrics, non-inline for text content
  - Footer: workflow identifier + section context
  - Truncation: stderr/stdout capped at 300/200 chars for mobile readability
  - No markdown code blocks in fields (poor mobile rendering)
- Any delivery issues encountered and resolution
- Note: import_workflows.py was NOT modified (no changes needed -- it already
  handles string replacement and the embed payload structure is purely in the
  workflow JSON)
  </action>
  <verify>
    <automated>python -m json.tool "D:/Coding Projects/Polymarket/PolyTool/infra/n8n/workflows/ris-unified-dev.json" > /dev/null 2>&1 && test -f "D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-09_discord_alert_layout_refinement.md" && echo "PASS" || echo "FAIL"</automated>
  </verify>
  <done>
Workflow re-imported successfully. At least one Discord embed message confirmed
delivered with color, title, fields, and footer. Dev log created with before/after
payload documentation, test results, and design choices.
  </done>
</task>

</tasks>

<verification>
1. `python -m json.tool infra/n8n/workflows/ris-unified-dev.json > /dev/null` -- JSON valid
2. `python infra/n8n/import_workflows.py` -- imports without error
3. Ingest failure test delivers RED embed to Discord
4. Health alert test delivers YELLOW/RED embed to Discord
5. Summary test delivers GREEN/YELLOW embed to Discord
6. All embeds have: title, color, fields array, footer, timestamp
7. Dev log exists at `docs/dev_logs/2026-04-09_discord_alert_layout_refinement.md`
</verification>

<success_criteria>
- All Discord notifications use embed format instead of plain text
- Severity colors are consistent: RED for failures/errors, YELLOW for warnings, GREEN for healthy summaries
- Each embed has a clear title, structured fields (3-6 max), and footer metadata
- Messages are compact and readable on mobile (no giant stderr dumps, no code blocks)
- Notification delivery remains optional (controlled by DISCORD_WEBHOOK_URL)
- No workflow logic changes beyond notification formatting
- Workflow JSON validates and re-imports cleanly
- Dev log documents the change
</success_criteria>

<output>
After completion, create `.planning/quick/260409-mik-refine-discord-notifications-in-the-unif/260409-mik-SUMMARY.md`
</output>
