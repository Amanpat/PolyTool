---
phase: quick-054
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/crypto_pairs/clob_stream.py
  - packages/polymarket/clob.py
  - packages/polymarket/crypto_pairs/opportunity_scan.py
  - packages/polymarket/crypto_pairs/paper_runner.py
  - tools/cli/crypto_pair_run.py
  - tests/test_crypto_pair_clob_stream.py
  - docs/dev_logs/2026-03-30_ws_clob_migration.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "ClobStreamClient connects to wss://ws-subscriptions-clob.polymarket.com/ws/market, sends snapshot+delta subscription, and maintains a sorted in-memory book per token"
    - "get_best_bid_ask(token_id) returns (bid, ask) from in-memory book without any HTTP call"
    - "Staleness guard returns None when book age exceeds 5 seconds"
    - "compute_pair_opportunity() uses WS stream when is_ready() is True, falls back to REST when stream is None or not ready"
    - "CryptoPairPaperRunner starts/stops ClobStreamClient lifecycle and passes it through scan_fn"
    - "All 5 unit tests pass offline (no network)"
  artifacts:
    - path: "packages/polymarket/crypto_pairs/clob_stream.py"
      provides: "ClobStreamClient class with subscribe/get_best_bid_ask/is_ready/start/stop"
    - path: "tests/test_crypto_pair_clob_stream.py"
      provides: "5+ offline unit tests"
    - path: "docs/dev_logs/2026-03-30_ws_clob_migration.md"
      provides: "Dev log documenting the migration"
  key_links:
    - from: "packages/polymarket/crypto_pairs/paper_runner.py"
      to: "packages/polymarket/crypto_pairs/clob_stream.py"
      via: "clob_stream param injected into CryptoPairPaperRunner.__init__"
    - from: "packages/polymarket/crypto_pairs/opportunity_scan.py"
      to: "packages/polymarket/crypto_pairs/clob_stream.py"
      via: "stream param in compute_pair_opportunity()"
---

<objective>
Replace REST polling (GET /book called twice per market per cycle) with a persistent WebSocket connection to the Polymarket CLOB market channel. The crypto pair bot will maintain a continuously-updated in-memory orderbook per token, eliminating 2 HTTP calls per market per cycle and enabling sub-second latency reads.

Purpose: Reduce HTTP overhead in the paper runner's scan loop; bring the crypto pair bot closer to live-ready feed architecture.
Output: ClobStreamClient class, modified scan/runner/CLI, and offline unit tests.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/.planning/STATE.md

<interfaces>
<!-- Key types and patterns the executor needs. No codebase exploration required. -->

From packages/polymarket/simtrader/tape/recorder.py:
```python
WS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DEFAULT_RECV_TIMEOUT_SECONDS = 5.0
DEFAULT_RECONNECT_SLEEP_SECONDS = 1.0

# WS subscription message format:
subscribe_msg = json.dumps({
    "assets_ids": self.asset_ids,  # list of token IDs
    "type": "market",
    "custom_feature_enabled": True,
    "initial_dump": True,   # triggers snapshot before deltas
})

# WS connection pattern (raw websocket.WebSocket(), not WebSocketApp):
ws_conn = websocket.WebSocket()
ws_conn.connect(ws_url)
ws_conn.settimeout(recv_timeout_seconds)
ws_conn.send(subscribe_msg)
# recv loop: ws_conn.recv() raises WebSocketTimeoutException on timeout,
# WebSocketConnectionClosedException on disconnect
```

From packages/polymarket/simtrader/tape/schema.py:
```python
EVENT_TYPE_BOOK = "book"          # full snapshot: bids/asks arrays
EVENT_TYPE_PRICE_CHANGE = "price_change"  # delta: side/price/size
```

WS message shapes (from Polymarket market channel):
- Book snapshot: {"event_type": "book", "asset_id": "...", "bids": [{"price":"0.50","size":"100"},...], "asks": [...]}
- Price change delta: {"event_type": "price_change", "asset_id": "...", "changes": [{"side":"BUY"/"SELL","price":"0.50","size":"0"}]}
  - size "0" means level removed; size > 0 means level added/updated
- Modern batched format also exists: top-level "price_changes": [...] array

From packages/polymarket/crypto_pairs/reference_feed.py (BinanceFeed — template to follow):
```python
class BinanceFeed:
    def __init__(self, stale_threshold_s=15.0, _time_fn=None):
        self._lock = threading.Lock()
        self._prices = {}        # symbol -> float
        self._timestamps = {}    # symbol -> float
        self._connection_state = FeedConnectionState.NEVER_CONNECTED
        self._ws_thread = None

    def connect(self):
        # Starts daemon thread running _ws_loop()
        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
        self._ws_thread.start()

    def disconnect(self):
        with self._lock:
            self._connection_state = FeedConnectionState.DISCONNECTED

    def _ws_loop(self):
        while True:
            with self._lock:
                if self._connection_state == FeedConnectionState.DISCONNECTED:
                    break
            try:
                ws_app = websocket.WebSocketApp(url, on_message=..., on_open=..., ...)
                ws_app.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as exc:
                ...
            time.sleep(2)
```

From packages/polymarket/clob.py:
```python
@dataclass
class OrderBookTop:
    token_id: str
    best_bid: Optional[float]
    best_ask: Optional[float]
    raw_json: dict

class ClobClient:
    def get_best_bid_ask(self, token_id: str) -> Optional[OrderBookTop]:
        # Makes HTTP GET /book?token_id=...
        # Returns OrderBookTop or None on failure
```

From packages/polymarket/crypto_pairs/opportunity_scan.py:
```python
def compute_pair_opportunity(market: CryptoPairMarket, clob_client=None) -> PairOpportunity:
    # Uses clob_client.get_best_bid_ask(token_id)
    # Returns PairOpportunity with yes_ask, no_ask, has_opportunity fields

def scan_opportunities(pair_markets, clob_client=None) -> list[PairOpportunity]:
    # Calls compute_pair_opportunity for each market
```

From packages/polymarket/crypto_pairs/paper_runner.py:
```python
class CryptoPairPaperRunner:
    def __init__(self, settings, *, gamma_client=None, clob_client=None,
                 reference_feed=None, store=None, execution_adapter=None,
                 sink=None, heartbeat_callback=None, now_fn=utc_now,
                 sleep_fn=time.sleep, discovery_fn=discover_crypto_pair_markets,
                 scan_fn=scan_opportunities, rank_fn=rank_opportunities,
                 verbose=False):
        ...
        self.clob_client = clob_client
        self.scan_fn = scan_fn

    def run(self):
        # Cycle loop calls:
        pair_markets = self.discovery_fn(gamma_client=self.gamma_client)
        opportunities = self.scan_fn(pair_markets, clob_client=self.clob_client)
```

From packages/polymarket/crypto_pairs/paper_ledger.py (PaperOpportunityObservation fields):
```python
# These are the observation fields already in the model — new fields
# clob_source, clob_age_ms, clob_snapshot_ready must be ADDED.
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement ClobStreamClient</name>
  <files>packages/polymarket/crypto_pairs/clob_stream.py, tests/test_crypto_pair_clob_stream.py</files>
  <behavior>
    - Test 1: snapshot bootstrap — inject a book event for token "T1" with bids=[{price:"0.48",size:"50"}], asks=[{price:"0.52",size:"100"}]; get_best_bid_ask("T1") returns (0.48, 0.52)
    - Test 2: delta application — after snapshot, inject price_change delta removing ask 0.52 (size "0") and adding ask 0.51; get_best_bid_ask returns (0.48, 0.51)
    - Test 3: staleness guard — inject book snapshot at t=0, advance mock clock to t=6; get_best_bid_ask returns None (age > 5s default stale_threshold)
    - Test 4: unsubscribe removes book state — subscribe "T1", inject snapshot, unsubscribe "T1"; is_ready("T1") returns False
    - Test 5: sort order correctness — inject book with asks in random price order [0.55, 0.51, 0.53]; get_best_bid_ask returns best_ask=0.51 (min ask)
    - Test 6: multi-token on one connection — two tokens T1 and T2 each receive their own snapshots; get_best_bid_ask correctly returns per-token values
  </behavior>
  <action>
Create `packages/polymarket/crypto_pairs/clob_stream.py` following the BinanceFeed daemon-thread pattern from reference_feed.py. Key requirements:

**ClobStreamClient class:**
```
__init__(self, *, stale_threshold_s=5.0, ws_url=WS_MARKET_URL,
         recv_timeout_s=5.0, reconnect_sleep_s=1.0,
         _time_fn=None, _event_source=None)
```
- `_time_fn`: injectable clock for staleness tests (default `time.time`)
- `_event_source`: injectable iterable of pre-parsed event dicts for offline testing (bypasses WS entirely, same pattern as ShadowRunner)
- Internal state (all behind `self._lock: threading.Lock()`):
  - `_books: dict[str, dict[str, SortedPriceLevels]]` — per token, per side ("bids"/"asks"), price -> size (float)
  - `_timestamps: dict[str, float]` — token -> unix time of last book update
  - `_subscribed: set[str]` — token IDs currently subscribed
  - `_stopped: bool` — controls reconnect loop exit
- `_bids_key = "bids"`, `_asks_key = "asks"` — side name constants

**Public interface:**
- `subscribe(token_id: str) -> None` — add token to subscribed set; subscription message sent on next reconnect if not yet connected (WS thread sends re-subscription with all current subscribed tokens)
- `unsubscribe(token_id: str) -> None` — remove token from subscribed set, clear its book state and timestamp
- `get_best_bid_ask(token_id: str) -> tuple[float, float] | None` — return (best_bid, best_ask) from in-memory book. Return None if: not subscribed, no snapshot yet, age > stale_threshold_s, or either side empty. best_bid = max price in bids dict. best_ask = min price in asks dict.
- `get_book_age_ms(token_id: str) -> int` — milliseconds since last update for token; returns 999999 if never updated
- `is_ready(token_id: str) -> bool` — True when subscribed, has snapshot data, and age <= stale_threshold_s
- `start() -> None` — idempotent; starts daemon thread running _ws_loop() (same as BinanceFeed.connect())
- `stop() -> None` — sets _stopped=True; signals WS loop to exit

**WS loop (raw websocket.WebSocket(), NOT WebSocketApp — matches TapeRecorder pattern):**
- Import `websocket` inside the method (soft dependency)
- On connect: send subscription message with `{"assets_ids": list(self._subscribed), "type": "market", "custom_feature_enabled": True, "initial_dump": True}`
- settimeout(recv_timeout_s)
- recv loop handles: WebSocketTimeoutException (continue), WebSocketConnectionClosedException (reconnect), normal messages (parse and apply)
- On reconnect: sleep reconnect_sleep_s, send subscription again

**Message parsing:**
```python
def _apply_message(self, raw_msg: str) -> None:
    data = json.loads(raw_msg)
    # Handle both single-event and batched price_changes[] format
    events = data.get("price_changes") or [data]
    for event in events:
        event_type = event.get("event_type") or event.get("type")
        asset_id = event.get("asset_id") or event.get("market")
        if not asset_id:
            continue
        if event_type == "book":
            self._apply_snapshot(asset_id, event)
        elif event_type == "price_change":
            self._apply_delta(asset_id, event)
```

**_apply_snapshot:** Replace entire bids/asks for token with parsed levels. Convert {"price": str, "size": str} to {float_price: float_size} dicts. Update timestamp.

**_apply_delta:** Parse "changes" list: each change has "side" (BUY=bids, SELL=asks), "price", "size". Size "0" or 0.0 → delete that price level. Size > 0 → update/insert. Update timestamp.

**If _event_source is set:** Skip WS entirely. In `start()`, run a thread that iterates `_event_source` calling `_apply_message(json.dumps(event))` for each (or directly `_apply_message` if events are dicts). This matches ShadowRunner's `_event_source` test hook.

Write tests BEFORE implementation. Tests use `_event_source` and `_time_fn` injection — no network.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_crypto_pair_clob_stream.py -x -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>6 tests pass. ClobStreamClient correctly maintains in-memory sorted book, applies deltas, enforces staleness, and works with injected event sources.</done>
</task>

<task type="auto">
  <name>Task 2: Wire ClobStreamClient into scan, runner, and CLI</name>
  <files>
    packages/polymarket/clob.py,
    packages/polymarket/crypto_pairs/opportunity_scan.py,
    packages/polymarket/crypto_pairs/paper_runner.py,
    tools/cli/crypto_pair_run.py,
    docs/dev_logs/2026-03-30_ws_clob_migration.md
  </files>
  <action>
Four targeted modifications plus a dev log. No changes to accumulation engine, momentum detection, signal logic, reference feed, SimTrader, or clob_order_client.py.

**1. packages/polymarket/clob.py — add `get_best_bid_ask_from_stream()`:**
Add method to ClobClient (after the existing `get_best_bid_ask` method):
```python
def get_best_bid_ask_from_stream(
    self,
    token_id: str,
    stream,  # ClobStreamClient — typed as Any to avoid circular import
    *,
    stale_threshold_s: float = 5.0,
) -> Optional[OrderBookTop]:
    """Read best bid/ask from a live WS stream with staleness guard.

    Returns None if stream is None, token not ready, or book age > stale_threshold_s.
    Falls back to REST via get_best_bid_ask() is NOT done here — caller decides fallback.
    """
    if stream is None:
        return None
    result = stream.get_best_bid_ask(token_id)
    if result is None:
        return None
    bid, ask = result
    return OrderBookTop(token_id=token_id, best_bid=bid, best_ask=ask, raw_json={})
```

**2. packages/polymarket/crypto_pairs/opportunity_scan.py — add `stream` param:**

Modify `compute_pair_opportunity` signature:
```python
def compute_pair_opportunity(
    market: CryptoPairMarket,
    clob_client=None,
    stream=None,        # ClobStreamClient or None
) -> PairOpportunity:
```

In the body, after constructing `opp`, replace the two `clob_client.get_best_bid_ask()` calls with:
```python
if stream is not None and stream.is_ready(market.yes_token_id) and stream.is_ready(market.no_token_id):
    yes_top = clob_client.get_best_bid_ask_from_stream(market.yes_token_id, stream)
    no_top = clob_client.get_best_bid_ask_from_stream(market.no_token_id, stream)
    clob_source = "ws"
    yes_age_ms = stream.get_book_age_ms(market.yes_token_id)
    no_age_ms = stream.get_book_age_ms(market.no_token_id)
    clob_age_ms = max(yes_age_ms, no_age_ms)
    clob_snapshot_ready = True
else:
    yes_top = clob_client.get_best_bid_ask(market.yes_token_id)
    no_top = clob_client.get_best_bid_ask(market.no_token_id)
    clob_source = "rest"
    clob_age_ms = -1
    clob_snapshot_ready = False
```

Add `clob_source`, `clob_age_ms`, `clob_snapshot_ready` to `PairOpportunity` dataclass:
```python
clob_source: str = "rest"        # "ws" | "rest"
clob_age_ms: int = -1            # -1 when REST (age unknown)
clob_snapshot_ready: bool = False
```

Modify `scan_opportunities` to accept and thread-through `stream=None`:
```python
def scan_opportunities(pair_markets, clob_client=None, stream=None):
    ...
    return [compute_pair_opportunity(m, clob_client=clob_client, stream=stream)
            for m in pair_markets]
```

**3. packages/polymarket/crypto_pairs/paper_runner.py — lifecycle and token subscription:**

Add `clob_stream=None` param to `CryptoPairPaperRunner.__init__()`:
```python
def __init__(self, settings, *, ..., clob_stream=None, ...):
    ...
    self.clob_stream = clob_stream
    self._owns_clob_stream = clob_stream is None  # will be set to True if we build one
```

Do NOT auto-create a ClobStreamClient inside __init__ (avoid unexpected network connections in test contexts). The runner only starts the stream if one was explicitly passed in (or if `use_ws_clob=True` was set — handled in CLI layer).

In `run()`, after the reference feed connect block, add:
```python
if self.clob_stream is not None:
    self.clob_stream.start()
    # Subscribe all token IDs from discovered markets on first cycle
    self._clob_stream_bootstrapped = False
```

In the cycle loop, after `pair_markets = self.discovery_fn(...)`, add:
```python
if self.clob_stream is not None and not getattr(self, "_clob_stream_bootstrapped", True):
    for m in pair_markets:
        self.clob_stream.subscribe(m.yes_token_id)
        self.clob_stream.subscribe(m.no_token_id)
    self._clob_stream_bootstrapped = True
```

Change the `scan_fn` call to pass stream:
```python
opportunities = self.scan_fn(pair_markets, clob_client=self.clob_client, stream=self.clob_stream)
```

In the `finally` block (where reference_feed.disconnect() is called), add:
```python
if self.clob_stream is not None:
    self.clob_stream.stop()
    self.store.record_runtime_event("clob_stream_stopped")
```

**4. tools/cli/crypto_pair_run.py — add `--use-ws-clob` flag:**

Add to `build_parser()`:
```python
parser.add_argument(
    "--use-ws-clob",
    action="store_true",
    default=True,
    help=(
        "Use persistent WebSocket CLOB feed instead of REST polling for orderbook reads. "
        "Enabled by default. Use --no-use-ws-clob to revert to REST-only mode."
    ),
)
parser.add_argument(
    "--no-use-ws-clob",
    dest="use_ws_clob",
    action="store_false",
    help="Disable WS CLOB feed; use REST polling for orderbook reads.",
)
```

In the paper mode runner construction block, after building `settings`, add:
```python
clob_stream = None
if args.use_ws_clob and not args.live:
    from packages.polymarket.crypto_pairs.clob_stream import ClobStreamClient
    clob_stream = ClobStreamClient()
```

Pass `clob_stream=clob_stream` to `CryptoPairPaperRunner(...)`.

**5. docs/dev_logs/2026-03-30_ws_clob_migration.md:**

Write a concise dev log (100-200 lines) covering:
- Motivation: REST polling cost (~2 HTTP calls per market per cycle at 0.5s cycle interval = 4+ req/s for 2 markets)
- What was built: ClobStreamClient, its connection pattern (matches TapeRecorder), book state model
- Files changed and what changed in each
- REST fallback behavior (still present, triggered when stream=None or not ready)
- Test approach: _event_source injection, _time_fn injection
- Known limitations / next steps (e.g., live mode wiring not yet done)
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_crypto_pair_clob_stream.py tests/test_crypto_pair_scan.py tests/test_crypto_pair_run.py -x -q --tb=short 2>&1 | tail -10 && python -m polytool --help 2>&1 | grep -i "crypto\|help" | head -5</automated>
  </verify>
  <done>
    - All 3 test files pass (clob_stream + scan + run)
    - PairOpportunity has clob_source, clob_age_ms, clob_snapshot_ready fields
    - scan_opportunities accepts stream= param, falls back to REST when stream is None
    - CryptoPairPaperRunner accepts clob_stream= param and manages start/stop lifecycle
    - --use-ws-clob / --no-use-ws-clob flags present in crypto-pair-run --help
    - Dev log written to docs/dev_logs/2026-03-30_ws_clob_migration.md
    - python -m polytool --help loads without ImportError
  </done>
</task>

</tasks>

<verification>
Full regression check after both tasks complete:

```bash
cd "D:/Coding Projects/Polymarket/PolyTool"
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```

Expected: all existing 2775 tests still pass, plus 6 new tests in test_crypto_pair_clob_stream.py.

Smoke check:
```bash
python -m polytool --help
python -m polytool crypto-pair-run --help 2>&1 | grep -i "ws-clob"
```
</verification>

<success_criteria>
- tests/test_crypto_pair_clob_stream.py: 6 tests pass (snapshot, delta, staleness, unsubscribe, sort, multi-token)
- PairOpportunity dataclass has clob_source / clob_age_ms / clob_snapshot_ready fields (backward-compatible, all default to rest/-1/False)
- scan_opportunities() signature accepts stream= keyword arg without breaking existing callers
- CryptoPairPaperRunner.__init__() accepts clob_stream= without breaking existing tests
- --use-ws-clob flag wired in CLI (default True in paper mode, not wired for live mode)
- REST fallback path is fully preserved: stream=None or is_ready()=False both route to clob_client.get_best_bid_ask()
- No changes to accumulation engine, momentum detection, reference feed, SimTrader, or clob_order_client.py
- Full test suite: >= 2781 passing (2775 existing + 6 new), 0 new failures
- Dev log written
</success_criteria>

<output>
After completion, create `.planning/quick/54-websocket-clob-feed-migration-for-crypto/054-SUMMARY.md`

Also create branch `feat/ws-clob-feed` from current `phase-1B` HEAD before starting work.
</output>
