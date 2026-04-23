---
date: 2026-04-23
slug: ris_wp3c_health_monitor_summary
work_packet: WP3-C
phase: RIS Phase 2A
status: complete
---

# WP3-C: Health Monitor Rich Output

## Objective

Enhance the `Health: Parse Output` Code node in
`infra/n8n/workflows/ris-unified-dev.json` so the n8n execution panel shows a
rich structured health summary — per-pipeline status, knowledge-store snapshot,
review queue, and provider routing — rather than raw exit-code data.

## Scope (WP3-C only)

- In-place update of one Code node: `Health: Parse Output` (id: `s1-parse`)
- No new nodes added; no node removals; no connection changes
- No Discord embed redesign (WP3-D), no daily summary (WP3-E)
- No changes to provider/evaluator/scoring/seed code, ClickHouse, Grafana, or Hermes

## What Changed

### `Health: Parse Output` — additions to return object

All existing fields preserved unchanged (`shouldAlert`, `overallStatus`,
`runCount`, `actionableChecks`, `statsHeadline`, `healthExitCode`,
`statsExitCode`, `healthStdout`, `statsStdout`, `healthStderr`, `statsStderr`,
`timestamp`) so `Health: Format Alert` and `Health: Alert Needed?` are
unaffected.

**New fields added:**

| Field | Source | Description |
|---|---|---|
| `overallCategory` | `healthData.overall_category` | `HEALTHY / DEGRADED / BLOCKED_ON_SETUP / FAILURE / no_data` |
| `pipelineStatuses` | `pipeline_failed` check `.data` | Array of `{pipeline, status, note}` for each of the 6 known pipelines |
| `knowledgeStore` | `statsData` | `{totalDocs, totalClaims, docsByFamily, gateDistribution, dispositionDistribution, recentNew, recentCached}` |
| `reviewQueue` | `statsData.review_queue` | `{queueDepth, byStatus, byGate}` |
| `providerRouting` | `statsData.routing_summary + provider_route_distribution + provider_failure_counts` | `{totalRouted, direct, escalated, fallback, byProvider, failureCounts}` |
| `operatorSummary` | Computed | Compact 5-line text for n8n execution panel |

### Per-pipeline status derivation

The `pipeline_failed` health check `data` object contains `error_pipelines` and
`blocked_pipelines` lists. The code maps these against the 6 known pipeline
names (`academic`, `reddit`, `blog`, `youtube`, `github`, `freshness`) and
assigns status `"error"`, `"blocked"`, or `"ok"`. When `run_count === 0`, all
pipelines are set to `"unknown"` with `note: "no_run_data"` since no inference
is possible.

### Operator summary format

```
Status: GREEN (HEALTHY)
Pipelines: ✅ academic | ✅ reddit | ✅ blog | ✅ youtube | ✅ github | ✅ freshness
KS: docs=47 claims=312 new=3
Queue: queue=0
Routing: no_routing_data
```

Error example:
```
Status: RED (DEGRADED)
Pipelines: ✅ academic | ❌ reddit | ✅ blog | ✅ youtube | ✅ github | ✅ freshness
KS: docs=46 claims=310 new=0
Queue: queue=2
Routing: routed=5 direct=4 esc=1 fb=0
```

## Files Changed

- `infra/n8n/workflows/ris-unified-dev.json` — 1 node updated (`Health: Parse Output` / `s1-parse`)

## Validation

```
# JSON parse and node/connection count
python -c "import json; wf=json.load(open('infra/n8n/workflows/ris-unified-dev.json',encoding='utf-8')); print(len(wf['nodes']), 'nodes,', len(wf['connections']), 'connections')"
# -> 76 nodes, 56 connections

# JS syntax validation
node -e "const fs=require('fs'); const wf=JSON.parse(fs.readFileSync('infra/n8n/workflows/ris-unified-dev.json','utf8')); const n=wf.nodes.find(n=>n.name==='Health: Parse Output'); new Function(n.parameters.jsCode); console.log('JS syntax: OK');"
# -> JS syntax: OK

# Changed node scope check
# -> WP3-B nodes (18): 18 - OK
# -> WP3-C nodes (1): 1 - OK
# -> Connections equal: True
# -> Unexpected Health/Summary/Operator changes: none

# CLI smoke test
python -m polytool --help
# -> CLI loads, no import errors
```

## What Remains for WP3-D and WP3-E

- **WP3-D**: Discord embeds with pipeline metrics — replace plain-text alerts
  with color-coded embeds using `pipelineStatuses`, `knowledgeStore`, and
  `reviewQueue` now available from the parse node
- **WP3-E**: Daily summary section — new 09:00 UTC trigger aggregating previous
  day's results into a Discord digest embed

## Codex Review

Tier: Skip (workflow JSON + docs only; no execution-path Python code changed).
