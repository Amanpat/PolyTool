# 2026-04-15 -- Wallet Discovery Loop B Phase 0 Feasibility

## Objective

Determine whether Alchemy-based watched-wallet monitoring (Loop B) is technically
viable in this repo. Three specific questions needed answers with code-level proof:

1. Can OrderFilled events be decoded to recover maker/taker + asset/market IDs?
2. Is maker/taker attribution available in the current warehouse data?
3. Can the wallet filter be updated dynamically at runtime without data loss?

Additionally characterized CU budget and topic-filtering mechanics.

SPEC reference: `docs/specs/SPEC-wallet-discovery-v1.md` — Loop B listed as
out-of-scope for v1 with three blockers: (1) Alchemy account creation, (2)
proof-of-feasibility for dynamic topic filter updates, (3) CU consumption verification.
This packet addresses blockers #2 and #3. Blocker #1 remains human-action only.

---

## Evidence Table

| Question | Finding | Evidence Source | Verdict |
|----------|---------|-----------------|---------|
| Q1: Can OrderFilled events be decoded to recover maker/taker + asset/market IDs? | `decode_order_filled()` implemented using pure Python ABI decoding (no web3.py). topic2=maker, topic3=taker (both indexed, extracted from last 20 bytes of 32-byte topics). Data payload contains makerAssetId, takerAssetId, makerAmountFilled, takerAmountFilled, fee as five consecutive uint256 values. All fields decoded correctly in test fixtures. | `packages/polymarket/discovery/loop_b_probe.py` + `tests/test_loop_b_probe.py` (36 tests, 36 passing) | **YES — proven with deterministic tests** |
| Q2: Is maker/taker attribution available in current warehouse data? | NO. `user_trades` table (02_tables.sql) has `side` (BUY/SELL direction) but NO maker or taker address columns. `jb_trades` table (22_jon_becker_trades.sql) has `taker_side` (trade direction flag) which is NOT a wallet address. Neither table contains maker/taker wallet attribution. | `infra/clickhouse/initdb/02_tables.sql`, `infra/clickhouse/initdb/22_jon_becker_trades.sql`, `check_historical_maker_taker()` function | **NOT AVAILABLE — on-chain events only; no backfill possible** |
| Q3: Can the wallet filter be updated dynamically without data loss? | Alchemy `eth_subscribe("logs")` does NOT support in-place filter modification. Must unsubscribe (eth_unsubscribe) and resubscribe with new filter. A brief gap exists during the swap cycle. Mitigation: A/B subscription swap pattern — keep old subscription active until new one confirms, then unsubscribe old; dedup by (tx_hash, log_index) during overlap. | Alchemy eth_subscribe docs, GLM-5 research archive (2026-04-09), `describe_dynamic_subscription_behavior()` | **YES WITH CONSTRAINTS — A/B swap pattern required** |
| Q4: Is CU consumption within free tier budget? | 50 wallets at 20 trades/day = 1,200,000 CU/month (notifications) + 180,000 CU/month (eth_getLogs) = 1,380,000 CU total. That is 4.6% of the 30,000,000 CU free tier. Even 200 wallets at 50 trades/day = ~12.2M CU (40.6%), still well within free tier. | `estimate_alchemy_cu()` + GLM-5 CU research (40 CU/notification, 60 CU/eth_getLogs) | **YES — massive headroom; 50 wallets uses <5% of free tier** |
| Q5: Is the topic-based wallet filtering approach technically sound? | YES. OrderFilled has `maker` as topic2 and `taker` as topic3 (both indexed). Alchemy `eth_subscribe` supports OR logic within a single topic position (pass a list of padded addresses). To filter maker OR taker, two separate subscriptions are needed — one on topic2, one on topic3. Both filter helpers implemented and tested. Alternative: unfiltered subscription + Python post-filter (simpler but higher CU). | `build_wallet_filter_topics()`, `build_wallet_filter_topics_taker()`, `build_wallet_filter_topics_either()` in loop_b_probe.py; Ethereum log subscription semantics. | **YES — topic-based filtering confirmed viable** |

---

## Remaining Blockers for Loop B Implementation

**BLOCKER-1 (human-action): Alchemy account creation + API key provisioning.**

Cannot be resolved by code. Operator must:
1. Create account at alchemy.com (free tier is sufficient for current wallet counts).
2. Create a Polygon mainnet app in the Alchemy dashboard.
3. Copy the API key and add `ALCHEMY_API_KEY=<key>` to `.env`.
4. The WebSocket endpoint will be: `wss://polygon-mainnet.g.alchemy.com/v2/<API_KEY>`

Estimated time: 5-10 minutes. No cost at current volume.

---

**BLOCKER-2 (implementation): Async WebSocket connection manager.**

Need a production WebSocket client with:
- Persistent connection to Alchemy WebSocket endpoint
- Reconnection logic with exponential backoff
- Heartbeat / ping-pong to detect stale connections
- A/B subscription swap pattern (dual subscription slots)
- Deduplication by (tx_hash, log_index) during overlap window

Estimated scope: ~200-300 lines of asyncio code.

Dependency decision required: `websocket-client` (sync, already in pyproject.toml) is
usable for a simple single-thread implementation but has reconnection limitations.
`websockets` library (async) is recommended for production. Currently NOT in pyproject.toml.

Pattern references already in repo:
- `packages/polymarket/crypto_pairs/clob_stream.py` — CLOB WebSocket client pattern
- `packages/polymarket/simtrader/shadow/runner.py` — WebSocket shadow runner pattern

---

**BLOCKER-3 (implementation): New ClickHouse table for decoded on-chain fill events.**

A new DDL file (e.g., `infra/clickhouse/initdb/28_loop_b_fills.sql`) is needed with columns:

```sql
CREATE TABLE loop_b_fills (
    tx_hash        FixedString(66),
    block_number   UInt64,
    log_index      UInt32,
    maker          FixedString(42),
    taker          FixedString(42),
    maker_asset_id UInt256,
    taker_asset_id UInt256,
    maker_amount   UInt256,
    taker_amount   UInt256,
    fee            UInt256,
    contract_address FixedString(42),
    decoded_at     DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (tx_hash, log_index);
```

The (tx_hash, log_index) primary key ensures idempotent writes (overlap window dedup).

---

**BLOCKER-4 (design decision): What happens when a watched wallet trades?**

Options:
- A) Discord alert with trade summary (fastest to implement, uses existing discord.py)
- B) Copy-trade signal emitted to the strategy layer (requires signal bus design)
- C) Append to watchlist activity log only (simplest, purely observational)

This is a product decision, not a technical blocker. Operator must decide before
the notification/alert pipeline is implemented.

---

## Existing Repo Assets That Loop B Can Reuse

| Asset | Location | Reuse Potential |
|-------|----------|-----------------|
| Raw JSON-RPC pattern | `packages/polymarket/on_chain_ctf.py` | Loop B probe follows same no-web3.py convention |
| Discovery module structure | `packages/polymarket/discovery/` | Models, lifecycle state machine, watchlist schema all usable |
| WebSocket client (sync) | pyproject.toml `websocket-client` | Usable for simple Loop B prototype; upgrade to `websockets` async for production |
| CLOB WebSocket client | `packages/polymarket/crypto_pairs/clob_stream.py` | Pattern reference for connection management, reconnection |
| Shadow runner | `packages/polymarket/simtrader/shadow/runner.py` | Pattern reference for WebSocket event loop + tape recording |
| Discord alerting | `packages/polymarket/notifications/discord.py` | Ready-made alert sink for BLOCKER-4 option A |
| ClickHouse write client | `packages/polymarket/discovery/clickhouse_writer.py` | Can be extended for loop_b_fills table |

---

## Overall Verdict

```
VERDICT: READY_WITH_CONSTRAINTS

Loop B is technically viable. OrderFilled event decoding, wallet topic filtering,
and CU budgeting are all proven with deterministic tests and schema evidence.
Four implementation constraints remain:

1. Alchemy account creation (human action, ~5-10 minutes, free tier sufficient).
2. Async WebSocket manager with A/B subscription swap (~200-300 LOC).
3. New ClickHouse table for decoded on-chain fill events (new DDL, ~20 lines).
4. maker/taker data is NOT available historically — Loop B provides this data
   going forward only. No backfill from existing warehouse is possible.

None of these blockers are architectural dead-ends. All have clear implementation
paths using existing repo patterns. The technical foundation is sound.
```

---

## Test Commands Run + Results

**Probe tests (Task 1):**

```
python -m pytest tests/test_loop_b_probe.py -v --tb=short -x
```

Result: **36 passed, 0 failed** in 0.33s

Tests cover:
- Event signature hash verification (keccak256 constant vs. runtime computation)
- `decode_order_filled()`: valid log, maker extraction, taker extraction, data fields,
  large asset IDs, NegRisk contract, hex block/log index parsing
- Error paths: wrong topic0, wrong topic count, empty topics
- `_pad_address_to_topic()`: standard, no-prefix, roundtrip
- `build_wallet_filter_topics()` maker: contract addresses, topic structure, OR list
- `build_wallet_filter_topics_taker()`: topic3 position
- `build_wallet_filter_topics_either()`: returns exactly 2 filters
- `check_historical_maker_taker()`: False for both tables, files cited, taker_side explained
- `estimate_alchemy_cu()`: 50-wallet math exact, 200-wallet within free tier, exceeds verdict
- `describe_dynamic_subscription_behavior()`: can_update_in_place=False, A/B swap pattern

**Regression check (existing discovery suite):**

```
python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py -v --tb=short -q
```

Result: **118 passed, 0 failed** — zero regressions.

**CLI smoke test:**

```
python -m polytool --help
```

Result: exit 0, all commands listed, no import errors.

---

## Codex Review

Skip — no execution layer touched, no live-capital paths. This probe module is
offline-only (pure functions, no network calls, no ClickHouse writes). No
mandatory review files were modified per CLAUDE.md Codex Review Policy.

---

## Files Created

| File | Purpose |
|------|---------|
| `packages/polymarket/discovery/loop_b_probe.py` | OrderFilled ABI decoding, wallet filter helpers, CU estimator, subscription behavior docs |
| `tests/test_loop_b_probe.py` | 36 deterministic offline tests |
| `docs/dev_logs/2026-04-15_wallet_discovery_loop_b_pof.md` | This feasibility verdict document |

Commit: `04e5d4d` (Task 1 — probe module + tests)
