---
phase: quick-260415-rdp
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/discovery/loop_b_probe.py
  - tests/test_loop_b_probe.py
  - docs/dev_logs/2026-04-15_wallet_discovery_loop_b_pof.md
autonomous: true
requirements: ["loop-b-feasibility"]

must_haves:
  truths:
    - "OrderFilled event ABI decoding is proven with a deterministic test fixture"
    - "Maker/taker + asset_id extraction from raw log data is verified"
    - "Topic-based wallet filtering approach is validated against event structure"
    - "Historical maker/taker data availability in current warehouse is documented"
    - "Dynamic watchlist subscription update behavior is characterized"
    - "Feasibility verdict (READY / READY_WITH_CONSTRAINTS / BLOCKED) is written with evidence"
  artifacts:
    - path: "packages/polymarket/discovery/loop_b_probe.py"
      provides: "OrderFilled ABI decoding + log filter helpers"
      exports: ["decode_order_filled", "build_wallet_filter_topics", "OrderFilledEvent"]
    - path: "tests/test_loop_b_probe.py"
      provides: "Deterministic tests for all probe helpers"
    - path: "docs/dev_logs/2026-04-15_wallet_discovery_loop_b_pof.md"
      provides: "Feasibility verdict with evidence table"
  key_links:
    - from: "packages/polymarket/discovery/loop_b_probe.py"
      to: "on_chain_ctf.py pattern"
      via: "same raw JSON-RPC approach, no web3.py"
      pattern: "eth_call|eth_getLogs"
---

<objective>
Prove or disprove the technical viability of Loop B (Alchemy-based watched-wallet
monitoring) for the Wallet Discovery pipeline. Produce a clear feasibility verdict
backed by deterministic tests and documented evidence.

Purpose: The SPEC-wallet-discovery-v1.md lists Loop B as out-of-scope for v1 with
three named blockers: (1) Alchemy account creation, (2) proof-of-feasibility for
dynamic topic filter updates at runtime, (3) CU consumption verification. This task
addresses blocker #2 (dynamic filters) and partially #3 (CU model validation) with
code-level proof. Blocker #1 (account creation) is a human-action prerequisite that
cannot be resolved by code alone.

Output: A probe module with OrderFilled event decoding, topic-filter construction
helpers, and a comprehensive feasibility dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@docs/specs/SPEC-wallet-discovery-v1.md
@docs/obsidian-vault/08-Research/04-Loop-B-Live-Monitoring.md
@docs/obsidian-vault/09-Decisions/Decision - Two-Feed Architecture.md
@docs/obsidian-vault/11-Prompt-Archive/2026-04-09 GLM5 - CLOB WebSocket and Alchemy CU.md
@packages/polymarket/on_chain_ctf.py
@packages/polymarket/discovery/mvf.py
@infra/clickhouse/initdb/02_tables.sql
@infra/clickhouse/initdb/22_jon_becker_trades.sql
@infra/clickhouse/initdb/27_wallet_discovery.sql

<interfaces>
<!-- Existing on-chain interaction pattern (no web3.py, raw JSON-RPC) -->

From packages/polymarket/on_chain_ctf.py:
```python
class OnChainCTFProvider:
    CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
    def __init__(self, rpc_url: Optional[str] = None, timeout: float = 10.0):
        self.rpc_url = rpc_url or os.environ.get("POLYGON_RPC_URL", "https://polygon-rpc.com")
    def _eth_call(self, data: str) -> Optional[str]:
        # raw JSON-RPC via requests.post
```

From packages/polymarket/discovery/__init__.py:
```python
__all__ = [
    'LifecycleState', 'ReviewStatus', 'QueueState',
    'InvalidTransitionError', 'validate_transition',
    'WatchlistRow', 'LeaderboardSnapshotRow', 'ScanQueueRow',
    'compute_mvf', 'MvfResult', 'mvf_to_dict',
]
```

From docs/obsidian-vault/08-Research/04-Loop-B-Live-Monitoring.md:
```
OrderFilled(orderHash, maker, taker, makerAssetId, takerAssetId,
            makerAmountFilled, takerAmountFilled, fee)
- maker = topic1 (indexed, filterable)
- taker = topic2 (indexed, filterable)

CTFExchange:        0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E
NegRiskCTFExchange: 0xC5d563A36AE78145C45a50134d48A1215220f80a
```

From infra/clickhouse/initdb/02_tables.sql:
```sql
-- user_trades has: proxy_wallet, trade_uid, ts, token_id, condition_id,
--   outcome, side, size, price, transaction_hash, raw_json
-- NO maker/taker field exists in any ClickHouse trade table.
```

From infra/clickhouse/initdb/22_jon_becker_trades.sql:
```sql
-- jb_trades has: taker_side (BUY/SELL direction), NOT maker/taker address
-- taker_side is trade direction, not wallet attribution
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Build OrderFilled decoding + wallet filter probe module</name>
  <files>packages/polymarket/discovery/loop_b_probe.py, tests/test_loop_b_probe.py</files>
  <action>
Create `packages/polymarket/discovery/loop_b_probe.py` with the following:

1. **OrderFilled event ABI constants:**
   - Event signature: `OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)`
   - Compute the keccak256 topic0 hash of this signature (use hashlib or inline the known constant).
   - Contract addresses for CTFExchange (`0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`) and NegRiskCTFExchange (`0xC5d563A36AE78145C45a50134d48A1215220f80a`).

2. **`OrderFilledEvent` dataclass:**
   - Fields: `order_hash: str`, `maker: str`, `taker: str`, `maker_asset_id: int`, `taker_asset_id: int`, `maker_amount_filled: int`, `taker_amount_filled: int`, `fee: int`, `contract_address: str`, `tx_hash: str`, `block_number: int`, `log_index: int`.
   - All addresses lowercased and 0x-prefixed.

3. **`decode_order_filled(log: dict) -> OrderFilledEvent`:**
   - Accepts a raw Ethereum log dict (with keys: `address`, `topics`, `data`, `transactionHash`, `blockNumber`, `logIndex`).
   - `topics[0]` = event signature hash (validate it matches).
   - `topics[1]` = orderHash (bytes32, indexed).
   - `topics[2]` = maker address (address, indexed -- right-padded in 32 bytes, extract last 20 bytes).
   - `topics[3]` = taker address (address, indexed -- same extraction).
   - `data` = ABI-encoded `(uint256, uint256, uint256, uint256, uint256)` for makerAssetId, takerAssetId, makerAmountFilled, takerAmountFilled, fee.
   - Decode `data` using pure Python: strip 0x prefix, split into 5 x 64-char hex chunks, int() each.
   - No web3.py or eth-abi dependency. Use the same raw-decode pattern as on_chain_ctf.py.
   - Raise `ValueError` on invalid topic0 or wrong topic count.

4. **`build_wallet_filter_topics(wallet_addresses: list[str]) -> dict`:**
   - Constructs the `eth_subscribe("logs")` filter parameter dict.
   - `address`: list of both CTFExchange contract addresses.
   - `topics`: `[topic0, null, [padded_addr_1, padded_addr_2, ...], null]` -- this filters for OrderFilled events where ANY of the listed addresses appears as maker (topic2).
   - Also provide `build_wallet_filter_topics_taker(...)` that filters on topic3 (taker position).
   - And `build_wallet_filter_topics_either(...)` that uses OR logic: since Ethereum log subscriptions support OR within a single topic position but not across positions, this function must return TWO filter objects (one for maker, one for taker) and document that the subscriber needs two subscriptions or a post-filter.
   - Each wallet address must be left-padded to 32 bytes (64 hex chars) with 0x prefix.

5. **`check_historical_maker_taker() -> dict`:**
   - A pure-analysis function (no network calls) that returns a dict describing the state of maker/taker data in the current warehouse.
   - Inspect the ClickHouse schemas by referencing the known DDL:
     - `user_trades`: has `side` (BUY/SELL) but NO maker/taker address fields.
     - `jb_trades`: has `taker_side` which is trade direction, NOT wallet attribution.
   - Return: `{"user_trades_has_maker_taker": False, "jb_trades_has_maker_taker": False, "source": "schema_inspection", "note": "maker/taker wallet attribution only available from on-chain OrderFilled events, not current warehouse tables"}`.

6. **`estimate_alchemy_cu(wallet_count: int, avg_trades_per_wallet_per_day: int = 20) -> dict`:**
   - Pure math function computing monthly CU estimate based on the GLM-5 research findings.
   - Notification cost: 40 CU per event (based on ~1000 bytes at 0.04 CU/byte).
   - Subscription creation: 10 CU one-time (per subscription, not per wallet).
   - Monthly notifications: wallet_count * avg_trades * 30 days * 40 CU.
   - Monthly eth_getLogs (for Loop D on-demand): 100 calls/day * 30 * 60 CU = 180,000 CU.
   - Return dict with `notifications_cu`, `getlogs_cu`, `total_cu`, `free_tier_cu` (30_000_000), `utilization_pct`, `verdict` (one of "WELL_WITHIN_FREE_TIER" / "APPROACHING_LIMIT" / "EXCEEDS_FREE_TIER").

7. **`describe_dynamic_subscription_behavior() -> dict`:**
   - Pure documentation function returning a dict characterizing what is known about dynamic watchlist updates.
   - Key facts from the GLM-5 research:
     - Alchemy `eth_subscribe("logs")` creates a persistent subscription on a WebSocket connection.
     - To change the filter (add/remove wallets), you must unsubscribe and resubscribe with new topics.
     - This requires: `eth_unsubscribe(subscription_id)` then `eth_subscribe("logs", new_filter)`.
     - There is a brief gap during re-subscription where events may be missed.
     - Mitigation: maintain the old subscription active until the new one confirms, then unsubscribe old.
     - Alternative: use two alternating subscriptions (A/B swap pattern).
     - The CLOB WebSocket (Loop D) supports in-place `subscribe`/`unsubscribe` operations per asset_id without reconnecting, but Alchemy standard `eth_subscribe` does not support filter modification in-place.
   - Return dict with `can_update_in_place`, `reconnect_required`, `recommended_pattern`, `gap_mitigation`, `alternative_approach`.

No external dependencies beyond stdlib + `requests` (already in project). Follow the no-web3.py convention from on_chain_ctf.py.

Then create `tests/test_loop_b_probe.py` with deterministic offline tests:

**Test fixtures:** Construct realistic raw Ethereum log dicts with known values. Use the actual OrderFilled event signature hash. Construct topic and data fields by hand.

**Tests (minimum 15):**
- `test_order_filled_event_signature_hash` -- verify the computed keccak256 matches the known value.
- `test_decode_order_filled_valid` -- decode a well-formed log, check all 8 fields + metadata.
- `test_decode_order_filled_extracts_maker_address` -- verify maker extracted from topic2 (last 20 bytes of 32-byte topic).
- `test_decode_order_filled_extracts_taker_address` -- verify taker extracted from topic3.
- `test_decode_order_filled_decodes_data_fields` -- verify makerAssetId, takerAssetId, makerAmountFilled, takerAmountFilled, fee from data.
- `test_decode_order_filled_invalid_topic0_raises` -- wrong event signature raises ValueError.
- `test_decode_order_filled_wrong_topic_count_raises` -- fewer than 4 topics raises ValueError.
- `test_build_wallet_filter_topics_maker` -- filter addresses both contracts, topics[2] contains padded wallet addresses.
- `test_build_wallet_filter_topics_taker` -- filter on topic3 position.
- `test_build_wallet_filter_topics_either_returns_two` -- returns list of 2 filter dicts.
- `test_wallet_address_padding` -- 20-byte address correctly padded to 32 bytes in topic filter.
- `test_check_historical_maker_taker` -- returns False for both tables, non-empty note.
- `test_estimate_alchemy_cu_50_wallets` -- 50 wallets, default 20 trades/day -> total ~1.38M CU, well within free tier.
- `test_estimate_alchemy_cu_200_wallets` -- 200 wallets, 50 trades/day -> check utilization and verdict.
- `test_describe_dynamic_subscription` -- returns expected keys, `can_update_in_place` is False.

For keccak256 computation: use `hashlib` if available (Python 3.11+ has `hashlib.new("sha3_256")`), BUT Ethereum uses keccak256 which is NOT SHA3-256. They differ in padding. Options:
  - Hardcode the known topic0 for OrderFilled: compute it once offline and store as a constant. This is the simplest and most correct approach. The known keccak256 of `OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)` can be verified against public sources (e.g., 4byte.directory, Etherscan).
  - If `pysha3` or `pycryptodome` is available, use `keccak.new(digest_bits=256)`. Check pyproject.toml first. If neither is available, hardcode only.
  - Do NOT use hashlib.sha3_256 -- it produces NIST SHA3, not Ethereum keccak256.

The test for the event signature hash should verify the hardcoded constant matches the expected value from Etherscan/4byte.directory.
  </action>
  <verify>
    <automated>python -m pytest tests/test_loop_b_probe.py -v --tb=short -x</automated>
  </verify>
  <done>
    - decode_order_filled() correctly extracts maker, taker, asset IDs, amounts, and fee from a raw Ethereum log fixture.
    - build_wallet_filter_topics() produces valid eth_subscribe filter params for maker/taker/either positions.
    - check_historical_maker_taker() documents that current warehouse lacks maker/taker address data.
    - estimate_alchemy_cu() computes CU estimates consistent with GLM-5 research (50 wallets = ~1.38M CU/month).
    - describe_dynamic_subscription_behavior() documents reconnect requirement and gap mitigation.
    - All 15+ tests pass offline with no network calls.
  </done>
</task>

<task type="auto">
  <name>Task 2: Write feasibility verdict dev log</name>
  <files>docs/dev_logs/2026-04-15_wallet_discovery_loop_b_pof.md</files>
  <action>
Create `docs/dev_logs/2026-04-15_wallet_discovery_loop_b_pof.md` with the following structure:

**Title:** `# 2026-04-15 -- Wallet Discovery Loop B Phase 0 Feasibility`

**Sections:**

1. **Objective:** Determine whether Alchemy-based watched-wallet monitoring (Loop B) is technically viable in this repo. Answer three specific questions with evidence.

2. **Evidence Table:** A table with columns: Question | Finding | Evidence Source | Verdict

   Fill with these rows:
   - Q1: "Can OrderFilled events be decoded to recover maker/taker + asset/market IDs?"
     - Finding: reference the decode_order_filled() function and test results.
     - Source: loop_b_probe.py + test fixtures.
     - Verdict: YES -- proven with deterministic test.
   - Q2: "Is maker/taker attribution available in current warehouse data?"
     - Finding: NO. `user_trades` has `side` (BUY/SELL) not maker/taker address. `jb_trades` has `taker_side` (direction) not wallet attribution. Maker/taker wallet addresses are ONLY available from on-chain OrderFilled events.
     - Source: infra/clickhouse/initdb/02_tables.sql, 22_jon_becker_trades.sql, check_historical_maker_taker().
     - Verdict: NOT AVAILABLE -- must be sourced from on-chain events.
   - Q3: "Can the wallet filter be updated dynamically without data loss?"
     - Finding: eth_subscribe does NOT support in-place filter modification. Must unsubscribe + resubscribe. Brief gap during swap. Mitigation: overlap subscriptions (old stays active until new confirms) or A/B swap pattern.
     - Source: Alchemy eth_subscribe docs, GLM-5 research archive.
     - Verdict: YES WITH CONSTRAINTS -- requires A/B subscription swap pattern to avoid gaps.
   - Q4: "Is CU consumption within free tier budget?"
     - Finding: 50 wallets at 20 trades/day = ~1.38M CU/month = 4.6% of 30M free tier.
     - Source: estimate_alchemy_cu() + GLM-5 CU research.
     - Verdict: YES -- massive headroom.
   - Q5: "Is the intended wallet-filtering approach technically sound?"
     - Finding: YES. OrderFilled event has `maker` as topic2 and `taker` as topic3 (both indexed). Alchemy eth_subscribe supports filtering on specific topic positions with OR logic within a position. To filter on either maker OR taker, two subscriptions are needed (one per topic position) OR a post-filter on a broader subscription.
     - Source: build_wallet_filter_topics() helpers + Ethereum log subscription semantics.
     - Verdict: YES -- topic-based filtering confirmed viable.

3. **Remaining Blockers for Loop B Implementation:**
   - BLOCKER-1 (human-action): Alchemy account creation + API key provisioning. Cannot be resolved by code. Operator must create account at alchemy.com and add ALCHEMY_API_KEY to .env.
   - BLOCKER-2 (implementation): WebSocket connection manager with reconnection, heartbeat, and A/B subscription swap. Estimated ~200-300 lines of asyncio code. Dependency: `websockets` library (not currently in pyproject.toml; `websocket-client` is present but is sync-only; Loop B needs async).
   - BLOCKER-3 (implementation): Event persistence layer -- decoded OrderFilled events need a ClickHouse destination table (new DDL required, columns: tx_hash, block_number, log_index, maker, taker, maker_asset_id, taker_asset_id, maker_amount, taker_amount, fee, contract_address, decoded_at).
   - BLOCKER-4 (design): Notification/alert pipeline -- what happens when a watched wallet trades? Discord alert? Copy-trade signal? This is a product decision, not a technical blocker.

4. **Existing Repo Assets That Loop B Can Reuse:**
   - `on_chain_ctf.py` -- raw JSON-RPC pattern (no web3.py). Loop B probe follows same convention.
   - `packages/polymarket/discovery/` -- existing module structure, models, lifecycle state machine.
   - `websocket-client` -- already in pyproject.toml. Could be used for sync WebSocket if asyncio is not required. However, for production Loop B, async `websockets` library is recommended.
   - `packages/polymarket/crypto_pairs/clob_stream.py` -- existing CLOB WebSocket client. Pattern reference for connection management.
   - `packages/polymarket/simtrader/shadow/runner.py` -- existing WebSocket shadow runner. Pattern reference.

5. **Overall Verdict:**
   Format as a clearly marked verdict block:
   ```
   VERDICT: READY_WITH_CONSTRAINTS

   Loop B is technically viable. OrderFilled event decoding, wallet topic filtering,
   and CU budgeting are all proven. Three implementation constraints remain:
   1. Alchemy account creation (human action, ~5 min).
   2. Async WebSocket manager with A/B subscription swap (~200-300 LOC).
   3. New ClickHouse table for decoded on-chain fill events.
   4. maker/taker data is NOT available historically -- Loop B provides this
      data going forward only. No backfill from existing warehouse.
   ```

6. **Test Commands Run + Results:**
   Include the exact pytest command and pass count from Task 1.
   Include CLI smoke: `python -m polytool --help` exits 0.
   Include regression check: `python -m pytest tests/test_loop_b_probe.py tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py -v --tb=short` -- all pass, no regressions.

7. **Codex Review:** Skip -- no execution layer touched, no live-capital paths. Probe module is offline-only.
  </action>
  <verify>
    <automated>python -c "import pathlib; p = pathlib.Path('docs/dev_logs/2026-04-15_wallet_discovery_loop_b_pof.md'); assert p.exists() and p.stat().st_size > 2000, f'Dev log missing or too small: {p.stat().st_size if p.exists() else 0} bytes'"</automated>
  </verify>
  <done>
    - Dev log exists at docs/dev_logs/2026-04-15_wallet_discovery_loop_b_pof.md.
    - Contains evidence table with 5 questions answered.
    - Contains clear VERDICT: READY_WITH_CONSTRAINTS block.
    - Contains remaining blockers list with 4 items.
    - Contains test results with exact command and pass count.
    - No claims made without test or schema evidence.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| None | This is offline probe code with no network calls, no external API access, no user input processing |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-rdp-01 | I (Info Disclosure) | loop_b_probe.py | accept | Probe module contains only public contract addresses and event ABI constants. No secrets, no API keys. |
| T-rdp-02 | S (Spoofing) | decode_order_filled | accept | Function decodes fixtures/logs, does not authenticate sources. In production Loop B, log authenticity is guaranteed by Alchemy's RPC connection. |
</threat_model>

<verification>
1. `python -m pytest tests/test_loop_b_probe.py -v --tb=short -x` -- all probe tests pass.
2. `python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py -v --tb=short` -- existing discovery tests still pass (no regressions).
3. `python -m polytool --help` -- CLI loads without import errors.
4. Dev log exists and contains VERDICT block.
</verification>

<success_criteria>
- OrderFilled event decoding proven with 15+ deterministic tests.
- Wallet topic filter construction verified for maker, taker, and either positions.
- Historical maker/taker data gap documented with schema evidence.
- CU budget validated: 50 wallets well within 30M free tier.
- Dynamic subscription update behavior characterized with recommended pattern.
- Feasibility verdict: READY_WITH_CONSTRAINTS written with evidence.
- Zero regressions in existing discovery test suite (118 tests).
</success_criteria>

<output>
After completion, create `.planning/quick/260415-rdp-run-wallet-discovery-phase-0-feasibility/260415-rdp-SUMMARY.md`
</output>
