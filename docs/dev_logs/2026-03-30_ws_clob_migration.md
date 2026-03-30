# Dev Log: WebSocket CLOB Feed Migration for Crypto Pair Bot

**Date:** 2026-03-30
**Branch:** feat/ws-clob-feed
**Quick task:** 054
**Status:** Complete

---

## Motivation

The crypto pair bot's scan loop previously called `clob_client.get_best_bid_ask(token_id)` twice
per market per cycle — once for the YES token and once for the NO token. With a 0.5s cycle interval
and 2 active markets (BTC + ETH), that's approximately 8 REST GET /book requests per second.

This approach has two problems:

1. **HTTP overhead**: Each REST call adds ~20-50ms latency and consumes server quota. At 0.5s
   cycles the bot spends a disproportionate fraction of each cycle waiting for network round-trips.
2. **Stale data**: By the time both REST responses arrive (typically 40-100ms apart), the book
   state may have changed, creating a temporal mismatch between YES ask and NO ask readings.

The fix: maintain a persistent WebSocket connection to the Polymarket CLOB market channel. The
channel delivers book snapshots and incremental deltas in real time. The bot reads from the
in-memory book (lock-protected dict lookup) instead of making HTTP calls.

---

## What Was Built

### `packages/polymarket/crypto_pairs/clob_stream.py` — ClobStreamClient

New module implementing a persistent WS book feed for the crypto pair bot.

**Design decisions:**

- **Raw `websocket.WebSocket()` (not `WebSocketApp`)**: Matches the existing `TapeRecorder` pattern
  in `packages/polymarket/simtrader/tape/recorder.py`. The raw client with `settimeout()` is
  simpler to control in a reconnect loop and avoids callback-threading complexity.

- **Daemon thread + `threading.Lock`**: Follows the `BinanceFeed` pattern from `reference_feed.py`.
  The WS receive loop runs in a background daemon thread. All state mutations go through
  `self._lock` to ensure thread-safe reads from the main cycle loop.

- **`_event_source` injection**: For offline testing, the caller provides an iterable of pre-parsed
  event dicts. The start() method spawns a thread that iterates the source instead of opening a WS
  connection. Identical pattern to `ShadowRunner._event_source` in the SimTrader stack.

- **`_time_fn` injection**: The staleness guard uses `self._time_fn()` instead of `time.time()`
  directly. Tests inject a controllable mock clock to advance time without sleeping.

- **5-second staleness threshold (default)**: If the last book update for a token is older than
  `stale_threshold_s`, `get_best_bid_ask()` returns `None` and the scan falls back to REST. This
  prevents acting on stale data if the WS connection drops.

- **Soft dependency on `websocket`**: The import happens inside `_ws_loop()`, so paper/test paths
  that never start a live WS connection never trigger the import.

**Public API:**
```
subscribe(token_id)        — add token; subscription sent on next reconnect
unsubscribe(token_id)      — remove token; clears book state
get_best_bid_ask(token_id) — (bid, ask) or None (not ready / stale / empty)
get_book_age_ms(token_id)  — ms since last update; 999999 if never updated
is_ready(token_id)         — True when subscribed, has snapshot, not stale
start()                    — idempotent; starts daemon thread
stop()                     — sets stopped flag; loop exits on next iteration
```

**Message formats handled:**
- Book snapshot: `{"event_type": "book", "asset_id": "...", "bids": [...], "asks": [...]}`
- Price change delta: `{"event_type": "price_change", "asset_id": "...", "changes": [...]}`
- Batched deltas: `{"price_changes": [{...}, {...}]}`

For deltas, `side="BUY"` maps to bids, `side="SELL"` maps to asks. Size `"0"` removes the level;
size > 0 updates or inserts.

---

### `tests/test_crypto_pair_clob_stream.py` — 12 Offline Tests

All tests are fully offline (no network) using `_event_source` and `_time_fn` injection.

| Test class | What it verifies |
|---|---|
| `TestSnapshotBootstrap` | Book snapshot sets correct (bid, ask) |
| `TestDeltaApplication` | Delta removes level (size=0) and adds new level |
| `TestStalenessGuard` | Age > threshold returns None; age < threshold returns value |
| `TestUnsubscribe` | Unsubscribe clears book; is_ready() → False |
| `TestSortOrder` | best_ask = min(asks); best_bid = max(bids) |
| `TestMultiToken` | Two tokens maintain independent books; unsubscribed token → None |
| `TestIsReadyAndAge` | is_ready() semantics; get_book_age_ms() values |

---

## Files Modified

### `packages/polymarket/clob.py`
Added `get_best_bid_ask_from_stream(token_id, stream)` method to `ClobClient`. Reads from the
stream's in-memory book and returns an `OrderBookTop` (same type as the REST path). Returns `None`
if stream is None or token is not ready. The caller (opportunity_scan.py) decides whether to fall
back to REST.

### `packages/polymarket/crypto_pairs/opportunity_scan.py`

Three changes:

1. **`PairOpportunity` dataclass**: Added three new backward-compatible fields with defaults:
   - `clob_source: str = "rest"` — tracks which read path was used
   - `clob_age_ms: int = -1` — WS book age in ms; -1 means REST (age unknown)
   - `clob_snapshot_ready: bool = False` — True when both tokens had fresh WS books

2. **`compute_pair_opportunity()`**: New `stream=None` parameter. When stream is provided and both
   tokens are `is_ready()`, reads prices via `get_best_bid_ask_from_stream()` and populates
   `clob_source="ws"`. Otherwise falls back to REST and sets `clob_source="rest"`.

3. **`scan_opportunities()`**: New `stream=None` parameter, threaded through to
   `compute_pair_opportunity()`.

### `packages/polymarket/crypto_pairs/paper_runner.py`

Three changes:

1. **`CryptoPairPaperRunner.__init__()`**: New `clob_stream=None` parameter. Stored as
   `self.clob_stream`. No auto-creation (avoids unexpected network in test contexts).

2. **`run()` startup**: After reference feed connect, if `clob_stream` is not None, calls
   `clob_stream.start()` and records a runtime event. Sets `_clob_stream_bootstrapped = False`.

3. **Cycle loop**: On the first cycle, iterates discovered markets and calls
   `clob_stream.subscribe(yes_token_id)` and `clob_stream.subscribe(no_token_id)` for each.
   Passes `stream=self.clob_stream` to `self.scan_fn()`.

4. **`finally` block**: Calls `clob_stream.stop()` after the reference feed disconnect.

### `tools/cli/crypto_pair_run.py`

Two changes:

1. **Parser**: Added `--use-ws-clob` (default True, paper mode) and `--no-use-ws-clob` (sets
   `dest="use_ws_clob"` to False) flags.

2. **Runner construction**: Creates a `ClobStreamClient()` when `use_ws_clob=True and not live`,
   then passes it as `clob_stream=clob_stream` to `CryptoPairPaperRunner`.

---

## REST Fallback Behavior

The REST path is fully preserved. Fallback triggers in three cases:

1. `stream=None` (e.g., `--no-use-ws-clob` flag or test with no stream)
2. `stream.is_ready(token_id)` is False for either token (not yet subscribed / stale / no snapshot)
3. Any `get_best_bid_ask_from_stream()` returning None (stream returned None)

Early returns from `compute_pair_opportunity` (missing_yes, missing_no) keep the default
`clob_source="rest"` value since the new fields have backward-compatible defaults.

---

## Test Approach

The ClobStreamClient is designed for testability from the ground up:

- `_event_source=iter([...])` — inject pre-built event dicts; the WS thread iterates them
  synchronously without any network
- `_time_fn=mock_fn` — control the clock for staleness assertions
- `_start_and_drain()` helper in tests waits for the daemon thread to exhaust the event source

Existing tests in `test_crypto_pair_scan.py` and `test_crypto_pair_run.py` pass unchanged because
all new parameters have default values (`stream=None`, `clob_stream=None`, `use_ws_clob=True` in
CLI layer doesn't affect test-level calls).

---

## Known Limitations / Next Steps

1. **Live mode not wired**: The `--use-ws-clob` flag is explicitly disabled for live mode
   (`use_ws_clob and not live`). Live mode wiring requires additional review of order timing
   implications and is deferred to a future task.

2. **Token subscription happens on first cycle**: The WS connection is opened before the first
   market discovery call, but token subscriptions are deferred until markets are discovered on
   cycle 1. There is a brief window where the WS is connected but has no subscriptions. This is
   by design — market slugs are not known at startup.

3. **No reconnect subscription refresh**: If new markets appear mid-run, the runner will not
   subscribe the new token IDs until `_clob_stream_bootstrapped` resets. For the current 5m/15m
   crypto pair bot this is acceptable (markets are stable within a run window). A more robust
   implementation would re-check subscriptions each cycle.

4. **Book cold start**: On the first 1-2 cycles after startup, the WS book may not yet have
   received a snapshot for all tokens. The `is_ready()` guard ensures the scan falls back to REST
   during this window. No special handling is needed.

5. **`websocket-client` package**: The live WS path requires `websocket-client` (already a
   dependency via `packages/polymarket/simtrader/tape/recorder.py`). Tests never trigger this
   import.
