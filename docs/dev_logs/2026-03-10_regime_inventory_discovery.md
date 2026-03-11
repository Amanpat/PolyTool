# Dev Log: Regime-Inventory Discovery Enhancement

**Date:** 2026-03-10
**Branch:** codex/tracka-adverse-selection-default-wiring
**Track:** Track A — Phase 1

---

## Motivation

The broader inventory scan found only one factual politics candidate and zero factual
`<48h` new-market candidates.  Before concluding that inventory is absent, we needed a
way to query regime-specific candidates *independent of overall rank* so we could
distinguish "absent" from "buried below rank-based scan limits".

---

## What Changed

### 1. `packages/polymarket/market_selection/regime_policy.py`

Added two public helpers for inventory discovery:

**`enrich_with_regime(market, *, reference_time, new_market_max_age_hours)`**
- Classifies a market's regime using the existing `classify_market_regime()` function.
- Returns a new dict with the original fields plus:
  - `regime` — "politics" | "sports" | "new_market" | "other"
  - `regime_source` — always `"derived"` (classifier-driven, not operator input)
  - `age_hours` — float hours since creation, or `None` if no timestamp
  - `is_new_market` — `True`/`False`/`None` (factual from timestamp, or from keyword match)
- Non-mutating (returns a new dict; input is unchanged).
- UNKNOWN/off-target markets get `regime="other"`, never silently promoted.

**`filter_by_factual_regime(markets, target_regime, *, reference_time, new_market_max_age_hours)`**
- Accepts only `politics`, `sports`, or `new_market` as `target_regime` — raises
  `ValueError` for `"unknown"` or `"other"` by design.
- Enriches and returns only markets whose *derived* regime exactly matches the target.
- Off-target/UNKNOWN markets are excluded entirely — no silent promotion.

### 2. `packages/polymarket/market_selection/api_client.py`

Enhanced `fetch_active_markets()` to include fields needed for regime classification:
`title`, `question`, `category`, `subcategory`, `tags`, `event_slug`, `event_title`.

These fields are preserved in the returned market dicts so that callers can run
`enrich_with_regime()` on the fetched data without a second API call.

### 3. `tools/cli/scan_gate2_candidates.py`

Added `--regime {politics,sports,new_market}` flag.

**Behavior when `--regime` is set:**
- **Bypasses the signal-only filter** — shows ALL matching-regime markets, not just
  those with Gate 2 edge/depth signal.  This answers "is inventory absent?" rather than
  "is inventory absent AND has signal?".
- **Live mode:** fetches enriched Gamma metadata (`min_volume=0`, `limit≥200`) and runs
  `enrich_with_regime()` on each market; cross-references scan results by slug.
- **Tape mode:** reads tape meta files (`meta.json`, `watch_meta.json`, `prep_meta.json`)
  and runs `enrich_with_regime()` on available fields; UNKNOWN tapes get `regime="other"`.
- Prints a count of how many matching-regime markets were found vs. total scanned.
- If zero matching markets are found, reports "regime is absent in this scan batch"
  (not just ranked low).

New helper functions added (all offline-testable):
- `_build_live_regime_meta(max_fetch)` — fetches + enriches Gamma market batch
- `_read_tape_market_fields(tape_dir)` — extracts metadata fields from tape meta files
- `_build_tape_regime_meta(tapes_dir)` — builds `{slug: enriched_dict}` from all tape dirs

---

## Tests

New file: `tests/test_regime_inventory_discovery.py` — 40 tests, all offline.

| Class | Coverage |
|---|---|
| `TestEnrichWithRegime` | politics/sports/new_market classification; age boundary at 48h; `age_hours`/`is_new_market` facets; no-mutation guarantee; tags-as-list; regime_source always "derived" |
| `TestFilterByFactualRegime` | politics/sports/new_market filtering; off-target exclusion; empty input; ValueError for "unknown"/"other"/"crypto" targets; cross-contamination (new_market≠politics, etc.) |
| `TestFetchActiveMarketsRegimeFields` | category/question/tags fields present in fetched market dicts; end-to-end enrichment to correct regime |
| `TestReadTapeMarketFields` | quickrun_context/shadow_context extraction; "market" key normalised to "slug"; missing/corrupt meta returns None |
| `TestBuildTapeRegimeMeta` | unknown tape → regime="other"; politics tape with context → regime="politics" |

---

## Manual Verification Commands

```bash
# Politics scan (live) — bypasses signal filter, shows all politics markets
python -m polytool scan-gate2-candidates --regime politics --top 30

# New-market scan (live, broader pool)
python -m polytool scan-gate2-candidates --regime new_market --top 20

# Politics scan with explanation
python -m polytool scan-gate2-candidates --regime politics --explain --top 10

# Tape scan filtered to politics
python -m polytool scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes --regime politics

# Tape scan filtered to new_market
python -m polytool scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes --regime new_market

# Unit tests only
python -m pytest tests/test_regime_inventory_discovery.py -v
```

---

## Scope Constraints

- Touched only: `packages/polymarket/market_selection/regime_policy.py`,
  `packages/polymarket/market_selection/api_client.py`,
  `tools/cli/scan_gate2_candidates.py`, and tests.
- Did NOT touch: watcher/session-pack logic, MarketMaker, risk manager, gate
  thresholds, API/UI, or broad docs.
- Existing scan behavior is unchanged when `--regime` is not specified.
