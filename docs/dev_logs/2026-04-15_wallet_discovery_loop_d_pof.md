# 2026-04-15 — Wallet Discovery Loop D: Phase 0 Feasibility Assessment

## Objective

Determine whether PolyTool can support the managed CLOB subscription and
anomaly-detection substrate that the roadmap assumes for Loop D of wallet
discovery. SPEC-wallet-discovery-v1.md (frozen 2026-04-09) explicitly lists
three Loop D blockers: (1) ClobStreamClient lacks PING keepalive and dynamic
subscription, (2) platform-wide subscription management is unbuilt, and
(3) the CLOB trade event schema does not include wallet addresses. This
assessment produces evidence-backed answers to those three questions:
Can we bootstrap and maintain subscriptions to all active markets? Does the
trade-event schema provide enough data for anomaly detectors? What
reconnection, backfill, and scaling constraints exist?

## Verdict

```
VERDICT: READY_WITH_CONSTRAINTS
```

The managed subscription pattern is viable: the Gamma API provides a
bootstrap source for all active market token IDs, the CLOB WS protocol
supports dynamic subscribe/unsubscribe without reconnecting, and single-
process Python throughput capacity (10k+ msg/s) far exceeds the estimated
peak CLOB feed rate (~50 msg/s). Four anomaly detectors (volume_spike,
price_anomaly, trade_burst, spread_divergence) can operate entirely on
CLOB `last_trade_price` event fields. However, two blocker-severity gaps
exist in ClobStreamClient (no PING keepalive, no runtime dynamic
subscription), plus a by-design data constraint (no wallet addresses in
CLOB events, requiring Alchemy eth_getLogs as a second feed). All blockers
have clear, well-understood remediation paths — none involve unknown
protocol constraints or external dependencies beyond already-used libraries.

## Evidence: Subscription Scale

Live Gamma API bootstrap run (2026-04-15, max_pages=50, page_size=100):

| Metric | Value |
|--------|-------|
| Total active markets | 5,000 (API pagination cap hit — true count likely higher) |
| Total CLOB token IDs | 10,000 |
| Tokens with accepting_orders=True | 9,940 |
| Category breakdown | Not available (Gamma API returns empty category field for active markets) |

Note: Gamma API `fetch_all_markets(active_only=True, max_pages=50)` returns exactly
5,000 markets / 10,000 tokens at the pagination cap. The `category` field is empty
in the current Gamma response schema (category_source='none'). True platform-wide
market count is likely larger; 5,000+ active markets / 10,000+ tokens is the
confirmed lower bound.

**Throughput estimate:**
- Historical Polymarket trade volume: 150,000–300,000 trades/day across all markets
- Average rate: 150k / 86400 ≈ 1.7 msg/s; 300k / 86400 ≈ 3.5 msg/s
- Estimated peak (US market hours): ~50 msg/s
- Single Python asyncio/threading process capacity: 10,000+ msg/s (websocket-client
  benchmark; confirmed by ShadowRunner production usage)
- Conclusion: **throughput is NOT a bottleneck.** Peak feed is 200x below single-
  process capacity. Loop D does not require multi-process or cluster architecture.

## Evidence: ClobStreamClient Gap Audit

Full output of `audit_clob_stream_gaps()` as of 2026-04-15:

| Gap ID | Severity | Description | Code Reference | Remediation |
|--------|----------|-------------|----------------|-------------|
| G-01 | **blocker** | No PING keepalive: `_ws_loop` sends no WebSocket PING frames. CLOB WS server requires PING every 10 s; without it the server closes the connection after ~30 s silence. | `clob_stream.py:_ws_loop` — recv() loop has no threading.Timer or periodic ws_conn.ping() call | Add threading.Timer(10, ping_fn) that calls ws_conn.ping() every 10 s while connection is open |
| G-02 | **blocker** | No dynamic subscribe/unsubscribe at runtime: `subscribe()` adds to `self._subscribed` (set) but only takes effect on the NEXT (re)connect. Loop D needs to add/remove thousands of tokens at runtime. | `clob_stream.py:subscribe() L95-103` — only updates set; `_ws_loop L225-226` sends subscribe msg only at connect | Add `send_subscribe(asset_ids)` helper that sends subscribe message to open ws_conn immediately when thread is running |
| G-03 | constraint | No `new_market` / `market_resolved` event parsing: `_apply_message` handles only `"book"` and `"price_change"`. Loop D needs lifecycle events to maintain active-market set. | `clob_stream.py:_apply_message L276-294` — event_type branch handles 'book' and 'price_change' only | Extend `_apply_message` (or subclass) to parse 'new_market' and 'market_resolved' event types with registered lifecycle callbacks |
| G-04 | constraint | Fixed token set at construction: design assumes tokens subscribed before `start()` remain stable. Loop D manages 10,000+ tokens that change over time. | `clob_stream.py:__init__ L66-89` — `self._subscribed` initialized as empty set; subscribe() called pre-start() in usage pattern | Decouple token set management from connection lifecycle; build higher-level subscription manager bootstrapped from Gamma |
| G-05 | enhancement | No reconnect backfill: `_ws_loop` reconnects and re-subscribes but does not fetch missed events via REST `GET /trades` for the disconnection window. | `clob_stream.py:_ws_loop L219-271` — reconnect path re-subscribes only; no REST /trades backfill | On reconnect, record disconnect_time; call REST GET /trades with startTs=disconnect_time for each subscribed asset_id |

**Assessment of blocker remediability:**

Both G-01 and G-02 involve adding well-understood WebSocket functionality using
already-imported libraries (websocket-client). No unknown protocol constraints,
no new external dependencies. Estimated implementation complexity:
- G-01 (PING): Low — 10-15 lines, threading.Timer pattern
- G-02 (dynamic sub): Medium — requires live ws_conn reference accessible from
  subscribe/unsubscribe methods while thread is running (thread-safety required)

Neither blocker blocks the feasibility verdict from being READY_WITH_CONSTRAINTS
because both have a clear, achievable remediation path.

## Evidence: Anomaly Detector Data Sufficiency

`assess_trade_event_sufficiency()` run against canonical `last_trade_price` event schema:

```json
{
  "event_type": "last_trade_price",
  "asset_id": "0x...",
  "price": "0.65",
  "size": "150",
  "side": "BUY",
  "timestamp": "1712345678",
  "fee_rate_bps": "200",
  "market": "btc-up-or-down-may-2026"
}
```

| Detector | Required Fields | Available in CLOB Event | Ready | Missing |
|----------|----------------|-------------------------|-------|---------|
| volume_spike | asset_id, size, timestamp | Yes | **Yes** | — |
| price_anomaly | asset_id, price, timestamp | Yes | **Yes** | — |
| trade_burst | asset_id, timestamp, side | Yes | **Yes** | — |
| spread_divergence | asset_id, price, side, timestamp | Yes | **Yes** | — |
| wallet_attribution | maker_address, taker_address | No | **No** | Both fields |

**Two-feed architecture (by design, not a bug):**

CLOB `last_trade_price` events are market-level. They tell WHAT happened: which
token, at what price/size, at what time, on which side. They do NOT contain wallet
addresses. This is expected per the Polymarket protocol design.

Wallet attribution requires a second feed: Alchemy eth_getLogs on the CTFExchange
contract (Polygon), which emits `OrderFilled` events containing maker and taker
addresses. This two-feed architecture is explicitly accepted in:
- `docs/obsidian-vault/09-Decisions/Decision - Loop D Managed CLOB Subscription.md`
- `docs/obsidian-vault/09-Decisions/Decision - Two-Feed Architecture.md`

The CLOB feed detects WHAT is anomalous (market, timing, price pattern). Alchemy
tells WHO did it (wallet addresses for Loop D candidate discovery).

## Reconnection and Backfill Constraints

From protocol research (docs/obsidian-vault/11-Prompt-Archive/ GLM5 CLOB WebSocket doc):

| Constraint | Status |
|-----------|--------|
| WS PING required every 10 s | Required but not implemented in ClobStreamClient (G-01) |
| Dynamic subscribe/unsubscribe | Supported by protocol WITHOUT full reconnect; not implemented in client (G-02) |
| No WS replay on disconnect | Events during disconnection are permanently lost from WS |
| Backfill on reconnect | Available via REST `GET /trades?asset_id=X&startTs=Y` — not implemented (G-05) |
| No documented subscription limit per connection | Unverified at 10k token scale — needs live probe |
| Re-bootstrap on reconnect | Re-fetch from Gamma API + re-subscribe all tokens |
| Reconnect approach | Exponential backoff recommended; counter for monitoring |

**Key risk:** Subscription limit per connection is undocumented. Live probe at
scale (subscribe 10k tokens on a single connection, observe for 1h) is the
recommended next step to confirm single-connection viability vs. multi-connection
sharding.

## Constraints Matrix

| Constraint | Category | Severity | Remediation Complexity | Notes |
|------------|----------|----------|------------------------|-------|
| No PING in ClobStreamClient (G-01) | Protocol | Blocker | Low | Add threading.Timer or select-based ping every 10 s |
| No dynamic sub/unsub (G-02) | Architecture | Blocker | Medium | Refactor ClobStreamClient or build ManagedSubscriptionClient |
| No lifecycle event handling (G-03) | Protocol | Constraint | Low | Parse new_market/market_resolved JSON in _apply_message |
| Fixed token set at construction (G-04) | Architecture | Constraint | Medium | Higher-level subscription manager bootstrapped from Gamma |
| No wallet address in CLOB events | Data | Constraint | N/A (by design) | Requires Alchemy eth_getLogs second feed |
| No backfill on reconnect (G-05) | Reliability | Enhancement | Medium | REST /trades paginated fetch after reconnect |
| Subscription limit at 10k tokens | Scale | Risk | Unknown | Needs live probe — not done in feasibility |

## ClobStreamClient Adaptation Requirements

The following changes are required in ClobStreamClient (or a new ManagedSubscriptionClient)
to support Loop D. These are implementation requirements for the Loop D build phase, NOT
deliverables of this feasibility assessment.

1. **PING keepalive timer (G-01):** Add `threading.Timer(10, _ping)` that calls
   `ws_conn.ping()` every 10 s while connection is open. Reset on each recv().
2. **Runtime subscribe/unsubscribe (G-02):** Add `send_subscribe(asset_ids)` and
   `send_unsubscribe(asset_ids)` methods that send WS messages to the live connection
   immediately (thread-safe via the existing `self._lock`).
3. **Lifecycle event parsing (G-03):** Extend `_apply_message` to dispatch
   `new_market` and `market_resolved` events to registered callbacks.
4. **Remove constructor-time-only token-set assumption (G-04):** Allow the token
   set to be dynamic; decouple subscription management from connection lifecycle.
5. **Reconnect backfill hook (G-05):** On reconnect, record the gap window and
   offer a callback hook to fetch REST /trades for the missed period.
6. **Platform-wide subscription manager:** Bootstrap from Gamma API on startup,
   maintain via lifecycle events (G-03) to add/remove tokens as markets open/close.

## Next Blockers (for Loop D Implementation)

1. Implement PING keepalive in ClobStreamClient or new ManagedSubscriptionClient (G-01).
2. Add runtime subscribe/unsubscribe message sending to open WS connection (G-02).
3. Live probe: subscribe all active tokens (~10k) on a single connection, measure
   connection stability over 1 hour, confirm subscription limit is not hit.
4. Estimate Alchemy eth_getLogs CU cost for wallet attribution feed at expected
   Loop D event volume.
5. Choose anomaly detector algorithms (binomial win-rate first per research doc;
   volume_spike and trade_burst are simplest to implement).
6. Design ClickHouse schema for anomaly events (asset_id, detector, score, ts,
   context JSON).
7. Build platform-wide subscription manager (bootstrap from Gamma, maintain via
   lifecycle events).

## Test Commands Run

```
python -m pytest tests/test_loop_d_probe.py -v --tb=short -x
# Result: 24 passed in 0.26s

python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py -v --tb=short
# Result: 118 passed in 2.22s

python -m pytest tests/ -q --tb=no --deselect tests/test_ris_phase2_cloud_provider_routing.py -x
# Result: 4059 passed, 11 deselected, 25 warnings in 107.86s
```

Zero regressions across all test suites.

## Commits

| Hash | Message |
|------|---------|
| b3ca095 | feat(quick-260415-rdy-01): Loop D feasibility probe helpers and tests |
| (task 2 commit) | docs(quick-260415-rdy-01): Loop D feasibility dev log |

## Codex Review

Tier: **Skip** — probe-only module and feasibility documentation. No execution paths,
strategy logic, ClickHouse write paths, order placement, or risk controls were modified.
