---
phase: quick
plan: "042"
subsystem: crypto-pair
tags: [market-discovery, crypto-pair-bot, targeted-lookup, slug-pattern]
dependency_graph:
  requires: []
  provides: [discover_updown_5m_markets, _generate_5m_slugs]
  affects: [packages/polymarket/crypto_pairs/market_discovery.py]
tech_stack:
  added: []
  patterns: [targeted-slug-lookup, dedup-merge, lookahead-slots]
key_files:
  created:
    - tests/test_market_discovery.py
  modified:
    - packages/polymarket/crypto_pairs/market_discovery.py
decisions:
  - Use fetch_markets_filtered(slugs=...) for direct targeted lookup instead of paginated bulk fetch
  - Merge targeted and bulk results with slug-based dedup to preserve backward compatibility
  - Default use_targeted_for_5m=True so existing callers immediately benefit
metrics:
  duration: ~7 minutes
  completed: "2026-03-29T06:21:09Z"
  tasks_completed: 1
  files_changed: 2
---

# Phase quick Plan 042: Fix Market Discovery for Active BTC/ETH/SOL 5m Markets Summary

**One-liner:** Targeted slug-pattern lookup (btc/eth/sol-updown-5m-{ts}) via `fetch_markets_filtered` replaces unreliable bulk pagination for 5m updown market discovery.

## What Was Built

`packages/polymarket/crypto_pairs/market_discovery.py` received three additions:

1. **`_generate_5m_slugs(symbols, lookahead_slots)`** — Computes the current 5-minute bucket (`time.time() // 300 * 300`) and generates `{sym}-updown-5m-{bucket}` slugs for current + N future slots. Default: 3 symbols × 4 slots = 12 slugs.

2. **`discover_updown_5m_markets(gamma_client, lookahead_slots)`** — Calls `GammaClient.fetch_markets_filtered(slugs=...)` with the generated slugs, applies the same filtering logic (active, accepting_orders, 2 CLOB tokens, symbol + duration regex match), and returns `list[CryptoPairMarket]`.

3. **`discover_crypto_pair_markets(..., use_targeted_for_5m=True)`** — New optional parameter. When True (default), calls `discover_updown_5m_markets()` after the bulk pagination pass and merges the results, deduplicating by slug. Backward compatible — existing callers get the improved behavior automatically.

## Tests

`tests/test_market_discovery.py` — 15 offline tests, all mocked, no network:

- `TestGenerate5mSlugs` (6 tests): format, default symbols, lookahead count, bucket alignment, consecutive spacing, current bucket presence
- `TestDiscoverUpdown5mMarkets` (6 tests): active market returns pair, inactive skipped, not-accepting-orders skipped, wrong token count skipped, fetch_markets_filtered called with correct slug count, ETH/SOL classification
- `TestDiscoverCryptoPairMarketsTargeted` (3 tests): targeted path active by default, disabled when False, dedup merge correct

## Verification

```
tests/test_market_discovery.py  15 passed in 0.30s
tests/ (full suite)             2749 passed, 0 failed, 25 warnings in 90.38s
python -m polytool --help       clean load, no import errors
```

## Deviations from Plan

None — plan executed exactly as written. The task specification was fully implemented.

## Commits

| Hash    | Message                                                                   |
|---------|---------------------------------------------------------------------------|
| 4dabce0 | fix(crypto-pair): targeted 5m slug discovery in market_discovery.py      |

## Self-Check: PASSED

- `packages/polymarket/crypto_pairs/market_discovery.py` — FOUND (modified)
- `tests/test_market_discovery.py` — FOUND (created)
- Commit `4dabce0` — FOUND in git log
