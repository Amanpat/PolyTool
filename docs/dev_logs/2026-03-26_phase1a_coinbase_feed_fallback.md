# Dev Log: Phase 1A — Coinbase Fallback Reference Feed

**Date:** 2026-03-26
**Branch:** phase-1A
**Objective:** Implement Coinbase WebSocket feed and AutoReferenceFeed fallback to unblock the
crypto pair paper soak after Binance HTTP 451 geo-restriction was discovered on 2026-03-25.

---

## Context

The 2026-03-25 smoke soak (run ID `603e0ef17ff2`) completed cleanly (240 cycles,
`stopped_reason=completed`) but produced zero data because Binance returned HTTP 451 on every
WebSocket connection attempt. The `crypto-pair-report` rubric verdict was `RERUN PAPER SOAK`.

The preferred unblocking path was implementing a Coinbase fallback feed inside
`packages/polymarket/crypto_pairs/reference_feed.py` — no geo-restriction applies to
Coinbase Advanced Trade API.

---

## Work Completed

### 1. CoinbaseFeed (`packages/polymarket/crypto_pairs/reference_feed.py`)

- New `CoinbaseFeed` class mirrors the `BinanceFeed` interface.
- Subscribes to `BTC-USD`, `ETH-USD`, `SOL-USD` via Coinbase Advanced Trade WebSocket:
  `wss://advanced-trade-api.coinbase.com/ws` (public ticker channel).
- Product ID normalization: `BTC-USD` → `BTC`, `ETH-USD` → `ETH`, `SOL-USD` → `SOL`.
- Full safety state machine: `NEVER_CONNECTED`, `CONNECTED`, `DISCONNECTED`.
- Stale threshold: same 15s default as Binance.
- `SOURCE_NAME = "coinbase"`.
- `parse_coinbase_ws_message(raw: str) -> Optional[tuple[str, float]]` — parses `type=ticker`
  payloads, ignores all others.
- `normalize_coinbase_product_id(product_id: str) -> str` — maps known products or raises
  `ValueError("Unsupported Coinbase product_id: ...")`.

### 2. AutoReferenceFeed (`packages/polymarket/crypto_pairs/reference_feed.py`)

- `AutoReferenceFeed(primary_feed, fallback_feed)` — returns primary snapshot when usable,
  falls back to fallback feed's snapshot automatically.
- Default primary: `BinanceFeed`. Default fallback: `CoinbaseFeed`.
- `get_snapshot(symbol)` transparently returns whichever snapshot is usable, preserving the
  correct `feed_source` label (`"binance"` or `"coinbase"`).

### 3. Provider selection

- `build_reference_feed(provider: str = "binance") -> ReferenceFeed` factory.
- `normalize_reference_feed_provider(provider: str) -> str` — validates and normalizes
  `"binance"`, `"coinbase"`, `"auto"` (case-insensitive); raises `ValueError` on unknown.
- `DEFAULT_STALE_THRESHOLD_S = 15.0` exported constant.
- CLI integration: `--reference-feed-provider binance|coinbase|auto` on `crypto-pair-run`.

### 4. Tests (`tests/test_crypto_pair_reference_feed.py`)

55 new offline tests, all passing:
- `TestReferencePriceSnapshot` (5 tests): `is_usable` semantics, `to_dict()` serialization.
- `TestBinanceFeedInitialState` (5 tests): pre-inject state.
- `TestBinanceFeedInjectPrice` (7 tests): price injection, case normalization, unsupported symbol.
- `TestBinanceFeedStaleness` (5 tests): threshold boundary conditions, cross-symbol isolation.
- `TestBinanceFeedUnsupportedSymbol` (2 tests).
- `TestBinanceFeedDisconnect` (2 tests): price retained, `is_usable` false.
- `TestFeedConnectionState` (2 tests): enum values and string comparison.
- `TestReferenceFeedProviderSelection` (4 tests): factory, provider normalization.
- `TestCoinbaseNormalization` (3 tests): ticker parsing, non-ticker messages, unsupported product.
- `TestCoinbaseFeedInjectPrice` (1 test): `feed_source="coinbase"`.
- `TestCoinbaseFeedStateSemantics` (2 tests): staleness, disconnect.
- `TestAutoReferenceFeed` (2 tests): preference order, fallback on disconnect.

### 5. Pre-existing test failures fixed (session work — same session)

Fixed 20 pre-existing test failures brought forward from prior context:

- **`ArbWatcher` injectable clocks** (14 failures): Added `_monotonic_fn` and `_sleep_fn`
  parameters to `ArbWatcher.__init__`; rewrote `run()` to use them for deterministic testing.
- **Duration-based exit**: `run()` exits when elapsed >= `duration_seconds`, printing
  "Duration elapsed; stopping."
- **`--markets` argparse `nargs="+"`**: Changed from single string to multi-token; updated
  `_parse_markets_arg` to join and split on comma.
- **Watchlist file format detection** (`_load_watchlist_file`): Supports JSON (`.json` or
  content starting with `{`/`[`) and slug-per-line text format. Error messages updated to
  match test expectations: `"looks like JSON but is not valid JSON"`,
  `"one market slug per non-blank line"`, `"watchlist file is empty"`.
- **Empty-markets error message**: Updated `_collect_watch_targets` to include both
  `--markets slug1 slug2` and `--markets "slug1,slug2"` patterns in message.
- **`TestCLI` timestamp staleness** (5 failures in `test_new_market_capture.py`): Fixed
  `_make_markets_response` to generate timestamps relative to `datetime.now(timezone.utc)`
  instead of hardcoded `_REF_TIME = 2026-03-17` (which was >9 days old).
- **`test_watch_meta_omits_regime_when_none`** (1 failure in `test_gate2_session_pack.py`):
  Fixed `_record_tape_for_market` to only write `"regime"` key to `watch_meta.json` when the
  effective regime is a known non-`"unknown"` value.

---

## Final test count

**2641 passed, 0 failed** (65s run).

---

## Files changed

- `packages/polymarket/crypto_pairs/reference_feed.py` — `CoinbaseFeed`, `AutoReferenceFeed`,
  provider factory, normalization helpers
- `tests/test_crypto_pair_reference_feed.py` — 55 new tests
- `tools/cli/watch_arb_candidates.py` — injectable clocks, duration exit, watchlist format
  detection, argparse `nargs="+"`, regime omission fix
- `tools/cli/new_market_capture.py` — `_reference_time` parameter added to `main()`
- `tests/test_new_market_capture.py` — timestamp generation fixed to use `datetime.now()`

---

## Next action

Run the 24h paper soak with Coinbase or auto feed:

```powershell
$env:CLICKHOUSE_PASSWORD = "polytool_admin"
python -m polytool crypto-pair-run --duration-seconds 86400 --sink-enabled --reference-feed-provider coinbase
```

Apply the promote / rerun / reject rubric from `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`
after the run finalizes.
