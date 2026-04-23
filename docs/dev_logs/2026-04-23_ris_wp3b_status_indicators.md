---
date: 2026-04-23
slug: ris_wp3b_status_indicators
work_packet: WP3-B
phase: RIS Phase 2A
status: complete
---

# WP3-B: Visual Success/Failure Indicators for RIS Pipeline Nodes

## Objective

Add glanceable success/failure status labels to the 6 core pipeline sections
(S2–S7: Academic, Reddit, Blog, YouTube, GitHub, Freshness) in
`infra/n8n/workflows/ris-unified-dev.json`, using the structured parse output
from WP3-A. An operator clicking any pipeline section in the n8n execution view
now sees the result at a glance without reading raw stdout.

## Scope (WP3-B only)

- In-place update of existing workflow JSON; no new nodes added, no rebuild
- No Discord embed redesign (WP3-D), no daily summary (WP3-E), no health monitor overhaul (WP3-C)
- No changes to provider/evaluator/scoring code, ClickHouse, Grafana, or Hermes

## What Changed

### Three node types updated per pipeline (18 total edits)

**1. `sX-parse` Code nodes (s2-parse through s7-parse) — success indicator**

Added `status_label` computation before the return statement:

```js
const statusLabel = errors.length > 0
  ? '⚠️ Academic: ' + docs_accepted + ' docs | ' + errors.length + ' warning(s)'
  : '✅ Academic: ' + docs_accepted + ' docs ingested';
```

`status_label` is now part of the structured return object alongside the existing
`docs_accepted`, `docs_rejected`, `errors`, etc. from WP3-A.

**2. `sX-done` Set nodes (s2-done through s7-done) — status passthrough**

Added a `status_label` assignment to each Set node:
```json
{ "name": "status_label", "value": "={{ $json.status_label }}", "type": "string" }
```

The Done node now surfaces the label in the n8n execution view — the most visible
checkpoint in the success path.

**3. `sX-format-err` Code nodes (s2-format-err through s7-format-err) — failure indicator**

Added `status_label` extraction from `exitCode` and `stderrRaw`, appended to the
return JSON alongside the existing embed/webhook fields:

```js
const statusLabel = '❌ Academic: exit ' + exitCode + (stderrRaw.length > 0 ? ' | ' + stderrRaw.substring(0, 60) : '');
```

## Example Status Messages

| Scenario | status_label |
|---|---|
| 3 docs ingested, no errors | `✅ Academic: 3 docs ingested` |
| 1 doc ingested, 1 warning | `⚠️ Academic: 1 docs \| 1 warning(s)` |
| 0 docs, exit 0 | `✅ Academic: 0 docs ingested` |
| API timeout, exit 1 | `❌ Academic: exit 1 \| API timeout: connection refused` |
| Non-zero exit, no stderr | `❌ Reddit: exit 2` |

## Files Changed

- `infra/n8n/workflows/ris-unified-dev.json` — 18 targeted edits across 12 nodes:
  - s2-parse, s2-done, s2-format-err (Academic)
  - s3-parse, s3-done, s3-format-err (Reddit)
  - s4-parse, s4-done, s4-format-err (Blog)
  - s5-parse, s5-done, s5-format-err (YouTube)
  - s6-parse, s6-done, s6-format-err (GitHub)
  - s7-parse, s7-done, s7-format-err (Freshness)

## Validation

```
# JSON parse validation
python -c "import json; data=json.load(open('infra/n8n/workflows/ris-unified-dev.json',encoding='utf-8')); print(len(data['nodes']), 'nodes,', len(data['connections']), 'connections')"
# -> 76 nodes, 56 connections

# JS syntax validation (new Function() on all 12 modified code nodes)
# -> OK s2-parse, OK s3-parse, OK s4-parse, OK s5-parse, OK s6-parse, OK s7-parse
# -> OK s2-format-err, OK s3-format-err, OK s4-format-err, OK s5-format-err, OK s6-format-err, OK s7-format-err

# status_label presence check (parse + done + fmt-err per pipeline)
# -> s2: parse=✓ done=✓ fmt-err=✓
# -> s3: parse=✓ done=✓ fmt-err=✓
# -> s4: parse=✓ done=✓ fmt-err=✓
# -> s5: parse=✓ done=✓ fmt-err=✓
# -> s6: parse=✓ done=✓ fmt-err=✓
# -> s7: parse=✓ done=✓ fmt-err=✓

# Simulated output (s2-parse, 3 acquired + 1 rejected):
# Success: ✅ Academic: 3 docs ingested | docs_accepted: 3
# Warning: ⚠️ Academic: 1 docs | 1 warning(s)
# Error (s2-format-err): ❌ Academic: exit 1 | API timeout: connection refused

# CLI smoke test
python -m polytool --help
# -> CLI loads, no import errors
```

## What Remains for WP3-C through WP3-E

- **WP3-C**: Health monitor rich output — parse S1 health/stats output into a
  per-pipeline status table (knowledge_store growth, review_queue depth, etc.)
- **WP3-D**: Discord embeds with pipeline metrics — replace plain-text alerts
  with color-coded embeds showing per-pipeline `docs_accepted`/`docs_rejected`
- **WP3-E**: Daily summary section — new 09:00 UTC trigger aggregating previous
  day's results into a Discord digest embed

## Codex Review

Tier: Skip (workflow JSON + docs only; no execution-path Python code changed).
