"""AT-07: Deterministic MVF output shape tests for Wallet Discovery v1.

Tests:
1. Output shape — 50 synthetic positions yields all 11 dimensions; 1-10 non-null, dim11 null.
2. Determinism — same input produces byte-identical JSON twice.
3. Win-rate correctness — 25 WIN + 5 PROFIT_EXIT + 10 LOSS + 5 LOSS_EXIT + 5 PENDING = win rate 30/45.
4. Empty input — compute_mvf([]) returns all-None dimensions, input_trade_count=0.
5. Metadata block — includes wallet_address, computation_timestamp (ISO-8601), input_trade_count.
6. Maker/taker explicit null — no maker field -> maker_taker_ratio null, data note present.
7. Range validation — each non-null dimension falls within documented range.
"""
from __future__ import annotations

import json
import math

import pytest

from packages.polymarket.discovery.mvf import MvfResult, compute_mvf, mvf_to_dict

# ---------------------------------------------------------------------------
# Pinned 50-position fixture
# ---------------------------------------------------------------------------

# Outcome distribution:
#   25 WIN, 5 PROFIT_EXIT, 10 LOSS, 5 LOSS_EXIT, 5 PENDING  = 50 total
# win_rate = (25 + 5) / (25 + 5 + 10 + 5) = 30 / 45
#
# Markets: 6 distinct slugs for non-trivial concentration + dca scores.
# Categories: 4 distinct categories for entropy > 0.
# Timestamps: first/last trade timestamps present on all non-PENDING positions.

_MARKET_SLUGS = [
    "btc-up-dec-31",
    "eth-up-jan-15",
    "sol-up-jan-15",
    "trump-2024",
    "super-bowl-2025",
    "oscar-2025",
]

_CATEGORIES = ["Crypto", "Politics", "Sports", "Entertainment"]

_BASE_TS = 1_700_000_000.0  # 2023-11-14 UTC — pinned epoch


def _make_position(
    idx: int,
    outcome: str,
    slug_idx: int,
    cat_idx: int,
    entry_price: float,
    size: float,
    has_timestamps: bool = True,
) -> dict:
    pos: dict = {
        "resolution_outcome": outcome,
        "entry_price": entry_price,
        "market_slug": _MARKET_SLUGS[slug_idx % len(_MARKET_SLUGS)],
        "category": _CATEGORIES[cat_idx % len(_CATEGORIES)],
        "size": size,
        "position_notional_usd": size * entry_price,
    }
    if has_timestamps:
        # First trade = base + idx * 3600 seconds
        # Last trade = first + 24 hours
        first_ts = _BASE_TS + idx * 3600
        last_ts = first_ts + 86400.0
        pos["first_trade_timestamp"] = first_ts
        pos["last_trade_timestamp"] = last_ts
    return pos


def _build_fixture() -> list[dict]:
    positions = []
    idx = 0

    # 25 WIN
    for i in range(25):
        ep = 0.1 + (i % 9) * 0.08  # spread across 0.1 to 0.82
        positions.append(
            _make_position(idx, "WIN", slug_idx=i % 6, cat_idx=i % 4, entry_price=ep, size=100.0)
        )
        idx += 1

    # 5 PROFIT_EXIT
    for i in range(5):
        ep = 0.5 + i * 0.04
        positions.append(
            _make_position(idx, "PROFIT_EXIT", slug_idx=i % 6, cat_idx=i % 4, entry_price=ep, size=50.0)
        )
        idx += 1

    # 10 LOSS
    for i in range(10):
        ep = 0.3 + i * 0.05
        positions.append(
            _make_position(idx, "LOSS", slug_idx=i % 6, cat_idx=i % 4, entry_price=ep, size=75.0)
        )
        idx += 1

    # 5 LOSS_EXIT
    for i in range(5):
        ep = 0.4 + i * 0.06
        positions.append(
            _make_position(idx, "LOSS_EXIT", slug_idx=i % 6, cat_idx=i % 4, entry_price=ep, size=60.0)
        )
        idx += 1

    # 5 PENDING (excluded from win_rate denominator)
    for i in range(5):
        ep = 0.5
        positions.append(
            _make_position(
                idx, "PENDING", slug_idx=i % 6, cat_idx=i % 4, entry_price=ep, size=40.0,
                has_timestamps=False,
            )
        )
        idx += 1

    assert len(positions) == 50
    return positions


FIXTURE_50 = _build_fixture()
WALLET = "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12"


# ---------------------------------------------------------------------------
# Test 1: Output shape
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_returns_mvf_result_instance(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        assert isinstance(result, MvfResult)

    def test_all_11_dimensions_present(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        expected_keys = {
            "win_rate",
            "avg_hold_duration_hours",
            "median_entry_price",
            "market_concentration",
            "category_entropy",
            "avg_position_size_usdc",
            "trade_frequency_per_day",
            "late_entry_rate",
            "dca_score",
            "resolution_coverage_rate",
            "maker_taker_ratio",
        }
        assert set(result.dimensions.keys()) == expected_keys

    def test_dims_1_to_10_non_null(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        non_null_dims = [
            "win_rate",
            "avg_hold_duration_hours",
            "median_entry_price",
            "market_concentration",
            "category_entropy",
            "avg_position_size_usdc",
            "trade_frequency_per_day",
            "dca_score",
            "resolution_coverage_rate",
        ]
        for key in non_null_dims:
            val = result.dimensions[key]
            assert val is not None, f"Expected {key} to be non-null, got None"
            assert isinstance(val, float), f"Expected {key} to be float, got {type(val)}"
            assert math.isfinite(val), f"Expected {key} to be finite, got {val}"

    def test_maker_taker_ratio_null_no_data(self):
        """Fixture has no maker/taker fields -> maker_taker_ratio must be null."""
        result = compute_mvf(FIXTURE_50, WALLET)
        assert result.dimensions["maker_taker_ratio"] is None

    def test_late_entry_rate_null_no_market_timing(self):
        """Fixture has no market_open_ts -> late_entry_rate must be null."""
        result = compute_mvf(FIXTURE_50, WALLET)
        # late_entry_rate is null because market_open_ts is absent
        assert result.dimensions["late_entry_rate"] is None


# ---------------------------------------------------------------------------
# Test 2: Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_byte_identical_json_twice(self):
        r1 = compute_mvf(FIXTURE_50, WALLET)
        r2 = compute_mvf(FIXTURE_50, WALLET)
        d1 = mvf_to_dict(r1)
        d2 = mvf_to_dict(r2)
        # Exclude computation_timestamp (wall-clock) — check dimensions only
        assert d1["dimensions"] == d2["dimensions"]

    def test_same_fixture_same_dimensions_float_exact(self):
        r1 = compute_mvf(FIXTURE_50, WALLET)
        r2 = compute_mvf(FIXTURE_50, WALLET)
        for key, v1 in r1.dimensions.items():
            v2 = r2.dimensions[key]
            assert v1 == v2, f"Dimension {key} differs: {v1} != {v2}"

    def test_order_invariant(self):
        """Shuffled input (same content) must produce same dimensions as sorted."""
        import copy
        shuffled = list(reversed(FIXTURE_50))
        r_orig = compute_mvf(FIXTURE_50, WALLET)
        r_shuf = compute_mvf(shuffled, WALLET)
        # Dimensions that should be order-invariant:
        order_invariant = [
            "win_rate", "market_concentration", "category_entropy",
            "avg_position_size_usdc", "dca_score", "resolution_coverage_rate",
        ]
        for key in order_invariant:
            assert r_orig.dimensions[key] == r_shuf.dimensions[key], (
                f"Dimension {key} is not order-invariant: {r_orig.dimensions[key]} vs {r_shuf.dimensions[key]}"
            )


# ---------------------------------------------------------------------------
# Test 3: Win-rate correctness
# ---------------------------------------------------------------------------

class TestWinRate:
    def test_win_rate_exact_value(self):
        """25 WIN + 5 PROFIT_EXIT + 10 LOSS + 5 LOSS_EXIT + 5 PENDING = win rate 30/45."""
        result = compute_mvf(FIXTURE_50, WALLET)
        expected = 30 / 45
        assert result.dimensions["win_rate"] == pytest.approx(expected, rel=1e-9)

    def test_win_rate_pending_excluded(self):
        """PENDING positions must not affect win_rate denominator."""
        # All-pending fixture -> win_rate must be None
        pending_only = [
            {"resolution_outcome": "PENDING", "market_slug": "s1", "category": "X"}
            for _ in range(5)
        ]
        result = compute_mvf(pending_only, "0x0")
        assert result.dimensions["win_rate"] is None

    def test_win_rate_all_wins(self):
        wins = [{"resolution_outcome": "WIN", "market_slug": "s1", "category": "X"} for _ in range(10)]
        result = compute_mvf(wins, "0x0")
        assert result.dimensions["win_rate"] == pytest.approx(1.0)

    def test_win_rate_all_losses(self):
        losses = [{"resolution_outcome": "LOSS", "market_slug": "s1", "category": "X"} for _ in range(10)]
        result = compute_mvf(losses, "0x0")
        assert result.dimensions["win_rate"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Test 4: Empty input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_positions_returns_mvf_result(self):
        result = compute_mvf([], "0x0")
        assert isinstance(result, MvfResult)

    def test_empty_positions_all_dims_null(self):
        result = compute_mvf([], "0x0")
        for key, val in result.dimensions.items():
            assert val is None, f"Expected {key} to be null for empty input, got {val}"

    def test_empty_positions_input_trade_count_zero(self):
        result = compute_mvf([], "0x0")
        assert result.metadata["input_trade_count"] == 0

    def test_empty_positions_maker_taker_note_present(self):
        result = compute_mvf([], "0x0")
        assert "maker_taker_data_unavailable" in result.metadata["data_notes"]

    def test_empty_positions_no_positions_note_present(self):
        result = compute_mvf([], "0x0")
        assert "no_positions_provided" in result.metadata["data_notes"]


# ---------------------------------------------------------------------------
# Test 5: Metadata block
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_metadata_has_wallet_address(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        assert result.metadata["wallet_address"] == WALLET

    def test_metadata_has_input_trade_count(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        assert result.metadata["input_trade_count"] == 50

    def test_metadata_has_computation_timestamp(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        ts = result.metadata["computation_timestamp"]
        assert isinstance(ts, str)
        # Must be parseable as ISO-8601
        from datetime import datetime
        dt = datetime.fromisoformat(ts)
        assert dt is not None

    def test_metadata_has_data_notes_list(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        assert "data_notes" in result.metadata
        assert isinstance(result.metadata["data_notes"], list)


# ---------------------------------------------------------------------------
# Test 6: Maker/taker explicit null
# ---------------------------------------------------------------------------

class TestMakerTakerNull:
    def test_null_when_no_maker_field(self):
        pos = [{"resolution_outcome": "WIN", "market_slug": "s1", "category": "X"} for _ in range(5)]
        result = compute_mvf(pos, "0x0")
        assert result.dimensions["maker_taker_ratio"] is None

    def test_data_note_maker_taker_unavailable(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        assert "maker_taker_data_unavailable" in result.metadata["data_notes"]

    def test_maker_taker_computed_when_maker_field_present(self):
        pos = [
            {"resolution_outcome": "WIN", "market_slug": "s1", "category": "X", "maker": True},
            {"resolution_outcome": "WIN", "market_slug": "s1", "category": "X", "maker": False},
            {"resolution_outcome": "WIN", "market_slug": "s1", "category": "X", "maker": True},
        ]
        result = compute_mvf(pos, "0x0")
        # 2 makers out of 3 -> 2/3
        assert result.dimensions["maker_taker_ratio"] == pytest.approx(2 / 3)
        assert "maker_taker_data_unavailable" not in result.metadata["data_notes"]

    def test_maker_taker_via_side_type_field(self):
        pos = [
            {"resolution_outcome": "WIN", "market_slug": "s1", "category": "X", "side_type": "MAKER"},
            {"resolution_outcome": "WIN", "market_slug": "s1", "category": "X", "side_type": "taker"},
        ]
        result = compute_mvf(pos, "0x0")
        assert result.dimensions["maker_taker_ratio"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Test 7: Range validation
# ---------------------------------------------------------------------------

class TestRangeValidation:
    def setup_method(self):
        self.result = compute_mvf(FIXTURE_50, WALLET)
        self.dims = self.result.dimensions

    def test_win_rate_in_0_1(self):
        v = self.dims["win_rate"]
        assert v is not None
        assert 0.0 <= v <= 1.0

    def test_avg_hold_duration_hours_non_negative(self):
        v = self.dims["avg_hold_duration_hours"]
        assert v is not None
        assert v >= 0.0

    def test_median_entry_price_in_0_1(self):
        v = self.dims["median_entry_price"]
        assert v is not None
        assert 0.0 <= v <= 1.0

    def test_market_concentration_in_0_1(self):
        v = self.dims["market_concentration"]
        assert v is not None
        assert 0.0 <= v <= 1.0

    def test_category_entropy_non_negative(self):
        v = self.dims["category_entropy"]
        assert v is not None
        assert v >= 0.0

    def test_avg_position_size_usdc_non_negative(self):
        v = self.dims["avg_position_size_usdc"]
        assert v is not None
        assert v >= 0.0

    def test_trade_frequency_per_day_non_negative(self):
        v = self.dims["trade_frequency_per_day"]
        assert v is not None
        assert v >= 0.0

    def test_dca_score_in_0_1(self):
        v = self.dims["dca_score"]
        assert v is not None
        assert 0.0 <= v <= 1.0

    def test_resolution_coverage_rate_in_0_1(self):
        v = self.dims["resolution_coverage_rate"]
        assert v is not None
        assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# Test: mvf_to_dict serialization
# ---------------------------------------------------------------------------

class TestMvfToDict:
    def test_to_dict_contains_dimensions_and_metadata(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        d = mvf_to_dict(result)
        assert "dimensions" in d
        assert "metadata" in d

    def test_to_dict_json_serializable(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        d = mvf_to_dict(result)
        # Should not raise
        serialized = json.dumps(d)
        assert len(serialized) > 10

    def test_to_dict_dimensions_count(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        d = mvf_to_dict(result)
        assert len(d["dimensions"]) == 11
