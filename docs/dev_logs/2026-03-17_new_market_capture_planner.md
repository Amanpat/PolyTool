# Dev Log: New-Market Capture Planner v0

**Date:** 2026-03-17
**Branch:** phase-1

---

## Context

The benchmark_v1 gap-fill planner (shipped earlier today) found 0 candidates for
the `new_market` bucket.  The Jon-Becker dataset snapshot is ~2026-02-03 (~40
days stale), so no markets created within 48h of 2026-03-15 are present.
Historical data provably cannot satisfy this bucket.

The `insufficiency.json` from that run confirms:
```json
{
  "insufficient_buckets": {
    "new_market": {
      "shortage": 5,
      "candidates_found": 0,
      "reason": "Only 0 candidates found; need 5. JB dataset snapshot likely predates the required creation window."
    }
  }
}
```

This packet implements the solution: discover candidates from the **live Gamma
API** instead of historical data, then plan fresh Gold tape capture.

---

## Files Changed

| File | Why |
|------|-----|
| `packages/polymarket/new_market_capture_planner.py` | Core planner: filter/rank/dedupe/build-result |
| `tools/cli/new_market_capture.py` | CLI driver: fetch → plan → write manifest |
| `packages/polymarket/market_selection/api_client.py` | Added `fetch_recent_markets()` returning `condition_id` + `market_id` fields |
| `polytool/__main__.py` | Registered `new-market-capture` command; added to help text |
| `tests/test_new_market_capture.py` | 42 offline tests — all mocked, no live network calls |
| `docs/specs/SPEC-new-market-capture-planner-v1.md` | Spec |
| `docs/dev_logs/2026-03-17_new_market_capture_planner.md` | This file |
| `docs/CURRENT_STATE.md` | Updated with new-market-capture planner status |

---

## Discovery Source

**Gamma API:** `GET https://gamma-api.polymarket.com/markets?active=true&closed=false&order=createdAt&ascending=false&limit=300`

This is the smallest existing market-listing surface in the repo.
`fetch_active_markets()` was already in `api_client.py`; a new companion
`fetch_recent_markets()` was added that additionally returns:
- `market_id` (Gamma integer ID as string)
- `condition_id` (hex condition ID)
- No volume filter (planner handles filtering)

---

## Planner Logic

```
fetch_recent_markets(limit=300)
    → discover_candidates()    # keep: 0 <= age_hours < 48, non-empty token_id, parseable created_at
    → rank_candidates()        # age_hours ASC, volume_24h DESC, slug ASC
    → dedupe_candidates()      # by token_id, keep first (best-ranked)
    → build_result()           # assign priorities 1..N, compute selection_reason
```

Classification is intentionally conservative: markets without a parseable
timestamp are excluded entirely rather than assumed to be new.

---

## Commands Run

```bash
# Run all new-market-capture tests (offline, mocked)
python -m pytest tests/test_new_market_capture.py -v --tb=short

# Run pre-existing batch silver tests to confirm no regression
python -m pytest tests/test_batch_silver.py tests/test_batch_silver_gap_fill.py -v --tb=short
```

---

## Test Results

```
tests/test_new_market_capture.py: 42 passed in 0.37s
tests/test_batch_silver.py + tests/test_batch_silver_gap_fill.py: 87 passed in 0.58s
```

All 42 new tests pass. 0 pre-existing regressions.

---

## Targets Found (Live Run)

**Not yet run against live API in this session.**

The planner is designed to be run by the operator when ready to begin capture:

```bash
python -m polytool new-market-capture
```

Expected outcome at time of writing (2026-03-17):
- If Polymarket has listed any new markets in the past 48h → targets.json written
- If none → insufficiency.json written (honest; operator must wait for listings)

---

## Open Questions for Capture Execution

1. **When to run the capture**: operator must run `new-market-capture` first, then
   immediately start `simtrader shadow` / `watch-arb-candidates` for each target.
   The `age_hours` field decays in real time; run promptly after plan generation.

2. **Record duration**: defaulting to 1800s (30 min). Sufficient for Gate 2 if the
   market has arb events; may need adjustment for very quiet new markets.

3. **Category confirmation**: new_market classification is age-based (< 48h), not
   content-based. The recorded tape may overlap with politics/sports/other buckets.
   `benchmark_manifest.py` will re-classify at manifest curation time — this is
   correct behaviour.

4. **Volume threshold**: `fetch_recent_markets` applies no volume filter by design
   (new markets may have low initial volume). The planner ranks by volume as a
   secondary criterion; low-volume markets will appear at the back of the list.

5. **Gamma API pagination**: current limit is 300. If more than 300 markets are
   active, some may be missed. Increase `--limit` if needed or if Gamma supports
   `created_at` date-range filtering.

6. **Integration with batch-reconstruct-silver**: this plan is for Gold (live)
   capture via `simtrader shadow`, not Silver reconstruction. The manifest schema
   (`benchmark_new_market_capture_v1`) is separate from `benchmark_gap_fill_v1`.
   A future "execute capture" step will consume this manifest.
