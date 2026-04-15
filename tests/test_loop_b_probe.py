"""Deterministic offline tests for Loop B feasibility probe.

All tests are network-free. No Alchemy API, no Polygon RPC, no ClickHouse.

Tests cover:
  - OrderFilled event signature hash (keccak256 constant verification)
  - decode_order_filled() — maker, taker, asset IDs, amounts, fee, metadata
  - Error paths: wrong topic0, wrong topic count, short data payload
  - build_wallet_filter_topics() — maker, taker, either positions
  - Address padding (_pad_address_to_topic)
  - check_historical_maker_taker() — schema analysis results
  - estimate_alchemy_cu() — CU budget math
  - describe_dynamic_subscription_behavior() — reconnect behavior doc
"""

from __future__ import annotations

import pytest

from packages.polymarket.discovery.loop_b_probe import (
    ORDER_FILLED_TOPIC0,
    ORDER_FILLED_SIGNATURE,
    ORDER_FILLED_TOPIC_COUNT,
    CTF_EXCHANGE_ADDRESS,
    NEG_RISK_CTF_EXCHANGE_ADDRESS,
    EXCHANGE_ADDRESSES,
    OrderFilledEvent,
    decode_order_filled,
    build_wallet_filter_topics,
    build_wallet_filter_topics_taker,
    build_wallet_filter_topics_either,
    check_historical_maker_taker,
    estimate_alchemy_cu,
    describe_dynamic_subscription_behavior,
    _compute_order_filled_topic0,
    _pad_address_to_topic,
    _extract_address_from_topic,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Known address constants used across multiple tests
MAKER_ADDR = "0x1234567890abcdef1234567890abcdef12345678"
TAKER_ADDR = "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
OTHER_ADDR = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

# Known numeric values for the ABI-encoded data payload
MAKER_ASSET_ID = 999
TAKER_ASSET_ID = 888
MAKER_AMOUNT = 1_000_000
TAKER_AMOUNT = 500_000
FEE = 10_000

# Pre-computed padded addresses (32 bytes = 64 hex chars, 0x-prefixed)
MAKER_TOPIC = "0x" + MAKER_ADDR[2:].zfill(64)
TAKER_TOPIC = "0x" + TAKER_ADDR[2:].zfill(64)

# ABI-encoded data payload (5 uint256 values, each 32 bytes)
DATA_PAYLOAD = "0x" + "".join(
    f"{v:064x}"
    for v in [MAKER_ASSET_ID, TAKER_ASSET_ID, MAKER_AMOUNT, TAKER_AMOUNT, FEE]
)

ORDER_HASH_TOPIC = "0x" + "ab" * 32  # arbitrary bytes32 value


def _make_log(
    topic0: str = ORDER_FILLED_TOPIC0,
    order_hash: str = ORDER_HASH_TOPIC,
    maker_topic: str = MAKER_TOPIC,
    taker_topic: str = TAKER_TOPIC,
    data: str = DATA_PAYLOAD,
    address: str = CTF_EXCHANGE_ADDRESS,
    tx_hash: str = "0x" + "ff" * 32,
    block_number: int = 12345678,
    log_index: int = 3,
) -> dict:
    """Build a realistic raw Ethereum log dict for OrderFilled."""
    return {
        "address": address,
        "topics": [topic0, order_hash, maker_topic, taker_topic],
        "data": data,
        "transactionHash": tx_hash,
        "blockNumber": block_number,
        "logIndex": log_index,
    }


# ---------------------------------------------------------------------------
# 1. Event signature hash
# ---------------------------------------------------------------------------


def test_order_filled_event_signature_hash():
    """The hardcoded topic0 constant must match the runtime keccak256 computation."""
    computed = _compute_order_filled_topic0()
    assert computed == ORDER_FILLED_TOPIC0, (
        f"Hardcoded ORDER_FILLED_TOPIC0 mismatch.\n"
        f"  Hardcoded: {ORDER_FILLED_TOPIC0}\n"
        f"  Computed:  {computed}\n"
        "Update the constant in loop_b_probe.py."
    )


def test_order_filled_topic0_format():
    """topic0 must be a lowercase 0x-prefixed 32-byte hex string (66 chars)."""
    assert ORDER_FILLED_TOPIC0.startswith("0x"), "topic0 must start with 0x"
    assert len(ORDER_FILLED_TOPIC0) == 66, f"Expected 66 chars, got {len(ORDER_FILLED_TOPIC0)}"
    assert ORDER_FILLED_TOPIC0 == ORDER_FILLED_TOPIC0.lower(), "topic0 must be lowercase"


def test_order_filled_signature_string():
    """Event signature must match the canonical ABI form (no spaces, correct types)."""
    assert ORDER_FILLED_SIGNATURE == (
        "OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)"
    )


# ---------------------------------------------------------------------------
# 2. decode_order_filled — happy path
# ---------------------------------------------------------------------------


def test_decode_order_filled_valid():
    """decode_order_filled returns an OrderFilledEvent with all 12 fields populated."""
    log = _make_log()
    event = decode_order_filled(log)

    assert isinstance(event, OrderFilledEvent)
    # Spot-check every field
    assert event.order_hash == ORDER_HASH_TOPIC
    assert event.maker == MAKER_ADDR.lower()
    assert event.taker == TAKER_ADDR.lower()
    assert event.maker_asset_id == MAKER_ASSET_ID
    assert event.taker_asset_id == TAKER_ASSET_ID
    assert event.maker_amount_filled == MAKER_AMOUNT
    assert event.taker_amount_filled == TAKER_AMOUNT
    assert event.fee == FEE
    assert event.contract_address == CTF_EXCHANGE_ADDRESS.lower()
    assert event.tx_hash == "0x" + "ff" * 32
    assert event.block_number == 12345678
    assert event.log_index == 3


def test_decode_order_filled_extracts_maker_address():
    """maker must be extracted from the last 20 bytes of the 32-byte topic2."""
    # Use a distinct maker address to make extraction unambiguous
    custom_maker = "0xabcdef1234567890abcdef1234567890abcdef12"
    maker_topic = "0x" + custom_maker[2:].zfill(64)
    log = _make_log(maker_topic=maker_topic)
    event = decode_order_filled(log)

    assert event.maker == custom_maker.lower()
    # Confirm it is NOT 32 bytes (a common mistake is returning the full topic)
    assert len(event.maker) == 42  # 0x + 40 hex chars = 20 bytes


def test_decode_order_filled_extracts_taker_address():
    """taker must be extracted from the last 20 bytes of the 32-byte topic3."""
    custom_taker = "0x9999888877776666555544443333222211110000"
    taker_topic = "0x" + custom_taker[2:].zfill(64)
    log = _make_log(taker_topic=taker_topic)
    event = decode_order_filled(log)

    assert event.taker == custom_taker.lower()
    assert len(event.taker) == 42


def test_decode_order_filled_decodes_data_fields():
    """All five data fields must decode correctly from the ABI-encoded data payload."""
    log = _make_log()
    event = decode_order_filled(log)

    assert event.maker_asset_id == MAKER_ASSET_ID
    assert event.taker_asset_id == TAKER_ASSET_ID
    assert event.maker_amount_filled == MAKER_AMOUNT
    assert event.taker_amount_filled == TAKER_AMOUNT
    assert event.fee == FEE


def test_decode_order_filled_large_asset_ids():
    """Asset IDs can be very large uint256 values (Polymarket uses token IDs > 2^128)."""
    big_asset_id = 2**128 + 12345
    data = "0x" + "".join(
        f"{v:064x}" for v in [big_asset_id, big_asset_id + 1, 1, 1, 0]
    )
    log = _make_log(data=data)
    event = decode_order_filled(log)

    assert event.maker_asset_id == big_asset_id
    assert event.taker_asset_id == big_asset_id + 1


def test_decode_order_filled_neg_risk_contract():
    """decode_order_filled works with NegRiskCTFExchange address as contract_address."""
    log = _make_log(address=NEG_RISK_CTF_EXCHANGE_ADDRESS)
    event = decode_order_filled(log)

    assert event.contract_address == NEG_RISK_CTF_EXCHANGE_ADDRESS.lower()


def test_decode_order_filled_hex_block_number():
    """blockNumber may arrive as a hex string from eth_subscribe; must parse correctly."""
    log = _make_log(block_number="0xbc614e")  # 12345678 in hex
    event = decode_order_filled(log)
    assert event.block_number == 12345678


def test_decode_order_filled_hex_log_index():
    """logIndex may arrive as a hex string from eth_subscribe; must parse correctly."""
    log = _make_log(log_index="0x3")
    event = decode_order_filled(log)
    assert event.log_index == 3


# ---------------------------------------------------------------------------
# 3. decode_order_filled — error paths
# ---------------------------------------------------------------------------


def test_decode_order_filled_invalid_topic0_raises():
    """A log with the wrong topic0 must raise ValueError."""
    wrong_topic0 = "0x" + "00" * 32  # clearly wrong
    log = _make_log(topic0=wrong_topic0)

    with pytest.raises(ValueError, match="topic0 mismatch"):
        decode_order_filled(log)


def test_decode_order_filled_wrong_topic_count_raises():
    """Fewer than 4 topics must raise ValueError."""
    log = _make_log()
    # Remove topics[3] (taker)
    log["topics"] = log["topics"][:3]

    with pytest.raises(ValueError, match="4 topics"):
        decode_order_filled(log)


def test_decode_order_filled_empty_topics_raises():
    """Empty topics list must raise ValueError."""
    log = _make_log()
    log["topics"] = []

    with pytest.raises(ValueError):
        decode_order_filled(log)


# ---------------------------------------------------------------------------
# 4. Wallet address padding
# ---------------------------------------------------------------------------


def test_wallet_address_padding_standard():
    """20-byte address must be left-padded to 32 bytes (64 hex chars) with 0x prefix."""
    addr = "0x1234567890abcdef1234567890abcdef12345678"
    padded = _pad_address_to_topic(addr)

    assert padded.startswith("0x")
    assert len(padded) == 66  # 0x + 64 hex chars = 32 bytes
    # Address occupies last 40 chars
    assert padded[-40:] == addr[2:].lower()
    # First 24 chars after 0x are zeros (24 hex = 12 bytes padding)
    assert padded[2:26] == "0" * 24


def test_wallet_address_padding_no_prefix():
    """Address without 0x prefix should also be padded correctly."""
    addr_no_prefix = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    padded = _pad_address_to_topic(addr_no_prefix)

    assert padded.startswith("0x")
    assert len(padded) == 66
    assert padded[-40:] == addr_no_prefix.lower()


def test_extract_address_from_topic_roundtrip():
    """Padding then extracting must return the original address."""
    original = "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    padded = _pad_address_to_topic(original)
    extracted = _extract_address_from_topic(padded)

    assert extracted == original.lower()


# ---------------------------------------------------------------------------
# 5. build_wallet_filter_topics — maker position
# ---------------------------------------------------------------------------


def test_build_wallet_filter_topics_maker():
    """Filter must target topic2 (maker) with padded wallet addresses."""
    wallets = [MAKER_ADDR, OTHER_ADDR]
    f = build_wallet_filter_topics(wallets)

    assert "address" in f
    assert "topics" in f

    # Contract addresses
    assert CTF_EXCHANGE_ADDRESS in f["address"]
    assert NEG_RISK_CTF_EXCHANGE_ADDRESS in f["address"]
    assert len(f["address"]) == 2

    topics = f["topics"]
    assert len(topics) == 4

    # topic0 = event signature
    assert topics[0] == ORDER_FILLED_TOPIC0

    # topic1 = None (orderHash not filtered)
    assert topics[1] is None

    # topic2 = list of padded maker addresses (OR logic)
    assert isinstance(topics[2], list)
    assert len(topics[2]) == 2
    assert _pad_address_to_topic(MAKER_ADDR) in topics[2]
    assert _pad_address_to_topic(OTHER_ADDR) in topics[2]

    # topic3 = None (taker not filtered)
    assert topics[3] is None


def test_build_wallet_filter_topics_maker_single_wallet():
    """Single-wallet filter must still produce a list for topic2."""
    f = build_wallet_filter_topics([MAKER_ADDR])
    topics = f["topics"]
    assert isinstance(topics[2], list)
    assert len(topics[2]) == 1


# ---------------------------------------------------------------------------
# 6. build_wallet_filter_topics_taker — taker position
# ---------------------------------------------------------------------------


def test_build_wallet_filter_topics_taker():
    """Taker filter must target topic3 (taker) with padded wallet addresses."""
    wallets = [TAKER_ADDR]
    f = build_wallet_filter_topics_taker(wallets)

    topics = f["topics"]
    assert len(topics) == 4
    assert topics[0] == ORDER_FILLED_TOPIC0
    assert topics[1] is None
    assert topics[2] is None  # maker NOT filtered
    assert isinstance(topics[3], list)
    assert _pad_address_to_topic(TAKER_ADDR) in topics[3]

    # Contract addresses included
    assert CTF_EXCHANGE_ADDRESS in f["address"]
    assert NEG_RISK_CTF_EXCHANGE_ADDRESS in f["address"]


# ---------------------------------------------------------------------------
# 7. build_wallet_filter_topics_either — two-filter approach
# ---------------------------------------------------------------------------


def test_build_wallet_filter_topics_either_returns_two():
    """either() must return exactly 2 filter dicts (one maker, one taker)."""
    wallets = [MAKER_ADDR, TAKER_ADDR]
    filters = build_wallet_filter_topics_either(wallets)

    assert isinstance(filters, list)
    assert len(filters) == 2


def test_build_wallet_filter_topics_either_first_is_maker():
    """filters[0] from either() must filter on topic2 (maker position)."""
    filters = build_wallet_filter_topics_either([MAKER_ADDR])
    maker_filter = filters[0]

    assert isinstance(maker_filter["topics"][2], list)
    assert maker_filter["topics"][3] is None


def test_build_wallet_filter_topics_either_second_is_taker():
    """filters[1] from either() must filter on topic3 (taker position)."""
    filters = build_wallet_filter_topics_either([TAKER_ADDR])
    taker_filter = filters[1]

    assert taker_filter["topics"][2] is None
    assert isinstance(taker_filter["topics"][3], list)


# ---------------------------------------------------------------------------
# 8. check_historical_maker_taker
# ---------------------------------------------------------------------------


def test_check_historical_maker_taker():
    """Warehouse schema inspection must report False for both tables."""
    result = check_historical_maker_taker()

    assert result["user_trades_has_maker_taker"] is False
    assert result["jb_trades_has_maker_taker"] is False
    assert result["source"] == "schema_inspection"
    assert len(result["note"]) > 20  # substantive note


def test_check_historical_maker_taker_schema_files_referenced():
    """Result must cite the actual DDL files reviewed."""
    result = check_historical_maker_taker()
    files = result.get("schema_files_reviewed", [])

    assert any("02_tables.sql" in f for f in files), "02_tables.sql must be cited"
    assert any("22_jon_becker_trades.sql" in f for f in files), (
        "22_jon_becker_trades.sql must be cited"
    )


def test_check_historical_maker_taker_explains_taker_side():
    """Result must explain that jb_trades.taker_side is direction, not address."""
    result = check_historical_maker_taker()
    note = result.get("jb_trades_fields_note", "")
    assert "direction" in note.lower() or "taker_side" in note.lower(), (
        "Must clarify that taker_side is trade direction, not wallet address"
    )


# ---------------------------------------------------------------------------
# 9. estimate_alchemy_cu
# ---------------------------------------------------------------------------


def test_estimate_alchemy_cu_50_wallets():
    """50 wallets at 20 trades/day should be well within the 30M free tier."""
    result = estimate_alchemy_cu(50, avg_trades_per_wallet_per_day=20)

    # Expected notifications CU: 50 * 20 * 30 * 40 = 1,200,000
    assert result["notifications_cu"] == 1_200_000

    # Expected getLogs CU: 100 * 30 * 60 = 180,000
    assert result["getlogs_cu"] == 180_000

    # Total: 1,380,000
    assert result["total_cu"] == 1_380_000

    # Utilization: 1,380,000 / 30,000,000 = 4.6%
    assert result["utilization_pct"] == pytest.approx(4.6, abs=0.1)

    assert result["verdict"] == "WELL_WITHIN_FREE_TIER"
    assert result["free_tier_cu"] == 30_000_000


def test_estimate_alchemy_cu_200_wallets():
    """200 wallets at 50 trades/day is still well within free tier."""
    result = estimate_alchemy_cu(200, avg_trades_per_wallet_per_day=50)

    # Expected notifications: 200 * 50 * 30 * 40 = 12,000,000
    assert result["notifications_cu"] == 12_000_000

    total = result["total_cu"]
    utilization = result["utilization_pct"]

    # Should be ~40.6% — approaching limit but not exceeding
    assert total < 30_000_000
    assert utilization < 50.0  # still well within free tier
    assert result["verdict"] == "WELL_WITHIN_FREE_TIER"


def test_estimate_alchemy_cu_exceeds_free_tier():
    """Very large watchlist should report EXCEEDS_FREE_TIER verdict."""
    # 10,000 wallets at 100 trades/day:
    # notifications = 10000 * 100 * 30 * 40 = 1,200,000,000 >> 30M
    result = estimate_alchemy_cu(10_000, avg_trades_per_wallet_per_day=100)
    assert result["verdict"] == "EXCEEDS_FREE_TIER"
    assert result["utilization_pct"] > 100.0


def test_estimate_alchemy_cu_returns_required_keys():
    """Result dict must contain all documented keys."""
    result = estimate_alchemy_cu(50)
    required_keys = {
        "wallet_count", "avg_trades_per_wallet_per_day",
        "notifications_cu", "getlogs_cu", "total_cu",
        "free_tier_cu", "utilization_pct", "verdict", "assumptions",
    }
    assert required_keys.issubset(result.keys()), (
        f"Missing keys: {required_keys - result.keys()}"
    )


# ---------------------------------------------------------------------------
# 10. describe_dynamic_subscription_behavior
# ---------------------------------------------------------------------------


def test_describe_dynamic_subscription():
    """Dynamic subscription function must return expected keys and can_update_in_place=False."""
    result = describe_dynamic_subscription_behavior()

    assert result["can_update_in_place"] is False
    assert result["reconnect_required"] is True


def test_describe_dynamic_subscription_required_keys():
    """Result must include all documented fields."""
    result = describe_dynamic_subscription_behavior()
    required_keys = {
        "can_update_in_place",
        "reconnect_required",
        "recommended_pattern",
        "gap_mitigation",
        "alternative_approach",
    }
    assert required_keys.issubset(result.keys()), (
        f"Missing keys: {required_keys - result.keys()}"
    )


def test_describe_dynamic_subscription_recommends_ab_swap():
    """Recommended pattern must be the A/B subscription swap approach."""
    result = describe_dynamic_subscription_behavior()
    pattern = result["recommended_pattern"].lower()
    assert "a/b" in pattern or "ab" in pattern or "swap" in pattern, (
        f"Unexpected recommended_pattern: {result['recommended_pattern']}"
    )


def test_describe_dynamic_subscription_documents_gap_mitigation():
    """gap_mitigation field must document overlap/dedup strategy."""
    result = describe_dynamic_subscription_behavior()
    mitigation = result["gap_mitigation"].lower()
    assert any(kw in mitigation for kw in ["overlap", "dedup", "old subscription", "active"]), (
        f"gap_mitigation does not document overlap strategy: {result['gap_mitigation']}"
    )


# ---------------------------------------------------------------------------
# 11. Contract address sanity checks
# ---------------------------------------------------------------------------


def test_exchange_addresses_list_contains_both():
    """EXCHANGE_ADDRESSES must contain both CTF exchange addresses."""
    assert CTF_EXCHANGE_ADDRESS in EXCHANGE_ADDRESSES
    assert NEG_RISK_CTF_EXCHANGE_ADDRESS in EXCHANGE_ADDRESSES
    assert len(EXCHANGE_ADDRESSES) == 2


def test_contract_addresses_are_lowercase():
    """All contract address constants must be lowercase 0x-prefixed."""
    for addr in [CTF_EXCHANGE_ADDRESS, NEG_RISK_CTF_EXCHANGE_ADDRESS]:
        assert addr.startswith("0x"), f"Address must start with 0x: {addr}"
        assert addr == addr.lower(), f"Address must be lowercase: {addr}"
        assert len(addr) == 42, f"Address must be 20 bytes (42 chars): {addr}"
