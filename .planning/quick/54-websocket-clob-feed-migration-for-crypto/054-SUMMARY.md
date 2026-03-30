---
phase: quick
plan: "054"
subsystem: crypto-pair-bot
tags: [websocket, clob, orderbook, performance, crypto-pair]
dependency_graph:
  requires: [packages/polymarket/crypto_pairs/clob_stream.py]
  provides: [ClobStreamClient, get_best_bid_ask_from_stream, WS-backed scan path]
  affects: [opportunity_scan.py, paper_runner.py, crypto_pair_run.py]
tech_stack:
  added: [websocket-client (soft dep; already present via TapeRecorder)]
  patterns: [daemon-thread + Lock (BinanceFeed pattern), _event_source injection (ShadowRunner pattern), _time_fn injection (mock clock)]
key_files:
  created:
    - packages/polymarket/crypto_pairs/clob_stream.py
    - tests/test_crypto_pair_clob_stream.py
    - docs/dev_logs/2026-03-30_ws_clob_migration.md
  modified:
    - packages/polymarket/clob.py
    - packages/polymarket/crypto_pairs/opportunity_scan.py
    - packages/polymarket/crypto_pairs/paper_runner.py
    - tools/cli/crypto_pair_run.py
decisions:
  - "Raw websocket.WebSocket() (not WebSocketApp) matches TapeRecorder pattern; simpler reconnect loop"
  - "5s staleness threshold: stale book returns None and scan falls back to REST"
  - "Token subscription deferred to first cycle: market slugs not known at startup"
  - "Live mode not wired: use_ws_clob gated by 'not live' until order-timing implications reviewed"
  - "Soft websocket import inside _ws_loop: paper/test paths never trigger the import"
metrics:
  duration: "~45 minutes"
  completed_date: "2026-03-30"
  tasks_completed: 2
  files_created: 3
  files_modified: 4
  tests_added: 12
  regression_count: 2787
---

# Quick Task 054: WebSocket CLOB Feed Migration Summary

Persistent WS CLOB book client for crypto pair bot, eliminating REST polling (8 GET /book calls/s) and replacing with lock-protected in-memory orderbook reads that fall back to REST when the WS book is stale or unavailable.

## Objective

Replace `clob_client.get_best_bid_ask(token_id)` REST calls in the crypto pair scan loop with reads from a continuously-updated in-memory orderbook maintained by a persistent WebSocket connection to `wss://ws-subscriptions-clob.polymarket.com/ws/market`.

## Tasks Completed

### Task 1 — TDD: ClobStreamClient (RED → GREEN)

**Commit:** `9d871a1`

Created `packages/polymarket/crypto_pairs/clob_stream.py` with full TDD workflow:

- RED phase: 12 offline tests written in `tests/test_crypto_pair_clob_stream.py` — all intentionally failing
- GREEN phase: implementation written to pass all 12 tests

Key design choices:
- Raw `websocket.WebSocket()` with `settimeout()` — matches `TapeRecorder` pattern, simpler reconnect loop than `WebSocketApp`
- Daemon thread + `threading.Lock` — matches `BinanceFeed` pattern from `reference_feed.py`
- `_event_source` injection: offline tests inject pre-built event dicts; WS thread iterates them instead of opening a connection
- `_time_fn` injection: mock clock for staleness assertions without real-time waits
- 5-second default staleness threshold: `get_best_bid_ask()` returns `None` if last book update is stale; scan falls back to REST
- Soft websocket import inside `_ws_loop`: paper/test paths never import `websocket`

Message formats handled:
- Book snapshot: `{"event_type": "book", "asset_id": ..., "bids": [...], "asks": [...]}`
- Price change delta: `{"event_type": "price_change", "asset_id": ..., "changes": [...]}`
- Batched deltas: `{"price_changes": [{...}, ...]}`
- Delta semantics: `side="BUY"` → bids, `side="SELL"` → asks; size `"0"` removes level

### Task 2 — Wire ClobStreamClient into scan, runner, and CLI

**Commit:** `d1d94fe`

Four files modified + dev log created:

**`packages/polymarket/clob.py`** — Added `get_best_bid_ask_from_stream(token_id, stream)` to `ClobClient`. Reads from stream's in-memory book, returns `OrderBookTop` (same type as REST path). Returns `None` if stream is None or token is not ready.

**`packages/polymarket/crypto_pairs/opportunity_scan.py`** — Three changes:
- `PairOpportunity` gets 3 new backward-compatible fields: `clob_source: str = "rest"`, `clob_age_ms: int = -1`, `clob_snapshot_ready: bool = False`
- `compute_pair_opportunity()` gains `stream=None` parameter; uses WS path when both tokens `is_ready()`, else REST
- `scan_opportunities()` gains `stream=None` parameter, passes through to `compute_pair_opportunity()`

**`packages/polymarket/crypto_pairs/paper_runner.py`** — `CryptoPairPaperRunner` gains `clob_stream=None` parameter. Lifecycle management: `start()` after reference feed connect, per-token subscriptions on first cycle (deferred because market slugs not known at startup), `stop()` in `finally` block.

**`tools/cli/crypto_pair_run.py`** — Added `--use-ws-clob` (default True for paper) and `--no-use-ws-clob` flags. Creates `ClobStreamClient()` when `use_ws_clob=True and not live`, passes to runner.

**`docs/dev_logs/2026-03-30_ws_clob_migration.md`** — Full design rationale, files modified, REST fallback behavior, test approach, known limitations.

## Verification

```
python -m pytest tests/test_crypto_pair_clob_stream.py tests/test_crypto_pair_scan.py tests/test_crypto_pair_run.py -x -q
91 passed in 1.97s

python -m pytest tests/ -x -q --tb=short
2787 passed, 25 warnings in 101.65s

python -m polytool crypto-pair-run --help  # shows --use-ws-clob / --no-use-ws-clob flags
```

## REST Fallback Behavior

The REST path is fully preserved. Fallback triggers in three cases:
1. `stream=None` (e.g., `--no-use-ws-clob` or test without a stream)
2. `stream.is_ready(token_id)` is False for either token (not yet subscribed / stale / no snapshot)
3. Any `get_best_bid_ask_from_stream()` returning None

Existing test callers in `test_crypto_pair_scan.py` and `test_crypto_pair_run.py` pass unchanged because all new parameters default to `None`.

## Deviations from Plan

None — plan executed exactly as written.

## Known Limitations (documented in dev log)

1. **Live mode not wired**: `--use-ws-clob` gated by `not live`. Live mode wiring deferred pending order-timing review.
2. **Cold start**: On the first 1-2 cycles, WS book may not have snapshot yet. `is_ready()` guard ensures REST fallback during this window.
3. **No mid-run subscription refresh**: New markets appearing mid-run will not get WS subscriptions until `_clob_stream_bootstrapped` resets. Acceptable for current stable 5m/15m run windows.

## Known Stubs

None — all data paths wired. WS path active when `is_ready()` returns True; REST path always available as fallback.

## Self-Check: PASSED
