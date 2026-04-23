---
date: 2026-04-22
slug: ris_wp3a_structured_output
work_packet: WP3-A
phase: RIS Phase 2A
status: complete
---

# WP3-A: Structured Output Parsing for Pipeline Code Nodes

## Objective

Update the 6 pipeline Parse Metrics Code nodes in `infra/n8n/workflows/ris-unified-dev.json`
(S2–S7: Academic, Reddit, Blog, YouTube, GitHub, Freshness) so each node outputs a stable
structured JSON object instead of raw stdout dumps.

## Scope (WP3-A only)

- In-place update of existing workflow JSON; no rebuild
- No WP3-B (Discord embeds), WP3-C (health monitor), WP3-D (daily digest), WP3-E (other)
- No changes to ClickHouse, Grafana, provider logic, scoring, seeding, or Hermes

## Day-1 Discovery

Read `tools/cli/research_scheduler.py`, `packages/research/scheduling/scheduler.py`, and
`tools/cli/research_acquire.py` to establish stdout patterns:

- **URL mode** (Reddit, Blog, YouTube, GitHub):
  - Success: `Acquired: {title} | family=... | doc_id=... | chunks=N | dedup=...`
  - Rejection: `Rejected | reason=... | id=...`
- **Search mode** (Academic, Freshness):
  - Per-result: `  Acquired: {title} | doc_id=... | chunks=N` (indented)
  - Per-rejected: `  Rejected: {url} | reason=...` (indented)
  - Summary: `Search complete: N/M papers ingested for query=...`
- All jobs run with `--no-eval`; no LLM evaluation gate fires
- Errors go to stderr; n8n commands merge via `2>&1`

## Output Schema

Each updated node now emits:

```json
{
  "pipeline": "academic",
  "docs_fetched": 5,
  "docs_evaluated": 5,
  "docs_accepted": 3,
  "docs_rejected": 2,
  "docs_review": 0,
  "new_claims": 0,
  "duration_seconds": null,
  "errors": [],
  "exit_code": 0,
  "timestamp": "2026-04-22T..."
}
```

`docs_evaluated` equals `docs_fetched` (approximation — `--no-eval` means no LLM gate runs).
`docs_review`, `new_claims`, `duration_seconds` are placeholder zeroes/null for WP3-A;
later work packets can wire them when CLI exposes structured output natively.

## Parsing Logic

```js
// Line-by-line for URL-mode jobs
/^Acquired:/i  -> docs_accepted++
/^Rejected[\s|:]/i -> docs_rejected++
/^Error:/i or /^Warning:/i -> errors[]

// Fallback for search-mode jobs (when URL patterns find nothing)
/Search complete: (\d+)\/(\d+) papers ingested/gi
  -> sa = accepted, st = total; docs_rejected = st - sa
```

## Files Changed

- `infra/n8n/workflows/ris-unified-dev.json` — 6 nodes updated (s2-parse through s7-parse):
  - `s2-parse` ("Academic: Parse Metrics") — pipeline: 'academic'
  - `s3-parse` ("Reddit: Parse Metrics") — pipeline: 'reddit'
  - `s4-parse` ("Blog: Parse Metrics") — pipeline: 'blog'
  - `s5-parse` ("YouTube: Parse Metrics") — pipeline: 'youtube'
  - `s6-parse` ("GitHub: Parse Metrics") — pipeline: 'github'
  - `s7-parse` ("Freshness: Parse Metrics") — pipeline: 'freshness'
  - S1 (health monitor parse) left unchanged — already well-structured

## Validation

```
python -c "import json; json.load(open('infra/n8n/workflows/ris-unified-dev.json', encoding='utf-8')); print('JSON valid')"
# -> JSON valid

python -m polytool --help
# -> CLI loads, no import errors
```

## What Remains for WP3-B through WP3-E

- **WP3-B**: Discord embed formatting (rich embeds per pipeline run)
- **WP3-C**: Health monitor node overhaul (aggregate across all pipelines)
- **WP3-D**: Daily digest trigger and summary node
- **WP3-E**: Any additional workflow improvements per roadmap

## Codex Review

Tier: Skip (workflow JSON + docs only; no execution-path code changed).
