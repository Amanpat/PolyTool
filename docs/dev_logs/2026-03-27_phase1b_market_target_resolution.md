# Dev Log: Phase 1B Market Target Resolution

**Date:** 2026-03-27
**Author:** Claude Code (quick-031)
**Context:** Phase 1B Gold corpus capture was blocked by operators pasting event URLs that produced "no markets returned for slug" errors in `simtrader shadow`.

---

## Summary

Added a `TargetResolver` module that accepts any real Polymarket URL or slug as the `--market` argument to `simtrader shadow`.  Before this change, operators had to manually look up the exact market slug from the Polymarket interface.  Now they can paste whatever URL is in their browser.

---

## Accepted `--market` Input Forms

| Form | Example |
|---|---|
| Direct market slug | `will-btc-hit-100k-by-dec-2025` |
| Market URL | `https://polymarket.com/market/will-btc-hit-100k-by-dec-2025` |
| Event slug | `btc-price-december-2025` |
| Event URL | `https://polymarket.com/event/btc-price-december-2025` |

All four forms are handled by `TargetResolver.resolve_target()`.

---

## New Module

**`packages/polymarket/simtrader/target_resolver.py`**

Exports:
- `TargetResolver` — main resolver class; `resolve_target(raw: str) -> ResolvedMarket`
- `ChildMarketChoice(Exception)` — raised when an event has multiple usable binary children; contains `candidates: list[dict]` (rank, slug, question, liquidity, volume) and `skipped: list[dict]` (slug, question, reason)
- `TargetResolverError(ValueError)` — raised when resolution fails completely; message names the input form and states what was tried

Internal helpers (not part of the public API but importable for testing):
- `_parse_target(raw) -> (slug, hint)` — URL parsing, raises TargetResolverError for unsupported paths
- `_fetch_event_child_markets(gamma_client, event_slug)` — page-scan-based child lookup
- `_rank_children(markets)` — filters and ranks usable binary markets

**Design note on GammaClient:** `fetch_markets_filtered` does NOT accept an `event_slug` parameter (confirmed by reading the actual source at `packages/polymarket/gamma.py` lines 401-446).  Child market lookup uses `fetch_markets_page` with a post-filter on `eventSlug`.

---

## Modified

**`tools/cli/simtrader.py` — `_shadow()`**

- Imports `TargetResolver`, `ChildMarketChoice`, `TargetResolverError` from the new module
- Replaces `picker.resolve_slug(args.market)` with `resolver.resolve_target(args.market)`
- Adds `ChildMarketChoice` handler: prints ranked shortlist with slug, question, liquidity, volume and skip reasons for rejected children; exits 1
- Adds `TargetResolverError` handler: prints diagnostic message; exits 1
- Keeps `MarketPickerError` handler as safety net
- `validate_book()` calls remain on `picker` (unchanged)
- `--market` argparse help text updated to show all 4 accepted input forms

---

## Resolution Logic Flow

```
resolve_target(raw)
  1. _parse_target(raw) -> (slug, hint)
     - http URL with /market/ -> hint="market"
     - http URL with /event/ -> hint="event"
     - bare string -> hint="unknown"
     - other URL path -> TargetResolverError

  2. If hint in ("market", "unknown"):
     try picker.resolve_slug(slug)
     - SUCCESS -> return ResolvedMarket
     - "no markets returned" + hint=="unknown" -> fall to step 3
     - other MarketPickerError -> TargetResolverError

  3. If hint=="event" or fell through from step 2:
     _fetch_event_child_markets(gamma, slug) -> [_ChildMarket, ...]
     - empty list -> TargetResolverError
     _rank_children(children) -> (usable, skipped)
     - no usable -> TargetResolverError listing skip reasons
     - 1 usable -> picker.resolve_slug(child.market_slug) -> ResolvedMarket
     - 2+ usable -> raise ChildMarketChoice(candidates, skipped)
```

---

## Ranking Criteria

Usable children must pass all checks (first failure wins skip reason):
1. `active == True` — else "closed"
2. `accepting_orders is not False` — else "not_accepting_orders"
3. `enable_order_book is not False` — else "orderbook_disabled"
4. `clob_token_ids is not empty` — else "no_token_ids"
5. `len(outcomes) == 2 and len(clob_token_ids) == 2` — else "not_binary (N outcomes)"

Ranked: liquidity descending, then volume descending as tiebreak.

---

## Test Results

```
python -m pytest tests/test_target_resolver.py -v
```
19 tests collected, 19 passed in 0.28s.

Tests cover:
- `_parse_target` for all 4 input forms, trailing slash, wrong path, non-polymarket domain
- `resolve_target` for direct slug, market URL, single-child event URL, multi-child event URL
- Fallback: bare slug that fails direct lookup retried as event slug
- Rejection: non-binary, empty token IDs, not accepting orders, closed
- Ranking: liquidity desc, volume desc tiebreak, rank field values, skipped list in ChildMarketChoice

```
python -m pytest tests/ -q
```
2685 passed, 0 failed, 25 warnings (all pre-existing datetime.utcnow deprecation warnings).

---

## Open Questions

1. Does the Gamma `/events` endpoint reliably embed child market slugs in the event response?  If so, `_fetch_event_child_markets` could query `/events?slug=<event_slug>` and extract the nested `markets[]` list instead of doing a page-scan — this would be more targeted.  Deferred until confirmed by live testing.
2. Does `fetch_markets_filtered` accept an `event_slug` param in any Gamma API version?  Current implementation avoids it because the Python client method doesn't support it.  If the upstream API accepts `event_slug` as a query param, a direct filter would reduce the page-scan overhead for large event corpora.
