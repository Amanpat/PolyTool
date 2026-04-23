---
date: 2026-04-23
slug: ris_wp3d_discord_embeds
work_packet: WP3-D
phase: RIS Phase 2A
status: complete
---

# WP3-D: Discord Embed Enrichment with Per-Pipeline Fields

## Objective

Improve the Discord alert formatting in `infra/n8n/workflows/ris-unified-dev.json` so
operators see color-coded, per-pipeline context in health alerts instead of aggregated
stats alone. Uses structured data added in WP3-C (pipelineStatuses, knowledgeStore,
reviewQueue) that was not yet wired into the alert-formatting nodes.

## Scope (WP3-D only)

- In-place update of 7 nodes in the existing workflow JSON; no new nodes, no new connections
- No daily summary logic (WP3-E), no monitoring infrastructure, no WP3-E work
- No changes to provider/evaluator/scoring/seed code, ClickHouse, Grafana, or Hermes

## What Changed

### 1. `s1-format-alert` ("Health: Format Alert") — primary WP3-D target

Replaced the old scattered fields (Docs, Runs, New, Cached, Errors, Top Families) with
three richer fields sourced from WP3-C parse output, plus kept Runs/Actionable Checks/Command Exit.

**New fields added:**

| Field | Source | Content |
|---|---|---|
| `Pipelines` | `pipelineStatuses` (WP3-C) | Per-pipeline row: `✅ academic  ❌ reddit  ✅ blog...` |
| `Knowledge Store` | `knowledgeStore` (WP3-C) | `docs=47  claims=312  new=3` |
| `Review Queue` | `reviewQueue` (WP3-C) | `2 pending` (queueDepth) |

**Description improvement:** `overallCategory` from WP3-C is appended when available:
```
"2 checks need attention (DEGRADED)"
```

**Fallback:** If `knowledgeStore` is absent (pre-WP3-C parse), falls back to
`statsHeadline.totalDocs` / `acquisitionNew` for compatibility.

**Example embed shape for a RED health alert:**
```json
{
  "title": "RIS Health: RED",
  "description": "pipeline_failed detected (DEGRADED)",
  "color": 16711680,
  "fields": [
    { "name": "Pipelines",       "value": "✅ academic  ❌ reddit  ✅ blog  ✅ youtube  ✅ github  ✅ freshness", "inline": false },
    { "name": "Knowledge Store", "value": "docs=47  claims=312  new=3", "inline": false },
    { "name": "Review Queue",    "value": "2 pending", "inline": true },
    { "name": "Runs",            "value": "42", "inline": true },
    { "name": "Actionable Checks", "value": "[RED] pipeline_failed: reddit failed 3 times in last 6h", "inline": false }
  ],
  "footer": { "text": "RIS | health" },
  "timestamp": "2026-04-23T..."
}
```

### 2. `s2-s7-format-err` (6 pipeline error nodes) — secondary WP3-D target

Added partial-parse logic: even on the error path, the code now scans stdout for
`Acquired:` / `Rejected:` lines (and `Search complete: N/M` for search-mode pipelines)
to surface partial work done before the failure.

**Description improvement:**
- Before: `Exit 1`
- After (when partial work found): `Exit 1 — partial: 2 accepted, 0 rejected`

**Embed shape unchanged:** title, color, Error Output, Last Output, footer, timestamp —
the same structure that WP3-B established, now with a more informative description.

The `status_label` field (added in WP3-B, used by the `sX-done` Set nodes) is preserved.

## Files Changed

- `infra/n8n/workflows/ris-unified-dev.json` — 7 nodes updated:
  - `s1-format-alert` ("Health: Format Alert")
  - `s2-format-err` ("Academic: Format Error")
  - `s3-format-err` ("Reddit: Format Error")
  - `s4-format-err` ("Blog: Format Error")
  - `s5-format-err` ("YouTube: Format Error")
  - `s6-format-err` ("GitHub: Format Error")
  - `s7-format-err` ("Freshness: Format Error")

No nodes added or removed. No connections changed.

## Validation

```
# JSON parse + node/connection count
python -c "import json; wf=json.load(open('infra/n8n/workflows/ris-unified-dev.json',encoding='utf-8')); print(len(wf['nodes']), 'nodes,', len(wf['connections']), 'connections')"
# -> 76 nodes, 56 connections

# JS syntax validation (node new Function() on all 7 edited code nodes)
# -> JS syntax OK: s1-format-alert (Health: Format Alert)
# -> JS syntax OK: s2-format-err (Academic: Format Error)
# -> JS syntax OK: s3-format-err (Reddit: Format Error)
# -> JS syntax OK: s4-format-err (Blog: Format Error)
# -> JS syntax OK: s5-format-err (YouTube: Format Error)
# -> JS syntax OK: s6-format-err (GitHub: Format Error)
# -> JS syntax OK: s7-format-err (Freshness: Format Error)

# Field presence checks (s1-format-alert)
# -> pipelineStatuses: OK  knowledgeStore: OK  reviewQueue: OK  overallCategory: OK
# -> embed.title: OK  embed.color: OK  embed.fields: OK  embed.footer: OK  embed.timestamp: OK

# Field presence checks (s2-s7-format-err)
# -> partialAccepted: OK  partialRejected: OK  hasPartial: OK  description with partial: OK
# -> embed.title: OK  embed.color: OK  status_label: OK

# CLI smoke test
python -m polytool --help
# -> CLI loads, no import errors
```

## What Remains for WP3-E

- **WP3-E**: Daily summary section — new 09:00 UTC trigger aggregating yesterday's
  results into a Discord digest embed. This is a separate work packet and was
  explicitly excluded from WP3-D scope.

## Codex Review

Tier: Skip (workflow JSON + docs only; no execution-path Python code changed).
