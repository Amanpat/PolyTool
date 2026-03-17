# SPEC-new-market-capture-planner-v1

**Status:** Shipped 2026-03-17
**Branch:** phase-1
**Supersedes:** n/a

---

## Problem

The benchmark_v1 tape manifest requires 5 tapes in the `new_market` bucket
(markets listed < 48h before the benchmark reference time).  The gap-fill
planner (SPEC-benchmark-gap-fill-planner-v1) found 0 `new_market` candidates
because the Jon-Becker dataset snapshot is ~40 days stale.  Historical data
cannot satisfy this bucket.

The solution is to discover newly listed markets from the live Gamma API and
plan fresh Gold tape capture.

---

## Solution

A two-part deliverable:

1. **`packages/polymarket/new_market_capture_planner.py`** — pure planner logic
   (no I/O; testable offline with mocked data)
2. **`tools/cli/new_market_capture.py`** — CLI driver that calls the API and writes
   output files

---

## Discovery Surface

**Source:** Gamma API — `GET /markets?active=true&closed=false&order=createdAt&ascending=false`

**Function:** `fetch_recent_markets(limit=300)` in
`packages/polymarket/market_selection/api_client.py`

This is the smallest existing market-listing surface in the repo.  The function
returns normalised market dicts including `condition_id`, `market_id`, `slug`,
`token_id`, `created_at`, and `volume_24h` — sufficient for the planner.

---

## Planner Pipeline

```
fetch_recent_markets()
    → discover_candidates()    # filter: 0 <= age_hours < 48, has token_id + timestamp
    → rank_candidates()        # sort: age_hours asc, volume_24h desc, slug asc
    → dedupe_candidates()      # dedup by token_id (keep first = best-ranked)
    → build_result()           # assign priorities, compute metadata
    → NewMarketCaptureResult   # targets + insufficiency flags
```

---

## Classification Rules

A market qualifies as `new_market` if **all** of the following hold:

1. `age_hours = (reference_time - created_at).total_seconds() / 3600`
2. `0.0 <= age_hours < 48.0`
3. `token_id` is non-empty (required for tape recording)
4. `created_at` is parseable as ISO8601

Markets without a timestamp are **excluded** (conservative — cannot confirm age).

`max_age_hours` defaults to 48.0 and is configurable via CLI.

---

## Target Manifest Contract

File: `config/benchmark_v1_new_market_capture.targets.json`

```json
{
  "schema_version": "benchmark_new_market_capture_v1",
  "generated_at": "2026-03-17T12:00:00Z",
  "targets": [
    {
      "bucket": "new_market",
      "slug": "will-xyz",
      "market_id": "12345",
      "token_id": "10955...",
      "listed_at": "2026-03-17T00:00:00Z",
      "age_hours": 12.34,
      "priority": 1,
      "record_duration_seconds": 1800,
      "selection_reason": "age_hours=12.34 listed_at=2026-03-17T00:00:00Z volume_24h=5000 slug=will-xyz"
    }
  ]
}
```

`priority` starts at 1 (highest). All candidates are emitted; caller can
truncate to the quota (5) if desired.

---

## Insufficiency Report Contract

File: `config/benchmark_v1_new_market_capture.insufficiency.json`

```json
{
  "schema_version": "new_market_capture_insufficient_v1",
  "generated_at": "2026-03-17T12:00:00Z",
  "bucket": "new_market",
  "candidates_found": 0,
  "required": 5,
  "shortage": 5,
  "reason": "Only 0 new-market candidates found via live Gamma API; need 5. ..."
}
```

Written when `candidates_found < required`.  If partial candidates exist, both
files are written simultaneously.

---

## CLI

```bash
# Discover new markets and write targets manifest
python -m polytool new-market-capture

# Dry run — fetch and classify but write nothing
python -m polytool new-market-capture --dry-run

# Custom parameters
python -m polytool new-market-capture --limit 500 --max-age-hours 24 --required 5 --record-duration 3600

# Custom output paths
python -m polytool new-market-capture \
  --output config/benchmark_v1_new_market_capture.targets.json \
  --insufficiency-output config/benchmark_v1_new_market_capture.insufficiency.json
```

**Exit codes:**
- `0` — fully sufficient (>= `required` targets written)
- `2` — partial (1..required-1 targets found; both manifest and insufficiency written)
- `1` — zero candidates found, or error

---

## Ranking

| Priority | Criterion |
|----------|-----------|
| 1st      | `age_hours` ascending (freshest first) |
| 2nd      | `volume_24h` descending (more liquid = better tape) |
| 3rd      | `slug` ascending (deterministic tiebreak) |

Freshest-first rationale: a market listed 2 hours ago has the most time
remaining in the `new_market` window; a market at 47.9 hours may expire before
the operator starts recording.

---

## Constraints

- **No fabricated markets.** Only real API responses produce targets.
- **Deterministic output.** Given the same API response and reference time, the
  same targets manifest is produced.
- **Conservative.** Markets without parseable timestamps are excluded. No fuzzy
  age estimation.
- **Gold tapes only.** This planner produces a recording plan; it does not
  initiate recording. The capture step uses the existing `simtrader shadow` /
  `watch-arb-candidates` surface.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/new_market_capture_planner.py` | New — core planner |
| `tools/cli/new_market_capture.py` | New — CLI driver |
| `packages/polymarket/market_selection/api_client.py` | Added `fetch_recent_markets()` |
| `polytool/__main__.py` | Registered `new-market-capture` command |
| `tests/test_new_market_capture.py` | New — 42 offline tests |
| `docs/specs/SPEC-new-market-capture-planner-v1.md` | This file |
| `docs/dev_logs/2026-03-17_new_market_capture_planner.md` | Dev log |
| `docs/CURRENT_STATE.md` | Updated status |
