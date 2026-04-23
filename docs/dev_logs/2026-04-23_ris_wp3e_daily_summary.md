---
date: 2026-04-23
slug: ris_wp3e_daily_summary
work_packet: WP3-E
phase: RIS Phase 2A
status: complete
---

# WP3-E: Daily Summary Digest at 09:00 UTC

## Objective

Add the daily-summary path to the existing unified RIS n8n workflow so it fires every morning
at 09:00 UTC and sends a compact digest embed to the operator webhook — using the WP3-C
structured data fields (`pipelineStatuses`, `knowledgeStore`, `reviewQueue`) for consistency
with the WP3-D alert embed style.

## Scope (WP3-E only)

- In-place update of 3 nodes in the existing S8 section: `s8-schedule`, `s8-sticky`, `s8-parse`
- No new nodes, no new connections (S8 was already fully connected as of WP3-D)
- No changes to provider/evaluator/scoring/seed code, WP4 collector/dashboard files, or Hermes

## What Changed

### Pre-existing S8 state

The S8 section was already present in the workflow with all nodes connected:

```
Summary: Schedule ─→ Summary: Run research-health ─→ Summary: Health OK?
  ├─[OK]─→  Summary: Run research-stats ─→ Summary: Format Message ─→ Operator: Notify Enabled?
  └─[ERR]─→ Summary: Format Error ──────────────────────────────────→ Operator: Notify Enabled?
```

Issues before WP3-E:
1. `s8-schedule` cron was `0 0 8 * * *` (08:00 UTC, not 09:00 UTC as specified)
2. `s8-parse` (Summary: Format Message) used WP3-A-style field names (`total_docs`,
   `acquisition_new`, `precheck_decisions`) instead of the WP3-C structured output
   (`pipelineStatuses`, `knowledgeStore`, `reviewQueue`, `overallCategory`)
3. `s8-sticky` note said "08:00 UTC"

### 1. `s8-schedule` — cron expression fix

| Before | After |
|---|---|
| `0 0 8 * * *` | `0 0 9 * * *` |

Fires every day at 09:00 UTC.

### 2. `s8-sticky` — label text fix

`## Section 8: Daily Summary -- 08:00 UTC` → `## Section 8: Daily Summary -- 09:00 UTC`

### 3. `s8-parse` (Summary: Format Message) — WP3-C structured parsing

Replaced the WP3-A-style field extraction with the same WP3-C parsing logic used in
`s1-parse` (Health: Parse Output), adapted for the `Summary:` node names. New code:

- Runs `safeParse` on both `Summary: Run research-health` and `Summary: Run research-stats` stdout
- Derives `actionableChecks` (RED/non-deferred-YELLOW health checks)
- Derives `overallCategory` from `healthData.overall_category`
- Derives `derivedStatus` (RED / YELLOW / HEALTHY) from checks + health summary
- Builds `pipelineStatuses` (ok / error / blocked / unknown) from `pipeline_failed` check data
- Builds `knowledgeStore` (totalDocs, totalClaims, recentNew, docsByFamily) from stats
- Reads `reviewQueueDepth` from `statsData.review_queue.queue_depth`
- Reads `providerRouting` (totalRouted, escalated, fallback) from `statsData.routing_summary`
- Produces a `RIS Daily Digest` embed with footer `RIS | daily-summary`

**No alert gate**: S8 always sends (unconditional daily digest). The health monitor path (S1)
has its own alert-needed gate; S8 does not.

## Example Digest Payload Shape

### Healthy day (all pipelines OK, no issues)

```json
{
  "title": "RIS Daily Digest",
  "description": "Health: HEALTHY (no_issues)",
  "color": 3066993,
  "fields": [
    { "name": "Pipelines",       "value": "✅ academic  ✅ reddit  ✅ blog  ✅ youtube  ✅ github  ✅ freshness", "inline": false },
    { "name": "Knowledge Store", "value": "docs=47  claims=312  new=3",  "inline": false },
    { "name": "Review Queue",    "value": "2 pending",                   "inline": true },
    { "name": "Routing",         "value": "routed=12  esc=2  fb=0",      "inline": true },
    { "name": "Top Families",    "value": "academic=15, blog=10, reddit=8", "inline": false }
  ],
  "footer": { "text": "RIS | daily-summary" },
  "timestamp": "2026-04-23T09:00:00.000Z"
}
```

### Degraded day (one pipeline erroring)

```json
{
  "title": "RIS Daily Digest",
  "description": "Health: YELLOW (pipeline_degraded)",
  "color": 16744448,
  "fields": [
    { "name": "Pipelines",       "value": "✅ academic  ❌ reddit  ✅ blog  ✅ youtube  ✅ github  ✅ freshness", "inline": false },
    { "name": "Knowledge Store", "value": "docs=47  claims=312  new=0",  "inline": false },
    { "name": "Review Queue",    "value": "2 pending",                   "inline": true },
    { "name": "Routing",         "value": "routed=9  esc=1  fb=0",       "inline": true },
    { "name": "Top Families",    "value": "academic=15, blog=10, github=5", "inline": false },
    { "name": "Issues",          "value": "[YELLOW] pipeline_failed: reddit failed 2 times in last 6h", "inline": false }
  ],
  "footer": { "text": "RIS | daily-summary" },
  "timestamp": "2026-04-23T09:00:00.000Z"
}
```

### Stats unavailable (health command fails)

Color stays GREEN unless health command fails too; `ksValue` falls back to `stats_unavailable`.
If `healthData.__parseError` is set, an actionableCheck is added and color shifts to RED.

## Files Changed

- `infra/n8n/workflows/ris-unified-dev.json` — 3 nodes updated:
  - `s8-schedule` (Summary: Schedule) — cron expression only
  - `s8-sticky` (S8: Summary - Label) — label text only
  - `s8-parse` (Summary: Format Message) — full JS replacement

No nodes added or removed. No connections changed. Node count: 76, connection count: 56.

## Validation

```
# JSON parse + node/connection count
python -c "import json; wf=json.load(open('infra/n8n/workflows/ris-unified-dev.json',encoding='utf-8')); print(len(wf['nodes']), 'nodes,', len(wf['connections']), 'connections')"
# -> 76 nodes, 56 connections

# Schedule assertion
# -> s8-schedule cron: 0 0 9 * * *
# -> PASS: schedule is 09:00 UTC

# Sticky note assertion
# -> PASS: sticky shows 09:00 UTC

# s8-parse WP3-C field presence checks
# -> FOUND: pipelineStatuses
# -> FOUND: knowledgeStore
# -> FOUND: reviewQueueDepth
# -> FOUND: overallCategory
# -> FOUND: derivedStatus
# -> FOUND: actionableChecks
# -> FOUND: providerRouting
# -> FOUND: RIS Daily Digest
# -> FOUND: daily-summary
# -> FOUND: Summary: Run research-health
# -> FOUND: Summary: Run research-stats
# -> All assertions passed.

# JS syntax validation (Node.js new Function)
node infra/n8n/_s8_parse_check.js
# -> JS syntax OK: s8-parse

# CLI smoke test
python -m polytool --help
# -> CLI loads, no import errors
```

## WP3 Status After WP3-E

| Work Packet | Status | Summary |
|---|---|---|
| WP3-A | complete | Structured parse output for all pipeline nodes |
| WP3-B | complete | Visual success/failure indicators (status_label, sX-done Set nodes) |
| WP3-C | complete | Health monitor rich output with pipelineStatuses/knowledgeStore/reviewQueue |
| WP3-D | complete | Discord embed enrichment with per-pipeline fields in health alerts and pipeline errors |
| WP3-E | complete | Daily summary path at 09:00 UTC using WP3-C structured data |

**WP3 is fully complete.** The next work packet in Phase 2A is WP4 (Monitoring Infrastructure:
ClickHouse DDL, n8n metrics collector, Grafana RIS dashboard, stale pipeline alert).

## Codex Review

Tier: Skip (workflow JSON + docs only; no execution-path Python code changed).
