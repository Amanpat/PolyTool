"""Loop B Feasibility Probe — OrderFilled ABI decoding + wallet filter helpers.

This module proves technical viability of Alchemy-based watched-wallet monitoring
(Loop B) for the Wallet Discovery pipeline. It contains:

  - OrderFilled event ABI constants (contract addresses, event signature hash)
  - OrderFilledEvent dataclass
  - decode_order_filled() — raw Ethereum log decoder, no web3.py
  - build_wallet_filter_topics*() — eth_subscribe filter param builders
  - check_historical_maker_taker() — schema inspection summary
  - estimate_alchemy_cu() — CU budget estimator
  - describe_dynamic_subscription_behavior() — reconnect behavior documentation

Design principles:
  - No web3.py. No eth-abi. Follows on_chain_ctf.py raw JSON-RPC convention.
  - Pure Python + stdlib only (keccak via pycryptodome when available, else
    uses the pre-computed constant).
  - All network-bound functionality is deferred to production Loop B
    implementation. This module is offline-safe.

References:
  SPEC-wallet-discovery-v1.md — Loop B out-of-scope blockers
  docs/obsidian-vault/08-Research/04-Loop-B-Live-Monitoring.md
  docs/obsidian-vault/11-Prompt-Archive/2026-04-09 GLM5 - CLOB WebSocket and Alchemy CU.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

# ---------------------------------------------------------------------------
# Contract addresses
# ---------------------------------------------------------------------------

CTF_EXCHANGE_ADDRESS = "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"
NEG_RISK_CTF_EXCHANGE_ADDRESS = "0xc5d563a36ae78145c45a50134d48a1215220f80a"

# Both exchange contracts that emit OrderFilled events we care about
EXCHANGE_ADDRESSES = [CTF_EXCHANGE_ADDRESS, NEG_RISK_CTF_EXCHANGE_ADDRESS]

# ---------------------------------------------------------------------------
# OrderFilled event ABI constants
# ---------------------------------------------------------------------------

# Event signature (canonical form):
#   OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)
ORDER_FILLED_SIGNATURE = (
    "OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)"
)

# keccak256 of the event signature — this is topic0 in every OrderFilled log.
#
# Computed via pycryptodome:
#   from Crypto.Hash import keccak
#   k = keccak.new(digest_bits=256)
#   k.update(b"OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)")
#   print("0x" + k.hexdigest())
#   => 0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6
#
# Verified against:
#   - pycryptodome keccak256 of the canonical ASCII signature string (offline)
#   - Pattern follows on_chain_ctf.py selector conventions
#
# Hardcoded constant for use in production code (avoids runtime dependency).
ORDER_FILLED_TOPIC0 = (
    "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"
)

# Number of topics in an OrderFilled log (topic0 + 3 indexed params)
ORDER_FILLED_TOPIC_COUNT = 4

# Number of uint256 data fields encoded in the non-indexed data payload
ORDER_FILLED_DATA_FIELD_COUNT = 5  # makerAssetId, takerAssetId, makerAmount, takerAmount, fee


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_order_filled_topic0() -> str:
    """Compute keccak256 of the OrderFilled event signature at runtime.

    Uses pycryptodome (Crypto.Hash.keccak). Falls back gracefully if
    pycryptodome is not installed (returns the hardcoded constant).

    Returns:
        Lowercase 0x-prefixed keccak256 hex string (66 chars).
    """
    try:
        from Crypto.Hash import keccak  # pycryptodome

        k = keccak.new(digest_bits=256)
        k.update(ORDER_FILLED_SIGNATURE.encode("ascii"))
        return "0x" + k.hexdigest()
    except ImportError:
        # Return the pre-computed constant — verified offline.
        return ORDER_FILLED_TOPIC0


def _pad_address_to_topic(address: str) -> str:
    """Left-pad a 20-byte Ethereum address to a 32-byte topic (64 hex chars, 0x-prefixed).

    Ethereum indexed address topics are stored as 32-byte values with the address
    right-aligned (left-padded with zeros).

    Args:
        address: Ethereum address (with or without 0x prefix, 20 bytes = 40 hex chars).

    Returns:
        0x-prefixed 64-char hex string.
    """
    addr = address.lower().removeprefix("0x")
    if len(addr) != 40:
        raise ValueError(f"Address must be 20 bytes (40 hex chars), got {len(addr)}: {address}")
    return "0x" + addr.zfill(64)


def _extract_address_from_topic(topic: str) -> str:
    """Extract a 20-byte Ethereum address from a 32-byte ABI-encoded topic.

    In Ethereum logs, indexed address parameters occupy a full 32-byte topic slot
    but the address occupies only the last 20 bytes (right-aligned).

    Args:
        topic: 0x-prefixed 64-char hex string (32 bytes).

    Returns:
        Lowercase 0x-prefixed 20-byte address (42 chars).
    """
    raw = topic.lower().removeprefix("0x")
    if len(raw) != 64:
        raise ValueError(f"Topic must be 32 bytes (64 hex chars), got {len(raw)}: {topic}")
    # Address is in the last 40 hex characters (20 bytes)
    return "0x" + raw[-40:]


# ---------------------------------------------------------------------------
# OrderFilledEvent dataclass
# ---------------------------------------------------------------------------


@dataclass
class OrderFilledEvent:
    """Decoded representation of an Ethereum OrderFilled log event.

    Field origins:
        order_hash       — topics[1] (bytes32, indexed)
        maker            — topics[2] (address, indexed, last 20 bytes of 32-byte topic)
        taker            — topics[3] (address, indexed, last 20 bytes of 32-byte topic)
        maker_asset_id   — data chunk 0 (uint256)
        taker_asset_id   — data chunk 1 (uint256)
        maker_amount_filled — data chunk 2 (uint256)
        taker_amount_filled — data chunk 3 (uint256)
        fee              — data chunk 4 (uint256)
        contract_address — log.address (lowercased)
        tx_hash          — log.transactionHash
        block_number     — log.blockNumber (int)
        log_index        — log.logIndex (int)
    """

    order_hash: str
    maker: str
    taker: str
    maker_asset_id: int
    taker_asset_id: int
    maker_amount_filled: int
    taker_amount_filled: int
    fee: int
    contract_address: str
    tx_hash: str
    block_number: int
    log_index: int


# ---------------------------------------------------------------------------
# Core decoder
# ---------------------------------------------------------------------------


def decode_order_filled(log: dict) -> OrderFilledEvent:
    """Decode a raw Ethereum log dict into an OrderFilledEvent.

    Accepts the raw dict format returned by eth_getLogs or eth_subscribe("logs").
    Performs pure-Python ABI decoding without web3.py or eth-abi.

    Args:
        log: Raw Ethereum log dict with keys:
             - address (str): Contract address that emitted the event
             - topics (list[str]): List of 0x-prefixed 32-byte topic hashes
             - data (str): 0x-prefixed ABI-encoded non-indexed parameters
             - transactionHash (str): Transaction hash
             - blockNumber (int | str): Block number (decimal int or hex str)
             - logIndex (int | str): Log index (decimal int or hex str)

    Returns:
        OrderFilledEvent with all fields populated and addresses lowercased.

    Raises:
        ValueError: If topics[0] does not match ORDER_FILLED_TOPIC0, or if the
                    log has fewer than ORDER_FILLED_TOPIC_COUNT topics, or if
                    the data payload cannot be decoded.
    """
    topics = log.get("topics", [])

    # Validate topic count
    if len(topics) < ORDER_FILLED_TOPIC_COUNT:
        raise ValueError(
            f"OrderFilled requires {ORDER_FILLED_TOPIC_COUNT} topics, "
            f"got {len(topics)}"
        )

    # Validate event signature (topic0)
    topic0 = topics[0].lower()
    expected = ORDER_FILLED_TOPIC0.lower()
    if topic0 != expected:
        raise ValueError(
            f"topic0 mismatch: expected {expected}, got {topic0}. "
            "Not an OrderFilled event."
        )

    # Decode indexed fields from topics
    order_hash = topics[1]  # bytes32 as hex string, no transformation needed
    maker = _extract_address_from_topic(topics[2])
    taker = _extract_address_from_topic(topics[3])

    # Decode non-indexed data payload
    # ABI encoding: each uint256 occupies exactly 32 bytes (64 hex chars)
    data_hex = log.get("data", "").lower().removeprefix("0x")
    expected_data_len = ORDER_FILLED_DATA_FIELD_COUNT * 64
    if len(data_hex) < expected_data_len:
        raise ValueError(
            f"data payload too short: expected >= {expected_data_len} hex chars, "
            f"got {len(data_hex)}"
        )

    chunks = [
        data_hex[i * 64 : (i + 1) * 64]
        for i in range(ORDER_FILLED_DATA_FIELD_COUNT)
    ]
    maker_asset_id = int(chunks[0], 16)
    taker_asset_id = int(chunks[1], 16)
    maker_amount_filled = int(chunks[2], 16)
    taker_amount_filled = int(chunks[3], 16)
    fee = int(chunks[4], 16)

    # Decode block number and log index (may come as hex strings in eth_subscribe)
    block_number_raw = log.get("blockNumber", 0)
    if isinstance(block_number_raw, str):
        block_number = int(block_number_raw, 16) if block_number_raw.startswith("0x") else int(block_number_raw)
    else:
        block_number = int(block_number_raw)

    log_index_raw = log.get("logIndex", 0)
    if isinstance(log_index_raw, str):
        log_index = int(log_index_raw, 16) if log_index_raw.startswith("0x") else int(log_index_raw)
    else:
        log_index = int(log_index_raw)

    return OrderFilledEvent(
        order_hash=order_hash,
        maker=maker,
        taker=taker,
        maker_asset_id=maker_asset_id,
        taker_asset_id=taker_asset_id,
        maker_amount_filled=maker_amount_filled,
        taker_amount_filled=taker_amount_filled,
        fee=fee,
        contract_address=log.get("address", "").lower(),
        tx_hash=log.get("transactionHash", ""),
        block_number=block_number,
        log_index=log_index,
    )


# ---------------------------------------------------------------------------
# Wallet filter topic builders
# ---------------------------------------------------------------------------


def build_wallet_filter_topics(wallet_addresses: List[str]) -> dict:
    """Build eth_subscribe("logs") filter params for OrderFilled where maker matches.

    Filters for OrderFilled events where ANY of the provided wallet addresses
    appears in topic2 (maker position). Uses Ethereum OR-within-topic semantics.

    Args:
        wallet_addresses: List of 20-byte Ethereum addresses (with or without 0x).

    Returns:
        Filter param dict suitable for eth_subscribe("logs", <filter>):
        {
            "address": [ctf_exchange, neg_risk_ctf_exchange],
            "topics": [
                topic0,   # ORDER_FILLED_TOPIC0
                null,     # orderHash — not filtered
                [padded_addr_1, padded_addr_2, ...],  # maker — OR logic
                null      # taker — not filtered
            ]
        }
    """
    padded = [_pad_address_to_topic(a) for a in wallet_addresses]
    return {
        "address": EXCHANGE_ADDRESSES,
        "topics": [
            ORDER_FILLED_TOPIC0,
            None,  # orderHash — not filtered
            padded,  # maker (topic2) — OR within this position
            None,   # taker — not filtered
        ],
    }


def build_wallet_filter_topics_taker(wallet_addresses: List[str]) -> dict:
    """Build eth_subscribe("logs") filter params for OrderFilled where taker matches.

    Filters for OrderFilled events where ANY of the provided wallet addresses
    appears in topic3 (taker position).

    Args:
        wallet_addresses: List of 20-byte Ethereum addresses.

    Returns:
        Filter param dict suitable for eth_subscribe("logs", <filter>).
    """
    padded = [_pad_address_to_topic(a) for a in wallet_addresses]
    return {
        "address": EXCHANGE_ADDRESSES,
        "topics": [
            ORDER_FILLED_TOPIC0,
            None,   # orderHash — not filtered
            None,   # maker — not filtered
            padded, # taker (topic3) — OR within this position
        ],
    }


def build_wallet_filter_topics_either(wallet_addresses: List[str]) -> List[dict]:
    """Build TWO eth_subscribe filter param dicts covering maker OR taker.

    Ethereum log subscriptions support OR logic WITHIN a single topic position
    but NOT ACROSS positions. To catch a wallet in either maker (topic2) or taker
    (topic3) position, two separate subscriptions are required.

    The caller must maintain both subscriptions simultaneously to get complete
    coverage. Alternatively, a single unfiltered subscription + post-filter
    (check maker or taker against watchlist) can be used if the event volume
    is manageable.

    Args:
        wallet_addresses: List of 20-byte Ethereum addresses.

    Returns:
        List of exactly 2 filter dicts:
          [0] — maker filter (topic2 position)
          [1] — taker filter (topic3 position)
    """
    return [
        build_wallet_filter_topics(wallet_addresses),
        build_wallet_filter_topics_taker(wallet_addresses),
    ]


# ---------------------------------------------------------------------------
# Historical data availability analysis
# ---------------------------------------------------------------------------


def check_historical_maker_taker() -> dict:
    """Document the state of maker/taker attribution in the current warehouse.

    Pure analysis function — no network calls, no DB connections. Returns a
    summary based on schema inspection of the ClickHouse DDL files.

    ClickHouse table analysis:
    - user_trades (02_tables.sql): has proxy_wallet, trade_uid, ts, token_id,
      condition_id, outcome, side (BUY/SELL direction), size, price,
      transaction_hash, raw_json. NO maker/taker address fields.
    - jb_trades (22_jon_becker_trades.sql): has taker_side (BUY/SELL trade
      direction). taker_side is NOT a wallet address — it is trade direction.
      NO maker/taker address fields.

    Conclusion: Maker/taker wallet attribution is only available from on-chain
    OrderFilled event logs. There is no historical backfill possible from the
    current warehouse schema.

    Returns:
        Dict describing warehouse maker/taker availability.
    """
    return {
        "user_trades_has_maker_taker": False,
        "jb_trades_has_maker_taker": False,
        "source": "schema_inspection",
        "schema_files_reviewed": [
            "infra/clickhouse/initdb/02_tables.sql",
            "infra/clickhouse/initdb/22_jon_becker_trades.sql",
        ],
        "user_trades_fields_note": (
            "user_trades.side = BUY/SELL trade direction, NOT wallet role. "
            "No maker or taker address columns exist."
        ),
        "jb_trades_fields_note": (
            "jb_trades.taker_side = BUY/SELL trade direction (opposite of maker). "
            "NOT a wallet address. No maker or taker address columns exist."
        ),
        "note": (
            "Maker/taker wallet attribution is only available from on-chain "
            "OrderFilled events (eth_getLogs or eth_subscribe). "
            "No backfill is possible from the current warehouse tables. "
            "Loop B provides this data going forward only."
        ),
    }


# ---------------------------------------------------------------------------
# CU budget estimator
# ---------------------------------------------------------------------------


def estimate_alchemy_cu(
    wallet_count: int,
    avg_trades_per_wallet_per_day: int = 20,
) -> dict:
    """Estimate monthly Alchemy Compute Unit (CU) consumption for Loop B.

    Based on GLM-5 research findings (2026-04-09 session archive):
      - eth_subscribe notification: ~40 CU per event (~1000 bytes at ~0.04 CU/byte)
      - eth_subscribe creation: 10 CU one-time per subscription
      - eth_getLogs: 60 CU per call (used by Loop D on-demand queries)

    Note: CU rates are approximate. Alchemy pricing can change. This function
    is intended for order-of-magnitude feasibility assessment only.

    Args:
        wallet_count: Number of wallets in the watchlist.
        avg_trades_per_wallet_per_day: Average OrderFilled events per wallet per day.

    Returns:
        Dict with CU breakdown and utilization verdict.
    """
    cu_per_notification = 40
    cu_per_getlogs = 60
    getlogs_calls_per_day = 100
    days_per_month = 30
    free_tier_cu = 30_000_000

    # Monthly notification CU (wallet_count * trades/day * days * CU/notification)
    notifications_cu = wallet_count * avg_trades_per_wallet_per_day * days_per_month * cu_per_notification

    # Monthly eth_getLogs CU (Loop D on-demand historical queries)
    getlogs_cu = getlogs_calls_per_day * days_per_month * cu_per_getlogs

    total_cu = notifications_cu + getlogs_cu
    utilization_pct = (total_cu / free_tier_cu) * 100.0

    if utilization_pct < 50.0:
        verdict = "WELL_WITHIN_FREE_TIER"
    elif utilization_pct < 80.0:
        verdict = "APPROACHING_LIMIT"
    else:
        verdict = "EXCEEDS_FREE_TIER"

    return {
        "wallet_count": wallet_count,
        "avg_trades_per_wallet_per_day": avg_trades_per_wallet_per_day,
        "notifications_cu": notifications_cu,
        "getlogs_cu": getlogs_cu,
        "total_cu": total_cu,
        "free_tier_cu": free_tier_cu,
        "utilization_pct": round(utilization_pct, 2),
        "verdict": verdict,
        "assumptions": {
            "cu_per_notification": cu_per_notification,
            "cu_per_getlogs": cu_per_getlogs,
            "getlogs_calls_per_day": getlogs_calls_per_day,
            "days_per_month": days_per_month,
        },
    }


# ---------------------------------------------------------------------------
# Dynamic subscription behavior documentation
# ---------------------------------------------------------------------------


def describe_dynamic_subscription_behavior() -> dict:
    """Characterize Alchemy eth_subscribe dynamic filter update behavior.

    Documents key findings from GLM-5 research (2026-04-09) about how
    Alchemy WebSocket subscriptions handle watchlist changes.

    Returns:
        Dict describing reconnect requirements and recommended patterns.
    """
    return {
        "can_update_in_place": False,
        "reconnect_required": True,
        "reason": (
            "Alchemy eth_subscribe('logs') creates an immutable subscription with a "
            "fixed topic filter. The filter CANNOT be modified after creation. "
            "To add or remove wallets from the watchlist, the current subscription "
            "must be cancelled (eth_unsubscribe) and a new one created with the "
            "updated wallet list."
        ),
        "gap_risk": (
            "During the unsubscribe/resubscribe cycle, a brief gap exists where "
            "OrderFilled events may be emitted but not received. Typical gap duration "
            "is <500ms (WebSocket round-trip + server processing)."
        ),
        "gap_mitigation": (
            "Keep the old subscription active until the new subscription confirms "
            "receipt of its first event (or a small fixed delay, e.g., 2s). "
            "Then unsubscribe the old one. Duplicate events during the overlap "
            "window must be deduplicated by (tx_hash, log_index)."
        ),
        "recommended_pattern": "A/B subscription swap",
        "ab_swap_description": (
            "Maintain two subscription slots (A and B). Active slot serves live events. "
            "When watchlist changes: (1) create new subscription on idle slot B with "
            "updated filter, (2) wait for first event on B (or 2s timeout), "
            "(3) mark B as active, (4) unsubscribe A. Dedup by (tx_hash, log_index) "
            "during overlap window."
        ),
        "alternative_approach": (
            "Subscribe to ALL OrderFilled events from both CTF exchange contracts "
            "(no wallet filter in topics) and apply post-filter in Python against "
            "the watchlist. This eliminates the resubscribe problem entirely, at "
            "the cost of higher CU consumption (all trades vs. watched wallet trades)."
        ),
        "clob_ws_comparison": (
            "The CLOB WebSocket (Loop D, Polymarket API) supports in-place "
            "subscribe/unsubscribe per asset_id without reconnecting. Alchemy "
            "eth_subscribe does NOT have this capability."
        ),
        "implementation_notes": [
            "eth_subscribe is WebSocket-only (not available via HTTP endpoint).",
            "Subscription IDs are strings returned in the subscription confirmation message.",
            "eth_unsubscribe takes the subscription ID as the only parameter.",
            "websockets (async) library recommended for production; websocket-client "
            "(sync, already in pyproject.toml) can be used for simpler single-thread "
            "implementations but has reconnection limitations.",
        ],
    }
