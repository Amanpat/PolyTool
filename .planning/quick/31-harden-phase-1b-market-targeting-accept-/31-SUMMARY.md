---
phase: quick-031
plan: "01"
subsystem: simtrader-shadow
tags: [target-resolution, url-parsing, event-child-markets, shadow-trading, phase-1b]
dependency_graph:
  requires: [packages/polymarket/simtrader/market_picker.py, packages/polymarket/gamma.py]
  provides: [packages/polymarket/simtrader/target_resolver.py]
  affects: [tools/cli/simtrader.py _shadow()]
tech_stack:
  added: [urllib.parse.urlparse for URL decomposition]
  patterns: [event child market page-scan, ranked shortlist exception pattern]
key_files:
  created:
    - packages/polymarket/simtrader/target_resolver.py
    - tests/test_target_resolver.py
    - docs/dev_logs/2026-03-27_phase1b_market_target_resolution.md
  modified:
    - tools/cli/simtrader.py
decisions:
  - "Use page-scan approach for _fetch_event_child_markets — GammaClient.fetch_markets_filtered has no event_slug param (confirmed by source inspection)"
  - "Check no_token_ids before not_binary in _rank_children so empty token list gets the correct skip reason"
  - "ChildMarketChoice is an Exception subclass (not ValueError) so callers can catch it separately from TargetResolverError"
metrics:
  duration_seconds: 564
  completed: "2026-03-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 1
  tests_added: 19
  regression_baseline: "2685 passed, 0 failed"
---

# Phase quick-031 Plan 01: Phase 1B Market Targeting Hardening Summary

**One-liner:** TargetResolver module accepts market slug, market URL, event slug, or event URL for `simtrader shadow`, with ranked child-market shortlist and exact skip reasons when an event URL has multiple candidates.

## What Was Built

The `simtrader shadow --market` flag previously only accepted exact market slugs.  Operators running Gold corpus capture sessions were hitting "no markets returned for slug" because they pasted event URLs copied from the Polymarket homepage.

This plan added a `TargetResolver` layer that handles all four input forms:

| Form | Example |
|---|---|
| Direct market slug | `will-btc-hit-100k` |
| Market URL | `https://polymarket.com/market/will-btc-hit-100k` |
| Event slug | `btc-price-dec-2025` |
| Event URL | `https://polymarket.com/event/btc-price-dec-2025` |

When an event URL has multiple usable binary children, the command prints a ranked shortlist (by liquidity, then volume) with exact skip reasons for rejected children instead of a cryptic error.

## Commits

| Task | Commit | Description |
|---|---|---|
| 1 — TargetResolver module + tests | 3bd7b42 | feat(quick-031-01): add TargetResolver module with 19 offline tests |
| 2 — Wire into shadow CLI + dev log | f390307 | feat(quick-031-01): wire TargetResolver into simtrader shadow CLI |

## Files Created/Modified

### Created
- `packages/polymarket/simtrader/target_resolver.py` — TargetResolver, ChildMarketChoice, TargetResolverError, _parse_target, _rank_children, _fetch_event_child_markets
- `tests/test_target_resolver.py` — 19 offline tests covering all resolution paths and rejection cases
- `docs/dev_logs/2026-03-27_phase1b_market_target_resolution.md` — dev log with full design rationale

### Modified
- `tools/cli/simtrader.py` — `_shadow()` updated to use TargetResolver; `--market` help text updated

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `_make_binary_market` test helper using falsy `or` for clob_token_ids**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** `clob_token_ids or ["tok-yes-...", "tok-no-..."]` evaluates the RHS when the passed value is `[]` (falsy), making `test_reject_no_token_ids_child` effectively test a market with two token IDs instead of zero.
- **Fix:** Changed to `clob_token_ids if clob_token_ids is not None else [...]` pattern in both `clob_token_ids` and `outcomes` parameters.
- **Files modified:** `tests/test_target_resolver.py`
- **Commit:** 3bd7b42

**2. [Rule 1 - Bug] Fixed `_ChildMarket.from_raw` using falsy `or` for boolean fields**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** `raw.get("acceptingOrders") or raw.get("accepting_orders")` fails to preserve `False` values because `False or ...` evaluates the RHS.
- **Fix:** Added `_coalesce(d, *keys)` helper that returns the first key present in the dict regardless of value truthiness.
- **Files modified:** `packages/polymarket/simtrader/target_resolver.py`
- **Commit:** 3bd7b42

**3. [Rule 1 - Bug] Fixed `_rank_children` check order for `no_token_ids`**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** `no_token_ids` check was placed after the `not_binary` check. Since `len([]) != 2` triggers `not_binary`, the `no_token_ids` branch was unreachable.
- **Fix:** Moved `not token_ids` check before the `len(outcomes) != 2 or len(token_ids) != 2` check.
- **Files modified:** `packages/polymarket/simtrader/target_resolver.py`
- **Commit:** 3bd7b42

**4. [Rule 1 - Bug] Fixed test regex case mismatch for `test_market_url_wrong_path`**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Test used `match="only /market/ and /event/"` (lowercase "only") but the error message uses `"Only"` (uppercase).
- **Fix:** Changed to `match=r"(?i)only /market/ and /event/"` for case-insensitive match.
- **Files modified:** `tests/test_target_resolver.py`
- **Commit:** 3bd7b42

## Test Results

```
tests/test_target_resolver.py: 19 passed
Full suite: 2685 passed, 0 failed, 25 warnings (pre-existing datetime.utcnow deprecations)
```

## Known Stubs

None — all resolution paths are fully wired. The `_fetch_event_child_markets` page-scan approach is functional but note the open question in the dev log about whether a more targeted event-slug query is possible.

## Self-Check: PASSED
